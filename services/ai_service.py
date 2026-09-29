"""
AI assistant: routes each user question to the correct sub-system
(NL-to-SQL for portfolio-data questions, RAG for financial-knowledge
questions, or both for hybrid questions), then produces a final,
grounded natural-language answer. Also persists chat history.
"""

import re
from database.database import db
from database.models import ChatHistory
from services.sql_service import run_nl_query, classify_intent
from services.rag_service import answer_knowledge_question
from services.ai_client import generate_llm_answer
from services.performance_service import calculate_portfolio_summary
from services.risk_service import analyze_concentration_risk

_KNOWLEDGE_TERMS = [
    "diversification", "diversify", "asset allocation", "what is risk",
    "portfolio risk", "drawdown", "volatility", "what is a stock",
    "what is a bond", "what is an etf", "explain", "define", "meaning of",
]

_HYBRID_MARKERS = [
    "why", "relevant to my portfolio", "does this affect", "should i be worried",
    "my portfolio", "risk alert",
]


def _generic_portfolio_snapshot(user_id):
    """A short, real, computed snapshot of the user's portfolio used to
    ground hybrid answers that don't map to one specific NL-to-SQL intent
    (e.g. 'Why is diversification relevant to my portfolio?')."""
    summary = calculate_portfolio_summary(user_id)
    if summary["num_holdings"] == 0:
        return "You don't have any holdings yet, so this doesn't apply to your portfolio just yet."

    concentration = analyze_concentration_risk(user_id)
    top_sector = concentration["by_sector"][0] if concentration["by_sector"] else None

    parts = [
        f"Your portfolio currently holds {summary['num_holdings']} asset(s) worth "
        f"₹{summary['total_current_value']:,.2f}."
    ]
    if top_sector:
        parts.append(
            f"Your largest sector exposure is {top_sector['sector']} at {top_sector['percent']}% "
            f"of your portfolio."
        )
    if concentration["is_concentrated"]:
        parts.append("This currently exceeds your configured concentration risk threshold.")
    return " ".join(parts)


def _looks_like_knowledge_question(question):
    q = question.lower()
    return any(term in q for term in _KNOWLEDGE_TERMS)


def _format_sql_result_as_text(intent, data):
    if intent == "total_investment":
        return f"Your total investment across all holdings is ₹{data:,.2f}."
    if intent == "total_current_value":
        return f"Your current portfolio value is ₹{data['total_current_value']:,.2f}."
    if intent == "total_profit_loss":
        sign = "profit" if data["total_profit_loss"] >= 0 else "loss"
        return f"Your total {sign} is ₹{abs(data['total_profit_loss']):,.2f}."
    if intent == "total_return":
        return f"Your overall portfolio return is {data['total_return_percent']}%."
    if intent == "num_holdings":
        return f"You currently have {data} holding(s) in your portfolio."
    if intent == "unread_alert_count":
        return f"You have {data} unread alert(s)."
    if intent in ("highest_profit_asset", "lowest_profit_asset", "highest_return_asset"):
        if data is None:
            return "There isn't enough priced data yet to answer that."
        return (
            f"{data['symbol']} ({data['asset_name']}) has a profit/loss of "
            f"₹{data['profit_loss']:,.2f} and a return of {data['return_percent']}%."
        )
    if intent == "list_holdings":
        if not data:
            return "You don't have any holdings yet."
        lines = [f"- {r['symbol']}: {r['quantity']} units @ ₹{r['buy_price']}" for r in data]
        return "Here are your holdings:\n" + "\n".join(lines)
    if intent == "recent_transactions":
        if not data:
            return "You don't have any transactions yet."
        lines = [f"- {r['transaction_type']} {r['quantity']} @ ₹{r['price']} on {r['transaction_date']}" for r in data]
        return "Your recent transactions:\n" + "\n".join(lines)
    if intent == "specific_symbol":
        if not data:
            return "I couldn't find that holding in your portfolio."
        r = data[0]
        return f"You hold {r['quantity']} units of {r['symbol']} ({r['asset_name']}) at an average buy price of ₹{r['buy_price']}."
    return "Here is the result."


def answer_question(user_id, question):
    """
    Routing logic:
      - Pure portfolio-data question (matches an NL-to-SQL intent) -> SQL
      - Pure financial-knowledge question (no portfolio intent match, or
        contains a knowledge term) -> RAG
      - Hybrid (has both a portfolio intent AND knowledge/why-type
        language) -> SQL + RAG combined
    """
    intent = classify_intent(question)
    knowledge_like = _looks_like_knowledge_question(question)
    hybrid_like = any(m in question.lower() for m in _HYBRID_MARKERS)

    route = None
    answer_text = ""
    sql_result = None
    rag_result = None

    if intent and not knowledge_like:
        route = "sql"
        sql_result = run_nl_query(user_id, question)
        if sql_result["ok"]:
            answer_text = _format_sql_result_as_text(sql_result["intent"], sql_result["data"])
        else:
            answer_text = sql_result["message"]

    elif intent and (knowledge_like or hybrid_like):
        route = "hybrid"
        sql_result = run_nl_query(user_id, question)
        rag_result = answer_knowledge_question(question)
        portfolio_part = (
            _format_sql_result_as_text(sql_result["intent"], sql_result["data"])
            if sql_result["ok"] else sql_result["message"]
        )
        answer_text = f"{portfolio_part}\n\n{rag_result['answer']}"

    elif hybrid_like and knowledge_like:
        # No specific numeric NL-to-SQL intent matched, but the question
        # both references "my portfolio" and asks about a financial
        # concept -- combine a real computed portfolio snapshot with RAG.
        route = "hybrid"
        rag_result = answer_knowledge_question(question)
        portfolio_part = _generic_portfolio_snapshot(user_id)
        answer_text = f"{portfolio_part}\n\n{rag_result['answer']}"

    else:
        route = "rag"
        rag_result = answer_knowledge_question(question)
        answer_text = rag_result["answer"]

    chat = ChatHistory(user_id=user_id, question=question, answer=answer_text, route_used=route)
    db.session.add(chat)
    db.session.commit()

    return {
        "answer": answer_text,
        "route": route,
        "sql_result": sql_result,
        "rag_result": rag_result,
    }


def get_chat_history(user_id, limit=30):
    return (
        ChatHistory.query.filter_by(user_id=user_id)
        .order_by(ChatHistory.created_at.desc())
        .limit(limit)
        .all()
    )
