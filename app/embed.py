"""Sentence-transformer embeddings shared by indexing and semantic queries."""

import os
from functools import lru_cache
from typing import Sequence

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingError(RuntimeError):
    """Raised when an embedding model is unavailable or cannot encode text."""


def get_model_name() -> str:
    return (
        os.getenv("KANDAGUIDE_EMBEDDING_MODEL", "").strip()
        or DEFAULT_EMBEDDING_MODEL
    )


@lru_cache(maxsize=2)
def _load_model(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise EmbeddingError(
            "sentence-transformers is not installed. Install project requirements."
        ) from error
    try:
        import httpx
        from huggingface_hub.errors import HfHubHTTPError
        from requests.exceptions import RequestException
    except ImportError as error:
        raise EmbeddingError(
            "The embedding model's download dependencies are unavailable."
        ) from error
    try:
        return SentenceTransformer(model_name)
    except (
        HfHubHTTPError,
        ImportError,
        OSError,
        RequestException,
        RuntimeError,
        ValueError,
        httpx.HTTPError,
    ) as error:
        raise EmbeddingError(
            f"The embedding model '{model_name}' could not be loaded."
        ) from error


def embed_texts(
    texts: Sequence[str], model_name: str | None = None
) -> list[list[float]]:
    """Encode document texts using the configured, cached embedding model."""
    if not texts:
        return []
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("texts must contain only non-empty strings.")

    model = _load_model(model_name or get_model_name())
    try:
        vectors = model.encode(
            list(texts),
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
    except (OSError, ValueError, RuntimeError) as error:
        raise EmbeddingError("The embedding model could not encode the text.") from error
    return [[float(value) for value in vector] for vector in vectors]


def embed_query(query: str, model_name: str | None = None) -> list[float]:
    """Encode one search query with the same model used for document chunks."""
    if not isinstance(query, str) or not query.strip():
        return []
    vectors = embed_texts([query], model_name=model_name)
    return vectors[0]
