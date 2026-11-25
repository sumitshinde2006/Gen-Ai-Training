# KandaGuide Interview Preparation

## 60-second project pitch

KandaGuide helps onion and garlic farmers find agricultural information without having to search through several documents themselves. It combines source-linked variety records and agricultural HTML/PDF references with a FastAPI service and a Streamlit interface. Its retrieval-augmented generation, or RAG, pipeline searches those sources and can return an answer with source citations or abstain when the available evidence is insufficient. A bounded agent workflow can route a request to agricultural retrieval, deterministic calculation tools, or both; Python `Decimal` calculations handle arithmetic rather than asking the language model to do it. The document search uses sentence-transformer embeddings and a persistent Chroma vector store, while the project also retains its structured-record search. The practical goal is to make variety, season, maturity, yield, and storage information easier to find and to keep answers traceable to their sources—not to replace local agronomic advice or promise that every source claim is reconciled.

## Hardest technical problem: representing agricultural facts faithfully

The hardest data challenge is deciding whether two agricultural numbers really conflict. Variety pages, handbooks, and field-demonstration reports may refer to different seasons, locations, maturity stages, or trial conditions. If those context fields are lost, a valid difference can look like a contradiction.

For example, the DOGR source record for Bhima Raj gives different yield ranges for Kharif, late Kharif, and Rabi. The MANAGE reference separately reports demonstration yields for Bhima Raj in Maharashtra: 235 q/ha in Kharif and 415 q/ha in late Kharif. Converting units (10 q/ha = 1 t/ha) puts these demonstration values in the same broad range as the DOGR figures, but the records still describe different source contexts and should not be presented as one interchangeable measurement. The ingested dataset keeps variety-level season text and a source URL; some yield and maturity fields retain season-specific details inside a text value.

The ingestion code converts numeric `q/ha` and `quintals/ha` expressions to `t/ha`, and the structured records distinguish some maturity values after transplanting from notes such as days after sowing. The document chunker also keeps the source URL, title, and PDF page for each chunk. These are useful safeguards, but they do **not** amount to full claim-level reconciliation:

- The unit conversion is textual and the stored yield values remain strings.
- A record can contain multiple seasons and season-specific numbers in the same field.
- `source_url` is attached to the record, not independently to every numerical claim.
- Some maturity entries remain ambiguous. For example, an NHB record stores “140-145 days” under `maturity_days_after_transplanting` even though the value itself does not name a reference stage. The DOGR parser also treats a maturity string containing “transplant” as transplant-based without requiring the phrase “after transplanting”.
- Chroma chunk provenance records source/page/title, but the chunk metadata does not normalize each numeric claim into its own season- and condition-specific fact.

The current pipeline can retrieve source-backed material and include citations; it does not automatically adjudicate competing agricultural claims. The lesson was to preserve the original wording and provenance, convert units transparently, and avoid treating season, location, trial type, or “days after sowing/transplanting” as optional decoration. A stronger future data model would store each claim separately with its original and normalized value, unit, variety, season, maturity reference point, conditions, and exact source/page. That claim-level structure is a proposed improvement, not a feature the current code fully implements.

Relevant implementation and source evidence: [`app/ingest.py`](../app/ingest.py), [`app/chunking.py`](../app/chunking.py), [`data/records.json`](../data/records.json), [`data/raw/manage_reference.txt`](../data/raw/manage_reference.txt), and [`docs/semantic-search.md`](./semantic-search.md).

## Ten likely interview questions and answers

### 1. What problem does KandaGuide solve?

It helps onion and garlic growers and other agricultural users find information about varieties, growing seasons, maturity, yield, and storage. It searches project records and agricultural documents, and it can perform supported calculations. It is an information aid, not a personalized agronomic recommendation service.

### 2. What is RAG, and why is it used?

Retrieval-Augmented Generation first retrieves relevant material from a knowledge collection and then gives that evidence to a language model to help form an answer. KandaGuide uses this pattern so answers can be tied to the project's agricultural sources rather than relying only on what a model learned during training. Retrieval does not guarantee correctness, so the application also checks for usable evidence, returns citations, and can abstain.

### 3. How does document ingestion work?

