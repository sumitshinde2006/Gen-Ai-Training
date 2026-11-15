# KandaGuide semantic search

KandaGuide's semantic search indexes the local HTML and PDF sources in
`data/raw/` as searchable text chunks. It uses sentence-transformer
embeddings and a persistent Chroma collection; it does not replace the
existing TF-IDF `/search` endpoint or the agricultural variety records.

## Chunking and provenance

`app.chunking` extracts visible content from HTML with BeautifulSoup and
page text from PDFs with pypdf. It removes common non-content HTML elements,
uses a document title, and records the known source URL. PDF page numbers
are the original one-based page numbers; HTML chunks use `page: null`.
Sources with no known URL use their local document URI as the source
identifier.

The chunker aims for 500 words with 75 words of overlap by default. It
groups complete sentences where possible and only splits an individual
sentence when that sentence is larger than the configured chunk size.
Overlap carries context across chunk boundaries, which can help retrieval
when a question relates to material on either side of a boundary.

`data/raw/manage_reference.txt` is an extracted sidecar of
`manage_onion_garlic.pdf` (its normalized text matches the PDF extraction).
The indexer uses the original PDF once, preserving its actual page
metadata, rather than indexing duplicate copies of that content.

## Embeddings and vector similarity

An embedding is a numerical vector that represents text. The default model
is `sentence-transformers/all-MiniLM-L6-v2`; `KANDAGUIDE_EMBEDDING_MODEL`
can select another compatible Sentence Transformers model. `app.embed`
caches the loaded model and uses the same configured model for documents
and queries. The first call downloads model files from Hugging Face if they
are not already cached, so first-time setup requires network access.

Chroma stores normalized vectors and uses cosine distance to rank nearby
chunks. A smaller distance means the vectors are closer; it does not prove
that a chunk contains a correct or sufficient answer. In particular,
semantic similarity cannot provide a live mandi price that is absent from
the source documents. The collection uses Chroma's HNSW cosine index with
`hnsw:search_ef=100`; as approximate nearest-neighbor search, rankings can
vary slightly after rebuilding the index.

## TF-IDF search versus semantic search

The existing `GET /search?q=...` endpoint applies TF-IDF and cosine
similarity to variety-record fields. It is useful for keyword overlap and
continues to return variety records with lexical similarity scores.

`GET /search/semantic?q=...&top_k=5` embeds the question and ranks source
document chunks by vector distance. It can match related wording even when
the exact same words are absent. It returns chunk text, provenance
metadata, and Chroma distance. Both are retrieval tools—not fact checks,
live-data services, or personalized agricultural recommendations.

## Build and use the index

From the repository root in PowerShell:

```powershell
.\myenv\Scripts\python.exe -m pip install -r requirements.txt
.\myenv\Scripts\python.exe -c "from app.chunking import chunk_documents; chunks = chunk_documents(); print(f'{len(chunks)} chunks extracted')"
.\myenv\Scripts\python.exe -c "from app.chunking import chunk_documents; from app.embed import embed_texts; chunks = chunk_documents(); vectors = embed_texts([chunk['text'] for chunk in chunks]); print(f'{len(vectors)} vectors generated')"
.\myenv\Scripts\python.exe -m app.vectorstore
.\myenv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The first command extracts chunks; the second demonstrates generating their
embeddings. Both full-corpus steps can take time and the embedding command
loads/downloads the configured model. The indexing command performs these
steps together, reports failures, rebuilds the `kandaguide_knowledge`
collection, and prints its persistent location. It does not start FastAPI.
The default database is in
`data/chroma/`; set `KANDAGUIDE_CHROMA_PATH` to use another directory.
The database is persistent and is not recreated when the API starts.
`KANDAGUIDE_EMBEDDING_MODEL` selects the embedding model consistently for
indexing and query encoding. The selected model is recorded in collection
metadata; if it changes, rebuild the index before searching so stored and
query vectors remain compatible.

Example request:

```text
GET http://127.0.0.1:8000/search/semantic?q=Which%20onion%20varieties%20have%20good%20storage%20life%3F&top_k=5
```

The endpoint accepts `top_k` from 1 through 20, returns an empty result
list for an empty collection, rejects blank questions, and reports vector
database failures without exposing internal exception details.
