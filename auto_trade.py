import ccxt
import time
import telebot
import pandas as pd
import threading
import urllib3
import streamlit as st
from datetime import datetime
import os
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================== PAGE CONFIG ==================
st.set_page_config(
    page_title="BINANCE INTELLIGENCE",
    page_icon="🧠",
    layout="wide"
)

# ================== MODULE-LEVEL SHARED STATE ==================
# Survives st.rerun() — module hanya diload sekali per proses
_lock = threading.Lock()
_shared = {
    'active_alerts': {},
    'last_alerts': {},
    'all_idr_symbols': [],
    'scanner_started': False,
    'bot_started': False,
    'usd_rate': 16200,
}

# ================== EXCHANGE ==================
exchange = ccxt.indodax({'enableRateLimit': True, 'verify': False})

# ================== SECRETS ==================
def _get_secret(key, default=""):
    try:
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

TOKEN   = _get_secret("TOKEN_LOW")
CHAT_ID = _get_secret("CHAT_ID")

bot = None
if TOKEN:
    try:
        bot = telebot.TeleBot(TOKEN)
    except Exception as e:
        print(f"❌ Bot init error: {e}")

# ================== LOGIN GATE ==================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("## 🧠 BINANCE INTELLIGENCE")
        st.markdown("---")
        st.markdown("### 🔐 Login Required")
        pw = st.text_input("Password", type="password", key="login_pw")
        if st.button("🚀 Login", use_container_width=True):
            if pw == _get_secret("WEB_PASSWORD", "181268"):
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("❌ Password salah!")
    st.stop()

# ================== MARKET ANALYSIS ==================
def get_market_analysis(symbol, usd_rate=16200):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, '1h', limit=100)
        if not ohlcv or len(ohlcv) < 20:
            return None
        df = pd.DataFrame(ohlcv, columns=['ts', 'open', 'high', 'low', 'close', 'vol'])

        df['sma_20'] = df['close'].rolling(window=20).mean()
        delta = df['close'].diff()
        gain  = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss  = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / loss)))

        green_vol = df[df['close'] > df['open']]['vol'].sum()
        red_vol   = df[df['close'] < df['open']]['vol'].sum()
        mpi = (green_vol / (green_vol + red_vol)) * 100 if (green_vol + red_vol) > 0 else 50

        last = df.iloc[-1]
        df['vol_avg'] = df['vol'].rolling(window=20).mean()
        vol_spike = last['vol'] / df['vol_avg'].iloc[-1] if df['vol_avg'].iloc[-1] > 0 else 0

        signal = "⚖️ NEUTRAL"
        if last['rsi'] < 35:
            signal = "🚀 STRONG ACCUMULATION"
        elif last['rsi'] > 65:
            signal = "🔴 DISTRIBUTION / SELL"

        curr_p = last['close']
        df['range_pct'] = (df['high'] - df['low']) / df['low']
        avg_range        = df['range_pct'].tail(20).mean()
        base_step        = max(min(avg_range, 0.08), 0.01)
        power_mult       = 1.0 + (vol_spike / 10)

        if "ACCUMULATION" in signal:
            tp1 = curr_p * (1 + base_step)
            tp2 = curr_p * (1 + base_step * 1.8 * power_mult)
            tp3 = curr_p * (1 + base_step * 3.5 * power_mult)
        elif "DISTRIBUTION" in signal:
            tp1 = curr_p * (1 - base_step)
            tp2 = curr_p * (1 - base_step * 1.8 * power_mult)
            tp3 = curr_p * (1 - base_step * 3.5 * power_mult)
        else:
            tp1 = tp2 = tp3 = curr_p

        grade = "C (LOW)"
        if "ACCUMULATION" in signal and mpi > 65 and vol_spike > 1.5:
            grade = "A+ (PERFECT)"
        elif "DISTRIBUTION" in signal and mpi < 35 and vol_spike > 1.5:
            grade = "A+ (PERFECT)"
        elif (mpi > 65 or mpi < 35) and vol_spike <= 1.5:
            grade = "B (EARLY)"

        return {
            'price_usd': (curr_p / usd_rate) * 0.95,
            'price_idr': curr_p,
            'tp1_usd':   (tp1 / usd_rate) * 0.95,
            'tp2_usd':   (tp2 / usd_rate) * 0.95,
            'tp3_usd':   (tp3 / usd_rate) * 0.95,
            'rsi': last['rsi'], 'mpi': mpi,
            'signal': signal, 'vol_spike': vol_spike, 'grade': grade,
        }
    except Exception:
        return None

