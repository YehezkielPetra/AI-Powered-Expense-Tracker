import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import google.generativeai as genai
from datetime import datetime, timedelta
import plotly.express as px
import json
import re
import hashlib
import smtplib
import random
from email.message import EmailMessage

# --- 1. CONFIG & SECRETS ---
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    DATABASE_URL = st.secrets["DATABASE_URL"]
    EMAIL_SENDER = st.secrets["EMAIL_SENDER"]
    EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]
    
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    genai.configure(api_key=GOOGLE_API_KEY)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
except Exception as e:
    st.error(f"⚠️ Konfigurasi Error: {e}")
    st.stop()

# --- 2. DATABASE INITIALIZATION ---
def init_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, email TEXT);"))
        conn.execute(text("""CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY, username TEXT REFERENCES users(username),
            tanggal TIMESTAMP DEFAULT CURRENT_TIMESTAMP, deskripsi TEXT, kategori TEXT, nominal DECIMAL(15,2));"""))
        conn.commit()

def get_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def send_otp(recipient_email):
    otp = str(random.randint(100000, 999999))
    msg = EmailMessage()
    msg.set_content(f"Kode OTP pendaftaran AI Tracker Anda adalah: {otp}")
    msg['Subject'] = 'Verifikasi Akun AI Tracker'
    msg['From'] = EMAIL_SENDER
    msg['To'] = recipient_email
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
            smtp.send_message(msg)
        return otp
    except:
        return None

# --- 3. LOGIKA PEMBERSIHAN SATUAN (RB/JT/K) ---
def clean_money_string(text_input):
    t = text_input.lower()
    def replace_suffix(match):
        val = float(match.group(1).replace(',', '.'))
        suffix = match.group(2)
        if suffix in ['jt', 'juta']: return str(int(val * 1000000))
        if suffix in ['rb', 'ribu', 'k']: return str(int(val * 1000))
        return match.group(0)
    t = re.sub(r'(\d+[.,]?\d*)\s*(jt|juta|rb|ribu|k)', replace_suffix, t)
    return t

