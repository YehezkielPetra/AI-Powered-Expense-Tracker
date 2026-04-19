import streamlit as st
import pandas as pd
import sqlite3
import google.generativeai as genai
from datetime import datetime
import plotly.express as px
import json

# --- CONFIG & SECRETS ---
# Di Streamlit Cloud, simpan API Key di bagian 'Secrets' dengan nama: GOOGLE_API_KEY
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
except:
    st.error("API Key belum dikonfigurasi di Streamlit Secrets.")

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect('database_publik.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS expenses 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  tanggal TEXT, deskripsi TEXT, kategori TEXT, nominal REAL)''')
    conn.commit()
    return conn

conn = init_db()

# --- APP UI ---
st.set_page_config(page_title="AI Tracker Cloud", layout="wide")
st.title("🚀 AI Expense Tracker (Live Version)")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Input Transaksi")
    user_input = st.text_input("Ketik pengeluaran (Contoh: Bensin 50rb)")
    
    if st.button("Simpan"):
        if user_input:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Extract transaction in JSON: {user_input}. Format: {{\"item\":\"str\", \"kategori\":\"Makanan/Transportasi/Lainnya\", \"nominal\":int}}"
            
            try:
                response = model.generate_content(prompt)
                res_text = response.text.replace('```json', '').replace('```', '').strip()
                data = json.loads(res_text)
                
                # Simpan ke DB
                c = conn.cursor()
                c.execute("INSERT INTO expenses (tanggal, deskripsi, kategori, nominal) VALUES (?,?,?,?)",
                          (datetime.now().strftime("%Y-%m-%d %H:%M"), data['item'], data['kategori'], data['nominal']))
                conn.commit()
                st.success(f"Berhasil: {data['item']}")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal memproses AI: {e}")

with col2:
    st.subheader("Visualisasi")
    df = pd.read_sql_query("SELECT * FROM expenses", conn)
    if not df.empty:
        fig = px.pie(df, values='nominal', names='kategori', hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

st.dataframe(df.sort_values(by='id', ascending=False), use_container_width=True)