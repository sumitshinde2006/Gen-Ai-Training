
# KandaGuide – AI-Powered Onion & Garlic Farming Assistant

**Student Name:** Sumit Gorakshanath Shinde  
**Student ID:** 2124UDSM2018  
**Department:** CSE (Data Science)  
**Project ID:** SJ-09 – Agriculture

## 1. Product

KandaGuide is an AI-powered agricultural information assistant designed
to help onion and garlic farmers find reliable information about crop
varieties, growing seasons, maturity periods, yield, storage and cultivation.

The project aims to develop a searchable agricultural knowledge base
and eventually an AI assistant using RAG and Agentic AI.

## 8. Agentic AI milestone

KandaGuide now includes a deterministic `storage_break_even` tool, an
independent hand-written agent loop, and a LangGraph workflow with
thread-scoped memory and an interrupt/resume approval step for storage
recommendations. The agents reuse the existing `app.rag.answer_question()`
retrieval and LLM pipeline. See [docs/agentic-ai.md](docs/agentic-ai.md) for
the workflow, memory limitations, source review, and implementation details.

### Storage break-even tool

For quantity `Q`, today's price `P`, and loss fraction `L`, the gross-revenue
break-even price is:

```text
today's revenue = Q × P
saleable quantity = Q × (1 − L)
break-even price per quintal = today's revenue ÷ saleable quantity
```

An explicit loss percentage is used exactly. If omitted, the tool returns
both 30% and 40% loss scenarios and labels the range unverified. The local
MANAGE reference associates 30–40% with Fusarium basal rot; it does not
verify a general DOGR default. A local DOGR variety record reports 31.11%
after four months specifically for Bhima Prasanskaran. The output is a
gross-revenue calculation, not full profit; storage months do not imply a
time-based loss rate.

### Install and run

```powershell
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

### `POST /agent`

Request a calculation:

```json
{
  "message": "I have 100 quintals of onion. Today's price is 2000 per quintal. Calculate the break-even price for 3 months with 30% storage loss.",
  "thread_id": "farmer-session-001",
  "approval": null
}
```

The response includes `status`, `answer`, `tools_used`, `citations`,
`calculation_result`, `requires_approval`, and `follow_up`. Calculation
results are marked as calculated results; agricultural claims come from RAG
and include citations.

For a storage decision request, the graph pauses and returns
`status: "awaiting_approval"`, the proposed `calculation_result`, and
`requires_approval: true`. Resume the same thread to approve:

```json
{
  "message": "Review the proposed storage decision",
  "thread_id": "farmer-session-001",
  "approval": "approved"
}
```

Or reject with `"approval": "rejected"`. Approval accepts only the proposed
decision response; no sale, order, buyer contact, or external transaction is
performed. The local in-memory checkpointer loses state when the server
restarts and is not shared across worker processes. A production deployment
should use persistent checkpoint storage and authenticate thread access.

### Tests

```powershell
python -m unittest test_agentic_ai test_graph_agent
python -m unittest discover -p "test_*.py"
```

## 2. Target Users

- Onion and garlic farmers
- Small and marginal farmers
- Farmer Producer Organizations (FPOs)
- Agricultural students
- Agricultural extension officers

## 3. Problem Statement

Farmers often face difficulties finding accurate and timely agricultural
information.

Major problems include:

- Lack of information about suitable onion and garlic varieties.
- Difficulty comparing crop maturity periods and yields.
- Limited access to variety-specific storage information.
- Agricultural information spread across multiple websites and documents.
- Difficulty understanding technical agricultural publications.

## 4. Proposed Solution

KandaGuide aims to provide:

1. Onion and garlic variety information.
2. Season-wise variety details.
3. Crop maturity and yield information.
4. Storage-life information.
5. Searchable agricultural documents.
6. AI-powered question answering with source citations.
7. Agricultural decision-support tools.

## 5. Data Sources

The project uses information from official agricultural institutions.

### ICAR-DOGR
Onion and garlic varieties developed:
https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit

### DOGR Garlic Information
https://dogr.res.in/index.php/component/content/article/garlicagropedia?layout=edit

### MANAGE
Good Agricultural Practices in Onion and Garlic:
https://www.manage.gov.in/publications/eBooks/Good%20Agricultural%20Practices%20in%20Onion%20and%20Garlic.pdf

### ICAR
Improved Onion Varieties Released:
https://icar.org.in/node/2087

All variety-specific values are linked to their sources.
Unknown values are stored as null rather than guessed.

## 6. Technology Stack

- Python
- FastAPI
- Pandas
- BeautifulSoup
- Requests
- Scikit-learn
- TF-IDF
- Cosine Similarity
- JSON
- Git and GitHub

## 7. Project Structure

```text
KandaGuide/
│
├── README.md
├── requirements.txt
├── .gitignore
│
├── data/
│   ├── raw/
│   └── records.json
│
├── app/
│   ├── fetch.py
│   ├── ingest.py
│   ├── models.py
│   ├── records.py
│   ├── main.py
│   └── smart_search.py
│
└── analysis/
    └── explore.py
