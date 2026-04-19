import streamlit as st
import pandas as pd
import sqlite3
import google.generativeai as genai
from datetime import datetime
import plotly.express as px
import json

# --- CONFIG & SECRETS ---
# Pastikan di Streamlit Cloud 'Secrets' sudah ada GOOGLE_API_KEY
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

# --- AI LOGIC (ANTI-404 AUTO DISCOVERY) ---
def process_with_ai(text):
    try:
        # Mencari model yang tersedia secara otomatis di akun user
        available_models = [m.name for m in genai.list_models() 
                           if 'generateContent' in m.supported_generation_methods]
        
        # Urutan prioritas model
        # Pindahkan 1.5 ke depan karena kuotanya lebih banyak
        prioritas = ['models/gemini-1.5-flash', 'models/gemini-2.0-flash', 'models/gemini-pro']
        
        target_model = None
        for p in prioritas:
            if p in available_models:
                target_model = p
                break
        
        if not target_model:
            target_model = available_models[0]

        model = genai.GenerativeModel(target_model)
        
        prompt = f"""
        Ekstrak data transaksi dari teks ini: "{text}"
        Wajib balas hanya dengan format JSON murni:
        {{"item": "nama barang", "kategori": "Makanan/Transportasi/Belanja/Tagihan/Lainnya", "nominal": angka_saja}}
        """
        
        response = model.generate_content(prompt)
        res_text = response.text.strip()
        
        # Membersihkan tag markdown jika AI menyertakannya
        if "```json" in res_text:
            res_text = res_text.split("```json")[1].split("```")[0].strip()
        elif "```" in res_text:
            res_text = res_text.split("```")[1].strip()
            
        return json.loads(res_text)
    except Exception as e:
        st.error(f"Gagal memproses AI: {e}")
        return None

# --- APP UI ---
st.set_page_config(page_title="AI Tracker Cloud", layout="wide")
st.title("🚀 AI Expense Tracker (Live Version)")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Input Transaksi")
    user_input = st.text_input("Ketik pengeluaran (Contoh: Beli gula 15000)", placeholder="Apa yang Anda beli hari ini?")
    
    if st.button("Simpan"):
        if user_input:
            with st.spinner("AI sedang memproses..."):
                data = process_with_ai(user_input)
                
                if data:
                    # Simpan ke Database
                    c = conn.cursor()
                    c.execute("INSERT INTO expenses (tanggal, deskripsi, kategori, nominal) VALUES (?,?,?,?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), data['item'], data['kategori'], data['nominal']))
                    conn.commit()
                    st.success(f"Berhasil mencatat: {data['item']} (Rp {data['nominal']:,})")
                    st.rerun()

with col2:
    st.subheader("Visualisasi")
    df = pd.read_sql_query("SELECT * FROM expenses", conn)
    if not df.empty:
        fig = px.pie(df, values='nominal', names='kategori', hole=0.5, 
                     title="Proporsi Pengeluaran",
                     color_discrete_sequence=px.colors.qualitative.Safe)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Belum ada data untuk ditampilkan.")

st.divider()
st.subheader("📜 Riwayat Transaksi")
if not df.empty:
    st.dataframe(df.sort_values(by='id', ascending=False), use_container_width=True)
else:
    st.write("Daftar transaksi kosong.")
