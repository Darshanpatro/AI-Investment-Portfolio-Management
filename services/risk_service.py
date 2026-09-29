"""
Risk service: concentration risk and drawdown, calculated from real
portfolio data. Thresholds come from configuration, not hard-coded
constants buried in logic.
"""

from flask import current_app
from services.performance_service import (
    calculate_asset_allocation,
    calculate_portfolio_value_series,
    calculate_drawdown_series,
)


def analyze_concentration_risk(user_id):
    threshold = current_app.config["CONCENTRATION_THRESHOLD_PERCENT"]
    allocation = calculate_asset_allocation(user_id)

    breaches = []
    for row in allocation["by_sector"]:
        if row["percent"] >= threshold:
            breaches.append({
                "type": "sector",
                "name": row["sector"],
                "percent": row["percent"],
                "message": (
                    f"High concentration detected in the {row['sector']} sector. "
                    f"{row['sector']} represents {row['percent']}% of the current "
                    f"portfolio allocation, which is at or above the configured "
                    f"threshold of {threshold}%."
                ),
            })

    for row in allocation["by_asset"]:
        if row["percent"] >= threshold:
            breaches.append({
                "type": "asset",
                "name": row["symbol"],
                "percent": row["percent"],
                "message": (
                    f"High concentration detected in a single holding. "
                    f"{row['symbol']} represents {row['percent']}% of the current "
                    f"portfolio allocation, which is at or above the configured "
                    f"threshold of {threshold}%."
                ),
            })

    return {
        "threshold_percent": threshold,
        "by_sector": allocation["by_sector"],
        "by_asset": allocation["by_asset"],
        "breaches": breaches,
        "is_concentrated": len(breaches) > 0,
    }


def analyze_drawdown(user_id):
    alert_threshold = current_app.config["DRAWDOWN_ALERT_THRESHOLD_PERCENT"]
    value_series = calculate_portfolio_value_series(user_id)

    if not value_series:
        return {
            "has_data": False,
            "current_drawdown_percent": None,
            "max_drawdown_percent": None,
            "previous_peak": None,
            "current_value": None,
            "alert_threshold_percent": alert_threshold,
            "breach": False,
        }

    dd_series = calculate_drawdown_series(value_series)
    latest = dd_series[-1]
    max_drawdown = min(p["drawdown_percent"] for p in dd_series)

    return {
        "has_data": True,
        "series": dd_series,
        "current_drawdown_percent": latest["drawdown_percent"],
        "max_drawdown_percent": round(max_drawdown, 2),
        "previous_peak": latest["peak"],
        "current_value": latest["value"],
        "alert_threshold_percent": alert_threshold,
        "breach": latest["drawdown_percent"] <= alert_threshold,
    }
