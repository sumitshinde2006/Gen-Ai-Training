"""Repeatable local `/ask` benchmark using mocked retrieval and LLM responses."""

import argparse
import json
import math
import os
import platform
import statistics
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.rag import clear_response_cache, response_cache_info
from app.settings import get_settings

QUESTION = "How should onion storage be managed?"
MOCK_CHUNKS = [
    {
        "chunk_id": "benchmark-onion-storage",
        "title": "Mock onion storage source",
        "source": "https://example.org/mock-onion-storage",
        "page": 1,
        "text": "Onion storage requires a dry, well ventilated space.",
        "distance": 0.2,
    }
]
MOCK_RESPONSE = json.dumps(
    {
        "answer": "Onion storage requires a dry, well ventilated space.",
        "confidence": "high",
        "follow_up": None,
    }
)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * percentile) - 1))
    return ordered[index]


def run_benchmark(request_count: int) -> dict[str, object]:
    if request_count < 1:
        raise ValueError("request_count must be at least one.")
    settings = get_settings()
    clear_response_cache()
    latencies_ms = []
    with (
        patch("app.rag.semantic_search", return_value=MOCK_CHUNKS),
        patch("app.rag.generate_response", return_value=MOCK_RESPONSE),
        TestClient(app) as client,
    ):
        for _ in range(request_count):
            started = time.perf_counter()
            response = client.post("/ask", json={"question": QUESTION})
            latencies_ms.append((time.perf_counter() - started) * 1000)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Mocked benchmark request failed with HTTP {response.status_code}."
                )

    cache = response_cache_info()
    return {
        "benchmark": "mocked FastAPI TestClient /ask",
        "provider_calls": "none; retrieval and LLM are mocked",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "logical_cpu_count": os.cpu_count(),
        "requests": request_count,
        "latency_ms": {
            "average": round(statistics.mean(latencies_ms), 3),
            "p50": round(statistics.median(latencies_ms), 3),
            "p95": round(_percentile(latencies_ms, 0.95), 3),
        },
        "token_usage": {
            "prompt_tokens_average": None,
            "completion_tokens_average": None,
            "measurement": "unavailable; mocked responses contain no provider usage metadata",
        },
        "cache": {
            **cache,
            "hit_rate": round(cache["hits"] / request_count, 4),
            "ttl_seconds": settings.cache_ttl_seconds,
            "max_entries": settings.cache_max_entries,
            "enabled": settings.cache_enabled,
        },
        "limits": {
            "max_question_characters": settings.max_question_length,
            "max_top_k": settings.max_top_k,
        },
        "conditions": (
            "Local in-process TestClient; sequential requests; first request is a "
            "cache miss, subsequent identical questions use the RAG response cache; "
            "does not measure network, embedding, vector database, or provider latency."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(run_benchmark(args.requests), indent=2))


if __name__ == "__main__":
    main()
