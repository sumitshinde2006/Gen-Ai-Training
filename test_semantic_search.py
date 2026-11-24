import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.chunking import chunk_document
from app.embed import EmbeddingError, embed_query, embed_texts
from app.main import app
from app.vectorstore import (
    COLLECTION_NAME,
    VectorStoreError,
    _client,
    get_collection,
    index_chunks,
    rebuild_index,
    semantic_search,
)

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
VARIETIES_HTML = RAW_DIR / "dogr_varieties.html"
MANAGE_PDF = RAW_DIR / "manage_onion_garlic.pdf"
client = TestClient(app)


class ChunkingTests(unittest.TestCase):
    def test_html_chunks_keep_source_title_and_null_page(self):
        chunks = chunk_document(VARIETIES_HTML, chunk_size=200, overlap=30)

        self.assertTrue(chunks)
        self.assertEqual(
            chunks[0]["source"],
            "https://www.dogr.res.in/index.php/research/"
            "varieties-developed?layout=edit",
        )
        self.assertEqual(chunks[0]["title"], "Varieties Developed")
        self.assertIsNone(chunks[0]["page"])
        self.assertTrue(all(chunk["text"].strip() for chunk in chunks))

    def test_pdf_chunks_use_actual_page_numbers_and_title(self):
        chunks = chunk_document(MANAGE_PDF, chunk_size=200, overlap=30)

        self.assertTrue(chunks)
        self.assertIn("Good Agricultural Practices", chunks[0]["title"])
        self.assertTrue(
            all(
                isinstance(chunk["page"], int) and 1 <= chunk["page"] <= 170
                for chunk in chunks
            )
        )
        self.assertIn(
            "https://www.manage.gov.in/publications/eBooks/"
            "Good%20Agricultural%20Practices%20in%20Onion%20and%20Garlic.pdf",
            {chunk["source"] for chunk in chunks},
        )

    def test_chunk_overlap_and_argument_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overlap.html"
            path.write_text(
                "<html><head><title>Test</title></head><body><main>"
                "Onion records describe the first variety in detail. "
                "Garlic records describe the second variety in detail. "
                "Storage records describe the third variety in detail."
                "</main></body></html>",
                encoding="utf-8",
            )
            chunks = chunk_document(path, chunk_size=12, overlap=5)

        self.assertGreaterEqual(len(chunks), 2)
        first_words = set(chunks[0]["text"].split())
        second_words = set(chunks[1]["text"].split())
        self.assertTrue(first_words.intersection(second_words))
        with self.assertRaises(ValueError):
            chunk_document(VARIETIES_HTML, chunk_size=10, overlap=10)


class EmbeddingTests(unittest.TestCase):
    def test_empty_inputs_do_not_load_the_model(self):
        self.assertEqual(embed_texts([]), [])
        self.assertEqual(embed_query("  "), [])

    def test_embedding_functions_return_numeric_vectors(self):
        class FakeModel:
            def encode(self, texts, **kwargs):
                return [[1.0] * 384 for _ in texts]

        with patch("app.embed._load_model", return_value=FakeModel()):
            vectors = embed_texts(["onion bulb production", "garlic storage"])
            query = embed_query("How should garlic bulbs be stored?")

        self.assertEqual(len(vectors), 2)
        self.assertEqual(len(vectors[0]), 384)
        self.assertEqual(len(vectors[1]), 384)
        self.assertEqual(len(query), 384)
        self.assertTrue(all(isinstance(value, float) for value in vectors[0]))


