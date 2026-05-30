# 🧠 BINANCE INTELLIGENCE — Streamlit Dashboard

Crypto market scanner berbasis **Indodax** yang dibangun di atas **Streamlit**. Menggabungkan web dashboard interaktif dengan login gate, Telegram alert, dan background scanner thread — semua dalam satu file Python.

---

## 📦 Tech Stack

| Komponen | Library / Tool |
|---|---|
| Dashboard UI | `streamlit` |
| Exchange API | `ccxt` (Indodax) |
| Telegram Bot | `pyTelegramBotAPI` |
| Data Processing | `pandas` |
| Concurrency | `threading` |
| Config | `python-dotenv` + `st.secrets` |

---

## 🚀 Fitur Utama

- **Login gate** — password protection sebelum akses dashboard
- **Background scanner** — thread terpisah memindai semua pasangan `/IDR` di Indodax
- **Live dashboard** — tabel sinyal dengan highlight warna (hijau/merah/kuning) + auto-refresh
- **Grade & signal filter** — sidebar untuk filter berdasarkan grade
- **USD/IDR rate adjustable** — slider di sidebar, real-time update ke semua kalkulasi harga
- **Telegram alert** — kirim notifikasi saat grade `A+ (PERFECT)` terdeteksi
- **Command bot** `/cek <coin>` — analisis manual via Telegram
- **State persistence** — shared state di module level, survive `st.rerun()`

---

## 📁 Struktur File

```
project/
├── auto_trade.py         # Satu-satunya file (dashboard + scanner + bot)
├── requirements.txt      # Dependensi Python
└── .streamlit/
    └── secrets.toml      # Secrets untuk Streamlit Cloud (jangan di-commit!)
```

---

## ⚙️ Setup & Instalasi

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Konfigurasi Secrets

**Lokal** — buat file `.streamlit/secrets.toml`:
```toml
TOKEN_LOW     = "telegram_bot_token"
CHAT_ID       = "telegram_chat_id"
WEB_PASSWORD  = "password_dashboard"
```

**Atau via `.env`** (fallback jika secrets tidak ada):
```env
TOKEN_LOW=<telegram_bot_token>
CHAT_ID=<telegram_chat_id>
WEB_PASSWORD=<password_dashboard>
```

| Variable | Keterangan |
|---|---|
| `TOKEN_LOW` | Token Telegram bot (Johanneshaq1_bot) |
| `CHAT_ID` | Chat ID penerima alert |
| `WEB_PASSWORD` | Password login dashboard (default: `181268`) |

### 3. Jalankan Lokal

```bash
streamlit run auto_trade.py
```

Dashboard: `http://localhost:8501`

---

## ☁️ Deploy ke Streamlit Cloud

1. Push repo ke GitHub (pastikan `.streamlit/secrets.toml` ada di `.gitignore`)
2. Connect repo di [share.streamlit.io](https://share.streamlit.io)
3. Set secrets di **App Settings → Secrets**:
```toml
TOKEN_LOW    = "..."
CHAT_ID      = "..."
WEB_PASSWORD = "..."
```
4. Deploy — background thread scanner dan bot Telegram akan otomatis berjalan

---

## 📊 Logika Sinyal

### RSI Signal
| Kondisi | Sinyal |
|---|---|
| RSI < 35 | 🚀 STRONG ACCUMULATION |
| RSI > 65 | 🔴 DISTRIBUTION / SELL |
| 35–65 | ⚖️ NEUTRAL |

### Grading
| Grade | Syarat |
|---|---|
| `A+ (PERFECT)` | Sinyal kuat + MPI ekstrem + Vol Spike > 1.5× |
| `B (EARLY)` | MPI ekstrem, Vol Spike ≤ 1.5× |
| `C (LOW)` | Kondisi lain |

---

## 🤖 Perintah Telegram

| Command | Fungsi |
|---|---|
| `/cek btc` | Analisis manual koin tertentu dari Indodax |

---

## 🔄 Arsitektur Thread

```
Streamlit Main Thread
├── Login gate → session_state
├── Sidebar: filter + USD rate + stats
├── Dashboard: tabel sinyal (auto-refresh tiap N detik)
└── Shared state: _shared dict + threading.Lock

Background Threads (daemon, start sekali per proses)
├── _scanner_loop()   → scan semua /IDR, update _shared['active_alerts']
└── bot.infinity_polling()  → handle command /cek dari Telegram
```

> State dishare via `_shared` dict di module level dengan `threading.Lock()`, sehingga survive `st.rerun()` tanpa reset.

---

## 🖥️ Fitur Dashboard

| Elemen | Keterangan |
|---|---|
| Metric row | Status LIVE, waktu sekarang, jumlah aset terscanned |
| Tabel sinyal | Sortir by waktu terbaru, highlight warna per sinyal |
| Grade filter | Multi-select: A+, B, C |
| USD/IDR rate | Number input, langsung mempengaruhi semua harga USD |
| Auto-refresh | Slider 3–30 detik |
| Telegram status | Indikator bot aktif/tidak di sidebar |

---

## ⚠️ Catatan Penting

- **Jangan commit `.streamlit/secrets.toml`** — sudah ada di `.gitignore` default Streamlit
- Bot ini terhubung ke **Indodax** (bukan Binance) meskipun nama dashboard menyebut "Binance Intelligence"
- Token Telegram di `DATA.env` sudah terekspos — **segera rotasi** via @BotFather
- Background thread berjalan sekali per proses Streamlit; jika di-deploy multi-worker, setiap worker punya scanner sendiri

---

## 🔗 Perbedaan vs Versi Flask (`main.py` / `auto_trade.py` sebelumnya)

| Aspek | Versi Flask | Versi Streamlit ini |
|---|---|---|
| Framework | Flask + HTML | Streamlit (pure Python) |
| Auth | HTTP Basic Auth | Login gate via `session_state` |
| Config source | `.env` saja | `st.secrets` + `.env` fallback |
| Dashboard | Custom HTML/JS | Streamlit native dataframe |
| Deploy | Railway / Heroku | Streamlit Cloud / Railway |
| Realtime refresh | Frontend JS polling | `st.rerun()` + `time.sleep()` |

---

## 📝 Lisensi

Private use. Tidak untuk didistribusikan tanpa izin.
