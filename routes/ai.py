"""
AI Assistant routes. The assistant page posts questions to a JSON API
that runs the real routing/NL-to-SQL/RAG pipeline in services/ai_service.py.
"""

from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from services.ai_service import answer_question, get_chat_history

ai_bp = Blueprint("ai", __name__)


@ai_bp.route("/assistant")
@login_required
def assistant_page():
    history = get_chat_history(current_user.id)
    return render_template("assistant.html", history=history)


@ai_bp.route("/api/assistant/ask", methods=["POST"])
@login_required
def api_ask():
    question = (request.json or {}).get("question", "").strip()
    if not question:
        return jsonify({"error": "Question cannot be empty."}), 400
    if len(question) > 500:
        return jsonify({"error": "Question is too long (max 500 characters)."}), 400

    result = answer_question(current_user.id, question)
    return jsonify(result)
