from unittest.mock import patch

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_response_structure_and_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "OK",
        "message": "KandaGuide API is running",
    }


def test_ask_returns_answer_and_citations_from_fake_llm():
    chunks = [
        {
            "chunk_id": "fixture-1",
            "title": "Onion storage guide",
            "source": "https://example.org/onion-guide",
            "page": 3,
            "text": "Onion storage requires good ventilation.",
            "distance": 0.2,
        }
    ]
    fake_llm_response = '{"answer": "Store onions with good ventilation.", "confidence": "high", "follow_up": null}'

    with (
        patch("app.rag.semantic_search", return_value=chunks),
        patch("app.rag.generate_response", return_value=fake_llm_response) as generate,
    ):
        response = client.post("/ask", json={"question": "How should onion storage work?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"].startswith("Store onions with good ventilation.")
    assert body["confidence"] == "high"
    assert body["citations"] == [
        {
            "title": "Onion storage guide",
            "source": "https://example.org/onion-guide",
            "page": 3,
            "chunk_id": "fixture-1",
        }
    ]
    generate.assert_called_once()


def test_ask_abstains_when_question_is_unsupported():
    with (
        patch("app.rag.semantic_search", return_value=[]),
        patch("app.rag.generate_response") as generate,
    ):
        response = client.post(
            "/ask",
            json={"question": "What is today's onion mandi price per quintal in Lasalgaon?"},
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "I don't know."
    assert response.json()["citations"] == []
    assert response.json()["confidence"] == "low"
    generate.assert_not_called()

