"""
Knowledge base routes. Shows real document/chunk counts from the
database and connects the search box directly to the RAG pipeline.
"""

from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required

from database.models import KnowledgeDocument
from services.rag_service import answer_knowledge_question, sync_knowledge_documents_table

knowledge_bp = Blueprint("knowledge", __name__)


@knowledge_bp.route("/knowledge")
@login_required
def knowledge_page():
    documents = KnowledgeDocument.query.order_by(KnowledgeDocument.title).all()
    total_chunks = sum(d.chunk_count for d in documents)
    return render_template("knowledge.html", documents=documents, total_chunks=total_chunks)


@knowledge_bp.route("/api/knowledge/search", methods=["POST"])
@login_required
def api_knowledge_search():
    query = (request.json or {}).get("query", "").strip()
    if not query:
        return jsonify({"error": "Query cannot be empty."}), 400

    result = answer_knowledge_question(query)
    return jsonify(result)


@knowledge_bp.route("/knowledge/reindex", methods=["POST"])
@login_required
def reindex_knowledge():
    """Rebuild the vector index and refresh the KNOWLEDGE_DOCUMENTS table
    from whatever .txt files currently exist on disk."""
    docs = sync_knowledge_documents_table(current_app.config["KNOWLEDGE_DOCS_DIR"])
    return jsonify({"reindexed": True, "documents": docs})
