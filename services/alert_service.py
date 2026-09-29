"""
Alert service: generates real alerts by running the actual risk engine
(concentration, drawdown, anomaly detection) and market-data checks,
then persists any new conditions to the ALERTS table. Alerts are
de-duplicated per day per (type, subject) so re-running the checker
repeatedly doesn't spam duplicate rows.
"""

import datetime
from database.database import db
from database.models import Alert
from services.risk_service import analyze_concentration_risk, analyze_drawdown
from services.anomaly_service import analyze_portfolio_anomalies
from services.performance_service import calculate_portfolio_summary


def _create_if_new(user_id, alert_type, title, message, severity):
    today = datetime.datetime.utcnow().date()
    existing = (
        Alert.query.filter_by(user_id=user_id, alert_type=alert_type, title=title)
        .filter(db.func.date(Alert.created_at) == today)
        .first()
    )
    if existing:
        return None
    alert = Alert(
        user_id=user_id,
        alert_type=alert_type,
        title=title,
        message=message,
        severity=severity,
    )
    db.session.add(alert)
    return alert


def run_alert_checks(user_id):
    """
    Runs every risk check for the user and writes any newly-detected
    conditions into the ALERTS table. Returns the list of newly created
    alerts (may be empty if nothing new was found, or if the portfolio
    is empty).
    """
    created = []

    summary = calculate_portfolio_summary(user_id)
    if summary["num_holdings"] == 0:
        return created

    # 1. Concentration risk
    concentration = analyze_concentration_risk(user_id)
    for breach in concentration["breaches"]:
        a = _create_if_new(
            user_id,
            "concentration",
            f"Concentration risk: {breach['name']}",
            breach["message"],
            severity="warning",
        )
        if a:
            created.append(a)

    # 2. Drawdown
    drawdown = analyze_drawdown(user_id)
    if drawdown["has_data"] and drawdown["breach"]:
        a = _create_if_new(
            user_id,
            "drawdown",
            "Portfolio drawdown threshold reached",
            (
                f"Your portfolio is currently down {drawdown['current_drawdown_percent']}% "
                f"from its recorded peak of ₹{drawdown['previous_peak']:,}. This is at or "
                f"beyond your configured monitoring threshold of "
                f"{drawdown['alert_threshold_percent']}%."
            ),
            severity="critical",
        )
        if a:
            created.append(a)

    # 3. Anomaly detection
    anomaly = analyze_portfolio_anomalies(user_id)
    for flag in anomaly["flagged"]:
        a = _create_if_new(
            user_id,
            "anomaly",
            f"Unusual price movement: {flag['symbol']}",
            flag["message"],
            severity="warning",
        )
        if a:
            created.append(a)

    # 4. Market-data availability warning
    if summary["unpriced_symbols"]:
        symbols = ", ".join(summary["unpriced_symbols"])
        a = _create_if_new(
            user_id,
            "market_data",
            "Market data unavailable for some holdings",
            (
                f"Current pricing could not be found for: {symbols}. Their investment "
                f"value is being shown in place of current value until market data is "
                f"available."
            ),
            severity="info",
        )
        if a:
            created.append(a)

    if created:
        db.session.commit()

    return created


def get_alerts(user_id, unread_only=False):
    q = Alert.query.filter_by(user_id=user_id)
    if unread_only:
        q = q.filter_by(is_read=False)
    return q.order_by(Alert.created_at.desc()).all()


def mark_alert_read(user_id, alert_id):
    alert = Alert.query.filter_by(id=alert_id, user_id=user_id).first()
    if alert is None:
        return False
    alert.is_read = True
    db.session.commit()
    return True


def mark_all_read(user_id):
    Alert.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})
    db.session.commit()
