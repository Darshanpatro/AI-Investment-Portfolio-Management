"""
Alerts routes: view alerts, mark individual/all as read, and manually
trigger a fresh alert check run against real current data.
"""

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from services.alert_service import get_alerts, mark_alert_read, mark_all_read, run_alert_checks

alerts_bp = Blueprint("alerts", __name__)


@alerts_bp.route("/alerts")
@login_required
def alerts_page():
    alerts = get_alerts(current_user.id)
    return render_template("alerts.html", alerts=alerts)


@alerts_bp.route("/alerts/refresh", methods=["POST"])
@login_required
def refresh_alerts():
    created = run_alert_checks(current_user.id)
    if created:
        flash(f"{len(created)} new alert(s) generated from current portfolio conditions.", "info")
    else:
        flash("No new alert conditions detected.", "secondary")
    return redirect(url_for("alerts.alerts_page"))


@alerts_bp.route("/alerts/<int:alert_id>/read", methods=["POST"])
@login_required
def read_alert(alert_id):
    mark_alert_read(current_user.id, alert_id)
    return redirect(url_for("alerts.alerts_page"))


@alerts_bp.route("/alerts/read-all", methods=["POST"])
@login_required
def read_all_alerts():
    mark_all_read(current_user.id)
    return redirect(url_for("alerts.alerts_page"))
