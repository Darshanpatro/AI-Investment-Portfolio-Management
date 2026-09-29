"""
SQLAlchemy ORM models for every table in the system.
"""

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

from database.database import db


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    holdings = db.relationship("Holding", backref="user", lazy=True, cascade="all, delete-orphan")
    transactions = db.relationship("Transaction", backref="user", lazy=True, cascade="all, delete-orphan")
    alerts = db.relationship("Alert", backref="user", lazy=True, cascade="all, delete-orphan")
    chats = db.relationship("ChatHistory", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


class Holding(db.Model):
    __tablename__ = "holdings"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    symbol = db.Column(db.String(20), nullable=False)
    asset_name = db.Column(db.String(120), nullable=False)
    asset_type = db.Column(db.String(40), nullable=False)  # Stock, ETF, Bond, Mutual Fund, Crypto...
    sector = db.Column(db.String(60), nullable=True)
    quantity = db.Column(db.Float, nullable=False)
    buy_price = db.Column(db.Float, nullable=False)
    purchase_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    transactions = db.relationship("Transaction", backref="holding", lazy=True, cascade="all, delete-orphan")


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    holding_id = db.Column(db.Integer, db.ForeignKey("holdings.id"), nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)  # BUY / SELL
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MarketData(db.Model):
    __tablename__ = "market_data"

    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    open = db.Column(db.Float, nullable=False)
    high = db.Column(db.Float, nullable=False)
    low = db.Column(db.Float, nullable=False)
    close = db.Column(db.Float, nullable=False)
    volume = db.Column(db.Float, nullable=True)

    __table_args__ = (db.UniqueConstraint("symbol", "date", name="uq_symbol_date"),)


class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    alert_type = db.Column(db.String(30), nullable=False)  # concentration/drawdown/anomaly/market_data
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(10), nullable=False, default="info")  # info/warning/critical
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)


class ChatHistory(db.Model):
    __tablename__ = "chat_history"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    route_used = db.Column(db.String(20), nullable=True)  # sql / rag / hybrid
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class KnowledgeDocument(db.Model):
    __tablename__ = "knowledge_documents"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    chunk_count = db.Column(db.Integer, default=0)
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)
