"""
Performance service: turns raw holdings + market data into real
calculated numbers. Nothing here is hard-coded -- every figure is
derived from the database at request time.
"""

import datetime
from services.market_data_service import get_current_price, get_price_history
from services.portfolio_service import get_holdings


def calculate_holding_metrics(holding):
    """Return a dict of computed metrics for a single holding."""
    current_price, price_source = get_current_price(holding.symbol)

    investment_value = holding.quantity * holding.buy_price

    if current_price is None:
        # Market data genuinely unavailable for this symbol -- be honest
        # about it instead of inventing a number.
        return {
            "holding_id": holding.id,
            "symbol": holding.symbol,
            "asset_name": holding.asset_name,
            "asset_type": holding.asset_type,
            "sector": holding.sector,
            "quantity": holding.quantity,
            "buy_price": holding.buy_price,
            "current_price": None,
            "price_source": "unavailable",
            "investment_value": round(investment_value, 2),
            "current_value": None,
            "profit_loss": None,
            "return_percent": None,
        }

    current_value = holding.quantity * current_price
    profit_loss = current_value - investment_value
    return_percent = (profit_loss / investment_value * 100) if investment_value else 0

    return {
        "holding_id": holding.id,
        "symbol": holding.symbol,
        "asset_name": holding.asset_name,
        "asset_type": holding.asset_type,
        "sector": holding.sector,
        "quantity": holding.quantity,
        "buy_price": holding.buy_price,
        "current_price": round(current_price, 2),
        "price_source": price_source,
        "investment_value": round(investment_value, 2),
        "current_value": round(current_value, 2),
        "profit_loss": round(profit_loss, 2),
        "return_percent": round(return_percent, 2),
    }


def calculate_portfolio_summary(user_id):
    """Aggregate real metrics across every holding for a user."""
    holdings = get_holdings(user_id)
    metrics = [calculate_holding_metrics(h) for h in holdings]

    priced = [m for m in metrics if m["current_value"] is not None]

    total_investment = sum(m["investment_value"] for m in metrics)
    total_current_value = sum(m["current_value"] for m in priced)
    # For holdings with unpriced/unavailable market data, fall back to
    # their investment value so totals stay meaningful rather than wrong.
    total_current_value += sum(
        m["investment_value"] for m in metrics if m["current_value"] is None
    )
    total_profit_loss = total_current_value - total_investment
    total_return_percent = (
        (total_profit_loss / total_investment * 100) if total_investment else 0
    )

    return {
        "holdings": metrics,
        "total_investment": round(total_investment, 2),
        "total_current_value": round(total_current_value, 2),
        "total_profit_loss": round(total_profit_loss, 2),
        "total_return_percent": round(total_return_percent, 2),
        "num_holdings": len(holdings),
        "unpriced_symbols": [m["symbol"] for m in metrics if m["current_value"] is None],
    }


def calculate_asset_allocation(user_id):
    """Percentage of portfolio value by asset and by sector."""
    summary = calculate_portfolio_summary(user_id)
    total = summary["total_current_value"]

    by_asset = []
    by_sector = {}

    for m in summary["holdings"]:
        value = m["current_value"] if m["current_value"] is not None else m["investment_value"]
        pct = (value / total * 100) if total else 0
        by_asset.append({
            "symbol": m["symbol"],
            "asset_name": m["asset_name"],
            "value": round(value, 2),
            "percent": round(pct, 2),
        })
        sector = m["sector"] or "Unclassified"
        by_sector[sector] = by_sector.get(sector, 0) + value

    by_sector_list = [
        {"sector": s, "value": round(v, 2), "percent": round((v / total * 100) if total else 0, 2)}
        for s, v in by_sector.items()
    ]

    by_asset.sort(key=lambda x: x["percent"], reverse=True)
    by_sector_list.sort(key=lambda x: x["percent"], reverse=True)

    return {"by_asset": by_asset, "by_sector": by_sector_list, "total_value": round(total, 2)}


def calculate_portfolio_value_series(user_id):
    """
    Reconstruct a real portfolio-value-over-time series by combining each
    holding's quantity (from its purchase date onward) with the daily
    historical closing price of its symbol. Used for the performance
    chart and for drawdown calculations.
    """
    holdings = get_holdings(user_id)
    if not holdings:
        return []

    # Build a date -> price lookup per symbol
    symbol_histories = {}
    all_dates = set()
    for h in holdings:
        history = get_price_history(h.symbol, limit=600)
        symbol_histories[h.symbol] = {d: c for d, c in history}
        all_dates.update(d for d, _ in history)

    if not all_dates:
        return []

    sorted_dates = sorted(all_dates)

    series = []
    for d in sorted_dates:
        day_value = 0.0
        has_any_holding = False
        for h in holdings:
            if h.purchase_date > d:
                continue
            has_any_holding = True
            price_map = symbol_histories.get(h.symbol, {})
            price = price_map.get(d)
            if price is None:
                # carry forward last known price for that symbol
                earlier = [pd for pd in price_map if pd <= d]
                price = price_map[max(earlier)] if earlier else h.buy_price
            day_value += h.quantity * price
        if has_any_holding:
            series.append({"date": d.isoformat(), "value": round(day_value, 2)})

    return series


def calculate_drawdown_series(value_series):
    """Given a portfolio value series, compute running peak and drawdown %."""
    peak = None
    out = []
    for point in value_series:
        v = point["value"]
        peak = v if peak is None else max(peak, v)
        drawdown = ((v - peak) / peak * 100) if peak else 0
        out.append({"date": point["date"], "value": v, "peak": round(peak, 2), "drawdown_percent": round(drawdown, 2)})
    return out
