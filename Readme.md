
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

Evaluation ran on 19 November 2026 (UTC timestamp: 2026-11-19T01:47:07Z) across the original 15 questions using isolated Chroma indexes and the local embedding model. The persistent collection was not changed. `GROQ_API_KEY` was available and Groq was explicitly selected for this run; 12 of 13 answerable calls per configuration failed with `APIConnectionError`. The key was not printed or included in the results. Answer quality metrics and the winner remain Pending because both runs did not complete.

| Metric | Configuration A | Configuration B |
|---|---:|---:|
| Chunk size | 400 | 600 |
| Top-k | 3 | 5 |
| Retrieval hit rate | 84.62% | 100.0% |
| Answer correctness (all 15 questions) | Pending | Pending |
| Citation correctness (all 15 questions) | Pending | Pending |
| Grounded answer rate (all 13 answerable questions) | Pending | Pending |
| Correct abstention rate | 100.0% (2/2) | 100.0% (2/2) |
| Unsupported-answer rate | 0.0% (0/2) | 0.0% (0/2) |
| Groq answer calls completed / failed | 1 / 12 | 1 / 12 |
| All answer evaluations completed / failed / skipped | 3 / 12 / 0 | 3 / 12 / 0 |
| Q6 refusal correctness | True | True |
| Mean retrieval latency | 16.03 ms | 16.03 ms |

**Winning configuration:** Pending. The selection rule requires all 15 answer evaluations to complete in both configurations. Config B has a higher retrieval hit rate, but incomplete Groq evaluations prevent a quality comparison.

Each configuration completed three responses: deterministic abstentions Q6 and Q10, and Q9, which returned "I don't know." despite retrieving DOGR chunks. Q9 is an incorrect abstention for an answerable question. The other 12 answerable questions (Q1-Q5, Q7-Q8, Q11-Q15) failed with `APIConnectionError`. Partial response observations remain in the per-question results and are not presented as complete aggregate answer or citation scores.

Evaluation materials: [dataset](eval/eval_set.json), [runner](eval/run_eval.py), [Configuration A results](eval/results_config_a.json), [Configuration B results](eval/results_config_b.json), and [summary](eval/evaluation_summary.md). Answer correctness uses at least 60% expected-keyword coverage as a transparent proxy, not objective ground truth. Citation correctness checks cited chunk IDs, source matches, and expected sources. Groundedness also checks expected-keyword coverage in retrieved context. See the summary for full scoring and winner criteria.

To repeat the Groq evaluation in PowerShell (with `GROQ_API_KEY` configured):

```powershell
$env:LLM_PROVIDER = "groq"
.\myenv\Scripts\python.exe eval/run_eval.py
```

The evaluator refuses to switch providers. Offline scoring tests use mocks and do not make paid calls:

```powershell
.\myenv\Scripts\python.exe -m unittest eval.test_run_eval
```

## Checkpoint 2 — Streamlit farming assistant

KandaGuide includes a Streamlit frontend connected to the existing FastAPI
backend. The sidebar provides Chat, Season-to-variety picker, and About pages,
and reports backend health. Chat supports the source-grounded `/ask` RAG route
and the existing `/agent` workflow when its route is available. Messages and
citations remain visible for the current Streamlit session.

The picker reads `data/records.json` directly. It filters the verified season
labels (including records suitable for multiple seasons), supports onion and
garlic filters, and sorts explicit numeric storage durations before records
without comparable month values. Maturity text is shown with the original
planting, sowing, or transplanting wording. Only explicit numeric storage
durations receive a “Stores up to N months” badge; qualitative keeping-quality
descriptions and loss-study intervals are not converted to durations. Each
variety card links to its recorded source URL.

Assistant feedback is stored locally in `data/feedback.sqlite`. Each response
can receive one thumbs-up or thumbs-down vote with an optional comment. The
database does not store API credentials. `.env` is ignored by Git; start from
`.env.example` to configure local settings.

### Install and run

From the project root, install dependencies (including Streamlit):

```powershell
python -m pip install -r requirements.txt
```

Set `API_BASE_URL` to the FastAPI base URL when it differs from the default
`http://127.0.0.1:8000`. For model-backed chat, configure the existing provider
variables described in [LLM integration](docs/llm-integration.md). Start the
backend and frontend in separate terminals:

```powershell
python -m uvicorn app.main:app --reload
```

```powershell
python -m streamlit run ui/app.py
```

The backend routes used by the frontend are:

| Method | Route | Request body | Frontend use |
|---|---|---|---|
| GET | `/health` | — | Backend connection status |
| GET | `/openapi.json` | — | Detect whether `/agent` is available |
| POST | `/ask` | `{"question": "..."}` | RAG answer and citations (`answer`, `citations`, `confidence`, `follow_up`) |
| POST | `/agent` | `{"message": "...", "thread_id": "...", "approval": null}` | Agent answer, citations, tools, and workflow status |

The frontend does not synthesize citations: it displays citations returned by
the backend and clearly marks answers without returned sources. Backend
timeouts, unavailable routes, and invalid response bodies produce an error
message while preserving the chat history. Agent mode is offered when the API
schema advertises `/agent`; runtime errors from unavailable agent dependencies
are reported in chat.

### Checkpoint 2 demo screenshot

The screenshot below is captured from the running Streamlit application:

![KandaGuide Checkpoint 2 Demo](docs/screenshots/checkpoint-2.png)
