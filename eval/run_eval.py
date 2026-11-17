"""Reproducible, isolated-index evaluation for KandaGuide RAG."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
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


def _percent(numerator: int, denominator: int) -> float | None:
    return round(100 * numerator / denominator, 2) if denominator else None


def _answer_proxy(answer: str, keywords: list[str]) -> bool:
    """Keyword coverage proxy; not a semantic judge or objective ground truth."""
    if not keywords:
        return answer.strip() == UNKNOWN_ANSWER
    lowered = answer.casefold()
    covered = sum(1 for keyword in keywords if keyword.casefold() in lowered)
    return covered / len(keywords) >= 0.6


def _run_configuration(rows: list[dict[str, Any]], name: str, size: int, top_k: int,
                       output_path: Path, provider_ready: bool) -> dict[str, Any]:
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
            try:
                retrieved = semantic_search(
                    row["question"], top_k=top_k, persist_directory=persist
                )
                latencies.append(time.perf_counter() - started)
                retrieval_hit = bool(
                    row["answerable"]
                    and any(chunk.get("source") in row["expected_sources"] for chunk in retrieved)
                )
                record: dict[str, Any] = {
                    "id": row["id"], "question": row["question"],
                    "answerable": row["answerable"],
                    "retrieved_chunks": retrieved,
                    "retrieval_hit": retrieval_hit if row["answerable"] else None,
                    "answer": None, "citations": [], "confidence": None,
                    "answer_correctness_proxy": None,
                    "unsupported_answer": None, "citation_accuracy": None,
                    "execution_error": None,
                }
                if provider_ready or row["id"] in {"Q6", "Q10"}:
                    try:
                        result = answer_question(
                            row["question"], top_k=top_k, persist_directory=persist
                        )
                    except (RAGError, ValueError) as error:
                        record["execution_error"] = type(error).__name__
                        errors.append(f"{row['id']}: {type(error).__name__}")
                    else:
                        record.update({
                            "answer": result["answer"], "citations": result["citations"],
                            "confidence": result["confidence"],
                            "answer_correctness_proxy": (
                                _answer_proxy(result["answer"], row["expected_keywords"])
                                if row["answerable"] else result["answer"] == UNKNOWN_ANSWER
                            ),
                            "unsupported_answer": (
                                result["answer"] != UNKNOWN_ANSWER if not row["answerable"] else None
                            ),
                        })
                        retrieved_by_id = {item.get("chunk_id"): item for item in retrieved}
                        expected_sources = row["expected_sources"]
                        citations = result["citations"]
                        record["citation_accuracy"] = (
                            bool(citations)
                            and all(
                                citation.get("chunk_id") in retrieved_by_id
                                and citation.get("source") == retrieved_by_id[citation.get("chunk_id")].get("source")
                                and citation.get("source") in expected_sources
                                for citation in citations
                            )
                        ) if row["answerable"] and result["answer"] != UNKNOWN_ANSWER else (
                            not citations if not row["answerable"] or result["answer"] == UNKNOWN_ANSWER else False
                        )
                results.append(record)
            except (VectorStoreError, ValueError, RuntimeError) as error:
                latencies.append(time.perf_counter() - started)
                safe_error = type(error).__name__
                errors.append(f"{row['id']}: {safe_error}")
                results.append({
                    "id": row["id"], "question": row["question"],
                    "answerable": row["answerable"], "retrieved_chunks": [],
                    "retrieval_hit": False if row["answerable"] else None,
                    "answer": None, "citations": [], "confidence": None,
                    "answer_correctness_proxy": None, "unsupported_answer": None,
                    "citation_accuracy": None, "execution_error": safe_error,
                })

        answerable_rows = [item for item in results if item["answerable"]]
        unanswerable_rows = [item for item in results if not item["answerable"]]
        has_answers = provider_ready and not errors and all(item["answer"] is not None for item in results)
        q6_answer = next((item["answer"] for item in results if item["id"] == "Q6"), None)
        citation_rows = [item for item in results if item["citation_accuracy"] is not None]
        correctness_rows = [item for item in results if item["answer_correctness_proxy"] is not None]
        metrics = {
            "questions_evaluated": len(rows),
            "answerable_questions": len(answerable_rows),
            "unanswerable_questions": len(unanswerable_rows),
            "retrieval_hit_rate_percent": _percent(
                sum(item["retrieval_hit"] is True for item in answerable_rows), len(answerable_rows)
            ),
            "citation_accuracy_percent": _percent(
                sum(item["citation_accuracy"] is True for item in citation_rows), len(citation_rows)
            ) if has_answers else None,
            "answer_correctness_proxy_percent": _percent(
                sum(item["answer_correctness_proxy"] is True for item in correctness_rows), len(correctness_rows)
            ) if has_answers else None,
            "unsupported_answer_rate_percent": _percent(
                sum(item["unsupported_answer"] is True for item in unanswerable_rows if item["unsupported_answer"] is not None),
                sum(item["unsupported_answer"] is not None for item in unanswerable_rows),
            ),
            "q6_refusal_correct": next(
                (item["answer"] == UNKNOWN_ANSWER for item in results if item["id"] == "Q6"),
                None,
            ) if q6_answer is not None else None,
            "execution_errors": errors,
            "average_retrieval_latency_ms": round(1000 * sum(latencies) / len(latencies), 2) if latencies else None,
            "llm_evaluation_status": (
                "completed" if has_answers else
                "pending: provider credentials/configuration unavailable" if not provider_ready else
                "pending: one or more LLM requests failed"
            ),
            "answer_correctness_method": "Keyword coverage proxy against manually prepared expected_keywords; not an objective or semantic ground-truth judge.",
        }
        payload = {
            "configuration": {"name": name, "chunk_size_words": size, "top_k": top_k,
                              "embedding_model": get_model_name(), "source_documents": [str(path.relative_to(ROOT)) for path in sorted((ROOT / "data" / "raw").glob("*")) if path.suffix.lower() in {".html", ".pdf"}]},
            "metrics": metrics,
            "results": results,
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload
    except (VectorStoreError, OSError, ValueError, RuntimeError) as error:
        error_name = type(error).__name__
        payload = {
            "configuration": {
                "name": name, "chunk_size_words": size, "top_k": top_k,
                "embedding_model": get_model_name(),
                "source_documents": [str(path.relative_to(ROOT)) for path in sorted((ROOT / "data" / "raw").glob("*")) if path.suffix.lower() in {".html", ".pdf"}],
            },
            "metrics": {
                "questions_evaluated": len(rows),
                "answerable_questions": sum(bool(row["answerable"]) for row in rows),
                "unanswerable_questions": sum(not bool(row["answerable"]) for row in rows),
                "retrieval_hit_rate_percent": None,
                "citation_accuracy_percent": None,
                "answer_correctness_proxy_percent": None,
                "unsupported_answer_rate_percent": None,
                "q6_refusal_correct": None,
                "execution_errors": [f"Index preparation failed ({error_name}); see execution environment for the cause."],
                "average_retrieval_latency_ms": None,
                "llm_evaluation_status": "pending: isolated evaluation index could not be prepared",
                "answer_correctness_method": "Keyword coverage proxy against manually prepared expected_keywords; not an objective or semantic ground-truth judge.",
            },
            "results": [{
                "id": row["id"], "question": row["question"],
                "answerable": row["answerable"], "retrieved_chunks": [],
                "retrieval_hit": None, "answer": None, "citations": [],
                "confidence": None, "answer_correctness_proxy": None,
                "unsupported_answer": None, "citation_accuracy": None,
                "execution_error": "isolated index unavailable",
            } for row in rows],
        }
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def _summary(config_a: dict[str, Any], config_b: dict[str, Any], llm_pending: bool) -> str:
    a, b = config_a["metrics"], config_b["metrics"]
    def value(metrics: dict[str, Any], key: str, suffix: str = "%") -> str:
        result = metrics.get(key)
        return "Pending" if result is None else f"{result}{suffix}"

    winner = "Pending actual LLM evaluation" if llm_pending else "Pending review of measured metrics"
    reason = (
        "Retrieval measurements are available, but generated-answer and citation metrics could not be completed because the configured LLM provider was unavailable."
        if llm_pending else
        "The script records reproducible retrieval and answer proxies. Review all measured metrics together before selecting a winner."
    )
    return f"""# RAG evaluation summary

