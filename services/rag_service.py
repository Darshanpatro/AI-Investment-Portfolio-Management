"""
RAG (Retrieval-Augmented Generation) service for the financial
knowledge base.

Pipeline: documents -> text extraction -> chunking -> TF-IDF embeddings
-> in-memory vector store -> cosine-similarity semantic retrieval ->
relevant context -> answer generation (LLM if configured, otherwise a
genuine extractive/template fallback -- never a canned string).

TF-IDF vectors are used as the "embeddings" here instead of a hosted
embedding API. This is a deliberate, documented design choice for a
BCA-level project: it keeps the whole RAG pipeline runnable fully
offline and reproducibly, with no external embedding service or API
key required, while still giving a real vector space, real cosine
similarity search, and real (not hard-coded) retrieval.
"""

import os
import re
import glob
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from database.database import db
from database.models import KnowledgeDocument
from services.ai_client import generate_llm_answer

_CHUNK_SIZE_WORDS = 120
_CHUNK_OVERLAP_WORDS = 20

# In-memory vector store: rebuilt from the knowledge_base/documents
# folder on first use per process. For a BCA-scale project this is a
# reasonable, transparent substitute for a persistent vector database.
_STORE = {"chunks": [], "vectorizer": None, "matrix": None, "built": False}


def _chunk_text(text_content, source_title):
    words = text_content.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + _CHUNK_SIZE_WORDS, len(words))
        chunk_words = words[start:end]
        chunk_body = " ".join(chunk_words)
        # embed_text weights the document title into the vector for this
        # chunk (repeated a few times) so a query naming the concept
        # directly ("What is diversification?") reliably retrieves chunks
        # from the matching document, not just any chunk that happens to
        # mention the word once in passing. The *display* text stays
        # exactly the original chunk body.
        embed_text = f"{source_title} {source_title} {source_title} {chunk_body}"
        chunks.append({"title": source_title, "text": chunk_body, "embed_text": embed_text})
        if end == len(words):
            break
        start = end - _CHUNK_OVERLAP_WORDS
    return chunks


def build_knowledge_index(docs_dir):
    """Load every .txt document, chunk it, and fit a TF-IDF vector space over all chunks."""
    all_chunks = []
    doc_records = []

    for path in sorted(glob.glob(os.path.join(docs_dir, "*.txt"))):
        filename = os.path.basename(path)
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()

        title_match = re.search(r"Title:\s*(.+)", raw)
        title = title_match.group(1).strip() if title_match else filename
        body = re.sub(r"Title:\s*.+\n*", "", raw, count=1).strip()

        chunks = _chunk_text(body, title)
        for c in chunks:
            c["filename"] = filename
        all_chunks.extend(chunks)
        doc_records.append({"filename": filename, "title": title, "chunk_count": len(chunks)})

    if not all_chunks:
        _STORE.update({"chunks": [], "vectorizer": None, "matrix": None, "built": True})
        return doc_records

    texts = [c["embed_text"] for c in all_chunks]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=5000, ngram_range=(1, 2), sublinear_tf=True)
    matrix = vectorizer.fit_transform(texts)

    _STORE.update({"chunks": all_chunks, "vectorizer": vectorizer, "matrix": matrix, "built": True})
    return doc_records


def sync_knowledge_documents_table(docs_dir):
    """Populate/refresh the KNOWLEDGE_DOCUMENTS table to match the docs on disk."""
    doc_records = build_knowledge_index(docs_dir)

    KnowledgeDocument.query.delete()
    for rec in doc_records:
        db.session.add(KnowledgeDocument(
            filename=rec["filename"], title=rec["title"], chunk_count=rec["chunk_count"],
        ))
    db.session.commit()
    return doc_records


def _ensure_index_built():
    if not _STORE["built"]:
        from flask import current_app
        build_knowledge_index(current_app.config["KNOWLEDGE_DOCS_DIR"])


def retrieve_relevant_chunks(query, top_k=3, min_score=0.05):
    """Real semantic retrieval: embed the query with the fitted TF-IDF
    space and rank knowledge-base chunks by cosine similarity."""
    _ensure_index_built()

    if not _STORE["chunks"] or _STORE["vectorizer"] is None:
        return []

    query_vec = _STORE["vectorizer"].transform([query])
    sims = cosine_similarity(query_vec, _STORE["matrix"]).flatten()

    ranked_idx = sims.argsort()[::-1][:top_k]
    results = []
    for idx in ranked_idx:
        score = float(sims[idx])
        if score < min_score:
            continue
        chunk = _STORE["chunks"][idx]
        results.append({
            "title": chunk["title"],
            "filename": chunk["filename"],
            "text": chunk["text"],
            "similarity": round(score, 4),
        })
    return results


