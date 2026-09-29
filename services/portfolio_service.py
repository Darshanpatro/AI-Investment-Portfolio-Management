"""
Portfolio service: CRUD for holdings and transactions, always scoped to
the current authenticated user's user_id so users can never see or
modify each other's data.
"""

import datetime
from database.database import db
from database.models import Holding, Transaction


class ValidationError(Exception):
    pass


def _validate_holding_input(data):
    errors = []

    symbol = (data.get("symbol") or "").strip().upper()
    asset_name = (data.get("asset_name") or "").strip()
    asset_type = (data.get("asset_type") or "").strip()
    sector = (data.get("sector") or "").strip()

    if not symbol or not symbol.replace("&", "").replace("-", "").isalnum():
        errors.append("Symbol is required and must be alphanumeric (e.g. TCS, INFY).")

    if not asset_name:
        errors.append("Asset name is required.")

    if not asset_type:
        errors.append("Asset type is required.")

    try:
        quantity = float(data.get("quantity"))
        if quantity <= 0:
            errors.append("Quantity must be greater than zero.")
    except (TypeError, ValueError):
        errors.append("Quantity must be a valid number.")
        quantity = None

    try:
        buy_price = float(data.get("buy_price"))
        if buy_price <= 0:
            errors.append("Buy price must be greater than zero.")
    except (TypeError, ValueError):
        errors.append("Buy price must be a valid number.")
        buy_price = None

    purchase_date = None
    raw_date = (data.get("purchase_date") or "").strip()
    try:
        purchase_date = datetime.datetime.strptime(raw_date, "%Y-%m-%d").date()
        if purchase_date > datetime.date.today():
            errors.append("Purchase date cannot be in the future.")
    except ValueError:
        errors.append("Purchase date must be a valid date (YYYY-MM-DD).")

    if errors:
        raise ValidationError("; ".join(errors))

    return {
        "symbol": symbol,
        "asset_name": asset_name,
        "asset_type": asset_type,
        "sector": sector or "Unclassified",
        "quantity": quantity,
        "buy_price": buy_price,
        "purchase_date": purchase_date,
    }


def add_holding(user_id, data):
    clean = _validate_holding_input(data)
    holding = Holding(user_id=user_id, **clean)
    db.session.add(holding)
    db.session.commit()

    txn = Transaction(
        user_id=user_id,
        holding_id=holding.id,
        transaction_type="BUY",
        quantity=clean["quantity"],
        price=clean["buy_price"],
        transaction_date=clean["purchase_date"],
    )
    db.session.add(txn)
    db.session.commit()
    return holding


def update_holding(user_id, holding_id, data):
    holding = Holding.query.filter_by(id=holding_id, user_id=user_id).first()
    if holding is None:
        raise ValidationError("Holding not found.")

    clean = _validate_holding_input(data)
    for key, value in clean.items():
        setattr(holding, key, value)
    db.session.commit()
    return holding


def delete_holding(user_id, holding_id):
    holding = Holding.query.filter_by(id=holding_id, user_id=user_id).first()
    if holding is None:
        raise ValidationError("Holding not found.")
    db.session.delete(holding)
    db.session.commit()
    return True


def get_holdings(user_id):
    return Holding.query.filter_by(user_id=user_id).order_by(Holding.created_at.desc()).all()


def get_holding(user_id, holding_id):
    return Holding.query.filter_by(id=holding_id, user_id=user_id).first()


def get_transactions(user_id):
    return Transaction.query.filter_by(user_id=user_id).order_by(Transaction.transaction_date.desc()).all()
