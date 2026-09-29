"""
One-time generator for ../data/market_data.csv.
Produces 2 years of daily OHLCV data for a fixed set of symbols using a
seeded random walk, so results are reproducible. One symbol (TCS) has a
deliberate volatility spike injected near the end of the series so the
Isolation Forest anomaly detector has something genuine to find.
This is clearly documented sample/historical data, not live data.
"""
import numpy as np
import pandas as pd
import datetime

np.random.seed(42)

SYMBOLS = {
    "TCS": {"start": 3800, "type": "Stock", "sector": "Technology"},
    "INFY": {"start": 1500, "type": "Stock", "sector": "Technology"},
    "HDFCBANK": {"start": 1650, "type": "Stock", "sector": "Banking"},
    "RELIANCE": {"start": 2900, "type": "Stock", "sector": "Energy"},
    "NIFTYBEES": {"start": 250, "type": "ETF", "sector": "Diversified"},
    "GOLDBEES": {"start": 60, "type": "ETF", "sector": "Commodity"},
    "SBIN": {"start": 780, "type": "Stock", "sector": "Banking"},
    "TATAMOTORS": {"start": 950, "type": "Stock", "sector": "Automobile"},
}

END_DATE = datetime.date(2026, 9, 15)
DAYS = 504  # ~2 trading years

rows = []
for symbol, meta in SYMBOLS.items():
    price = meta["start"]
    dates = pd.bdate_range(end=END_DATE, periods=DAYS)
    daily_vol = 0.016
    for i, d in enumerate(dates):
        drift = 0.0003
        shock = np.random.normal(drift, daily_vol)

        # Inject an artificial anomaly cluster into TCS near the end
        if symbol == "TCS" and 470 <= i <= 475:
            shock = np.random.normal(0, 0.09)  # abnormal volatility

        open_p = price
        close_p = max(1.0, price * (1 + shock))
        high_p = max(open_p, close_p) * (1 + abs(np.random.normal(0, 0.004)))
        low_p = min(open_p, close_p) * (1 - abs(np.random.normal(0, 0.004)))
        volume = int(np.random.uniform(500000, 3000000))

        rows.append({
            "symbol": symbol,
            "date": d.date().isoformat(),
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": volume,
            "asset_type": meta["type"],
            "sector": meta["sector"],
        })
        price = close_p

df = pd.DataFrame(rows)
df.to_csv("../data/market_data.csv", index=False)
print("Generated", len(df), "rows for", len(SYMBOLS), "symbols")
print(df.groupby("symbol")["close"].last())
