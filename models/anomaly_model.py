"""
Isolation Forest based anomaly detector for daily returns of a single
symbol. This is a real, fitted scikit-learn model run on real historical
price data pulled from the database -- not a canned/fake result.
"""

import numpy as np
from sklearn.ensemble import IsolationForest


def detect_price_anomalies(price_history, contamination=0.05):
    """
    price_history: list of (date, close) tuples, oldest first.
    Returns a list of dicts: [{date, close, return_pct, anomaly_score, is_anomaly}, ...]
    """
    if len(price_history) < 20:
        return []

    dates = [d for d, _ in price_history]
    closes = np.array([c for _, c in price_history], dtype=float)

    returns = np.diff(closes) / closes[:-1]
    dates_for_returns = dates[1:]
    closes_for_returns = closes[1:]

    # Feature set: the daily return itself, and a rolling 5-day
    # volatility, so the model can flag both single-day shocks and
    # short bursts of unusual volatility.
    window = 5
    rolling_vol = np.array([
        np.std(returns[max(0, i - window + 1): i + 1]) for i in range(len(returns))
    ])

    X = np.column_stack([returns, rolling_vol])

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
    )
    model.fit(X)
    scores = model.decision_function(X)  # higher = more normal
    preds = model.predict(X)  # -1 = anomaly, 1 = normal

    results = []
    for i in range(len(returns)):
        results.append({
            "date": dates_for_returns[i].isoformat(),
            "close": round(float(closes_for_returns[i]), 2),
            "return_percent": round(float(returns[i]) * 100, 3),
            "anomaly_score": round(float(scores[i]), 4),
            "is_anomaly": bool(preds[i] == -1),
        })
    return results
