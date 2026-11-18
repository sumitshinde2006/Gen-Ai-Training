"""Reproducible, isolated-index evaluation for KandaGuide RAG."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from dotenv import load_dotenv

from app.chunking import chunk_documents
from app.embed import get_model_name
from app.llm import LLMConfigurationError, _provider_config
from app.rag import RAGError, UNKNOWN_ANSWER, answer_question
from app.vectorstore import VectorStoreError, index_chunks, semantic_search

EVAL_SET = ROOT / "eval" / "eval_set.json"
CONFIGS = (
    ("A", 400, 3, ROOT / "eval" / "results_config_a.json"),
    ("B", 600, 5, ROOT / "eval" / "results_config_b.json"),
)
ANSWER_CORRECTNESS_METHOD = (
    "For answerable questions, at least 60% of manually prepared expected_keywords "
    "must occur in the answer. For unanswerable questions, the exact response "
    f"{UNKNOWN_ANSWER!r} is required. This transparent keyword/refusal proxy is not a semantic judge."
)
CONTEXT_SUPPORT_METHOD = (
    "For answerable questions, at least 60% of expected_keywords must occur in the "
    "retrieved chunk text. A grounded answer additionally must pass answer correctness "
    "and citation correctness. This is a reproducible support proxy, not claim-level entailment."
)
WINNER_METHOD = (
    "Both configurations must complete all 15 answer evaluations without errors. "
    "The primary quality score is the unweighted mean of answer correctness, citation "
    "correctness, grounded answers, and correct abstention. Retrieval hit rate is the "
    "first tie-breaker; lower unsupported-answer rate is the second. If all are tied, "
    "report a tie."
)
SETUP_INSTRUCTION = (
    "Answer evaluation requires a configured Groq key. Set GROQ_API_KEY in .env or "
    "the environment and set LLM_PROVIDER=groq, then rerun `python eval/run_eval.py`. "
    "This evaluator does not switch to Gemini or another provider."
)


def _percent(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 2) if denominator else None


def _answer_proxy(answer: str, keywords: list[str], answerable: bool = True) -> bool:
    """Score expected-keyword coverage, or exact abstention for unanswerables."""
    if not answerable:
        return answer.strip() == UNKNOWN_ANSWER
    if not keywords:
        return False
    lowered = answer.casefold()
    covered = sum(1 for keyword in keywords if keyword.casefold() in lowered)
    return covered / len(keywords) >= 0.6


def _context_support_proxy(chunks: list[dict[str, Any]], keywords: list[str]) -> bool:
    if not keywords:
        return False
    context = "\n".join(str(chunk.get("text", "")) for chunk in chunks).casefold()
    covered = sum(1 for keyword in keywords if keyword.casefold() in context)
    return covered / len(keywords) >= 0.6


def _citation_correct(citations: list[dict[str, Any]], retrieved: list[dict[str, Any]],
                      expected_sources: list[str]) -> bool:
    if not citations:
        return False
    retrieved_by_id = {item.get("chunk_id"): item for item in retrieved}
    return all(
        citation.get("chunk_id") in retrieved_by_id
        and citation.get("source") == retrieved_by_id[citation.get("chunk_id")].get("source")
        and citation.get("source") in expected_sources
        for citation in citations
    )


def _source_documents() -> list[str]:
    return [
        str(path.relative_to(ROOT))
        for path in sorted((ROOT / "data" / "raw").glob("*"))
        if path.suffix.lower() in {".html", ".pdf"}
    ]


def _exception_types(error: BaseException) -> list[str]:
    chain = []
    current: BaseException | None = error
    while current is not None and len(chain) < 5:
        chain.append(type(current).__name__)
        current = current.__cause__
    return chain


def _empty_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "question": row["question"],
        "expected_answer": row["expected_answer"],
        "answerable": row["answerable"], "retrieved_chunks": [],
        "retrieval_hit": False if row["answerable"] else None,
        "answer": None, "citations": [], "confidence": None,
        "answer_correctness": None, "answer_correctness_proxy": None,
        "citation_correctness": None,
        "supported_by_retrieved_context": None,
        "grounded_answer": None, "correct_abstention": None,
        "unsupported_answer": None,
        "evaluation_status": "pending", "execution_error": None,
        "execution_error_chain": [],
    }


def _score_answer(record: dict[str, Any], row: dict[str, Any], result: dict[str, Any]) -> None:
    answer = result.get("answer")
    citations = result.get("citations") or []
    retrieved = record["retrieved_chunks"]
    correct = _answer_proxy(answer or "", row["expected_keywords"], row["answerable"])
    citation_correct = (
        not citations
        if not row["answerable"] and answer == UNKNOWN_ANSWER
        else _citation_correct(citations, retrieved, row["expected_sources"])
    )
    context_support = (
        _context_support_proxy(retrieved, row["expected_keywords"])
        if row["answerable"] else None
    )
    correct_abstention = (
        answer == UNKNOWN_ANSWER if not row["answerable"] else None
    )
    record.update({
        "answer": answer,
        "citations": citations,
        "confidence": result.get("confidence"),
        "answer_correctness": correct,
        "answer_correctness_proxy": correct,
        "citation_correctness": citation_correct,
        "supported_by_retrieved_context": context_support,
        "grounded_answer": bool(
            row["answerable"] and answer != UNKNOWN_ANSWER and correct
            and citation_correct and context_support
        ),
        "correct_abstention": correct_abstention,
        "unsupported_answer": (
            answer != UNKNOWN_ANSWER if not row["answerable"] else None
        ),
        "evaluation_status": "completed",
    })


def _metrics(rows: list[dict[str, Any]], results: list[dict[str, Any]],
             provider_ready: bool, errors: list[str]) -> dict[str, Any]:
    answerable = [item for item in results if item["answerable"]]
    unanswerable = [item for item in results if not item["answerable"]]
    completed = [item for item in results if item["evaluation_status"] == "completed"]
    completed_answerable = [item for item in completed if item["answerable"]]
    completed_unanswerable = [item for item in completed if not item["answerable"]]
    scored_unanswerable = [item for item in unanswerable if item["evaluation_status"] == "completed"]
    all_answer_evaluated = provider_ready and len(completed) == len(rows) and not errors

    def measured_percent(field: str, denominator: int) -> float | None:
        if not provider_ready:
            return None
        return _percent(sum(item.get(field) is True for item in completed), denominator)

    unsupported_values = [item for item in scored_unanswerable if item["unsupported_answer"] is not None]
    metrics = {
        "questions_evaluated": len(rows),
        "answerable_questions": len(answerable),
        "unanswerable_questions": len(unanswerable),
        "retrieval_hit_rate_percent": _percent(
            sum(item["retrieval_hit"] is True for item in answerable), len(answerable)
        ),
        "answer_correctness_percent": measured_percent("answer_correctness", len(completed)),
        "answer_correctness_proxy_percent": measured_percent("answer_correctness", len(completed)),
        "answer_correctness_scored": len(completed),
        "answer_correctness_correct": sum(item.get("answer_correctness") is True for item in completed),
        "citation_correctness_percent": measured_percent("citation_correctness", len(completed)),
        "citation_accuracy_percent": measured_percent("citation_correctness", len(completed)),
        "citation_correctness_scored": len(completed),
        "citation_correctness_correct": sum(item.get("citation_correctness") is True for item in completed),
        "grounded_answer_percent": _percent(
            sum(item["grounded_answer"] is True for item in completed_answerable),
            len(completed_answerable),
        ) if provider_ready else None,
        "grounded_answer_scored": len(completed_answerable) if provider_ready else 0,
        "grounded_answer_correct": sum(item["grounded_answer"] is True for item in completed_answerable),
        "correct_abstention_percent": _percent(
            sum(item["correct_abstention"] is True for item in completed_unanswerable),
            len(completed_unanswerable),
        ) if provider_ready else None,
        "correct_abstention_scored": len(completed_unanswerable) if provider_ready else 0,
        "correct_abstention_correct": sum(item["correct_abstention"] is True for item in completed_unanswerable),
        "unsupported_answer_rate_percent": _percent(
            sum(item["unsupported_answer"] is True for item in unsupported_values),
            len(unsupported_values),
        ) if provider_ready else None,
        "q6_refusal_correct": next((item["correct_abstention"] for item in results if item["id"] == "Q6"), None),
        "answer_evaluations_completed": len(completed),
        "groq_answer_calls_completed": len(completed_answerable),
        "groq_answer_calls_failed": sum(item["evaluation_status"] == "failed" and item["answerable"] for item in results) if provider_ready else 0,
        "answer_evaluations_skipped": sum(item["evaluation_status"] == "skipped" for item in results),
        "answer_evaluations_failed": sum(item["evaluation_status"] == "failed" for item in results),
        "execution_errors": errors,
        "average_retrieval_latency_ms": None,
        "llm_evaluation_status": (
            "completed" if all_answer_evaluated else
            "incomplete: one or more answer evaluations failed" if provider_ready else
            "pending: Groq provider or credentials unavailable"
        ),
        "answer_correctness_method": ANSWER_CORRECTNESS_METHOD,
        "citation_correctness_method": (
            "A response passes if every emitted citation's chunk ID exists in the retrieved chunks, "
            "its source matches that chunk, and the source is listed in expected_sources. An abstention "
            "with no citations is not treated as a correct citation for an answerable question."
        ),
        "grounded_answer_method": CONTEXT_SUPPORT_METHOD,
        "winner_method": WINNER_METHOD,
    }
    return metrics


def _run_configuration(rows: list[dict[str, Any]], name: str, size: int, top_k: int,
                       output_paths: tuple[Path, ...], provider_ready: bool,
                       timestamp: str) -> dict[str, Any]:
    temp_root = Path(tempfile.mkdtemp(prefix=f"kandaguide_eval_{name.lower()}_"))
    persist = temp_root / "chroma"
    results: list[dict[str, Any]] = []
    latencies: list[float] = []
    errors: list[str] = []
    try:
        chunks = chunk_documents(chunk_size=size)
        if not chunks:
            raise RuntimeError("No supported agricultural source chunks were found.")
        index_chunks(chunks, persist_directory=persist)

        for row in rows:
            started = time.perf_counter()
            record = _empty_record(row)
            try:
                retrieved = semantic_search(row["question"], top_k=top_k, persist_directory=persist)
                latencies.append(time.perf_counter() - started)
                record["retrieved_chunks"] = retrieved
                record["retrieval_hit"] = bool(
                    row["answerable"]
                    and any(chunk.get("source") in row["expected_sources"] for chunk in retrieved)
                ) if row["answerable"] else None

                if not provider_ready:
                    record["evaluation_status"] = "skipped"
                    record["execution_error"] = "Groq credentials/provider unavailable; answer evaluation skipped."
                else:
                    try:
                        result = answer_question(row["question"], top_k=top_k, persist_directory=persist)
                    except (RAGError, ValueError) as error:
                        record["evaluation_status"] = "failed"
                        record["execution_error"] = type(error).__name__
                        record["execution_error_chain"] = _exception_types(error)
                        errors.append(f"{row['id']}: {' -> '.join(record['execution_error_chain'])}")
                    else:
                        _score_answer(record, row, result)
            except (VectorStoreError, ValueError, RuntimeError) as error:
                latencies.append(time.perf_counter() - started)
                error_type = type(error).__name__
                errors.append(f"{row['id']}: {error_type}")
                record["evaluation_status"] = "failed" if provider_ready else "skipped"
                record["execution_error"] = error_type
                record["execution_error_chain"] = _exception_types(error)
            results.append(record)

        metrics = _metrics(rows, results, provider_ready, errors)
        metrics["average_retrieval_latency_ms"] = (
            round(1000 * sum(latencies) / len(latencies), 2) if latencies else None
        )
        payload = {
            "evaluation_timestamp_utc": timestamp,
            "configuration": {
                "name": name, "chunk_size_words": size, "top_k": top_k,
                "embedding_model": get_model_name(), "source_documents": _source_documents(),
                "llm_provider": "groq" if provider_ready else None,
            },
            "metrics": metrics,
            "results": results,
        }
    except (VectorStoreError, OSError, ValueError, RuntimeError) as error:
        error_type = type(error).__name__
        metrics = {
            "questions_evaluated": len(rows),
            "answerable_questions": sum(bool(row["answerable"]) for row in rows),
            "unanswerable_questions": sum(not bool(row["answerable"]) for row in rows),
            "retrieval_hit_rate_percent": None,
            "answer_correctness_percent": None,
            "answer_correctness_proxy_percent": None,
            "answer_correctness_scored": 0,
            "answer_correctness_correct": 0,
            "citation_correctness_percent": None,
            "citation_accuracy_percent": None,
            "citation_correctness_scored": 0,
            "citation_correctness_correct": 0,
            "grounded_answer_percent": None,
            "grounded_answer_scored": 0,
            "grounded_answer_correct": 0,
            "correct_abstention_percent": None,
            "correct_abstention_scored": 0,
            "correct_abstention_correct": 0,
            "unsupported_answer_rate_percent": None,
            "q6_refusal_correct": None,
            "answer_evaluations_completed": 0,
            "groq_answer_calls_completed": 0,
            "groq_answer_calls_failed": len(rows) if provider_ready else 0,
            "answer_evaluations_skipped": len(rows) if not provider_ready else 0,
            "answer_evaluations_failed": len(rows) if provider_ready else 0,
            "execution_errors": [f"Index preparation failed ({error_type})."],
            "average_retrieval_latency_ms": None,
            "llm_evaluation_status": "incomplete: isolated evaluation index could not be prepared",
            "answer_correctness_method": ANSWER_CORRECTNESS_METHOD,
            "citation_correctness_method": "Citation correctness could not be evaluated because the isolated index failed.",
            "grounded_answer_method": CONTEXT_SUPPORT_METHOD,
            "winner_method": WINNER_METHOD,
        }
        payload = {
            "evaluation_timestamp_utc": timestamp,
            "configuration": {
                "name": name, "chunk_size_words": size, "top_k": top_k,
                "embedding_model": get_model_name(), "source_documents": _source_documents(),
                "llm_provider": "groq" if provider_ready else None,
            },
            "metrics": metrics,
            "results": [
                {
                    **_empty_record(row),
                    "evaluation_status": "failed" if provider_ready else "skipped",
                    "execution_error": "isolated index unavailable",
                }
                for row in rows
            ],
        }
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    for output_path in output_paths:
        output_path.write_text(serialized, encoding="utf-8")
    return payload


def _quality_score(metrics: dict[str, Any]) -> float:
    keys = (
        "answer_correctness_percent", "citation_correctness_percent",
        "grounded_answer_percent", "correct_abstention_percent",
    )
    return round(sum(float(metrics[key]) for key in keys) / len(keys), 2)


def _choose_winner(a: dict[str, Any], b: dict[str, Any], llm_pending: bool) -> tuple[str, str]:
    if llm_pending:
        return "Pending", "At least one configuration did not complete all 15 Groq answer evaluations without errors."
    am, bm = a["metrics"], b["metrics"]
    aq, bq = _quality_score(am), _quality_score(bm)
    if aq != bq:
        winner = "Configuration A" if aq > bq else "Configuration B"
        return winner, f"It had the higher primary quality score ({aq:.2f}% vs. {bq:.2f}%)."
    ar, br = am["retrieval_hit_rate_percent"], bm["retrieval_hit_rate_percent"]
    if ar != br:
        winner = "Configuration A" if ar > br else "Configuration B"
        return winner, f"Primary quality scores tied at {aq:.2f}%; it had the higher retrieval hit rate ({ar}% vs. {br}%)."
    au, bu = am["unsupported_answer_rate_percent"], bm["unsupported_answer_rate_percent"]
    if au != bu:
        winner = "Configuration A" if au < bu else "Configuration B"
        return winner, f"Primary quality and retrieval scores tied; it had the lower unsupported-answer rate ({min(au, bu)}%)."
    return "Tie", f"Both configurations tied on the primary quality score ({aq:.2f}%), retrieval hit rate ({ar}%), and unsupported-answer rate ({au}%)."


def _summary(config_a: dict[str, Any], config_b: dict[str, Any], timestamp: str,
             llm_pending: bool) -> str:
    a, b = config_a["metrics"], config_b["metrics"]
    def value(metrics: dict[str, Any], key: str, suffix: str = "%") -> str:
        result = metrics.get(key)
        return "Pending" if result is None else f"{result}{suffix}"
    winner, reason = _choose_winner(config_a, config_b, llm_pending)

    def failed_items(payload: dict[str, Any]) -> str:
        failed = [
            f"{item['id']} ({' -> '.join(item.get('execution_error_chain') or [item.get('execution_error') or 'error'])})"
            for item in payload["results"] if item["evaluation_status"] == "failed"
        ]
        skipped = [item["id"] for item in payload["results"] if item["evaluation_status"] == "skipped"]
        parts = []
        if failed:
            parts.append("failed: " + ", ".join(failed))
        if skipped:
            parts.append("skipped: " + ", ".join(skipped))
        return "; ".join(parts) or "None"

    return f"""# RAG evaluation summary

