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


def test_ask_answers_variety_storage_from_source_linked_records():
    records = [
        {
            "variety_name": "Bhima Kiran",
            "category": "onion",
            "season": "Rabi",
            "storage_life": "Suitable for storage up to 5-6 months",
            "source_url": "https://example.org/dogr",
        },
        {
            "variety_name": "Bhima Shakti",
            "category": "onion",
            "season": "Rabi Late Kharif",
            "storage_life": "Late kharif and rabi harvest suitable for storage up to 5-6 months",
            "source_url": "https://example.org/dogr",
        },
        {
            "variety_name": "Garlic Example",
            "category": "garlic",
            "season": "Rabi",
            "storage_life": "Excellent storage qualities",
            "source_url": "https://example.org/garlic",
        },
    ]
    with (
        patch("app.rag.smart_search", return_value=records),
        patch("app.rag.semantic_search") as semantic_search,
        patch("app.rag.generate_response") as generate,
    ):
        response = client.post(
            "/ask",
            json={"question": "Which onion varieties have good storage life?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert "Bhima Kiran" in body["answer"]
    assert "Bhima Shakti" in body["answer"]
    assert "Garlic Example" not in body["answer"]
    assert len(body["citations"]) == 2
    assert all(citation["source"] == "https://example.org/dogr" for citation in body["citations"])
    semantic_search.assert_not_called()
    generate.assert_not_called()