# --- 4. LOGIKA AI ---
def process_with_ai(text_input):
    cleaned_text = clean_money_string(text_input)
    data = {"item": text_input, "kategori": "Lainnya", "nominal": 0}
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Extract expense from: '{cleaned_text}'. Return ONLY JSON: {{\"item\": \"string\", \"kategori\": \"string\", \"nominal\": int}}."
        response = model.generate_content(prompt)
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            data = json.loads(match.group())
    except:
        pass
    
    if data.get('nominal', 0) == 0:
        found_numbers = re.findall(r'\d+', cleaned_text)
        if found_numbers:
            data['nominal'] = int(found_numbers[0])

    raw_nom = str(data.get('nominal', '0'))
    clean_nom = re.sub(r'[^\d]', '', raw_nom)
    data['nominal'] = int(clean_nom) if clean_nom else 0
    return data

# --- 5. MAIN INTERFACE ---
st.set_page_config(page_title="AI Tracker Secure", layout="wide", page_icon="🛡️")
init_db()

if 'user' not in st.session_state: st.session_state.user = None
if 'otp_sent' not in st.session_state: st.session_state.otp_sent = False

def main():
    if st.session_state.user is None:
        st.title("🛡️ Secure AI Tracker")
        t_log, t_reg = st.tabs(["Login", "Register"])
        
        with t_log:
            u = st.text_input("Username", key="l_u")
            p = st.text_input("Password", type="password", key="l_p")
            if st.button("Login", use_container_width=True):
                with engine.connect() as conn:
                    res = conn.execute(text("SELECT password FROM users WHERE username = :u"), {"u": u}).fetchone()
                if res and res[0] == get_hash(p):
                    st.session_state.user = u
                    st.rerun()
                else: st.error("Username atau Password salah")
                    
        with t_reg:
            nu = st.text_input("Username Baru", key="r_u")
            ne = st.text_input("Email", key="r_e")
            np = st.text_input("Password Baru", type="password", key="r_p")
            np2 = st.text_input("Konfirmasi Password", type="password", key="r_p2")
            
            if not st.session_state.otp_sent:
                if st.button("Kirim Kode OTP", use_container_width=True):
                    if nu and ne and np == np2 and len(np) >= 6:
                        otp = send_otp(ne)
                        if otp:
                            st.session_state.otp_sent = True
                            st.session_state.gen_otp = otp
                            st.success(f"OTP dikirim ke {ne}!")
                    else: st.error("Data tidak valid / Password minimal 6 karakter.")
            else:
                u_otp = st.text_input("Masukkan Kode OTP")
                if st.button("Daftar Akun", use_container_width=True):
                    if u_otp == st.session_state.gen_otp:
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("INSERT INTO users (username, password, email) VALUES (:u,:p,:e)"),
                                             {"u": nu, "p": get_hash(np), "e": ne})
                                conn.commit()
                            st.success("Berhasil! Silakan Login.")
                            st.session_state.otp_sent = False
                        except: st.error("Username sudah ada.")
                    else: st.error("OTP Salah")

    else:
        user = st.session_state.user
        st.sidebar.title(f"👤 {user}")
        menu = st.sidebar.radio("Navigasi", ["🏠 Dashboard", "📜 History"])
        
        if st.sidebar.button("Logout", use_container_width=True):
            st.session_state.user = None
            st.rerun()

        if menu == "🏠 Dashboard":
            st.title(f"Selamat Datang, {user}!")
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Input Transaksi AI")
                txt = st.text_input("Ketik pengeluaran (Contoh: Bakso 25rb)", key="input_exp")
                if st.button("Simpan", use_container_width=True):
                    if txt:
                        with st.spinner("Memproses..."):
                            data = process_with_ai(txt)
                            if data['nominal'] > 0:
                                with engine.connect() as conn:
                                    conn.execute(text("""
                                        INSERT INTO expenses (username, tanggal, deskripsi, kategori, nominal) 
                                        VALUES (:u, :t, :d, :k, :n)
                                    """), {
                                        "u": user, "t": datetime.now(), 
                                        "d": data['item'], "k": data['kategori'], "n": float(data['nominal'])
                                    })
                                    conn.commit()
                                st.success(f"Tersimpan: {data['item']} - Rp {data['nominal']:,.0f}")
                                st.rerun()
                            else:
                                st.error("Gagal mendeteksi harga.")

            with col2:
                st.subheader("Ringkasan Hari Ini")
                with engine.connect() as conn:
                    df_today = pd.read_sql_query(text("""
                        SELECT * FROM expenses 
                        WHERE username = :u AND tanggal >= (CURRENT_TIMESTAMP - INTERVAL '24 hours')
                    """), conn, params={"u": user})
                
                if not df_today.empty:
                    st.metric("Total Pengeluaran", f"Rp {df_today['nominal'].sum():,.0f}")
                    fig = px.pie(df_today, values='nominal', names='kategori', hole=0.5)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Belum ada transaksi dalam 24 jam terakhir.")

        elif menu == "📜 History":
            st.title("Riwayat Transaksi")
            with engine.connect() as conn:
                df_all = pd.read_sql_query(text("SELECT * FROM expenses WHERE username = :u ORDER BY tanggal DESC"), conn, params={"u": user})
            
            if not df_all.empty:
                df_all['tanggal'] = pd.to_datetime(df_all['tanggal'])
                
                for index, row in df_all.iterrows():
                    with st.expander(f"📌 {row['tanggal'].strftime('%d %b %Y %H:%M')} | {row['deskripsi']} - Rp {row['nominal']:,.0f}"):
                        c1, c2, c3 = st.columns([2, 1, 1])
                        new_desc = c1.text_input("Deskripsi", value=row['deskripsi'], key=f"desc_{row['id']}")
                        new_cat = c2.selectbox("Kategori", ["Makanan", "Transportasi", "Belanja", "Tagihan", "Lainnya"], 
                                             index=["Makanan", "Transportasi", "Belanja", "Tagihan", "Lainnya"].index(row['kategori']) if row['kategori'] in ["Makanan", "Transportasi", "Belanja", "Tagihan", "Lainnya"] else 4,
                                             key=f"cat_{row['id']}")
                        new_nom = c3.number_input("Nominal", value=float(row['nominal']), key=f"nom_{row['id']}")
                        
                        btn_up, btn_del, _ = st.columns([1, 1, 2])
                        if btn_up.button("Update", key=f"up_{row['id']}"):
                            with engine.connect() as conn:
                                conn.execute(text("UPDATE expenses SET deskripsi=:d, kategori=:k, nominal=:n WHERE id=:id"),
                                             {"d": new_desc, "k": new_cat, "n": new_nom, "id": row['id']})
                                conn.commit()
                            st.success("Berhasil diupdate!")
                            st.rerun()
                        
                        if btn_del.button("Hapus", key=f"del_{row['id']}"):
                            with engine.connect() as conn:
                                conn.execute(text("DELETE FROM expenses WHERE id=:id"), {"id": row['id']})
                                conn.commit()
                            st.warning("Data dihapus!")
                            st.rerun()
            else:
                st.warning("Data masih kosong.")

if __name__ == "__main__":
    main()
