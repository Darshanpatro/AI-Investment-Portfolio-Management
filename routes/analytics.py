"""
Analytics routes: performance page (charts) and its JSON data endpoints,
consumed by Chart.js on the frontend. All data is computed live from the
database -- nothing is pre-baked into the templates.
"""

from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user

from services.performance_service import (
    calculate_portfolio_summary,
    calculate_asset_allocation,
    calculate_portfolio_value_series,
)

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.route("/performance")
@login_required
def performance_page():
    summary = calculate_portfolio_summary(current_user.id)
    return render_template("performance.html", summary=summary)


@analytics_bp.route("/api/performance/value-series")
@login_required
def api_value_series():
    series = calculate_portfolio_value_series(current_user.id)
    return jsonify(series)


@analytics_bp.route("/api/performance/by-asset")
@login_required
def api_performance_by_asset():
    summary = calculate_portfolio_summary(current_user.id)
    return jsonify(summary["holdings"])


@analytics_bp.route("/api/allocation")
@login_required
def api_allocation():
    allocation = calculate_asset_allocation(current_user.id)
    return jsonify(allocation)