The document pipeline reads supported HTML and PDF files under `data/raw/`. BeautifulSoup extracts HTML text, and pypdf extracts PDF text page by page. The separate structured-record ingestion code parses DOGR variety pages and includes records for varieties from an NHB source. Document chunks are then embedded and indexed in Chroma. Keeping these as separate paths matters: source-linked variety records and semantic document chunks are related, but they are not the same dataset.

### 4. What is chunking, and why is it necessary?

Chunking splits long documents into smaller passages so a search can return relevant sections instead of passing an entire handbook to the model. KandaGuide's default chunker aims for 500 words with 75 words of overlap, grouping sentences where possible. Overlap helps retain context across boundaries. Chunks also retain source, title, and, for PDFs, the original page number so retrieved evidence can be cited.

### 5. How does vector search work?

The application converts each chunk and each user query into a vector, which is a list of numbers representing text. Chroma compares the query vector with stored chunk vectors and returns nearby matches. KandaGuide configures cosine distance and an HNSW approximate-nearest-neighbor index. A closer vector is a relevance signal, not proof that the passage is correct or sufficient.

### 6. What is the role of embeddings and ChromaDB?

The default embedding model is `sentence-transformers/all-MiniLM-L6-v2`. It encodes both documents and queries into a shared vector space. ChromaDB persists the document vectors and metadata, allowing the application to retrieve likely relevant chunks later. The metadata includes the source, title, and page where available. If the configured embedding model changes, the index must be rebuilt so document and query vectors remain compatible.

### 7. What is the difference between RAG and Agentic AI?

RAG is the evidence-retrieval and answer-generation pattern. Agentic AI adds controlled decision-making about what operation to perform. KandaGuide's agent can choose agricultural retrieval, a deterministic calculation, both, or a clarification. The agent reuses the RAG pipeline; it does not replace it.

### 8. How does the agent select and execute tools?

The request planner first uses local rules for clear, common requests. Less obvious requests may use the configured language model to classify intent and extract values the user actually supplied. The plan is validated, then the workflow routes to RAG, deterministic Python calculation tools, or both. Python tools perform calculations using `Decimal`; the model is not used as the arithmetic engine. Some storage-decision workflows pause for user approval. The graph's `MemorySaver` is in-process memory, so it is cleared on restart and is not shared across workers.

### 9. How are answer accuracy and citations evaluated?

The repository includes a 15-question RAG evaluation that compares two chunk-size/top-k configurations using isolated temporary indexes. It checks retrieval against expected sources, answer keyword coverage, citation chunk/source matching, support keywords in retrieved text, and exact abstention on unanswerable questions. These are reproducible proxies, not semantic or claim-level verification.

In the latest recorded run (2026-11-24 UTC), Configuration B achieved 100% retrieval hit rate and 93.33% answer keyword-proxy correctness, but citation correctness was 20% and the grounded-answer proxy was 7.69%. Both configurations abstained correctly on the two unanswerable questions. Those results show that retrieving a relevant source is not enough: citation and answer grounding still need improvement.

### 10. How is the application deployed and tested?

The repository provides a Dockerfile, a Docker Compose setup for the FastAPI API and Streamlit UI, and a Render Blueprint with separate API and UI services. These files describe deployment configuration; they do not prove that every configured service is currently available. GitHub Actions is configured to run Ruff, pytest, and a Docker image build.

For this Day 14 verification, `python -m pytest -q` completed with **120 passed and one deprecation warning**, and `python -m ruff check .` passed. The credentialed Groq evaluation completed both configurations with no failed or skipped questions. The local Docker build could not run because the Docker CLI could not connect to the Docker Desktop Linux engine; the daemon was unavailable. The configured CI workflow and deployment files are not substitutes for that local build result or a current live deployment check.

## Source pointers

- [`docs/agentic-ai.md`](./agentic-ai.md) — planner, graph, tools, memory, approval, and limitations.
- [`docs/semantic-search.md`](./semantic-search.md) — chunking, embeddings, vector search, and provenance.
- [`eval/evaluation_summary.md`](../eval/evaluation_summary.md) — latest RAG evaluation metrics and scoring caveats.
- [`Readme.md`](../Readme.md) — project scope, source notes, deployment configuration, and test instructions.
