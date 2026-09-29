"""
Thin wrapper around an external LLM API (Anthropic Messages API by
default). Reads its key/url/model from Flask config (which reads from
.env), never from frontend code, and is used by both the RAG service
and the AI assistant's answer-generation step.

If LLM_API_KEY is not configured, or the API call fails for any reason,
callers receive (None-ish fallback text is NOT produced here; the
*caller* decides its own honest fallback) and a used_llm=False flag, so
the app degrades gracefully instead of crashing or pretending to have
called an LLM.
"""

import requests
from flask import current_app


def generate_llm_answer(system_prompt, user_message, max_tokens=400):
    """
    Returns (text, used_llm: bool). If no API key is configured or the
    call fails, returns (None, False) and the caller supplies its own
    genuine fallback -- this function never fabricates an LLM response.
    """
    api_key = current_app.config.get("LLM_API_KEY")
    api_url = current_app.config.get("LLM_API_URL")
    model = current_app.config.get("LLM_MODEL")

    if not api_key:
        return None, False

    try:
        resp = requests.post(
            api_url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_message}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        text_parts = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        answer = "\n".join(text_parts).strip()
        if answer:
            return answer, True
        return None, False
    except Exception as e:
        current_app.logger.warning(f"LLM API call failed, falling back to rule-based answer: {e}")
        return None, False