# ================== TELEGRAM ==================
def _send_alert(coin_name, data):
    if not bot or not CHAT_ID:
        return
    try:
        msg = (
            f"🌟 **BINANCE INTELLIGENCE ALERT** 🌟\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 Asset: `{coin_name}`\n"
            f"🏆 Grade: **{data['grade']}** 🔥\n"
            f"📢 Signal: **{data['signal']}**\n"
            f"💵 Entry: `${data['price_usd']:.8f}`\n"
            f"🎯 **TP1: `${data['tp1_usd']:.8f}`**\n"
            f"🚀 **TP2: `${data['tp2_usd']:.8f}`**\n"
            f"🌌 **TP3: `${data['tp3_usd']:.8f}`**\n"
            f"🐳 Power: `{data['mpi']:.1f}%` | ⚡ Vol: `{data['vol_spike']:.1f}x`"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(
            "📊 View Chart",
            url=f"https://indodax.com/market/{coin_name}IDR"
        ))
        bot.send_message(CHAT_ID, msg, parse_mode='Markdown', reply_markup=markup)
    except Exception:
        pass

# ================== BOT COMMANDS ==================
if bot:
    @bot.message_handler(commands=['cek'])
    def cmd_cek(m):
        try:
            parts = m.text.split()
            if len(parts) < 2:
                bot.reply_to(m, "Gunakan: `/cek btc`")
                return
            coin = parts[1].upper().replace("IDR", "")
            with _lock:
                usd_rate = _shared['usd_rate']
            analysis = get_market_analysis(f"{coin}/IDR", usd_rate)
            if analysis:
                res = (
                    f"🧠 **ANALYSIS: {coin}**\n"
                    f"🏆 Grade: **{analysis['grade']}**\n"
                    f"📢 Signal: **{analysis['signal']}**\n"
                    f"💵 Price: `${analysis['price_usd']:.8f}`\n"
                    f"🎯 TP1: `${analysis['tp1_usd']:.8f}`\n"
                    f"📊 RSI: `{analysis['rsi']:.2f}`\n"
                    f"🐳 Power: `{analysis['mpi']:.1f}%`"
                )
                bot.send_message(m.chat.id, res, parse_mode='Markdown')
            else:
                bot.reply_to(m, f"❌ Data `{coin}` tidak ditemukan.")
        except Exception as e:
            bot.reply_to(m, f"⚠️ Error: {str(e)}")

# ================== SCANNER THREAD ==================
def _scanner_loop():
    try:
        markets = exchange.load_markets()
        with _lock:
            _shared['all_idr_symbols'] = [s for s in markets if s.endswith('/IDR')]
        print(f"✅ Intelligence Engine Ready: {len(_shared['all_idr_symbols'])} Assets")
    except Exception as e:
        print(f"❌ Error fetch markets: {e}")
        return

    while True:
        with _lock:
            symbols  = _shared['all_idr_symbols'].copy()
            usd_rate = _shared['usd_rate']

        for symbol in symbols:
            try:
                data = get_market_analysis(symbol, usd_rate)
                if data is None:
                    continue
                coin      = symbol.split('/')[0]
                data['time'] = datetime.now().strftime('%H:%M:%S')

                with _lock:
                    _shared['active_alerts'][coin] = data
                    if data['grade'] == "A+ (PERFECT)":
                        if _shared['last_alerts'].get(coin) != data['signal']:
                            _send_alert(coin, data)
                            _shared['last_alerts'][coin] = data['signal']
                time.sleep(1)
            except Exception:
                continue
        time.sleep(30)

