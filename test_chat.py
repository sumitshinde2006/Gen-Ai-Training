import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.llm import LLMConfigurationError, LLMProviderError, generate_response
from app.main import app, load_chat_prompts


client = TestClient(app)
RECORD = {
    "variety_name": "Bhima Kiran",
    "category": "onion",
    "season": "Rabi",
    "maturity_days_after_transplanting": "125-135 days after transplanting",
    "yield_t_ha": "28-32t/ha",
    "storage_life": "Suitable for storage up to 5-6 months",
    "source_url": "https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit",
    "similarity_score": 0.5,
}


class ChatEndpointTests(unittest.TestCase):
    def test_existing_endpoints_and_app_start(self):
        self.assertEqual(client.get("/health").status_code, 200)
        self.assertEqual(client.get("/records").status_code, 200)
        self.assertEqual(client.get("/search", params={"q": "Bhima"}).status_code, 200)

    def test_chat_returns_exact_response_fields_and_source_context(self):
        generated = {
            "answer": "Bhima Kiran is listed for Rabi and stores up to 5-6 months.",
            "confidence": "medium",
            "follow_up": "Would you like to compare another recorded variety?",
        }
        with patch("app.main.smart_search", return_value=[RECORD]), patch(
            "app.main.generate_response", return_value=json.dumps(generated)
        ) as generate:
            response = client.post(
                "/chat",
                json={"question": "What storage life is recorded for Bhima Kiran?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()), {"answer", "confidence", "follow_up"}
        )
        self.assertEqual(response.json()["confidence"], generated["confidence"])
        self.assertEqual(response.json()["follow_up"], generated["follow_up"])
        self.assertIn(RECORD["source_url"], response.json()["answer"])
        self.assertIn(RECORD["source_url"], generate.call_args.args[1])

    def test_empty_and_whitespace_questions_are_rejected(self):
        for question in ("", "   "):
            with self.subTest(question=question):
                self.assertEqual(
                    client.post("/chat", json={"question": question}).status_code,
                    422,
                )

    def test_too_long_question_is_rejected(self):
        response = client.post("/chat", json={"question": "x" * 1001})
        self.assertEqual(response.status_code, 422)

    def test_q6_returns_unavailable_without_calling_model(self):
        with patch("app.main.generate_response") as generate:
            response = client.post(
                "/chat",
                json={"question": "What is today's onion mandi price per quintal in Lasalgaon?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()), {"answer", "confidence", "follow_up"}
        )
        self.assertIn("do not contain live mandi prices", response.json()["answer"])
        self.assertEqual(response.json()["confidence"], "low")
        generate.assert_not_called()

    def test_invalid_provider_and_missing_key_return_safe_503(self):
        cases = (
            {"LLM_PROVIDER": "unknown", "GROQ_API_KEY": "", "GEMINI_API_KEY": ""},
            {"LLM_PROVIDER": "groq", "GROQ_API_KEY": "", "GEMINI_API_KEY": ""},
        )
        for values in cases:
            with self.subTest(provider=values["LLM_PROVIDER"]), patch.dict(
                os.environ, values, clear=False
            ), patch("app.main.smart_search", return_value=[RECORD]):
                response = client.post(
                    "/chat", json={"question": "Tell me about Bhima Kiran."}
                )

            self.assertEqual(response.status_code, 503)
            self.assertEqual(
                set(response.json()), {"answer", "confidence", "follow_up"}
            )
            self.assertNotIn("API_KEY", response.text)

    def test_provider_failure_returns_safe_503(self):
        with patch("app.main.smart_search", return_value=[RECORD]), patch(
            "app.main.generate_response",
            side_effect=LLMProviderError("private provider details"),
        ):
            response = client.post(
                "/chat", json={"question": "Tell me about Bhima Kiran."}
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            set(response.json()), {"answer", "confidence", "follow_up"}
        )
        self.assertNotIn("private provider details", response.text)


class ProviderAndPromptTests(unittest.TestCase):
    def test_invalid_provider_and_missing_key_are_configuration_errors(self):
        cases = (
            {"LLM_PROVIDER": "not-a-provider", "GROQ_API_KEY": ""},
            {"LLM_PROVIDER": "groq", "GROQ_API_KEY": ""},
        )
        for values in cases:
            with self.subTest(provider=values["LLM_PROVIDER"]), patch.dict(
                os.environ, values, clear=False
            ):
                with self.assertRaises(LLMConfigurationError):
                    generate_response("system", "user")

    def test_both_prompt_versions_load(self):
        system_v1, task_v1 = load_chat_prompts("v1")
        system_v2, task_v2 = load_chat_prompts("v2")

        self.assertTrue(system_v1.strip())
        self.assertTrue(task_v1.strip())
        self.assertEqual(system_v1, system_v2)
        self.assertNotEqual(task_v1, task_v2)

    def test_groq_timeout_is_sanitized(self):
        from groq import APITimeoutError
        from unittest.mock import Mock

        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "groq", "GROQ_API_KEY": "test-key"},
            clear=False,
        ), patch("groq.Groq") as groq_client:
            groq_client.return_value.chat.completions.create.side_effect = (
                APITimeoutError(request=Mock())
            )
            with self.assertRaisesRegex(LLMProviderError, "timed out"):
                generate_response("system", "user")

    def test_groq_api_error_is_sanitized(self):
        from groq import APIError
        from unittest.mock import Mock

        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "groq", "GROQ_API_KEY": "test-key"},
            clear=False,
        ), patch("groq.Groq") as groq_client:
            groq_client.return_value.chat.completions.create.side_effect = APIError(
                "private provider details", request=Mock(), body=None
            )
            with self.assertRaisesRegex(
                LLMProviderError, "Groq provider could not complete"
            ) as raised:
                generate_response("system", "user")
            self.assertNotIn("private provider details", str(raised.exception))

    def test_gemini_timeout_is_sanitized(self):
        import httpx2

        with patch.dict(
            os.environ,
            {"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key"},
            clear=False,
        ), patch("google.genai.Client") as gemini_client:
            gemini_client.return_value.models.generate_content.side_effect = (
                httpx2.TimeoutException("private transport details")
            )
            with self.assertRaisesRegex(LLMProviderError, "timed out"):
                generate_response("system", "user")


if __name__ == "__main__":
    unittest.main()
