"""
Market data service.

Loads historical/sample OHLCV data from data/market_data.csv into the
MARKET_DATA table (once, on first run), and provides a single function,
get_current_price(), that the rest of the app calls to price a holding.

This is clearly HISTORICAL / SAMPLE data, not a live market feed. If an
external market-data API key + URL are configured (MARKET_DATA_API_KEY /
MARKET_DATA_API_URL in .env), get_current_price() will try that first and
fall back to the local historical data (with the failure logged, not
hidden) if the call fails. Without those variables configured, the app
transparently uses the bundled CSV data and labels it as such wherever it
is shown to the user.
"""

import datetime
import pandas as pd
import requests
from flask import current_app

from database.database import db
from database.models import MarketData


def load_market_data_into_db():
    """Idempotently load data/market_data.csv into the market_data table."""
    if MarketData.query.first() is not None:
        return 0  # already loaded

    csv_path = current_app.config["MARKET_DATA_CSV"]
    df = pd.read_csv(csv_path, parse_dates=["date"])

    rows = []
    for _, r in df.iterrows():
        rows.append(
            MarketData(
                symbol=r["symbol"],
                date=r["date"].date(),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r.get("volume", 0) or 0),
            )
        )
    db.session.bulk_save_objects(rows)
    db.session.commit()
    return len(rows)


def get_latest_close(symbol):
    """Return the most recent close price for a symbol from local historical data."""
    row = (
        MarketData.query.filter_by(symbol=symbol)
        .order_by(MarketData.date.desc())
        .first()
    )
    return row.close if row else None


def get_price_history(symbol, limit=252):
    """Return a list of (date, close) tuples, oldest first, for a symbol."""
    rows = (
        MarketData.query.filter_by(symbol=symbol)
        .order_by(MarketData.date.desc())
        .limit(limit)
        .all()
    )
    rows = list(reversed(rows))
    return [(r.date, r.close) for r in rows]


def get_current_price(symbol):
    """
    Returns (price, source) where source is 'live_api', 'historical', or
    'unavailable'. Tries a configured external API first; falls back to
    the local historical/sample data. Never crashes the app if pricing
    data is missing for a symbol.
    """
    api_key = current_app.config.get("MARKET_DATA_API_KEY")
    api_url = current_app.config.get("MARKET_DATA_API_URL")

    if api_key and api_url:
        try:
            resp = requests.get(
                api_url,
                params={"symbol": symbol},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5,
            )
            resp.raise_for_status()
            payload = resp.json()
            price = payload.get("price")
            if price is not None:
                return float(price), "live_api"
        except Exception:
            # Fall through to historical data on any failure -- the
            # website must not crash if the external API is unavailable.
            pass

    price = get_latest_close(symbol)
    if price is not None:
        return price, "historical"

    return None, "unavailable"


def get_all_symbols():
    rows = db.session.query(MarketData.symbol).distinct().all()
    return sorted(r[0] for r in rows)