# ================== START THREADS (sekali per proses) ==================
with _lock:
    if not _shared['scanner_started']:
        _shared['scanner_started'] = True
        threading.Thread(target=_scanner_loop, daemon=True).start()

    if bot and not _shared['bot_started']:
        _shared['bot_started'] = True
        threading.Thread(target=lambda: bot.infinity_polling(), daemon=True).start()

# ================== SIDEBAR ==================
with st.sidebar:
    st.title("⚙️ Configuration")

    usd_rate_input = st.number_input("💱 USD/IDR Rate", value=16200, step=100, min_value=1000)
    with _lock:
        _shared['usd_rate'] = usd_rate_input

    grade_filter = st.multiselect(
        "🎯 Grade Filter",
        options=["A+ (PERFECT)", "B (EARLY)", "C (LOW)"],
        default=["A+ (PERFECT)", "B (EARLY)", "C (LOW)"],
    )

    refresh_interval = st.slider("🔄 Refresh (detik)", min_value=3, max_value=30, value=5)

    st.divider()
    st.markdown("**📡 Telegram Bot**")
    if bot and CHAT_ID:
        st.success("✅ Aktif")
    else:
        st.warning("⚠️ Token tidak tersedia")

    st.divider()
    with _lock:
        total_symbols = len(_shared['all_idr_symbols'])
        total_data    = len(_shared['active_alerts'])
    st.metric("Aset IDR", total_symbols)
    st.metric("Data Masuk", total_data)

    st.divider()
    if st.button("🔓 Logout"):
        st.session_state['logged_in'] = False
        st.rerun()

# ================== MAIN DASHBOARD ==================
st.title("🧠 BINANCE INTELLIGENCE")
st.caption("Crypto Market Scanner — Indodax IDR")

with _lock:
    scanned = len(_shared['active_alerts'])

c1, c2, c3 = st.columns(3)
c1.metric("Status", "🟢 LIVE")
c2.metric("Waktu", datetime.now().strftime('%H:%M:%S'))
c3.metric("Aset Terscanned", scanned)

st.divider()

# Ambil & filter data
with _lock:
    snapshot = _shared['active_alerts'].copy()

filtered = {k: v for k, v in snapshot.items() if not grade_filter or v.get('grade') in grade_filter}
sorted_items = sorted(filtered.items(), key=lambda x: x[1].get('time', ''), reverse=True)

if not sorted_items:
    st.info("⏳ Scanner sedang berjalan... Data akan muncul dalam 1–2 menit.")
else:
    rows = [
        {
            "Asset":     coin,
            "Signal":    info['signal'],
            "Grade":     info['grade'],
            "Price USD": f"${info['price_usd']:.8f}",
            "TP1":       f"${info['tp1_usd']:.8f}",
            "TP2":       f"${info['tp2_usd']:.8f}",
            "TP3":       f"${info['tp3_usd']:.8f}",
            "RSI":       f"{info['rsi']:.2f}",
            "MPI":       f"{info['mpi']:.1f}%",
            "Vol Spike": f"{info['vol_spike']:.1f}x",
            "Time":      info['time'],
        }
        for coin, info in sorted_items
    ]

    def _highlight(row):
        sig = row['Signal']
        if 'ACCUMULATION' in sig:
            c = 'background-color: rgba(0, 200, 83, 0.18)'
        elif 'DISTRIBUTION' in sig:
            c = 'background-color: rgba(244, 67, 54, 0.18)'
        else:
            c = 'background-color: rgba(255, 193, 7, 0.12)'
        return [c] * len(row)

    df = pd.DataFrame(rows)
    st.dataframe(df.style.apply(_highlight, axis=1), use_container_width=True, hide_index=True)

# ================== AUTO REFRESH ==================
time.sleep(refresh_interval)
st.rerun()
