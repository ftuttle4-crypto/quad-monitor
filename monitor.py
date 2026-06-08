import os
import sys
import smtplib
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo
import yfinance as yf
import pandas as pd
import numpy as np

# --- The Author's Exact Gate Functions ---

def _band_gate(prices: pd.Series, ref: pd.Series, threshold: float) -> pd.Series:
    if threshold <= 0:
        gate = (prices > ref).astype(float)
        gate[ref.isna()] = np.nan
        return gate

    upper = ref * (1.0 + threshold)
    lower = ref * (1.0 - threshold)
    out = np.full(len(prices), np.nan)
    state = np.nan
    p_arr = prices.to_numpy()
    u_arr = upper.to_numpy()
    l_arr = lower.to_numpy()
    r_arr = ref.to_numpy()
    
    for i in range(len(prices)):
        if np.isnan(r_arr[i]) or np.isnan(p_arr[i]):
            out[i] = np.nan
            state = np.nan
            continue
        if np.isnan(state):
            state = 1.0 if p_arr[i] > r_arr[i] else 0.0
        if p_arr[i] > u_arr[i]:
            state = 1.0
        elif p_arr[i] < l_arr[i]:
            state = 0.0
        out[i] = state
    return pd.Series(out, index=prices.index)

def sma_gate(prices: pd.Series, period: int, threshold: float) -> pd.Series:
    sma = prices.rolling(window=period, min_periods=period).mean()
    return _band_gate(prices, sma, threshold)


# --- Execution Logic ---

def verify_execution_time():
    """Acts as a bouncer to handle Daylight Saving Time offsets and massive GitHub cron delays."""
    ny_time = datetime.now(ZoneInfo("America/New_York"))
    
    # Allow the script to run anywhere from 3 PM to 6 PM NY time
    if ny_time.hour not in [15, 16, 17, 18]:
        print(f"Stand down: It is currently {ny_time.strftime('%I:%M %p')} in NY.")
        print("Waiting for the standard afternoon execution window. Exiting gracefully.")
        sys.exit(0)

def calculate_quad_risk():
    ticker = yf.Ticker("QQQ")
    df = ticker.history(period="2y", interval="1d", auto_adjust=True)
    
    close_prices = df['Close']
    returns = close_prices.pct_change().dropna()
    current_price = close_prices.iloc[-1]
    
    # 1. Moving Averages with 5% Hysteresis Band (0.05)
    gate_250 = sma_gate(close_prices, period=250, threshold=0.05).iloc[-1]
    gate_100 = sma_gate(close_prices, period=100, threshold=0.05).iloc[-1]
    
    # Calculate raw SMA for email display and tripwires
    sma_250_val = close_prices.rolling(window=250).mean().iloc[-1]
    sma_100_val = close_prices.rolling(window=100).mean().iloc[-1]
    pct_from_250 = ((current_price - sma_250_val) / sma_250_val) * 100
    pct_from_100 = ((current_price - sma_100_val) / sma_100_val) * 100
    
    # 2. Volatility and AR(1)
    vol_21 = returns.rolling(window=21).std().iloc[-1] * np.sqrt(252)
    ar1_coeff = returns.iloc[-30:].autocorr(lag=1)
    
    gate_vol = 1.0 if vol_21 < 0.40 else 0.0
    gate_mom = 1.0 if ar1_coeff > 0.0 else 0.0
    
    # 3. K2 Voting Logic
    green_count = int(sum([gate_250, gate_100, gate_vol, gate_mom]))
    
    system_status = "RISK-ON (Maintain 70% QLD / 30% SWVXX)" if green_count >= 2 else "RISK-OFF (Rotate 100% SWVXX)"
    
# 4. The Upgraded Email Body
    email_body = f"""
Quad Risk K2 Daily Monitor
-------------------------
🎯 SYSTEM SIGNAL: {system_status}
🟢 Green Indicators: {green_count}/4

Current QQQ Price: ${current_price:.2f}

--- INDICATOR BREAKDOWN ---
1. 250-Day SMA Gate: {'GREEN' if gate_250 == 1.0 else 'RED'}
   ↳ Raw SMA Line: ${sma_250_val:.2f} (Dist: {pct_from_250:+.2f}%)
   ↳ Tripwires: Drops to RED below ${sma_250_val * 0.95:.2f} | Flips to GREEN above ${sma_250_val * 1.05:.2f}

2. 100-Day SMA Gate: {'GREEN' if gate_100 == 1.0 else 'RED'}
   ↳ Raw SMA Line: ${sma_100_val:.2f} (Dist: {pct_from_100:+.2f}%)
   ↳ Tripwires: Drops to RED below ${sma_100_val * 0.95:.2f} | Flips to GREEN above ${sma_100_val * 1.05:.2f}

3. 21-Day Volatility: {vol_21 * 100:.2f}% (Limit: <40%) | {'GREEN' if gate_vol == 1.0 else 'RED'}
4. 30-Day AR(1) Momentum: {ar1_coeff:.4f} (Limit: >0) | {'GREEN' if gate_mom == 1.0 else 'RED'}

--- WHAT YOU NEED TO DO ---
Because this system uses 5% memory bands, the script automatically handles the "HOLD" zones for you. Check your current brokerage account:

• If your account matches the 🎯 SYSTEM SIGNAL -> DO NOTHING.
• If your account does NOT match the signal -> EXECUTE TRADE near the close to align with the new signal.
"""
    return email_body

def send_email(body):
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")
    recipient_email = os.environ.get("RECEIVER_EMAIL") # Matches your daily_run.yml exactly
    
    if not all([sender_email, sender_password, recipient_email]):
        print("Email credentials missing.")
        return

    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = "Quad Risk K2 Daily Update"
    msg['From'] = sender_email
    msg['To'] = recipient_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(sender_email, sender_password)
        smtp.send_message(msg)
        print("Email sent successfully.")

if __name__ == "__main__":
    # --- TEMPORARILY COMMENTED OUT FOR LIVE TESTING TONIGHT ---
    #verify_execution_time()
    
    try:
        report = calculate_quad_risk()
        send_email(report)
    except Exception as e:
        print(f"Script failed: {e}")
