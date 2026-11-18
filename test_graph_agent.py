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
        self.call("calc", "Today's price is 2000 per quintal")
        result = self.call("calc", "Calculate break-even for 3 months with 30% loss")
        self.assertEqual(result["calculation_result"]["break_even_selling_price_per_quintal"], "2857.14")

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


if __name__ == "__main__":
    unittest.main()
