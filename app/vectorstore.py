"""Persistent Chroma indexing and semantic retrieval for KandaGuide."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Sequence

from app.chunking import (
    RAW_DIR,
    DocumentChunk,
    chunk_documents,
    chunk_document,
    list_document_paths,
)
from app.embed import (
    EmbeddingError,
    embed_query,
    embed_texts,
    get_model_name,
)
from pypdf.errors import PdfReadError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PERSIST_DIRECTORY = PROJECT_ROOT / "data" / "chroma"
COLLECTION_NAME = "kandaguide_knowledge"
MAX_TOP_K = 20
HNSW_SEARCH_EF = 100
_HTML_PAGE_SENTINEL = -1


class VectorStoreError(RuntimeError):
    """Raised when the persistent vector store cannot be read or updated."""


def _persist_path(persist_directory: Path | str | None = None) -> Path:
    configured = persist_directory or os.getenv("KANDAGUIDE_CHROMA_PATH")
    return Path(configured).expanduser().resolve() if configured else DEFAULT_PERSIST_DIRECTORY


@lru_cache(maxsize=4)
def _client(persist_path: str):
    try:
        import chromadb
    except ImportError as error:
        raise VectorStoreError(
            "chromadb is not installed. Install project requirements."
        ) from error

    try:
        Path(persist_path).mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=persist_path)
    except (OSError, ValueError, RuntimeError, chromadb.errors.ChromaError) as error:
        raise VectorStoreError("The persistent vector database is unavailable.") from error


def get_collection(persist_directory: Path | str | None = None):
    """Open or create the persistent KandaGuide knowledge collection."""
    try:
        import chromadb
    except ImportError as error:
        raise VectorStoreError(
            "chromadb is not installed. Install project requirements."
        ) from error

    client = _client(str(_persist_path(persist_directory)))
    try:
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={
                "hnsw:space": "cosine",
                "hnsw:search_ef": HNSW_SEARCH_EF,
                "embedding_model": get_model_name(),
            },
        )
        metadata = collection.metadata or {}
        indexed_model = metadata.get("embedding_model")
        configured_model = get_model_name()
        if not indexed_model:
            raise VectorStoreError(
                "The index does not record its embedding model; rebuild it before searching."
            )
        if indexed_model != configured_model:
            raise VectorStoreError(
                "The index uses a different embedding model; rebuild it before searching."
            )
        return collection
    except VectorStoreError:
        raise
    except chromadb.errors.ChromaError as error:
        raise VectorStoreError("The KandaGuide collection is unavailable.") from error


def _metadata(chunk: DocumentChunk) -> dict[str, str | int]:
    return {
        "chunk_id": chunk["chunk_id"],
        "source": chunk["source"],
        "page": chunk["page"] if chunk["page"] is not None else _HTML_PAGE_SENTINEL,
        "title": chunk["title"],
    }


def index_chunks(
    chunks: Sequence[DocumentChunk],
    persist_directory: Path | str | None = None,
) -> int:
    """Upsert chunks and remove stale chunks for each supplied source."""
    if not chunks:
        return 0
    ids = [chunk["chunk_id"] for chunk in chunks]
    if len(set(ids)) != len(ids):
        raise ValueError("Chunk IDs must be unique.")

    collection = get_collection(persist_directory)
    try:
        import chromadb

        embeddings = embed_texts([chunk["text"] for chunk in chunks])
        sources = {chunk["source"] for chunk in chunks}
        collection.upsert(
            ids=ids,
            documents=[chunk["text"] for chunk in chunks],
            metadatas=[_metadata(chunk) for chunk in chunks],
            embeddings=embeddings,
        )

        for source in sources:
            existing = collection.get(
                where={"source": source},
                include=["metadatas"],
            )
            desired_ids = {
                chunk["chunk_id"] for chunk in chunks if chunk["source"] == source
            }
            stale_ids = [
                chunk_id
                for chunk_id in existing["ids"]
                if chunk_id not in desired_ids
            ]
            if stale_ids:
                collection.delete(ids=stale_ids)
    except EmbeddingError as error:
        raise VectorStoreError("KandaGuide could not generate embeddings.") from error
    except chromadb.errors.ChromaError as error:
        raise VectorStoreError("KandaGuide could not update the vector database.") from error
    except (OSError, ValueError, RuntimeError) as error:
        raise VectorStoreError("KandaGuide could not index the document chunks.") from error
    else:
        return len(chunks)


def semantic_search(
    query: str,
    top_k: int = 5,
    persist_directory: Path | str | None = None,
) -> list[dict[str, object]]:
    """Return the nearest chunks and Chroma cosine distances for a query."""
    if not isinstance(query, str) or not query.strip():
        return []
    if top_k < 1 or top_k > MAX_TOP_K:
        raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}.")

    collection = get_collection(persist_directory)
    try:
        import chromadb

        count = collection.count()
        if count == 0:
            return []

        embedding = embed_query(query)
        if not embedding:
            return []
        matches = collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )
    except EmbeddingError as error:
        raise VectorStoreError("KandaGuide could not embed the search query.") from error
    except chromadb.errors.ChromaError as error:
        raise VectorStoreError("KandaGuide semantic search is unavailable.") from error
    except (OSError, ValueError, RuntimeError) as error:
        raise VectorStoreError("KandaGuide semantic search is unavailable.") from error

    ids = matches["ids"][0]
    documents = matches.get("documents", [[]])[0]
    metadatas = matches.get("metadatas", [[]])[0]
    distances = matches.get("distances", [[]])[0]
    results: list[dict[str, object]] = []

    for chunk_id, text, metadata, distance in zip(
        ids, documents, metadatas, distances
    ):
        page = metadata.get("page")
        results.append(
            {
                "chunk_id": metadata.get("chunk_id", chunk_id),
                "text": text,
                "source": metadata.get("source", ""),
                "page": None if page == _HTML_PAGE_SENTINEL else page,
                "title": metadata.get("title", ""),
                "distance": float(distance),
            }
        )
    return results


def rebuild_index(
    chunks: Sequence[DocumentChunk] | None = None,
    raw_dir: Path = RAW_DIR,
    persist_directory: Path | str | None = None,
) -> int:
    """Replace the collection contents, removing all chunks from old sources."""
    if chunks is None:
        if not list_document_paths(raw_dir):
            raise FileNotFoundError(f"No supported source documents found in {raw_dir}.")
        chunks = chunk_documents(raw_dir=raw_dir)

    try:
        import chromadb
    except ImportError as error:
        raise VectorStoreError(
            "chromadb is not installed. Install project requirements."
        ) from error

    client = _client(str(_persist_path(persist_directory)))
    try:
        client.delete_collection(COLLECTION_NAME)
    except chromadb.errors.NotFoundError:
        pass
    except chromadb.errors.ChromaError as error:
        raise VectorStoreError("The KandaGuide collection could not be rebuilt.") from error

    get_collection(persist_directory)
    return index_chunks(chunks, persist_directory=persist_directory)


def _index_all_documents() -> int:
    paths = list_document_paths()
    if not paths:
        print(f"No HTML or PDF source documents found in {RAW_DIR}.")
        return 1

    chunks: list[DocumentChunk] = []
    failed: list[tuple[Path, str]] = []
    for path in paths:
        try:
            chunks.extend(chunk_document(path))
        except (OSError, UnicodeError, ValueError, PdfReadError) as error:
            failed.append((path, str(error)))

    for path, error in failed:
        print(f"[FAILED] {path.name}: {error}")
    if failed:
        print("Index was not changed because one or more documents failed.")
        return 1

    try:
        count = rebuild_index(chunks)
    except (OSError, ValueError, VectorStoreError) as error:
        print(f"Indexing failed: {error}")
        return 1

    print(f"Documents processed: {len(paths)}")
    print(f"Chunks indexed: {count}")
    print(f"Persistent database: {_persist_path()}")
    print(f"Collection: {COLLECTION_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_index_all_documents())
