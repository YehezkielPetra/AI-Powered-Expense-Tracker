import streamlit as st
import pandas as pd
import sqlite3
import google.generativeai as genai
from datetime import datetime
import plotly.express as px
import json
import re

# --- CONFIG & SECRETS ---
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception:
    st.error("⚠️ API Key belum dikonfigurasi di Streamlit Secrets.")

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('database_publik.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS expenses 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  tanggal TEXT, deskripsi TEXT, kategori TEXT, nominal REAL)''')
    conn.commit()
    return conn

conn = init_db()

# --- LOGIKA KONVERSI NOMINAL (RB, JT, K) ---
def konversi_nominal(teks):
    teks = teks.lower().replace(',', '.') # Standarisasi koma ke titik untuk angka desimal
    
    # Cari pola angka yang diikuti satuan (misal: 1.5jt, 50rb, 10k)
    match = re.search(r'(\d+\.?\d*)\s*(rb|jt|k|jt|jt-an|rban)', teks)
    
    if match:
        angka = float(match.group(1))
        satuan = match.group(2)
        
        if satuan in ['rb', 'k', 'rban']:
            return angka * 1000
        elif satuan in ['jt', 'jt-an']:
            return angka * 1000000
    
    # Jika tidak ada satuan, ambil angka murni dan hapus titik pemisah ribuan
    nums = re.findall(r'\d+', teks.replace('.', '').replace(',', ''))
    return float(nums[0]) if nums else 0

# --- AI LOGIC DENGAN CADANGAN OFFLINE ---
def process_with_ai(text):
    def fallback_parse(t):
        t = t.lower()
        nom = konversi_nominal(t)
        
        kat = "Lainnya"
        if any(k in t for k in ["makan", "kopi", "bakso", "nasi", "sate", "ayam"]): kat = "Makanan"
        elif any(k in t for k in ["bensin", "gojek", "grab", "parkir", "ojek"]): kat = "Transportasi"
        elif any(k in t for k in ["shopee", "tokped", "beli", "baju", "celana"]): kat = "Belanja"
        elif any(k in t for k in ["listrik", "air", "wifi", "pulsa", "kuota"]): kat = "Tagihan"
        
        # Bersihkan deskripsi dari angka dan satuan
        desk = re.sub(r'\d+\.?\d*\s*(rb|jt|k|jt|jt-an|rban)', '', t)
        desk = re.sub(r'\d+', '', desk).replace('rp', '').strip().title()
        
        return {"item": desk or "Transaksi", "kategori": kat, "nominal": nom}

    try:
        available_models = [m.name for m in genai.list_models() 
                           if 'generateContent' in m.supported_generation_methods]
        prioritas = ['models/gemini-1.5-flash', 'models/gemini-2.0-flash']
        target = next((p for p in prioritas if p in available_models), available_models[0])

        model = genai.GenerativeModel(target)
        # Kita tambahkan instruksi khusus di prompt AI agar dia juga paham singkatan
        prompt = f"Extract transaction in JSON. If user says 'rb' it means 1000, 'jt' means 1000000. Text: {text}. Format: {{\"item\":\"str\", \"kategori\":\"str\", \"nominal\":int}}"
        
        response = model.generate_content(prompt)
        res_text = response.text.strip()
        
        if "```json" in res_text:
            res_text = res_text.split("```json")[1].split("```")[0].strip()
        elif "```" in res_text:
            res_text = res_text.split("```")[1].strip()
            
        return json.loads(res_text)

    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower():
            st.warning("⚠️ Kuota AI habis, menggunakan mode Offline pintar.")
        return fallback_parse(text)

# --- UI STREAMLIT ---
st.set_page_config(page_title="AI Tracker Cloud", layout="wide")
st.title("💰 AI Expense Tracker (v2026)")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Input Transaksi")
    user_input = st.text_input("Contoh: Bensin 50rb atau Sewa kos 1.5jt", placeholder="Tulis di sini...")
    
    if st.button("Simpan"):
        if user_input:
            with st.spinner("Sedang memproses..."):
                data = process_with_ai(user_input)
                
                if data and data['nominal'] > 0:
                    c = conn.cursor()
                    c.execute("INSERT INTO expenses (tanggal, deskripsi, kategori, nominal) VALUES (?,?,?,?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), data['item'], data['kategori'], data['nominal']))
                    conn.commit()
                    st.success(f"Berhasil: {data['item']} (Rp {data['nominal']:,.0f})")
                    st.rerun()
                else:
                    st.error("Nominal tidak terdeteksi. Gunakan format: 'Kopi 15rb'")

with col2:
    st.subheader("Visualisasi")
    df = pd.read_sql_query("SELECT * FROM expenses", conn)
    if not df.empty:
        total = df['nominal'].sum()
        st.metric("Total Pengeluaran", f"Rp {total:,.0f}")
        fig = px.pie(df, values='nominal', names='kategori', hole=0.5)
        st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("📜 Riwayat Transaksi")
if not df.empty:
    st.dataframe(df.sort_values(by='id', ascending=False), use_container_width=True)