Evaluation timestamp (UTC): {timestamp}. Both configurations use isolated temporary Chroma indexes; the existing persistent collection is untouched. The evaluation set contains the original 15 questions.

| Metric | Configuration A | Configuration B |
|---|---:|---:|
| Chunk size | 400 words | 600 words |
| Top-k | 3 | 5 |
| Questions | {a['questions_evaluated']} | {b['questions_evaluated']} |
| Retrieval hit rate | {value(a, 'retrieval_hit_rate_percent')} | {value(b, 'retrieval_hit_rate_percent')} |
| Answer correctness (scored responses) | {value(a, 'answer_correctness_percent')} ({a['answer_correctness_correct']}/{a['answer_correctness_scored']}) | {value(b, 'answer_correctness_percent')} ({b['answer_correctness_correct']}/{b['answer_correctness_scored']}) |
| Citation correctness (scored responses) | {value(a, 'citation_correctness_percent')} ({a['citation_correctness_correct']}/{a['citation_correctness_scored']}) | {value(b, 'citation_correctness_percent')} ({b['citation_correctness_correct']}/{b['citation_correctness_scored']}) |
| Grounded answer rate (successful answerable responses) | {value(a, 'grounded_answer_percent')} ({a['grounded_answer_correct']}/{a['grounded_answer_scored']}) | {value(b, 'grounded_answer_percent')} ({b['grounded_answer_correct']}/{b['grounded_answer_scored']}) |
| Correct abstention rate (successful unanswerable responses) | {value(a, 'correct_abstention_percent')} ({a['correct_abstention_correct']}/{a['correct_abstention_scored']}) | {value(b, 'correct_abstention_percent')} ({b['correct_abstention_correct']}/{b['correct_abstention_scored']}) |
| Unsupported-answer rate (unanswerable questions) | {value(a, 'unsupported_answer_rate_percent')} | {value(b, 'unsupported_answer_rate_percent')} |
| Groq answer calls completed / failed | {a['groq_answer_calls_completed']} / {a['groq_answer_calls_failed']} | {b['groq_answer_calls_completed']} / {b['groq_answer_calls_failed']} |
| All answer evaluations completed / failed / skipped | {a['answer_evaluations_completed']} / {a['answer_evaluations_failed']} / {a['answer_evaluations_skipped']} | {b['answer_evaluations_completed']} / {b['answer_evaluations_failed']} / {b['answer_evaluations_skipped']} |
| Q6 exact refusal | {a['q6_refusal_correct']} | {b['q6_refusal_correct']} |
| Mean retrieval latency | {value(a, 'average_retrieval_latency_ms', ' ms')} | {value(b, 'average_retrieval_latency_ms', ' ms')} |
| Failed or skipped questions | {failed_items(config_a)} | {failed_items(config_b)} |

