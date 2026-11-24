"""LangGraph workflow tests; skipped until the optional package is installed."""

import unittest

try:
    import langgraph  # noqa: F401
except ImportError:
    LANGGRAPH_AVAILABLE = False
else:
    LANGGRAPH_AVAILABLE = True


@unittest.skipUnless(LANGGRAPH_AVAILABLE, "install LangGraph from requirements.txt")
class LangGraphWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.graph import build_graph
        cls.build_graph = staticmethod(build_graph)

    @staticmethod
    def fake_rag(question):
        return {"answer": "Evidence-backed answer [Source: fixture]", "citations": [{"source": "fixture", "chunk_id": "1"}]}

    def setUp(self):
        self.graph = self.build_graph(rag_fn=self.fake_rag)

    def call(self, thread, message):
        return self.graph.invoke({"message": message, "messages": [message]}, config={"configurable": {"thread_id": thread}})

    def test_graph_compiles_and_rag_path(self):
        result = self.call("rag", "What storage methods are documented?")
        self.assertIn("Evidence-backed", result["answer"])
        self.assertEqual(result["tools_used"], ["rag"])

    def test_combined_rag_and_calculation_path(self):
        message = "What storage methods are documented? Calculate break-even for 100 quintals at price 2000 per quintal for 3 months with 30% loss."
        result = self.call("combined", message)
        self.assertEqual(set(result["tools_used"]), {"rag", "storage_break_even"})
        self.assertTrue(result["citations"])
        self.assertEqual(result["calculation_result"]["break_even_selling_price_per_quintal"], "2857.14")

    def test_calculation_path_and_memory_same_thread(self):
        self.call("calc", "I have 100 quintals")
        self.call("calc", "Today's purchase price is 2000 per quintal")
        result = self.call(
            "calc",
            "Calculate break-even for 3 months with 30% loss using the same quantity "
            "and purchase price as before.",
        )
        self.assertEqual(result["calculation_result"]["break_even_selling_price_per_quintal"], "2857.14")

    def test_new_calculation_does_not_reuse_prior_thread_values(self):
        first = self.call("isolation", "Calculate revenue for 8,000 kg at ₹20/kg.")
        self.assertEqual(first["calculation_result"]["total_revenue"], "160000.00")
        second = self.call(
            "isolation",
            "Calculate profit for 2,000 kg at ₹30/kg with ₹5,000 expenses.",
        )
        self.assertEqual(second["calculation_result"]["quantity_kg"], "2000.00")
        self.assertEqual(second["calculation_result"]["net_profit"], "55000.00")
        self.assertEqual(second["tools_used"], ["profit_calculation"])
        self.assertIsNone(second["follow_up"])

    def test_new_request_does_not_reuse_previous_rag_output(self):
        self.call("fresh-state", "What storage methods are documented?")
        result = self.call(
            "fresh-state",
            "Calculate profit for 2,000 kg at ₹30/kg with ₹5,000 expenses.",
        )
        self.assertNotIn("Evidence-backed", result["answer"])
        self.assertEqual(result["tools_used"], ["profit_calculation"])

    def test_graph_asks_only_for_missing_profit_inputs(self):
        result = self.call("missing-profit-inputs", "Calculate profit for 5,000 kg onions.")
        self.assertEqual(
            result["follow_up"]["missing_inputs"],
            ["selling price", "expenses"],
        )
        self.assertEqual(result["tools_used"], ["profit_calculation"])
        self.assertNotIn("storage", result["answer"].casefold())

    def test_explicit_context_reference_reuses_only_requested_quantity(self):
        self.call("selective-context", "Calculate revenue for 8,000 kg at ₹20/kg.")
        result = self.call(
            "selective-context",
            "Calculate profit using the same quantity as before, at ₹30/kg, "
            "with expenses of ₹5,000.",
        )
        self.assertEqual(result["calculation_result"]["quantity_kg"], "8000.00")
        self.assertEqual(result["calculation_result"]["net_profit"], "235000.00")

    def test_different_threads_do_not_share_memory(self):
        self.call("one", "I have 100 quintals")
        result = self.call("two", "Calculate break-even for 3 months with 30% loss")
        self.assertTrue(result["follow_up"])

    def test_approval_interrupt_resume_and_rejection(self):
        config = {"configurable": {"thread_id": "approval"}}
        result = self.graph.invoke({"message": "I have 100 quintals and price 2000 per quintal; calculate 3 months with 30% loss and recommend whether I should store.", "messages": ["I have 100 quintals and price 2000 per quintal; calculate 3 months with 30% loss and recommend whether I should store."]}, config=config)
        self.assertTrue(result["__interrupt__"])
        self.assertEqual(result["status"], "running")
        resumed = self.graph.invoke(__import__("langgraph.types", fromlist=["Command"]).Command(resume="rejected"), config=config)
        self.assertEqual(resumed["status"], "rejected")
        self.assertIn("not approved", resumed["answer"])

    def test_approval_confirmation(self):
        config = {"configurable": {"thread_id": "approved"}}
        msg = "100 quintals at price 2000 per quintal, calculate 3 months with 30% loss and recommend whether I should store"
        self.graph.invoke({"message": msg, "messages": [msg]}, config=config)
        from langgraph.types import Command
        result = self.graph.invoke(Command(resume="approved"), config=config)
        self.assertEqual(result["status"], "completed")
        self.assertIn("approved", result["answer"])

    def test_agent_api_interrupt_and_resume(self):
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        import app.graph as graph_module
        from app.main import app

        client = TestClient(app)
        message = "100 quintals at price 2000 per quintal, calculate 3 months with 30% loss and recommend whether I should store"
        for decision, expected_status in (("approved", "completed"), ("rejected", "rejected")):
            thread_id = "api-" + decision
            workflow = self.build_graph(rag_fn=self.fake_rag)
            with patch.object(graph_module, "graph", workflow):
                pending = client.post("/agent", json={"message": message, "thread_id": thread_id, "approval": None})
                self.assertEqual(pending.status_code, 200)
                self.assertEqual(pending.json()["status"], "awaiting_approval")
                self.assertTrue(pending.json()["requires_approval"])
                self.assertIsNotNone(pending.json()["calculation_result"])
                resumed = client.post("/agent", json={"message": "resume decision", "thread_id": thread_id, "approval": decision})
                self.assertEqual(resumed.status_code, 200)
                self.assertEqual(resumed.json()["status"], expected_status)

    def test_agent_api_runs_profit_calculation_without_follow_up(self):
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        import app.graph as graph_module
        from app.main import app

        client = TestClient(app)
        workflow = self.build_graph(rag_fn=self.fake_rag)
        message = (
            "Calculate net profit for 6,500 kg onions, with 70% sold at ₹25/kg "
            "and 30% at ₹18/kg, and expenses of ₹20,000."
        )
        with patch.object(graph_module, "graph", workflow):
            response = client.post(
                "/agent",
                json={"message": message, "thread_id": "profit-api-regression"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["calculation_result"]["net_profit"], "128850.00")
        self.assertIsNone(body["follow_up"])
        self.assertEqual(body["tools_used"], ["profit_calculation"])

    def test_planner_handles_unseen_profit_paraphrase_without_llm_arithmetic(self):
        import json
        from unittest.mock import patch
        from app.agent_planner import plan_agent_request

        plan = {
            "intent": "calculation",
            "operation": "profit",
            "arguments": {
                "quantity": {"value": 6500, "unit": "kg"},
                "sales": [
                    {
                        "percentage": 70,
                        "quantity": None,
                        "price": 25,
                        "price_unit": "per_kg",
                    },
                    {
                        "percentage": None,
                        "quantity": None,
                        "price": 18,
                        "price_unit": "per_kg",
                    },
                ],
                "expenses": [{"amount": 20000, "label": "Costs"}],
                "purchase_price": None,
                "months": None,
                "loss_percent": None,
                "values": [],
                "rate": None,
                "base": None,
                "operator": None,
                "operands": [],
            },
            "knowledge_question": None,
            "clarification": None,
        }
        workflow = self.build_graph(
            rag_fn=self.fake_rag,
            planner_fn=plan_agent_request,
        )
        with patch(
            "app.agent_planner.generate_response",
            return_value=json.dumps(plan),
        ) as planner:
            result = workflow.invoke(
                {
                    "message": (
                        "I moved 6,500 kilograms, sold 70% at ₹25/kg and the rest "
                        "at ₹18/kg, and paid ₹20,000 in costs; what do I clear?"
                    ),
                    "messages": [
                        "I moved 6,500 kilograms, sold 70% at ₹25/kg and the rest "
                        "at ₹18/kg, and paid ₹20,000 in costs; what do I clear?"
                    ],
                },
                config={"configurable": {"thread_id": "unseen-profit"}},
            )
        self.assertEqual(result["calculation_result"]["net_profit"], "128850.00")
        planner.assert_called_once()

    def test_mixed_planner_routes_both_rag_and_python_calculation(self):
        import json
        from unittest.mock import patch
        from app.agent_planner import plan_agent_request

        plan = {
            "intent": "mixed",
            "operation": "profit",
            "arguments": {
                "quantity": {"value": 1000, "unit": "kg"},
                "sales": [{
                    "percentage": None,
                    "quantity": None,
                    "price": 20,
                    "price_unit": "per_kg",
                }],
                "expenses": [{"amount": 2000, "label": "Expenses"}],
                "purchase_price": None,
                "months": None,
                "loss_percent": None,
                "values": [],
                "rate": None,
                "base": None,
                "operator": None,
                "operands": [],
            },
            "knowledge_question": "What onion storage practices are documented?",
            "clarification": None,
        }
        workflow = self.build_graph(
            rag_fn=self.fake_rag,
            planner_fn=plan_agent_request,
        )
        with patch("app.agent_planner.generate_response", return_value=json.dumps(plan)):
            result = workflow.invoke(
                {
                    "message": (
                        "What onion storage practices are documented? I have 1,000 kg "
                        "sold at ₹20/kg and expenses of ₹2,000; calculate my profit."
                    ),
                    "messages": [
                        "What onion storage practices are documented? I have 1,000 kg "
                        "sold at ₹20/kg and expenses of ₹2,000; calculate my profit."
                    ],
                },
                config={"configurable": {"thread_id": "mixed-tools"}},
            )
        self.assertIn("Evidence-backed", result["answer"])
        self.assertEqual(result["calculation_result"]["net_profit"], "18000.00")
        self.assertEqual(set(result["tools_used"]), {"rag", "profit_calculation"})

    def test_planner_routes_other_math_intents_to_deterministic_tools(self):
        import json
        from unittest.mock import patch
        from app.agent_planner import plan_agent_request

        cases = (
            (
                "What is 15% of ₹20,000?",
                "percentage",
                {"rate": 15, "base": 20000},
                "percentage_calculation",
                "3000.00",
                "result",
            ),
            (
                "Add ₹2,000 in storage costs and ₹1,500 for transport.",
                "cost_total",
                {"expenses": [
                    {"amount": 2000, "label": "Storage"},
                    {"amount": 1500, "label": "Transport"},
                ]},
                "cost_total",
                "3500.00",
                "total_cost",
            ),
            (
                "Compare ₹25/kg with ₹2,000 per quintal.",
                "price_comparison",
                {"values": [
                    {"value": 25, "unit": "per_kg", "label": "Offer A"},
                    {"value": 2000, "unit": "per_quintal", "label": "Offer B"},
                ]},
                "price_comparison",
                "5.00",
                "difference",
            ),
            (
                "What is 12 multiplied by 8?",
                "arithmetic",
                {"operator": "multiply", "operands": [12, 8]},
                "arithmetic",
                "96.00",
                "result",
            ),
        )
        for index, (message, operation, supplied_arguments, tool, expected, key) in enumerate(cases):
            arguments = {
                "quantity": None,
                "sales": [],
                "expenses": [],
                "purchase_price": None,
                "months": None,
                "loss_percent": None,
                "values": [],
                "rate": None,
                "base": None,
                "operator": None,
                "operands": [],
                **supplied_arguments,
            }
            plan = {
                "intent": "calculation",
                "operation": operation,
                "arguments": arguments,
                "knowledge_question": None,
                "clarification": None,
            }
            workflow = self.build_graph(
                rag_fn=self.fake_rag,
                planner_fn=plan_agent_request,
            )
            with self.subTest(operation=operation), patch(
                "app.agent_planner.generate_response",
                return_value=json.dumps(plan),
            ):
                result = workflow.invoke(
                    {"message": message, "messages": [message]},
                    config={"configurable": {"thread_id": f"math-{index}"}},
                )
            self.assertEqual(result["calculation_result"][key], expected)
            self.assertEqual(result["tools_used"], [tool])


if __name__ == "__main__":
    unittest.main()
