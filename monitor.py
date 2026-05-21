import os
import smtplib
from email.message import EmailMessage
import yfinance as yf
import pandas as pd
import numpy as np

def calculate_quad_risk():
    # 1. Fetch QQQ Daily Data (Need at least 250 days for the longest SMA)
    # Using 2 years to ensure we have enough trading days
    ticker = yf.Ticker("QQQ")
    df = ticker.history(period="2y", interval="1d", auto_adjust=True)
    
    if df.empty:
        raise ValueError("Failed to fetch data from yfinance.")
        
    close_prices = df['Close']
    returns = close_prices.pct_change().dropna()
    
    # 2. Extract Latest Price
    current_price = close_prices.iloc[-1]
    
    # 3. Calculate the 4 Indicators
    # Gate 1 & 2: Moving Averages (250 and 100)
    sma_250 = close_prices.rolling(window=250).mean().iloc[-1]
    sma_100 = close_prices.rolling(window=100).mean().iloc[-1]
    
    # Gate 3: 21-Day Realized Volatility (Annualized)
    # np.sqrt(252) converts daily volatility to annualized volatility
    vol_21 = returns.rolling(window=21).std().iloc[-1] * np.sqrt(252)
    
    # Gate 4: 30-Day AR(1) Momentum Coefficient
    # Calculates the correlation between today's return and yesterday's return over 30 days
    recent_30_returns = returns.iloc[-30:]
    ar1_coeff = recent_30_returns.autocorr(lag=1)
    
    # 4. Evaluate Gate Conditions (Default 0.0% Buffer)
    trend_long = current_price > sma_250
    trend_medium = current_price > sma_100
    vol_safe = vol_21 < 0.40  # Under 40% annualized volatility
    momentum_positive = ar1_coeff > 0.0
    
    # 5. Calculate Distances for Human Buffer (NEW)
    pct_from_250 = ((current_price - sma_250) / sma_250) * 100
    pct_from_100 = ((current_price - sma_100) / sma_100) * 100
    
    # 6. Apply "K" Rule (Vote of 2 out of 4)
    green_count = sum([trend_long, trend_medium, vol_safe, momentum_positive])
    system_status = "RISK-ON (Maintain QLD)" if green_count >= 2 else "RISK-OFF (Move to Cash/ZROZ)"
    
    # 7. Format the Email
    email_body = f"""
Quad Risk K2 Daily Monitor
-------------------------
System Status: {system_status}
Green Indicators: {green_count}/4

Current QQQ Price: ${current_price:.2f}

1. 250-Day SMA: ${sma_250:.2f} (Dist: {pct_from_250:+.2f}%) | {'GREEN' if trend_long else 'RED'}
2. 100-Day SMA: ${sma_100:.2f} (Dist: {pct_from_100:+.2f}%) | {'GREEN' if trend_medium else 'RED'}
3. 21-Day Volatility: {vol_21 * 100:.2f}% (Limit: <40%) | {'GREEN' if vol_safe else 'RED'}
4. 30-Day AR(1) Momentum: {ar1_coeff:.4f} (Limit: >0) | {'GREEN' if momentum_positive else 'RED'}

---
NOTE: If executing on the final trading day of the month, verify the SMA Distance percentages. If the distance is < 1.0%, ensure the trend is definitive before placing a Market-On-Close (MOC) order to avoid whipsaw.
"""
    return email_body

def send_email(body):
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")
    recipient_email = os.environ.get("RECIPIENT_EMAIL")
    
    if not all([sender_email, sender_password, recipient_email]):
        print("Email credentials missing in environment variables.")
        return

    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = "Quad Risk K2 Daily Update"
    msg['From'] = sender_email
    msg['To'] = recipient_email

    try:
        # Assuming Gmail SMTP setup - adjust if using a different provider
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)
        print("Email sent successfully.")
    except Exception as e:
        print(f"Error sending email: {e}")

if __name__ == "__main__":
    print("Running Quad Risk K2 calculations...")
    try:
        report = calculate_quad_risk()
        print(report)
        send_email(report)
    except Exception as e:
        print(f"Script failed: {e}")