## Winner

**{winner}.** {reason}

## Scoring and comparison method

- **Retrieval hit:** at least one retrieved chunk has a URL in that question's `expected_sources`; denominator is all 13 answerable questions.
- **Answer correctness:** for answerable questions, at least 60% of manually prepared `expected_keywords` appear in the answer; for the two unanswerable questions, only the exact `{UNKNOWN_ANSWER}` is correct. This is a transparent keyword/refusal proxy, not semantic ground truth.
- **Citation correctness:** every citation must reference a retrieved chunk ID, match that chunk's source, and use an expected source. Missing citations fail the citation check.
- **Supported by retrieved context:** at least 60% of expected keywords occur in retrieved chunk text. A grounded answer must also pass answer correctness and citation correctness. This is not claim-level entailment.
- **Correct abstention:** exact `{UNKNOWN_ANSWER}` for each unanswerable question, denominator 2. Failed calls do not count as correct.
- **Winner:** both runs must complete all 15 answer evaluations without errors. Then compare the unweighted mean of answer correctness, citation correctness, grounded answers, and correct abstention. Retrieval hit rate breaks a primary-score tie; lower unsupported-answer rate breaks the next tie. If all tie, report a tie.

Errors and exception type chains are recorded per question in the JSON results. Failed calls are excluded from answer metric denominators and cannot count as successful answers; the completed/failed counts show coverage. Retrieval-only runs leave answer metrics pending and do not select a winner.