class PersistentVectorStoreTests(unittest.TestCase):
    def close_database(self, directory):
        database_client = _client(str(Path(directory).resolve()))
        database_client.close()
        _client.cache_clear()

    def test_indexing_is_idempotent_updates_remove_stale_chunks_and_persist(self):
        source_chunks = chunk_document(
            VARIETIES_HTML, chunk_size=200, overlap=30
        )[:2]
        self.assertEqual(len(source_chunks), 2)

        with tempfile.TemporaryDirectory() as directory:
            first_embedding = [1.0, 0.0]
            second_embedding = [0.0, 1.0]

            def fake_embed_texts(texts):
                return [
                    first_embedding if text == source_chunks[0]["text"] else second_embedding
                    for text in texts
                ]

            with (
                patch("app.vectorstore.embed_texts", side_effect=fake_embed_texts),
                patch("app.vectorstore.embed_query", return_value=first_embedding),
            ):
                try:
                    self.assertEqual(index_chunks(source_chunks, directory), 2)
                    collection = get_collection(directory)
                    self.assertEqual(collection.name, COLLECTION_NAME)
                    self.assertEqual(
                        collection.metadata["embedding_model"],
                        "sentence-transformers/all-MiniLM-L6-v2",
                    )
                    self.assertEqual(collection.metadata["hnsw:search_ef"], 100)
                    self.assertEqual(collection.count(), 2)

                    index_chunks(source_chunks, directory)
                    self.assertEqual(get_collection(directory).count(), 2)

                    matches = semantic_search(
                        source_chunks[0]["text"][:160],
                        top_k=1,
                        persist_directory=directory,
                    )
                    self.assertEqual(matches[0]["chunk_id"], source_chunks[0]["chunk_id"])
                    self.assertIsNone(matches[0]["page"])
                    self.assertGreaterEqual(matches[0]["distance"], 0)

                    self.close_database(directory)
                    reopened = get_collection(directory)
                    self.assertEqual(reopened.count(), 2)

                    self.assertEqual(index_chunks(source_chunks[:1], directory), 1)
                    self.assertEqual(get_collection(directory).count(), 1)

                    self.assertEqual(
                        rebuild_index(source_chunks[1:], persist_directory=directory), 1
                    )
                    self.assertEqual(get_collection(directory).count(), 1)
                finally:
                    self.close_database(directory)

    def test_empty_collection_and_invalid_search_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            try:
                self.assertEqual(semantic_search("garlic storage", persist_directory=directory), [])
                self.assertEqual(semantic_search("  ", persist_directory=directory), [])
                with self.assertRaises(ValueError):
                    semantic_search("garlic", top_k=0, persist_directory=directory)
            finally:
                self.close_database(directory)

    def test_collection_rejects_an_embedding_model_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            try:
                collection = get_collection(directory)
                collection.modify(metadata={"embedding_model": "different-model"})
                with patch(
                    "app.vectorstore.get_model_name",
                    return_value="sentence-transformers/all-MiniLM-L6-v2",
                ), self.assertRaises(VectorStoreError):
                    get_collection(directory)
            finally:
                self.close_database(directory)

    def test_rebuild_embedding_failure_preserves_existing_index(self):
        source_chunks = chunk_document(
            VARIETIES_HTML, chunk_size=200, overlap=30
        )[:1]
        with tempfile.TemporaryDirectory() as directory:
            with patch("app.vectorstore.embed_texts", return_value=[[1.0, 0.0]]):
                index_chunks(source_chunks, directory)

            try:
                with patch(
                    "app.vectorstore.embed_texts",
                    side_effect=EmbeddingError("model unavailable"),
                ), self.assertRaises(VectorStoreError):
                    rebuild_index(source_chunks, persist_directory=directory)

                self.assertEqual(get_collection(directory).count(), 1)
            finally:
                self.close_database(directory)


class SemanticSearchEndpointTests(unittest.TestCase):
    def test_semantic_search_response_and_existing_endpoints(self):
        match = {
            "chunk_id": "chunk-1",
            "text": "Retrieved agricultural document text.",
            "source": "https://example.org/source",
            "page": 3,
            "title": "Source title",
            "distance": 0.25,
        }
        with patch("app.main.search_chunks", return_value=[match]) as search:
            response = client.get(
                "/search/semantic",
                params={"q": "Which onion varieties have good storage life?", "top_k": 2},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total_results"], 1)
        self.assertEqual(response.json()["results"][0], match)
        search.assert_called_once_with(
            "Which onion varieties have good storage life?", top_k=2
        )
        self.assertEqual(client.get("/health").status_code, 200)
        self.assertEqual(client.get("/records").status_code, 200)
        self.assertEqual(client.get("/search", params={"q": "Bhima"}).status_code, 200)

    def test_semantic_search_validates_queries_and_hides_store_errors(self):
        for params in (
            {"q": ""},
            {"q": "   "},
            {"q": "onion", "top_k": 0},
            {"q": "onion", "top_k": 21},
        ):
            with self.subTest(params=params):
                response = client.get("/search/semantic", params=params)
                self.assertEqual(response.status_code, 422)

        with patch(
            "app.main.search_chunks",
            side_effect=VectorStoreError("private database detail"),
        ):
            response = client.get("/search/semantic", params={"q": "onion"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private database detail", response.text)

    def test_empty_collection_returns_an_empty_result_list(self):
        with patch("app.main.search_chunks", return_value=[]):
            response = client.get(
                "/search/semantic", params={"q": "Which onion varieties have good storage life?"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])


if __name__ == "__main__":
    unittest.main()
