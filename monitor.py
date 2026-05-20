import yfinance as yf
import pandas as pd
import numpy as np
from statsmodels.tsa.ar_model import AutoReg
import smtplib
from email.mime.text import MIMEText
import os
from datetime import datetime

# Authenticate using the hidden GitHub Secrets
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")

# 1. Fetch QQQ market data
data = yf.download("QQQ", period="1y")
close = data['Close'].squeeze()

# 2. Calculate the 4 Indicators
current_price = close.iloc[-1]
sma_100 = close.rolling(window=100).mean().iloc[-1]
sma_250 = close.rolling(window=250).mean().iloc[-1]

# Annualized 21-day Realized Volatility
daily_returns = close.pct_change().dropna()
vol_21d = daily_returns.tail(21).std() * np.sqrt(252) * 100

# AR(1) Momentum over the last 30 days
prices_30d = close.tail(30).values
model = AutoReg(prices_30d, lags=1).fit()
ar1_coeff = model.params[1]

# 3. Evaluate the Status
cond1 = current_price > sma_250
cond2 = current_price > sma_100
cond3 = vol_21d < 40
cond4 = ar1_coeff > 0

green_count = sum([cond1, cond2, cond3, cond4])
status = "RISK-ON (Maintain 70% QLD / 30% SWVXX)" if green_count >= 2 else "RISK-OFF (Rotate 100% SWVXX)"

# 4. Format the Email Output
date_str = datetime.now().strftime("%Y-%m-%d")
body = f"""
Quad Risk K2 Daily Monitor - {date_str}

Status: {green_count}/4 Green -> {status}

1. Price vs 250 SMA: {current_price:.2f} / {sma_250:.2f} -> {'GREEN' if cond1 else 'RED'}
2. Price vs 100 SMA: {current_price:.2f} / {sma_100:.2f} -> {'GREEN' if cond2 else 'RED'}
3. 21D Volatility: {vol_21d:.2f}% (Limit: <40%) -> {'GREEN' if cond3 else 'RED'}
4. AR(1) 30D Coeff: {ar1_coeff:.4f} (Limit: >0) -> {'GREEN' if cond4 else 'RED'}
"""

# 5. Send the Email
msg = MIMEText(body)
msg['Subject'] = f"Quad Status: {green_count}/4 Green"
msg['From'] = SENDER_EMAIL
msg['To'] = RECEIVER_EMAIL

with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
    server.login(SENDER_EMAIL, SENDER_PASSWORD)
    server.send_message(msg)