See [the evaluation dataset](eval_set.json), [Configuration A results](results_config_a.json), and [Configuration B results](results_config_b.json).
"""


def _groq_status() -> tuple[bool, str | None]:
    """Confirm the configured provider is Groq without exposing its key."""
    configured_provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    if configured_provider != "groq":
        return False, "LLM_PROVIDER is not set to groq. " + SETUP_INSTRUCTION
    try:
        provider, _, _ = _provider_config()
    except LLMConfigurationError:
        return False, SETUP_INSTRUCTION
    if provider != "groq":
        return False, "Groq provider verification failed. " + SETUP_INSTRUCTION
    return True, None


def main() -> int:
    load_dotenv(ROOT / ".env")
    rows = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    if len(rows) != 15 or len({row["question"] for row in rows}) != 15:
        raise ValueError("Evaluation set must contain exactly 15 unique questions.")

    provider_ready, setup_message = _groq_status()
    if provider_ready:
        print("Groq answer evaluation enabled; credentials detected (key hidden).")
    else:
        print(setup_message)
        print("Continuing with retrieval-only scoring; answer metrics will remain pending.")

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payloads = [
        _run_configuration(
            rows, name, size, top_k, (output_path,), provider_ready, timestamp
        )
        for name, size, top_k, output_path in CONFIGS
    ]
    llm_pending = any(payload["metrics"]["llm_evaluation_status"] != "completed" for payload in payloads)
    summary = _summary(payloads[0], payloads[1], timestamp, llm_pending)
    (ROOT / "eval" / "evaluation_summary.md").write_text(summary, encoding="utf-8")
    print("Evaluation outputs written to eval/results_config_a.json, eval/results_config_b.json, and eval/evaluation_summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
