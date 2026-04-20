# 🛡️ Secure AI Tracker

**Secure AI Tracker** adalah aplikasi pengelolaan keuangan cerdas berbasis Web yang menggunakan **Google Gemini AI** untuk memproses input transaksi secara natural dan **Supabase (PostgreSQL)** untuk penyimpanan data yang aman.

Aplikasi ini dibangun menggunakan **Streamlit** dan dirancang untuk membantu pengguna mencatat pengeluaran harian hanya dengan mengetik kalimat santai.

## 🚀 Fitur Utama

* **AI Expense Parsing**: Mencatat pengeluaran otomatis dari teks (contoh: "makan bakso 25rb" atau "sepeda 1.5jt").
* **Secure Authentication**: Sistem login menggunakan *Password Hashing* (SHA-256).
* **Email Verification**: Pendaftaran akun baru dilengkapi dengan verifikasi kode **OTP via Email**.
* **Data Visualization**: Ringkasan pengeluaran harian dalam bentuk grafik pie interaktif.
* **Database Cloud**: Menggunakan Supabase sebagai database PostgreSQL yang andal dan dapat diakses kapan saja.
* **Smart Suffix Support**: Mendukung deteksi satuan otomatis seperti `rb`, `jt`, dan `k`.

## 🛠️ Tech Stack

* **Frontend/UI**: Streamlit
* **Language**: Python
* **AI Engine**: Google Gemini Pro (Generative AI)
* **Database**: Supabase (PostgreSQL)
* **Visualization**: Plotly Express
* **ORM**: SQLAlchemy

## 📦 Cara Instalasi

1.  **Clone Repository**
    ```bash
    git clone [https://github.com/username-kamu/ai-powered-expense-tracker.git](https://github.com/username-kamu/ai-powered-expense-tracker.git)
    cd ai-powered-expense-tracker
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Setup Secrets**
    Buat folder `.streamlit` dan file `secrets.toml` (untuk lokal) atau isi di dashboard Streamlit Cloud:
    ```toml
    GOOGLE_API_KEY = "YOUR_GEMINI_API_KEY"
    DATABASE_URL = "YOUR_SUPABASE_URL"
    EMAIL_SENDER = "your-email@gmail.com"
    EMAIL_PASSWORD = "your-app-password"
    ```

4.  **Jalankan Aplikasi**
    ```bash
    streamlit run app.py
    ```

## 📝 Contoh Penggunaan AI

Anda cukup mengetik di kolom input:
- *"Beli kopi starbucks 50k"*
- *"Ganti ban motor 250rb"*
- *"Bayar kosan 1.5jt"*

AI akan otomatis memisahkan item, nominal, dan kategorinya secara presisi.

---
Dibuat oleh [Yehezkiel Petra](https://github.com/username-kamu) - Mahasiswa Universitas Bunda Mulia.