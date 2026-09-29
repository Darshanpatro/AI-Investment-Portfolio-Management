"""
Anomaly detection service: runs the Isolation Forest model against each
symbol the user actually holds, using real historical price data from
the database.
"""

from flask import current_app
from services.market_data_service import get_price_history
from services.portfolio_service import get_holdings
from models.anomaly_model import detect_price_anomalies


def analyze_portfolio_anomalies(user_id):
    contamination = current_app.config["ANOMALY_CONTAMINATION"]
    holdings = get_holdings(user_id)
    symbols = sorted({h.symbol for h in holdings})

    results = {}
    flagged_summaries = []

    for symbol in symbols:
        history = get_price_history(symbol, limit=300)
        if len(history) < 20:
            results[symbol] = {"available": False, "reason": "Not enough historical data.", "points": []}
            continue

        points = detect_price_anomalies(history, contamination=contamination)
        anomalies = [p for p in points if p["is_anomaly"]]

        results[symbol] = {
            "available": True,
            "points": points,
            "anomaly_count": len(anomalies),
            "recent_anomalies": anomalies[-5:],
        }

        if anomalies:
            # Report the most *significant* anomaly (largest absolute daily
            # move), not simply the most recent one. Isolation Forest also
            # keys on the local volatility feature, so the newest flagged
            # point can sometimes be a small move inside a turbulent
            # stretch -- which reads confusingly on the risk page.
            most_significant = max(anomalies, key=lambda p: abs(p["return_percent"]))
            flagged_summaries.append({
                "symbol": symbol,
                "date": most_significant["date"],
                "return_percent": most_significant["return_percent"],
                "anomaly_count": len(anomalies),
                "message": (
                    f"Unusual price behaviour detected for {symbol}. The most significant "
                    f"flagged observation was on {most_significant['date']}, a "
                    f"{most_significant['return_percent']}% daily move. "
                    f"{len(anomalies)} observation(s) in the analysed window differ "
                    f"statistically from this symbol's historical pattern of daily returns "
                    f"and short-term volatility. This flags a statistical deviation only; "
                    f"it does not predict future price direction."
                ),
            })

    return {
        "contamination": contamination,
        "symbols_analyzed": symbols,
        "results": results,
        "flagged": flagged_summaries,
    }
