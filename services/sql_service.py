"""
Controlled Natural-Language-to-SQL engine.

Design choice (documented for the IEEE report): rather than letting an
LLM generate arbitrary free-form SQL, this engine classifies the
question into one of a small set of PERMITTED intents, each of which
maps to a fixed, parameterized, read-only SQL template. The template is
then run through validate_sql() as a second, independent safety check
before execution. This gives the "NL -> SQL -> validate -> execute"
pipeline the assignment asks for, while making it structurally
impossible to run anything other than a whitelisted, user-scoped SELECT.

Every query is always filtered by the current user's user_id, so one
user can never see another user's data through this feature.
"""

import re
from sqlalchemy import text
from database.database import db
from database.models import Holding

ALLOWED_TABLES = {"holdings", "transactions", "alerts"}
FORBIDDEN_KEYWORDS = ("insert", "update", "delete", "drop", "alter", "create", "--", ";")


class UnsafeQueryError(Exception):
    pass


def validate_sql(sql_text, user_id):
    """
    Independent safety check run on every generated SQL string before
    execution. Rejects anything that is not a single read-only SELECT
    against an allowed table, scoped to the given user_id.
    """
    lowered = sql_text.strip().lower()

    if not lowered.startswith("select"):
        raise UnsafeQueryError("Only SELECT statements are permitted.")

    for kw in FORBIDDEN_KEYWORDS:
        if kw in lowered:
            raise UnsafeQueryError(f"Query contains a forbidden keyword: '{kw}'.")

    referenced_tables = set(re.findall(r"from\s+(\w+)|join\s+(\w+)", lowered))
    referenced_tables = {t for pair in referenced_tables for t in pair if t}
    if not referenced_tables.issubset(ALLOWED_TABLES):
        raise UnsafeQueryError("Query references a table outside the allowed whitelist.")

    if f":user_id" not in lowered:
        raise UnsafeQueryError("Query must be scoped to the current user (missing :user_id filter).")

    return True


# --- Intent classification -------------------------------------------------

_INTENT_PATTERNS = [
    ("total_investment", [r"total investment", r"how much.*invest", r"money.*invested"]),
    ("total_current_value", [r"current value", r"portfolio.*worth", r"worth.*now"]),
    ("total_profit_loss", [r"total profit", r"total loss", r"overall profit", r"profit.*loss"]),
    ("total_return", [r"portfolio return", r"overall return", r"my return"]),
    ("num_holdings", [r"how many holdings", r"number of holdings", r"how many (stocks|assets)"]),
    ("highest_profit_asset", [r"highest profit", r"best perform", r"most profit", r"top gainer"]),
    ("lowest_profit_asset", [r"lowest profit", r"worst perform", r"most loss", r"biggest loser", r"top loser"]),
    ("highest_return_asset", [r"highest return", r"best return"]),
    ("list_holdings", [r"list.*holdings", r"what.*hold", r"show.*holdings", r"my holdings"]),
    ("recent_transactions", [r"recent transaction", r"transaction history", r"my transactions"]),
    ("unread_alert_count", [r"how many alerts", r"unread alert", r"pending alert"]),
    ("specific_symbol", [r"how much (\w+)", r"do i (own|hold) (\w+)", r"my (\w+) holding"]),
]


def classify_intent(question):
    q = question.lower().strip()
    for intent, patterns in _INTENT_PATTERNS:
        for p in patterns:
            if re.search(p, q):
                return intent
    return None


_SYMBOL_RE = re.compile(r"\b([A-Za-z]{2,10})\b")
_KNOWN_STOPWORDS = {"how", "much", "do", "i", "own", "hold", "my", "the", "of", "in",
                     "is", "what", "a", "an", "holding", "for"}


def _extract_symbol(question, user_id):
    """Try to match a token in the question against the user's actual holding symbols."""
    user_symbols = {
        s[0].upper()
        for s in db.session.query(Holding.symbol).filter_by(user_id=user_id).distinct().all()
    }
    tokens = [t.upper() for t in _SYMBOL_RE.findall(question) if t.lower() not in _KNOWN_STOPWORDS]
    for t in tokens:
        if t in user_symbols:
            return t
    return None


