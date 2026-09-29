"""
Risk analysis routes: concentration risk, drawdown, and anomaly
detection. All values are computed live -- concentration percentages
from actual holdings, drawdown from a reconstructed real value series,
and anomalies from a real fitted Isolation Forest model.
"""

from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user

from services.risk_service import analyze_concentration_risk, analyze_drawdown
from services.anomaly_service import analyze_portfolio_anomalies

risk_bp = Blueprint("risk", __name__)


@risk_bp.route("/risk")
@login_required
def risk_page():
    concentration = analyze_concentration_risk(current_user.id)
    drawdown = analyze_drawdown(current_user.id)
    anomaly = analyze_portfolio_anomalies(current_user.id)
    return render_template(
        "risk.html",
        concentration=concentration,
        drawdown=drawdown,
        anomaly=anomaly,
    )


@risk_bp.route("/api/risk/drawdown-series")
@login_required
def api_drawdown_series():
    drawdown = analyze_drawdown(current_user.id)
    return jsonify(drawdown.get("series", []))


@risk_bp.route("/api/risk/anomaly/<symbol>")
@login_required
def api_anomaly_symbol(symbol):
    anomaly = analyze_portfolio_anomalies(current_user.id)
    return jsonify(anomaly["results"].get(symbol.upper(), {"available": False}))
