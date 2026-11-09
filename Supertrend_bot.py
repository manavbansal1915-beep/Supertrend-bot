import requests
import datetime
import pytz
import pandas as pd
import pandas_ta as ta
import ccxt

# ================= CONFIGURATION =================
SYMBOLS = ["ETH/USDT:USDT", "XAU/USDT"]
TIMEFRAME = "15m"
ATR_LENGTH = 20
MULTIPLIER = 2.0

TELEGRAM_BOT_TOKEN = "9274093019:AAHS6aw0BxoztcDuxbgaUrDiiNS6jmv7M4Y"
TELEGRAM_CHAT_ID = "6179357654"

# IST Trading Window (18:30 to 22:30 IST)
START_HOUR = 18
START_MINUTE = 30
END_HOUR = 22
END_MINUTE = 30
# ==================================================

exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

def is_within_ist_window():
    ist_tz = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.datetime.now(ist_tz).time()
    start_time = datetime.time(START_HOUR, START_MINUTE)
    end_time = datetime.time(END_HOUR, END_MINUTE)
    return start_time <= now_ist <= end_time

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Failed to send alert: {e}")

def fetch_ohlcv_dataframe(symbol, timeframe, limit=100):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

def check_symbol_supertrend(symbol):
    df = fetch_ohlcv_dataframe(symbol, TIMEFRAME, limit=100)
    if df is None or len(df) < ATR_LENGTH + 5:
        return

    st_data = ta.supertrend(df['High'], df['Low'], df['Close'], length=ATR_LENGTH, multiplier=MULTIPLIER)
    df = pd.concat([df, st_data], axis=1)

    col_dir = f"SUPERTd_{ATR_LENGTH}_{MULTIPLIER}.0"
    if col_dir not in df.columns:
        col_dir = [c for c in df.columns if c.startswith('SUPERTd_')][0]

    current_dir = df[col_dir].iloc[-2]
    previous_dir = df[col_dir].iloc[-3]
    current_price = df['Close'].iloc[-2]
    candle_time = df['timestamp'].iloc[-2].strftime('%Y-%m-%d %H:%M:%S IST')

    # Detect a flip on the closed 15m candle
    if current_dir != previous_dir:
        direction_text = "🟢 *BULLISH FLIP (Green)*" if current_dir == 1 else "🔴 *BEARISH FLIP (Red)*"
        clean_symbol_name = symbol.replace("/", "").replace(":USDT", "")
        
        msg = (
            f"🚨 *Supertrend Alert ({ATR_LENGTH}, {MULTIPLIER})* 🚨\n\n"
            f"Asset: *{clean_symbol_name}*\n"
            f"Status: {direction_text}\n"
            f"Price: `{current_price:,.2f}`\n"
            f"Timeframe: `{TIMEFRAME}`\n"
            f"Candle Time: `{candle_time}`"
        )
        send_telegram_alert(msg)
        print(f"ALERT SENT: {clean_symbol_name} flipped to {current_dir}")
    else:
        print(f"[{symbol}] No flip detected. Current state: {current_dir}")

def main():
    if not is_within_ist_window():
        print("Outside active trading window (18:30 - 22:30 IST). Skipping check.")
        return

    print("Inside trading window. Checking Supertrend...")
    for symbol in SYMBOLS:
        try:
            check_symbol_supertrend(symbol)
        except Exception as e:
            print(f"Error processing {symbol}: {e}")

if __name__ == "__main__":
    main()
    
