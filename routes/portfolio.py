"""
Portfolio routes: dashboard, holdings CRUD (create/read/update/delete),
and transactions. Every query is scoped to current_user.id.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from services import portfolio_service
from services.portfolio_service import ValidationError
from services.performance_service import calculate_portfolio_summary, calculate_asset_allocation
from services.alert_service import run_alert_checks, get_alerts

portfolio_bp = Blueprint("portfolio", __name__)


@portfolio_bp.route("/")
@login_required
def dashboard():
    # Refresh alerts based on current live data every time the dashboard loads.
    run_alert_checks(current_user.id)

    summary = calculate_portfolio_summary(current_user.id)
    allocation = calculate_asset_allocation(current_user.id)
    recent_alerts = get_alerts(current_user.id)[:5]

    return render_template(
        "dashboard.html",
        summary=summary,
        allocation=allocation,
        recent_alerts=recent_alerts,
    )


@portfolio_bp.route("/portfolio")
@login_required
def portfolio_page():
    summary = calculate_portfolio_summary(current_user.id)
    return render_template("portfolio.html", summary=summary)


@portfolio_bp.route("/holdings")
@login_required
def holdings_page():
    holdings = portfolio_service.get_holdings(current_user.id)
    return render_template("holdings.html", holdings=holdings)


@portfolio_bp.route("/holdings/add", methods=["POST"])
@login_required
def add_holding():
    try:
        portfolio_service.add_holding(current_user.id, request.form)
        flash("Holding added successfully.", "success")
    except ValidationError as e:
        flash(str(e), "danger")
    return redirect(url_for("portfolio.holdings_page"))


@portfolio_bp.route("/holdings/<int:holding_id>/edit", methods=["POST"])
@login_required
def edit_holding(holding_id):
    try:
        portfolio_service.update_holding(current_user.id, holding_id, request.form)
        flash("Holding updated successfully.", "success")
    except ValidationError as e:
        flash(str(e), "danger")
    return redirect(url_for("portfolio.holdings_page"))


@portfolio_bp.route("/holdings/<int:holding_id>/delete", methods=["POST"])
@login_required
def delete_holding(holding_id):
    try:
        portfolio_service.delete_holding(current_user.id, holding_id)
        flash("Holding deleted.", "info")
    except ValidationError as e:
        flash(str(e), "danger")
    return redirect(url_for("portfolio.holdings_page"))


@portfolio_bp.route("/holdings/<int:holding_id>/json")
@login_required
def holding_json(holding_id):
    """Used by the frontend to populate the Edit modal with real data."""
    h = portfolio_service.get_holding(current_user.id, holding_id)
    if h is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "id": h.id, "symbol": h.symbol, "asset_name": h.asset_name,
        "asset_type": h.asset_type, "sector": h.sector, "quantity": h.quantity,
        "buy_price": h.buy_price, "purchase_date": h.purchase_date.isoformat(),
    })


@portfolio_bp.route("/transactions")
@login_required
def transactions_page():
    transactions = portfolio_service.get_transactions(current_user.id)
    return render_template("transactions.html", transactions=transactions)


@portfolio_bp.route("/settings")
@login_required
def settings_page():
    return render_template("settings.html")
