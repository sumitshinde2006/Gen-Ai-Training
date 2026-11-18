"""Offline tests for KandaGuide's deterministic tool and hand-written agent."""

import unittest
from decimal import Decimal

from app.agent_loop import extract_inputs, run_agent
from app.tools import ToolInputError, storage_break_even


class StorageToolTests(unittest.TestCase):
    def calc(self, loss):
        return storage_break_even(100, 2000, 3, loss)

    def test_zero_percent_loss(self):
        result = self.calc(0)
        self.assertEqual(result["break_even_selling_price_per_quintal"], "2000.00")
        self.assertEqual(result["remaining_saleable_quantity_quintals"], "100.00")

    def test_30_percent_loss(self):
        self.assertEqual(self.calc(30)["break_even_selling_price_per_quintal"], "2857.14")

    def test_40_percent_loss(self):
        self.assertEqual(self.calc(40)["break_even_selling_price_per_quintal"], "3333.33")

    def test_variety_specific_loss_is_exact(self):
        result = storage_break_even(10, 2000, 4, Decimal("31.11"))
        self.assertEqual(result["expected_storage_loss_percent"], "31.11")
        self.assertEqual(result["loss_input_status"], "explicit_percentage")

    def test_default_loss_is_a_range_and_unverified(self):
        result = storage_break_even(100, 2000, 3)
        self.assertEqual(result["expected_storage_loss_percent"], {"minimum_percent": "30", "maximum_percent": "40"})
        self.assertEqual(result["break_even_selling_price_per_quintal"], {"minimum": "2857.14", "maximum": "3333.33"})
        self.assertEqual(result["loss_input_status"], "unverified_range")
        self.assertIn("not support", result["loss_provenance"])

    def test_invalid_quantity(self):
        for quantity in (0, -1, "bad", None):
            with self.subTest(quantity=quantity), self.assertRaises(ToolInputError):
                storage_break_even(quantity, 2, 3, 10)

    def test_invalid_price(self):
        for price in (-1, "bad", None):
            with self.subTest(price=price), self.assertRaises(ToolInputError):
                storage_break_even(2, price, 3, 10)

    def test_invalid_duration(self):
        for months in (-1, "bad", None):
            with self.subTest(months=months), self.assertRaises(ToolInputError):
                storage_break_even(2, 10, months, 10)

    def test_invalid_loss(self):
        for loss in (-0.1, 100, "bad"):
            with self.subTest(loss=loss), self.assertRaises(ToolInputError):
                storage_break_even(2, 10, 3, loss)

    def test_decimal_precision_rounding(self):
        result = storage_break_even("1.25", "123.45", "2", "12.5")
        self.assertEqual(result["todays_gross_revenue"], "154.31")
        self.assertEqual(result["break_even_selling_price_per_quintal"], "141.09")

    def test_negative_price_and_duration_rejected(self):
        with self.assertRaises(ToolInputError):
            storage_break_even(1, -1, 1, 10)
        with self.assertRaises(ToolInputError):
            storage_break_even(1, 1, -1, 10)


class HandWrittenAgentTests(unittest.TestCase):
    @staticmethod
    def fake_rag(question):
        return {"answer": "Supported onion storage fact. [Source: example]", "citations": [{"source": "example"}]}

    def test_rag_only(self):
        result = run_agent("What storage information is available?", rag_fn=self.fake_rag)
        self.assertEqual(result["tools_used"], ["rag"])
        self.assertEqual(len(result["citations"]), 1)

    def test_calculation_only(self):
        result = run_agent("Calculate break-even: 100 quintals, today's price is 2000 per quintal, 3 months, 30% loss.")
        self.assertEqual(result["tools_used"], ["storage_break_even"])
        self.assertEqual(result["calculation_result"]["break_even_selling_price_per_quintal"], "2857.14")

    def test_combined_request(self):
        result = run_agent("What storage risks are documented and calculate break-even for 100 quintals at today's price 2000 per quintal for 3 months with 30% loss.", rag_fn=self.fake_rag)
        self.assertEqual(set(result["tools_used"]), {"rag", "storage_break_even"})
        self.assertTrue(result["calculation_result"])
        self.assertTrue(result["citations"])

    def test_verified_variety_percentage_used_at_recorded_duration(self):
        result = run_agent("Calculate break-even for 100 quintals at today's price 2000 per quintal for 4 months for Bhima Prasanskaran.", rag_fn=self.fake_rag)
        self.assertEqual(result["calculation_result"]["expected_storage_loss_percent"], "31.11")
        self.assertEqual(result["calculation_result"]["loss_input_status"], "variety_specific_record")
        self.assertTrue(any("Bhima Prasanskaran" in citation["title"] for citation in result["citations"]))

    def test_missing_inputs_prompt(self):
        result = run_agent("Calculate break-even for 100 quintals")
        self.assertIsNone(result["calculation_result"])
        self.assertIn("missing_inputs", result["follow_up"])

    def test_invalid_inputs(self):
        result = run_agent("Calculate break-even for 0 quintals at price 2000 per quintal for 3 months with 10% loss.")
        self.assertIsNone(result["calculation_result"])
        self.assertIn("greater than zero", result["answer"])

    def test_tool_selection_and_history(self):
        values = extract_inputs("I have 100 quintals. Today's price is 2000 per quintal. Calculate for 3 months with 30% loss.")
        self.assertEqual(values["quantity_quintals"], "100")
        self.assertEqual(values["todays_price_per_quintal"], "2000")
        self.assertEqual(values["months_of_storage"], "3")
        result = run_agent("Calculate break-even for 3 months with 30% loss", history=["I have 100 quintals", "Today's price is 2000 per quintal"])
        self.assertIsNotNone(result["calculation_result"])

    def test_maximum_steps_enforced(self):
        result = run_agent("hello", max_steps=MAX_STEPS + 1)
        self.assertIn("max_steps", result["answer"])


MAX_STEPS = 3


class AgentApiValidationTests(unittest.TestCase):
    def test_agent_request_validation(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        invalid_requests = [
            {"message": "hi", "thread_id": "bad thread", "approval": None},
            {"message": "hi", "thread_id": "ok", "approval": "maybe"},
            {"message": "x" * 1001, "thread_id": "ok", "approval": None},
        ]
        for payload in invalid_requests:
            with self.subTest(payload=payload):
                self.assertEqual(client.post("/agent", json=payload).status_code, 422)

    def test_existing_ask_route_remains_available(self):
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)
        with patch("app.main.answer_question", return_value={"answer": "Fixture answer", "citations": [], "retrieved_chunks": []}):
            response = client.post("/ask", json={"question": "Tell me about onion storage"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Fixture answer")


if __name__ == "__main__":
    unittest.main()
