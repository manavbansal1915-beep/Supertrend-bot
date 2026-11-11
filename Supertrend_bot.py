import requests
import datetime
import pytz
import pandas as pd
import ccxt

SYMBOLS = ["ETH/USDT:USDT", "XAU/USDT"]
TIMEFRAME = "15m"
ATR_LENGTH = 20
MULTIPLIER = 2.0

TELEGRAM_BOT_TOKEN = "9274093019:AAHS6aw0BxoztcDuxbgaUrDiiNS6jmv7M4Y"
TELEGRAM_CHAT_ID = "6179357654"

exchange = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Telegram response status: {response.status_code}")
    except Exception as e:
        print(f"Failed to send alert: {e}")

def calculate_supertrend(df, period=20, multiplier=2.0):
    high = df['high']
    low = df['low']
    close = df['close']

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    hl2 = (high + low) / 2
    basic_ub = hl2 + (multiplier * atr)
    basic_lb = hl2 - (multiplier * atr)

    final_ub = basic_ub.copy()
    final_lb = basic_lb.copy()
    st_direction = pd.Series(1, index=df.index)

    for i in range(period, len(df)):
        if basic_ub.iloc[i] < final_ub.iloc[i-1] or close.iloc[i-1] > final_ub.iloc[i-1]:
            final_ub.iloc[i] = basic_ub.iloc[i]
        else:
            final_ub.iloc[i] = final_ub.iloc[i-1]

        if basic_lb.iloc[i] > final_lb.iloc[i-1] or close.iloc[i-1] < final_lb.iloc[i-1]:
            final_lb.iloc[i] = basic_lb.iloc[i]
        else:
            final_lb.iloc[i] = final_lb.iloc[i-1]

        if i == period:
            st_direction.iloc[i] = 1
        else:
            prev_dir = st_direction.iloc[i-1]
            if prev_dir == 1:
                if close.iloc[i] <= final_lb.iloc[i]:
                    st_direction.iloc[i] = -1
                else:
                    st_direction.iloc[i] = 1
            else:
                if close.iloc[i] >= final_ub.iloc[i]:
                    st_direction.iloc[i] = 1
                else:
                    st_direction.iloc[i] = -1

    df['st_dir'] = st_direction
    return df

def check_symbol_supertrend(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=100)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata')
        
        df = calculate_supertrend(df, ATR_LENGTH, MULTIPLIER)
        
        current_dir = df['st_dir'].iloc[-2]
        previous_dir = df['st_dir'].iloc[-3]
        current_price = df['close'].iloc[-2]
        candle_time = df['timestamp'].iloc[-2].strftime('%Y-%m-%d %H:%M:%S IST')

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
            
    except Exception as e:
        print(f"Error processing {symbol}: {e}")

def main():
    print("Running 24/7 Supertrend check...")
    for symbol in SYMBOLS:
        check_symbol_supertrend(symbol)

if __name__ == "__main__":
    main()
