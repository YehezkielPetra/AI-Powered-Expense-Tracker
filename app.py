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
    # --- STEP 1: LOGIKA OFFLINE (CADANGAN) ---
    def fallback_parse(t):
        t = t.lower()
        nums = re.findall(r'\d+', t.replace('.', '').replace(',', ''))
        nom = float(nums[0]) if nums else 0
        kat = "Lainnya"
        if any(k in t for k in ["makan", "kopi", "bakso", "nasi"]): kat = "Makanan"
        elif any(k in t for k in ["bensin", "gojek", "parkir"]): kat = "Transportasi"
        desk = re.sub(r'\d+', '', t).replace('rp', '').strip().title()
        return {"item": desk or "Transaksi", "kategori": kat, "nominal": nom}

    # --- STEP 2: COBA PAKE AI ---
    try:
        available_models = [m.name for m in genai.list_models() 
                           if 'generateContent' in m.supported_generation_methods]
        
        # Utamakan 1.5 Flash karena kuotanya lebih besar dari 2.0
        prioritas = ['models/gemini-1.5-flash', 'models/gemini-2.0-flash']
        target = next((p for p in prioritas if p in available_models), available_models[0])

        model = genai.GenerativeModel(target)
        prompt = f"Extract JSON: {text}. Format: {{\"item\":\"str\", \"kategori\":\"str\", \"nominal\":int}}"
        
        # Tambahkan timeout singkat agar tidak nunggu kelamaan
        response = model.generate_content(prompt)
        res_text = response.text.strip()
        
        if "```json" in res_text:
            res_text = res_text.split("```json")[1].split("```")[0].strip()
        return json.loads(res_text)

    except Exception as e:
        # --- STEP 3: JIKA AI ERROR (429/404), PAKAI LOGIKA OFFLINE ---
        st.warning("⚠️ Kuota AI Habis. Menggunakan pemrosesan offline...")
        return fallback_parse(text)

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