```
## 8. How to Run

### 1. Activate the virtual environment

**Windows PowerShell:**

```powershell
myenv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Download agricultural documents

```bash
python -m app.fetch
```

### 4. Process agricultural data

```bash
python -m app.ingest
```

This generates the cleaned agricultural dataset in `data/records.json`.

### 5. Run data analysis

```bash
python -m analysis.explore
```

### 6. Start FastAPI

```bash
uvicorn app.main:app --reload
```

### 7. Open API documentation

http://127.0.0.1:8000/docs

### 8. Test the API

- `GET /health` – Check API status.
- `GET /records` – Retrieve agricultural records.
- `GET /records/1` – Retrieve a specific variety.
- `GET /search?q=Bhima` – Search agricultural varieties.
- `POST /questions` – Submit a farming question.
- `POST /chat` – Generate an evidence-grounded answer using retrieved
  variety records and a configured Groq or Gemini provider.

`POST /questions` remains an acknowledgement endpoint for compatibility.
See [LLM integration](docs/llm-integration.md) for provider setup and
`POST /chat` details.

## Checkpoint 1

- Checkpoint 1 documentation and API smoke-test results are available in
  [`docs/checkpoint-1.md`](docs/checkpoint-1.md).
- Learn how LLMs and RAG could fit KandaGuide in
  [`docs/how_llms_work.md`](docs/how_llms_work.md).
- The FastAPI run steps above use the existing `myenv` environment and
  `uvicorn app.main:app --reload` command.

## 9. API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /health | Check API status |
| GET | /records | Get agricultural records |
| GET | /records/{id} | Get one variety |
| GET | /search?q=Bhima | Search varieties |
| POST | /questions | Submit a farming question |
| POST | /chat | Ask a source-grounded agricultural question |
| POST | /ask | Ask over indexed source documents and receive chunk citations |

## LLM integration (S1/S2)

KandaGuide can use Groq or Google Gemini without application-code changes.
Install dependencies and prepare a local environment file:

```powershell
.\myenv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

If `.env` already exists, keep it and edit it without overwriting it.
Set `LLM_PROVIDER=groq` and `GROQ_API_KEY`, or use
`LLM_PROVIDER=gemini` and `GEMINI_API_KEY`. Optionally set `LLM_MODEL` to a
model ID supported by the selected provider; when blank, the documented
provider default is used. Never commit `.env`; `.env.example` has empty
credential fields.

Run FastAPI from the repository root:

```powershell
.\myenv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Example request:

```json
{"question": "Which onion varieties have good storage life?"}
```

Example response:

```json
{
  "answer": "Answer based on retrieved agricultural records, with source URLs.",
  "confidence": "medium",
  "follow_up": "Would you like to compare Rabi onion varieties?"
}
```

The exact answer depends on retrieved records. If information is unavailable,
KandaGuide states that limitation instead of filling the gap. Prompt V1 is
the default; V1/V2 evaluation status is documented in
[`eval/prompt_compare.md`](eval/prompt_compare.md). See
[`docs/llm-integration.md`](docs/llm-integration.md) for model IDs, provider
architecture, setup, and error behavior.

## Semantic document search (S1/S2)

KandaGuide also supports persistent semantic search over the HTML and PDF
documents in `data/raw/`. Install the added dependencies and build the local
index:

```powershell
.\myenv\Scripts\python.exe -m pip install -r requirements.txt
.\myenv\Scripts\python.exe -m app.vectorstore
```

