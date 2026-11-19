"""Offline scorer/evaluator tests; no live provider calls are made."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.rag import RAGError
from eval import run_eval


def row(answerable=True):
    return {
        "id": "QX",
        "question": "What alpha beta?",
        "expected_answer": "Fixture expected answer",
        "expected_sources": ["source-a"],
        "expected_keywords": ["alpha", "beta"],
        "answerable": answerable,
    }


class EvaluationScoringTests(unittest.TestCase):
    def test_answer_and_context_keyword_scoring(self):
        self.assertTrue(run_eval._answer_proxy("alpha beta result", ["alpha", "beta"]))
        self.assertFalse(run_eval._answer_proxy("alpha only", ["alpha", "beta"]))
        self.assertTrue(run_eval._answer_proxy("I don't know.", [], answerable=False))
        self.assertFalse(run_eval._answer_proxy("unsupported", [], answerable=False))
        self.assertTrue(run_eval._context_support_proxy([{"text": "alpha beta context"}], ["alpha", "beta"]))

    def test_answerable_abstention_does_not_pass_citation_scoring_without_a_citation(self):
        record = run_eval._empty_record(row())
        record["retrieved_chunks"] = [{"chunk_id": "chunk-1", "source": "source-a", "text": "alpha beta"}]
        run_eval._score_answer(record, row(), {
            "answer": "I don't know.", "citations": [], "confidence": "low",
        })
        self.assertFalse(record["citation_correctness"])
        self.assertFalse(record["answer_correctness"])

    def test_completed_results_are_scored_and_timestamped(self):
        retrieved = [{"chunk_id": "chunk-1", "source": "source-a", "text": "alpha beta facts", "distance": 0.1}]
        answer = {
            "answer": "Alpha beta facts [Source: source-a]",
            "citations": [{"chunk_id": "chunk-1", "source": "source-a"}],
            "confidence": "high",
            "retrieved_chunks": retrieved,
        }
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "result.json"
            with patch.object(run_eval, "chunk_documents", return_value=[{}]), \
                 patch.object(run_eval, "index_chunks"), \
                 patch.object(run_eval, "semantic_search", return_value=retrieved), \
                 patch.object(run_eval, "answer_question", return_value=answer), \
                 patch.object(run_eval, "get_model_name", return_value="fixture-model"):
                payload = run_eval._run_configuration([row()], "A", 400, 3, (out,), True, "2026-01-01T00:00:00+00:00")
            self.assertEqual(payload["metrics"]["answer_correctness_percent"], 100.0)
            self.assertEqual(payload["metrics"]["citation_correctness_percent"], 100.0)
            self.assertEqual(payload["metrics"]["grounded_answer_percent"], 100.0)
            self.assertEqual(payload["results"][0]["evaluation_status"], "completed")
            self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["evaluation_timestamp_utc"], "2026-01-01T00:00:00+00:00")

    def test_missing_groq_skips_answers_without_calling_rag(self):
        retrieved = [{"chunk_id": "chunk-1", "source": "source-a", "text": "alpha beta facts", "distance": 0.1}]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(run_eval, "chunk_documents", return_value=[{}]), \
                 patch.object(run_eval, "index_chunks"), \
                 patch.object(run_eval, "semantic_search", return_value=retrieved), \
                 patch.object(run_eval, "answer_question") as answer_question, \
                 patch.object(run_eval, "get_model_name", return_value="fixture-model"):
                payload = run_eval._run_configuration([row()], "A", 400, 3, (Path(directory) / "result.json",), False, "now")
            answer_question.assert_not_called()
            self.assertIsNone(payload["metrics"]["answer_correctness_percent"])
            self.assertEqual(payload["results"][0]["evaluation_status"], "skipped")
            self.assertTrue(payload["results"][0]["retrieval_hit"])

    def test_failed_groq_answer_is_not_scored_as_success(self):
        retrieved = [{"chunk_id": "chunk-1", "source": "source-a", "text": "alpha beta facts", "distance": 0.1}]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(run_eval, "chunk_documents", return_value=[{}]), \
                 patch.object(run_eval, "index_chunks"), \
                 patch.object(run_eval, "semantic_search", return_value=retrieved), \
                 patch.object(run_eval, "answer_question", side_effect=RAGError("fixture error")), \
                 patch.object(run_eval, "get_model_name", return_value="fixture-model"):
                payload = run_eval._run_configuration([row()], "A", 400, 3, (Path(directory) / "result.json",), True, "now")
            self.assertIsNone(payload["metrics"]["answer_correctness_percent"])
            self.assertEqual(payload["metrics"]["answer_evaluations_failed"], 1)
            self.assertEqual(payload["results"][0]["evaluation_status"], "failed")

    def test_partial_api_failures_leave_aggregate_quality_pending(self):
        answerable = row()
        unanswerable = row(answerable=False)
        completed = run_eval._empty_record(unanswerable)
        run_eval._score_answer(completed, unanswerable, {
            "answer": "I don't know.", "citations": [], "confidence": "low",
        })
        failed = run_eval._empty_record(answerable)
        failed["evaluation_status"] = "failed"
        metrics = run_eval._metrics(
            [answerable, unanswerable], [completed, failed], True, ["QX: LLMProviderError"]
        )
        self.assertIsNone(metrics["answer_correctness_percent"])
        self.assertIsNone(metrics["citation_correctness_percent"])
        self.assertIsNone(metrics["grounded_answer_percent"])
        self.assertEqual(metrics["correct_abstention_percent"], 100.0)

    def test_groq_provider_is_required(self):
        with patch.dict("os.environ", {"LLM_PROVIDER": "gemini"}, clear=False):
            ready, message = run_eval._groq_status()
        self.assertFalse(ready)
        self.assertIn("LLM_PROVIDER=groq", message)

    def test_missing_groq_key_returns_setup_instruction(self):
        with patch.dict("os.environ", {"LLM_PROVIDER": "groq", "GROQ_API_KEY": ""}, clear=False):
            ready, message = run_eval._groq_status()
        self.assertFalse(ready)
        self.assertIn("GROQ_API_KEY", message)
        self.assertIn("python eval/run_eval.py", message)

    def test_winner_requires_complete_evaluation_and_uses_quality_first(self):
        def payload(answer, retrieval):
            return {"metrics": {
                "answer_correctness_percent": answer,
                "citation_correctness_percent": answer,
                "grounded_answer_percent": answer,
                "correct_abstention_percent": answer,
                "retrieval_hit_rate_percent": retrieval,
                "unsupported_answer_rate_percent": 0.0,
            }}
        a, b = payload(90, 80), payload(80, 100)
        self.assertEqual(run_eval._choose_winner(a, b, False)[0], "Configuration A")
        self.assertEqual(run_eval._choose_winner(a, b, True)[0], "Pending")


if __name__ == "__main__":
    unittest.main()
