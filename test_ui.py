"""Focused tests for the KandaGuide frontend data and feedback behavior."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from ui import app


class VarietyPickerTests(unittest.TestCase):
    def test_all_seasons_and_crop_filters_use_dataset_values(self):
        records = app.load_varieties()
        kharif = app.filter_varieties(records, "Kharif")
        late = app.filter_varieties(records, "Late Kharif")
        rabi = app.filter_varieties(records, "Rabi")
        self.assertIn("Bhima Dark Red", {row["variety_name"] for row in kharif})
        self.assertIn("Bhima Raj", {row["variety_name"] for row in late})
        self.assertIn("Bhima Omkar", {row["variety_name"] for row in rabi})
        self.assertNotIn("Bhima Shakti", {row["variety_name"] for row in kharif})
        self.assertIn("Bhima Shakti", {row["variety_name"] for row in late})
        garlic = app.filter_varieties(records, "Rabi", "Garlic")
        self.assertTrue(garlic)
        self.assertTrue(all(row["category"] == "garlic" for row in garlic))
        self.assertEqual(app.filter_varieties(records, "Kharif", "Garlic"), [])

    def test_only_explicit_storage_months_are_numeric_and_sorted(self):
        self.assertEqual(app.storage_months({"storage_life": "6-8 months"}), 8)
        self.assertEqual(app.storage_months({"storage_life": "Suitable for storage up to 5-6 months"}), 6)
        self.assertIsNone(app.storage_months({"storage_life": "Excellent storage qualities"}))
        self.assertIsNone(app.storage_months({"storage_life": "31.11% after four months of storage"}))
        raj = next(row for row in app.load_varieties() if row["variety_name"] == "Bhima Raj")
        self.assertIsNone(app.storage_months(raj, "Kharif"))
        self.assertEqual(app.storage_months(raj, "Late Kharif"), 4)
        self.assertEqual(app.storage_months(raj, "Rabi"), 3)
        red = next(row for row in app.load_varieties() if row["variety_name"] == "Bhima Red")
        self.assertIsNone(app.storage_months(red, "Kharif"))
        self.assertEqual(app.storage_months(red, "Late Kharif"), 4)
        self.assertEqual(app.storage_months(red, "Rabi"), 3)
        shubra = next(row for row in app.load_varieties() if row["variety_name"] == "Bhima Shubra")
        self.assertIsNone(app.storage_months(shubra, "Kharif"))
        self.assertEqual(app.storage_months(shubra, "Late Kharif"), 3)
        rows = [
            {"variety_name": "Unknown", "storage_life": "Good keeping quality"},
            {"variety_name": "Short", "storage_life": "Kharif harvest can be stored up to 2 months"},
            {"variety_name": "Long", "storage_life": "6-8 months"},
        ]
        self.assertEqual([row["variety_name"] for row in app.sort_varieties(rows)], ["Long", "Short", "Unknown"])

    def test_maturity_sources_keep_planting_or_sowing_note(self):
        records = app.load_varieties()
        garlic = next(row for row in records if row["variety_name"] == "Bhima Omkar")
        self.assertIsNone(garlic["maturity_days_after_transplanting"])
        self.assertEqual(garlic["maturity_note"], "120-135 days after planting")


class FeedbackTests(unittest.TestCase):
    def test_feedback_persists_and_duplicate_response_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "feedback.sqlite"
            with patch.object(app, "FEEDBACK_DB", database):
                self.assertFalse(app.feedback_saved("response-1"))
                self.assertTrue(app.save_feedback(
                    response_id="response-1", question="Question", answer="Answer",
                    feedback_type="up", comment="Helpful", selected_mode="RAG",
                ))
                self.assertFalse(app.save_feedback(
                    response_id="response-1", question="Question", answer="Answer",
                    feedback_type="down", comment="duplicate", selected_mode="RAG",
                ))
                self.assertTrue(app.feedback_saved("response-1"))
                self.assertTrue(app.save_feedback(
                    response_id="response-2", question="Question 2", answer="Answer 2",
                    feedback_type="down", comment="Needs more detail", selected_mode="Agent",
                ))
            # A second connection sees the stored record, as it will after app restart.
            with patch.object(app, "FEEDBACK_DB", database):
                self.assertTrue(app.feedback_saved("response-1"))


class BackendClientTests(unittest.TestCase):
    def test_rag_and_agent_use_the_existing_api_payloads(self):
        response = Mock()
        citation = {"title": "Source title", "source": "https://example.org/source.pdf", "page": 4}
        response.json.return_value = {"answer": "Supported answer", "citations": [citation]}
        response.raise_for_status.return_value = None
        with patch.object(app.requests, "post", return_value=response) as post:
            result = app._request_answer("Question?", "RAG", "thread-1")
            self.assertEqual(result["citations"], [citation])
            post.assert_called_with(
                "http://127.0.0.1:8000/ask", json={"question": "Question?"}, timeout=app.REQUEST_TIMEOUT
            )
            app._request_answer("Question?", "Agent", "thread-1")
            post.assert_called_with(
                "http://127.0.0.1:8000/agent",
                json={"message": "Question?", "thread_id": "thread-1", "approval": None},
                timeout=app.REQUEST_TIMEOUT,
            )

    def test_backend_connection_errors_are_friendly(self):
        with patch.object(app.requests, "get", side_effect=app.requests.ConnectionError("offline")):
            healthy, agent, detail = app.check_backend()
        self.assertFalse(healthy)
        self.assertFalse(agent)
        self.assertIn("Backend unavailable", detail)


if __name__ == "__main__":
    unittest.main()