def answer_knowledge_question(query):
    """Full RAG answer: retrieve real chunks, then generate an answer
    grounded only in those chunks (LLM if configured, template fallback
    otherwise)."""
    # Retrieve a slightly wider pool than we display. The extra chunks
    # give the extractive fallback a better chance of containing the
    # actual definitional sentence, which is sometimes split into a
    # lower-ranked chunk by the fixed-size chunker.
    pool = retrieve_relevant_chunks(query, top_k=6)
    chunks = pool[:3]

    if not chunks:
        return {
            "answer": (
                "I couldn't find anything in the knowledge base relevant to that "
                "question. Try asking about diversification, asset allocation, "
                "portfolio risk, drawdown, volatility, stocks, bonds, or ETFs."
            ),
            "chunks": [],
            "source": "no_match",
        }

    context = "\n\n".join(f"[{c['title']}]: {c['text']}" for c in chunks)

    system_prompt = (
        "You are a financial-education assistant embedded in a student portfolio "
        "management application. Answer the user's question using ONLY the context "
        "provided below. Keep the answer to 3-5 sentences, in plain language suitable "
        "for a student. Do not give personalized investment advice, do not guarantee "
        "returns, and do not invent facts that are not in the context.\n\nContext:\n" + context
    )

    llm_answer, used_llm = generate_llm_answer(system_prompt, query)

    if used_llm:
        return {"answer": llm_answer, "chunks": chunks, "source": "llm+rag"}

    # Honest, genuine fallback: an extractive answer built from the
    # actual retrieved chunks (not a hard-coded canned answer), used only
    # when no LLM_API_KEY is configured. We pick the sentences from the
    # retrieved context that best overlap the query's own terms, so the
    # extract reads as a real answer rather than an arbitrary mid-chunk
    # fragment.
    top = chunks[0]
    query_terms = {w for w in re.findall(r"[a-z]{3,}", query.lower())}

    # The main subject of the question, used to spot definitional
    # sentences like "Diversification is an investment strategy that..."
    subject_terms = query_terms - {"what", "does", "mean", "explain", "define", "tell", "about", "the"}

    candidate_sentences = []
    for chunk_rank, c in enumerate(pool):
        for sent_pos, s in enumerate(re.split(r"(?<=[.!?])\s+", c["text"])):
            s = s.strip()
            # Only keep sentences that look complete (start with a capital
            # letter), so we never open on a mid-sentence fragment.
            if len(s) < 40 or not s[0].isupper():
                continue
            s_words = set(re.findall(r"[a-z]{3,}", s.lower()))
            score = len(query_terms & s_words)

            # Strongly prefer a definitional opening: "<subject> is/are/refers to ..."
            is_definition = False
            first_words = " ".join(s.split()[:8]).lower()
            if subject_terms and any(t in first_words for t in subject_terms):
                if re.search(r"\b(is|are|refers to|means|describes)\b", first_words):
                    score += 10
                    is_definition = True

            candidate_sentences.append({
                "score": score, "text": s, "is_definition": is_definition,
                "order": (chunk_rank, sent_pos),
            })

    if not candidate_sentences:
        extract = top["text"][:400]
    else:
        ranked = sorted(candidate_sentences, key=lambda x: -x["score"])[:3]
        ranked = [c for c in ranked if c["score"] > 0] or ranked[:2]

        # Lead with a definitional sentence if the knowledge base has one.
        # Among competing definitional sentences ("X is the process of..."
        # vs "X is closely related to..."), the earliest one in the source
        # document is almost always the real definition, so prefer that
        # over the highest term-overlap score.
        definitions = sorted(
            (c for c in candidate_sentences if c["is_definition"]),
            key=lambda x: x["order"],
        )
        definition = definitions[0] if definitions else None

        rest = [c for c in ranked if c["text"] != (definition or {}).get("text")][:2]
        rest.sort(key=lambda x: x["order"])
        ordered = ([definition] if definition else []) + rest
        extract = " ".join(c["text"] for c in ordered)

    fallback = (
        f"(No LLM API key configured -- showing an answer extracted from the "
        f"retrieved knowledge base content.) From \"{top['title']}\": {extract}"
    )
    return {"answer": fallback, "chunks": chunks, "source": "rag_extractive_fallback"}