# --- Query templates (parameterized, whitelisted) --------------------------

_TEMPLATES = {
    "total_investment": "SELECT SUM(quantity * buy_price) AS value FROM holdings WHERE user_id = :user_id",
    "num_holdings": "SELECT COUNT(*) AS value FROM holdings WHERE user_id = :user_id",
    "list_holdings": "SELECT symbol, asset_name, quantity, buy_price FROM holdings WHERE user_id = :user_id",
    "recent_transactions": (
        "SELECT transaction_type, quantity, price, transaction_date FROM transactions "
        "WHERE user_id = :user_id ORDER BY transaction_date DESC LIMIT 10"
    ),
    "unread_alert_count": "SELECT COUNT(*) AS value FROM alerts WHERE user_id = :user_id AND is_read = 0",
    "specific_symbol": (
        "SELECT symbol, asset_name, quantity, buy_price FROM holdings "
        "WHERE user_id = :user_id AND symbol = :symbol"
    ),
}

# Intents that require calculation with live/historical market prices
# (i.e. current value, profit, return) are computed via the performance
# service rather than raw SQL, since "current price" is not stored as a
# static column -- but they are still routed through this NL-to-SQL
# layer's intent classification and still fully scoped to user_id.
_COMPUTED_INTENTS = {
    "total_current_value", "total_profit_loss", "total_return",
    "highest_profit_asset", "lowest_profit_asset", "highest_return_asset",
}


def run_nl_query(user_id, question):
    """
    Full pipeline: question -> intent classification -> generate SQL (or
    route to computed intent) -> validate -> execute -> return structured
    result. Returns a dict with keys: ok, intent, sql (if any), data,
    message (used when the request cannot be safely handled).
    """
    from services.performance_service import calculate_portfolio_summary  # local import avoids cycle

    intent = classify_intent(question)

    if intent is None:
        return {
            "ok": False,
            "intent": None,
            "message": (
                "I could not confidently map that question to a permitted "
                "portfolio-data query, so I won't guess at a database query. "
                "Try asking about your total investment, current value, "
                "profit/loss, returns, number of holdings, or a specific "
                "holding by symbol."
            ),
        }

    if intent in _COMPUTED_INTENTS:
        summary = calculate_portfolio_summary(user_id)
        if intent == "total_current_value":
            data = {"total_current_value": summary["total_current_value"]}
        elif intent == "total_profit_loss":
            data = {"total_profit_loss": summary["total_profit_loss"]}
        elif intent == "total_return":
            data = {"total_return_percent": summary["total_return_percent"]}
        else:
            priced = [h for h in summary["holdings"] if h["profit_loss"] is not None]
            if not priced:
                return {"ok": True, "intent": intent, "sql": None, "data": None,
                         "message": "No priced holdings available yet to compare."}
            if intent == "highest_profit_asset":
                best = max(priced, key=lambda h: h["profit_loss"])
            elif intent == "lowest_profit_asset":
                best = min(priced, key=lambda h: h["profit_loss"])
            else:
                best = max(priced, key=lambda h: h["return_percent"])
            data = best
        return {"ok": True, "intent": intent, "sql": "(computed via performance service)", "data": data}

    if intent == "specific_symbol":
        symbol = _extract_symbol(question, user_id)
        if symbol is None:
            return {
                "ok": False,
                "intent": intent,
                "message": "I couldn't match that to a symbol in your portfolio. Check the spelling and try again.",
            }
        sql = _TEMPLATES["specific_symbol"]
        validate_sql(sql, user_id)
        result = db.session.execute(text(sql), {"user_id": user_id, "symbol": symbol}).mappings().all()
        return {"ok": True, "intent": intent, "sql": sql, "data": [dict(r) for r in result]}

    sql = _TEMPLATES[intent]
    validate_sql(sql, user_id)
    result = db.session.execute(text(sql), {"user_id": user_id}).mappings().all()
    rows = [dict(r) for r in result]

    if intent in ("total_investment", "num_holdings", "unread_alert_count"):
        data = rows[0]["value"] if rows else 0
    else:
        data = rows

    return {"ok": True, "intent": intent, "sql": sql, "data": data}