The index command extracts and chunks the documents, generates
`sentence-transformers/all-MiniLM-L6-v2` embeddings, and stores them in the
`kandaguide_knowledge` Chroma collection under `data/chroma/`. The first
embedding run may download the model. The MANAGE `.txt` sidecar is skipped
when its original PDF is available, avoiding duplicate chunks and retaining
PDF page numbers.

Start FastAPI as shown above and query the separate semantic endpoint:

```text
GET http://127.0.0.1:8000/search/semantic?q=Which%20onion%20varieties%20have%20good%20storage%20life%3F&top_k=5
```

The existing `GET /search` remains a TF-IDF search over variety records.
Semantic-search setup, provenance, persistence, and evaluation are described
in [`docs/semantic-search.md`](docs/semantic-search.md) and
[`eval/search_results.md`](eval/search_results.md).

## 10. Development Progress

- Day 1: Project introduction and Python fundamentals.
- Day 2: Variety dataset and record operations.
- Day 3: Agricultural data ingestion pipeline.
- Day 4: FastAPI, Pandas and smart search.
- Checkpoint 1: LLM/RAG documentation and HTTP validation of the existing
  FastAPI endpoints.

## 11. Expected Outcome

KandaGuide aims to provide farmers with an accessible,
searchable and source-backed agricultural information assistant.

**Developed by Sumit Gorakshanath Shinde**  
Sanjivani University – SJ-09 Agriculture

## RAG Evaluation Results

Evaluation ran on 18 November 2026 (UTC timestamp: 2026-11-18T01:01:47Z) using isolated Chroma indexes and the local embedding model. The existing persistent collection was not changed. Groq was explicitly selected for this run using the existing `GROQ_API_KEY`; the `.env` provider setting was left untouched. Twelve of the 13 answerable questions failed during RAG answer generation with `RAGError`, so the answer evaluation is incomplete and no winner is selected.

| Metric | Configuration A | Configuration B |
|---|---:|---:|
| Chunk size | 400 | 600 |
| Top-k | 3 | 5 |
| Retrieval hit rate | 84.62% | 100.0% |
| Answer correctness | 66.67% (2/3 completed responses) | 66.67% (2/3 completed responses) |
| Citation correctness | 66.67% (2/3 completed responses) | 66.67% (2/3 completed responses) |
| Grounded answer rate | 0.0% (0/1 completed answerable response) | 0.0% (0/1 completed answerable response) |
| Correct abstention rate | 100.0% (2/2) | 100.0% (2/2) |
| Unsupported-answer rate | 0.0% (0/2) | 0.0% (0/2) |
| Groq answer calls completed / failed | 1 / 12 | 1 / 12 |
| Q6 refusal correctness | True | True |
| Mean retrieval latency | 21.34 ms | 20.37 ms |

**Winning configuration:** Pending. Both configurations failed to complete all 15 answer evaluations. Config B had the higher retrieval hit rate, but answer quality is not comparable enough to select a winner.

The completed-response correctness metrics use only successful answer evaluations; failed API calls are excluded from score denominators and listed in the result JSON. Each configuration completed three answer evaluations: the two deterministic abstentions (Q6 and Q10) plus Q9, which returned “I don't know.” despite retrieving DOGR chunks. Q9 failed answer correctness, citation correctness, and groundedness scoring and needs manual review. The other 12 failed answer evaluations are Q1–Q5, Q7–Q8, and Q11–Q15.

Evaluation materials: [dataset](eval/eval_set.json), [runner](eval/run_eval.py), [Configuration A results](eval/results_config_a.json), [Configuration B results](eval/results_config_b.json), and [summary](eval/evaluation_summary.md). Answer correctness uses at least 60% expected-keyword coverage as a transparent proxy, not objective ground truth. Citation correctness checks cited chunk IDs, source matches, and expected sources. Groundedness additionally checks expected-keyword coverage in retrieved context. See the summary for full scoring and winner criteria.

To repeat the Groq evaluation in PowerShell (with `GROQ_API_KEY` configured):

```powershell
$env:LLM_PROVIDER = "groq"
.\myenv\Scripts\python.exe eval/run_eval.py
```

The evaluator refuses to switch providers. Offline scoring tests use mocks and do not make paid calls:

```powershell
.\myenv\Scripts\python.exe -m unittest eval.test_run_eval
```
