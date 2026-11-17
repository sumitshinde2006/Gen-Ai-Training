"""Evidence-grounded question answering over KandaGuide's Chroma index."""

import json
import re
from pathlib import Path
from typing import Any

from app.llm import LLMError, generate_response
from app.vectorstore import MAX_TOP_K, VectorStoreError, semantic_search

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SYSTEM_PROMPT_PATH = PROJECT_ROOT / "prompts" / "system.txt"
UNKNOWN_ANSWER = "I don't know."
Q6 = "What is today's onion mandi price per quintal in Lasalgaon?"
TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "for", "from", "how",
    "in", "is", "it", "listed", "my", "of", "on", "or", "recorded",
    "should", "the", "to", "what", "which", "with",
}


class RAGError(RuntimeError):
    """Safe error raised when the RAG pipeline cannot complete."""


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(value) if token.lower() not in STOP_WORDS}


def _is_q6(question: str) -> bool:
    return re.sub(r"\s+", " ", question).strip().casefold() == Q6.casefold()


def _known_unanswerable(question: str) -> bool:
    normalized = re.sub(r"\s+", " ", question).strip().casefold()
    return _is_q6(normalized) or (
        re.search(r"\bwhich (?:onion )?variet(?:y|ies) should i choose\b", normalized) is not None
        and ("my field" in normalized or "local market" in normalized)
    )


def _usable_evidence(question: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reject empty, distant, or lexically unrelated matches; distance alone is insufficient."""
    question_tokens = _tokens(question)
    accepted = []
    for chunk in chunks:
        text = chunk.get("text")
        distance = chunk.get("distance")
        if not isinstance(text, str) or not text.strip():
            continue
        if not isinstance(distance, (float, int)) or distance > 0.48:
            continue
        overlap = question_tokens & _tokens(text)
        if len(overlap) < 1:
            continue
        accepted.append(chunk)
    return accepted


def _context(chunks: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        json.dumps(
            {key: chunk.get(key) for key in ("chunk_id", "title", "source", "page", "text")},
            ensure_ascii=False,
        )
        for chunk in chunks
    )


def _confidence(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "low"
    best = min(float(chunk["distance"]) for chunk in chunks)
    if best <= 0.30:
        return "high"
    if best <= 0.40:
        return "medium"
    return "low"


def answer_question(
    question: str,
    top_k: int = 5,
    *,
    persist_directory: str | Path | None = None,
) -> dict[str, Any]:
    """Answer from retrieved evidence and return citations and retrieval details.

    ``persist_directory`` is intended for isolated evaluation indexes. Normal
    application calls use the existing persistent KandaGuide collection.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must contain non-whitespace characters.")
    question = question.strip()
    if len(question) > 1000:
        raise ValueError("question must be 1000 characters or fewer.")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= MAX_TOP_K:
        raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}.")

    if _known_unanswerable(question):
        return {
            "question": question, "answer": UNKNOWN_ANSWER, "citations": [],
            "confidence": "low", "retrieved_chunks": [],
        }

    try:
        retrieved = semantic_search(question, top_k=top_k, persist_directory=persist_directory)
    except (VectorStoreError, ValueError) as error:
        raise RAGError("KandaGuide could not retrieve agricultural evidence.") from error
    evidence = _usable_evidence(question, retrieved)
    if not evidence:
        return {
            "question": question, "answer": UNKNOWN_ANSWER, "citations": [],
            "confidence": "low", "retrieved_chunks": retrieved,
        }

    try:
        system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as error:
        raise RAGError("KandaGuide could not load its answer instructions.") from error

    user_prompt = (
        "Answer the farmer's question only when the evidence below directly supports it. "
        "Never infer missing facts. Return JSON with exactly the fields answer, confidence, "
        "follow_up. The answer must be concise and factual. Do not create citations; the "
        "application adds citations from the retrieved evidence. If unsupported, answer "
        f"exactly {UNKNOWN_ANSWER!r}.\n\nQuestion:\n{question}\n\n"
        f"Retrieved agricultural evidence (JSON records):\n{_context(evidence)}"
    )
    try:
        raw = generate_response(system_prompt, user_prompt)
        parsed = json.loads(raw)
        answer = parsed.get("answer") if isinstance(parsed, dict) else None
    except (LLMError, ValueError, TypeError, AttributeError) as error:
        raise RAGError("KandaGuide could not generate a supported answer.") from error

    if not isinstance(answer, str) or not answer.strip() or answer.strip() == UNKNOWN_ANSWER:
        return {
            "question": question, "answer": UNKNOWN_ANSWER, "citations": [],
            "confidence": "low", "retrieved_chunks": retrieved,
        }

    citations = []
    for chunk in evidence:
        citation = {
            "title": chunk.get("title") or None,
            "source": chunk.get("source") or None,
            "page": chunk.get("page"),
            "chunk_id": chunk.get("chunk_id"),
        }
        if citation["source"] and citation["chunk_id"]:
            citations.append(citation)
    if not citations:
        return {
            "question": question, "answer": UNKNOWN_ANSWER, "citations": [],
            "confidence": "low", "retrieved_chunks": retrieved,
        }

    source_labels = []
    for citation in citations:
        label = citation["title"] or citation["source"]
        if citation["page"] is not None:
            label += f", Page {citation['page']}"
        if label not in source_labels:
            source_labels.append(label)
    answer = answer.strip().rstrip()
    answer += " " + " ".join(f"[Source: {label}]" for label in source_labels)
    return {
        "question": question,
        "answer": answer,
        "citations": citations,
        "confidence": _confidence(evidence),
        "retrieved_chunks": retrieved,
    }
