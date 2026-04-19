import streamlit as st
import pandas as pd
import sqlite3
import google.generativeai as genai
from datetime import datetime, timedelta
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

# --- LOGIKA KONVERSI NOMINAL PINTAR (rb, jt, k) ---
def konversi_nominal(teks):
    teks = teks.lower().replace(',', '.')
    # Mencari pola angka + satuan (contoh: 50rb, 1.5jt, 10k)
    match = re.search(r'(\d+\.?\d*)\s*(rb|jt|k|rban|jt-an)', teks)
    
    if match:
        angka = float(match.group(1))
        satuan = match.group(2)
        if satuan in ['rb', 'k', 'rban']:
            return angka * 1000
        elif satuan in ['jt', 'jt-an']:
            return angka * 1000000
            
    # Jika tidak ada satuan, ambil angka murni
    nums = re.findall(r'\d+', teks.replace('.', '').replace(',', ''))
    return float(nums[0]) if nums else 0

# --- AI LOGIC DENGAN CADANGAN OFFLINE ---
def process_with_ai(text):
    def fallback_parse(t):
        nom = konversi_nominal(t)
        kat = "Lainnya"
        t_low = t.lower()
        if any(k in t_low for k in ["makan", "kopi", "bakso", "nasi", "sate", "ayam"]): kat = "Makanan"
        elif any(k in t_low for k in ["bensin", "gojek", "grab", "parkir", "ojek", "fuel"]): kat = "Transportasi"
        elif any(k in t_low for k in ["shopee", "tokped", "beli", "baju", "celana", "mall"]): kat = "Belanja"
        elif any(k in t_low for k in ["listrik", "air", "wifi", "pulsa", "kuota", "kos"]): kat = "Tagihan"
        
        # Bersihkan deskripsi
        desk = re.sub(r'\d+\.?\d*\s*(rb|jt|k|rban|jt-an)', '', t_low)
        desk = re.sub(r'\d+', '', desk).replace('rp', '').strip().title()
        return {"item": desk or "Transaksi", "kategori": kat, "nominal": nom}

    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        prioritas = ['models/gemini-1.5-flash', 'models/gemini-2.0-flash']
        target = next((p for p in prioritas if p in available_models), available_models[0])

        model = genai.GenerativeModel(target)
        prompt = f"Extract transaction in JSON. 'rb'=1000, 'jt'=1000000. Text: {text}. Format: {{\"item\":\"str\", \"kategori\":\"str\", \"nominal\":int}}"
        
        response = model.generate_content(prompt)
        res_text = response.text.strip()
        
        if "```json" in res_text:
            res_text = res_text.split("```json")[1].split("```")[0].strip()
        elif "```" in res_text:
            res_text = res_text.split("```")[1].strip()
            
        return json.loads(res_text)
    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower():
            st.warning("⚠️ Kuota AI habis, menggunakan mode Offline Pintar.")
        return fallback_parse(text)

# --- UI STREAMLIT ---
st.set_page_config(page_title="AI Tracker 2026", layout="wide", page_icon="💰")

# Sidebar Navigation
st.sidebar.title("Menu Utama")
menu = st.sidebar.radio("Pindah Halaman:", ["🏠 Dashboard", "📜 History Detail"])

if menu == "🏠 Dashboard":
    st.title("💰 AI Expense Tracker")
    st.markdown("Catat pengeluaranmu secepat kilat dengan bantuan AI.")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Input Transaksi")
        user_input = st.text_input("Contoh: Bensin 50rb atau Kopi 15k", placeholder="Ketik di sini...")
        
        if st.button("Simpan Transaksi"):
            if user_input:
                with st.spinner("AI sedang memproses..."):
                    data = process_with_ai(user_input)
                    if data and data['nominal'] > 0:
                        c = conn.cursor()
                        c.execute("INSERT INTO expenses (tanggal, deskripsi, kategori, nominal) VALUES (?,?,?,?)",
                                  (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), data['item'], data['kategori'], data['nominal']))
                        conn.commit()
                        st.success(f"Tersimpan: {data['item']} - Rp {data['nominal']:,.0f}")
                        st.rerun()
                    else:
                        st.error("Gagal mendeteksi nominal. Gunakan format: 'Bakso 20rb'")

    with col2:
        st.subheader("Ringkasan Hari Ini")
        df_today = pd.read_sql_query("SELECT * FROM expenses WHERE date(tanggal) = date('now')", conn)
        if not df_today.empty:
            st.metric("Total Hari Ini", f"Rp {df_today['nominal'].sum():,.0f}")
            fig = px.pie(df_today, values='nominal', names='kategori', hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Belum ada pengeluaran hari ini.")

    st.divider()
    st.subheader("Recent Transactions")
    df_recent = pd.read_sql_query("SELECT * FROM expenses ORDER BY id DESC LIMIT 5", conn)
    st.table(df_recent[['tanggal', 'deskripsi', 'kategori', 'nominal']])

elif menu == "📜 History Detail":
    st.title("📜 History Pengeluaran")
    
    df = pd.read_sql_query("SELECT * FROM expenses", conn)
    if df.empty:
        st.warning("Data masih kosong. Silakan input transaksi terlebih dahulu.")
    else:
        df['tanggal'] = pd.to_datetime(df['tanggal'])
        now = datetime.now()
        
        tab1, tab2, tab3 = st.tabs(["📅 Hari Ini", "📅 Minggu Ini", "📅 Bulan Ini"])
        
        with tab1:
            df_day = df[df['tanggal'].dt.date == now.date()]
            st.metric("Total Hari Ini", f"Rp {df_day['nominal'].sum():,.0f}")
            st.dataframe(df_day.sort_values(by='tanggal', ascending=False), use_container_width=True)
            
        with tab2:
            start_week = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0)
            df_week = df[df['tanggal'] >= start_week]
            st.metric("Total Minggu Ini", f"Rp {df_week['nominal'].sum():,.0f}")
            if not df_week.empty:
                fig_bar = px.bar(df_week, x='tanggal', y='nominal', color='kategori', barmode='group')
                st.plotly_chart(fig_bar, use_container_width=True)
            st.dataframe(df_week.sort_values(by='tanggal', ascending=False), use_container_width=True)
            
        with tab3:
            df_month = df[(df['tanggal'].dt.month == now.month) & (df['tanggal'].dt.year == now.year)]
            st.metric("Total Bulan Ini", f"Rp {df_month['nominal'].sum():,.0f}")
            if not df_month.empty:
                fig_month = px.pie(df_month, values='nominal', names='kategori', hole=0.5)
                st.plotly_chart(fig_month, use_container_width=True)
            st.dataframe(df_month.sort_values(by='tanggal', ascending=False), use_container_width=True)