Evaluation date: generated at execution time. The script evaluates each configuration in its own temporary Chroma directory and deletes that directory afterward; the existing persistent collection is untouched.

| Metric | Configuration A | Configuration B |
|---|---:|---:|
| Chunk size | 400 words | 600 words |
| Top-k | 3 | 5 |
| Questions evaluated | {a['questions_evaluated']} | {b['questions_evaluated']} |
| Answerable / unanswerable | {a['answerable_questions']} / {a['unanswerable_questions']} | {b['answerable_questions']} / {b['unanswerable_questions']} |
| Retrieval hit rate | {value(a, 'retrieval_hit_rate_percent')} | {value(b, 'retrieval_hit_rate_percent')} |
| Citation accuracy | {value(a, 'citation_accuracy_percent')} | {value(b, 'citation_accuracy_percent')} |
| Answer correctness proxy | {value(a, 'answer_correctness_proxy_percent')} | {value(b, 'answer_correctness_proxy_percent')} |
| Unsupported-answer rate | {value(a, 'unsupported_answer_rate_percent')} | {value(b, 'unsupported_answer_rate_percent')} |
| Q6 refusal correct | {a['q6_refusal_correct']} | {b['q6_refusal_correct']} |
| Average retrieval latency | {value(a, 'average_retrieval_latency_ms', ' ms')} | {value(b, 'average_retrieval_latency_ms', ' ms')} |
| Execution errors | {len(a['execution_errors'])} | {len(b['execution_errors'])} |

## Winner

**{winner}.** {reason}

The answer-correctness figure is keyword coverage against the dataset's manually written keywords. It is a reproducible screening proxy, not an LLM judge and not objective ground truth. Citation accuracy checks that every citation matches a retrieved chunk and an expected source. Retrieval hit rate checks whether any expected source URL was retrieved for an answerable row. Unsupported-answer rate is the share of unanswerable rows that received anything other than the exact refusal.

See [the evaluation dataset](eval_set.json), [Configuration A results](results_config_a.json), and [Configuration B results](results_config_b.json).
"""


def main() -> int:
    load_dotenv(ROOT / ".env")
    rows = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    if len(rows) != 15 or len({row["question"] for row in rows}) != 15:
        raise ValueError("Evaluation set must contain exactly 15 unique questions.")
    try:
        _provider_config()
        provider_ready = True
    except LLMConfigurationError:
        provider_ready = False
    payloads = [
        _run_configuration(rows, name, size, top_k, path, provider_ready)
        for name, size, top_k, path in CONFIGS
    ]
    llm_pending = any(
        payload["metrics"]["llm_evaluation_status"] != "completed"
        for payload in payloads
    )
    summary = _summary(payloads[0], payloads[1], llm_pending)
    (ROOT / "eval" / "evaluation_summary.md").write_text(summary, encoding="utf-8")
    print("Evaluation outputs written to eval/results_config_a.json, eval/results_config_b.json, and eval/evaluation_summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
