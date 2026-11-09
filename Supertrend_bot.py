import time
import requests
import datetime
import pytz
import pandas as pd
import pandas_ta as ta
import ccxt

# ================= CONFIGURATION =================
SYMBOLS = ["ETH/USDT:USDT", "XAU/USDT"]  # Assets to monitor
TIMEFRAME = "15m"                        # Changed to 15-minute timeframe
ATR_LENGTH = 20                          # Supertrend Period
MULTIPLIER = 2.0                         # Supertrend Multiplier

TELEGRAM_BOT_TOKEN = "9274093019:AAHS6aw0BxoztcDuxbgaUrDiiNS6jmv7M4Y"
TELEGRAM_CHAT_ID = "6179357654"
CHECK_INTERVAL_SECONDS = 30              # Frequency check interval (30s)

# IST Trading Window (18:30 to 22:30 IST)
START_HOUR = 18
START_MINUTE = 30
END_HOUR = 22
END_MINUTE = 30
# ==================================================

# Initialize exchange connection via CCXT
exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

def is_within_ist_window():
    """Checks if current time is between 18:30 and 22:30 IST."""
    ist_tz = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.datetime.now(ist_tz).time()
    
    start_time = datetime.time(START_HOUR, START_MINUTE)
    end_time = datetime.time(END_HOUR, END_MINUTE)
    
    return start_time <= now_ist <= end_time

def send_telegram_alert(message):
    """Sends a formatted notification message to your Telegram chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": message, 
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if not response.ok:
            print(f"Telegram API Error: {response.text}")
    except Exception as e:
        print(f"Failed to transmit Telegram alert: {e}")

def fetch_ohlcv_dataframe(symbol, timeframe, limit=100):
    """Fetches historical candle bars and returns a Pandas DataFrame converted to IST."""
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Convert timestamp from UTC to Asia/Kolkata (IST)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

def check_symbol_supertrend(symbol, state_tracker):
    """Calculates Supertrend 20/2 and checks if a flip occurred on the latest closed candle."""
    df = fetch_ohlcv_dataframe(symbol, TIMEFRAME, limit=100)
    if df is None or len(df) < ATR_LENGTH + 5:
        return

    # Compute Supertrend 20/2 using pandas-ta
    st_data = ta.supertrend(df['High'], df['Low'], df['Close'], length=ATR_LENGTH, multiplier=MULTIPLIER)
    df = pd.concat([df, st_data], axis=1)

    col_dir = f"SUPERTd_{ATR_LENGTH}_{MULTIPLIER}.0"
    if col_dir not in df.columns:
        col_dir = [c for c in df.columns if c.startswith('SUPERTd_')][0]

    # Evaluate the most recently closed candle (-2) and the previous one (-3)
    current_dir = df[col_dir].iloc[-2]
    previous_dir = df[col_dir].iloc[-3]
    current_price = df['Close'].iloc[-2]
    candle_time = df['timestamp'].iloc[-2].strftime('%Y-%m-%d %H:%M:%S IST')

    # Initialize state tracker on startup
    if symbol not in state_tracker:
        state_tracker[symbol] = current_dir
        print(f"[{symbol}] Tracking initialized. Current State: {'BULLISH' if current_dir == 1 else 'BEARISH'}")
        return

    # Detect a directional flip
    if current_dir != previous_dir:
        state_tracker[symbol] = current_dir  # Update state
        
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
        print(f"ALERT SENT: {clean_symbol_name} flipped to direction {current_dir} at {current_price}")
    else:
        print(f"[{symbol}] Checked 15m candle: No flip (State: {'BULLISH' if current_dir == 1 else 'BEARISH'}, Price: {current_price})")

def main():
    print(f"--- Supertrend 15m Bot Initialized (Active Window: 18:30 - 22:30 IST) ---")
    state_tracker = {}
    
    while True:
        if is_within_ist_window():
            for symbol in SYMBOLS:
                try:
                    check_symbol_supertrend(symbol, state_tracker)
                except Exception as e:
                    print(f"Error processing {symbol}: {e}")
                
                time.sleep(2)  # Rate limit safety
        else:
            ist_now = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%H:%M:%S IST')
            print(f"[{ist_now}] Outside active trading window (18:30 - 22:30 IST). Bot sleeping...")
            # Reset state tracker when outside window so fresh states load next session
            state_tracker.clear()
            
        time.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
