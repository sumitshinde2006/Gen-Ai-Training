# KandaGuide — Checkpoint 1

## Objectives

- Document core LLM and RAG concepts in accessible language.
- Explain the existing TF-IDF and cosine-similarity search implementation.
- Record ten realistic onion and garlic farmer questions and whether the
  current searchable records can answer them.
- Verify the existing FastAPI endpoints using actual HTTP requests.
- Preserve the completed Day 1–Day 4 files and project structure.

## Files created or modified

**Created**

- `docs/how_llms_work.md` — LLM/RAG learning notes, the planned workflow
  diagram, `smart_search()` explanation, and Q1–Q10 with coverage notes.
- `docs/checkpoint-1.md` — this checkpoint summary and run instructions.
- `docs/checkpoint-1-test-results.md` — actual automated HTTP test results.

**Modified**

- `Readme.md` — added Checkpoint 1 progress, documentation links, and
  clarified FastAPI run instructions.

No application source code or existing data files were changed. The
existing Day 1–Day 4 work and dataset were retained.

## API endpoints tested

The tests were sent to the running FastAPI server. All expected responses
were received:

| Endpoint | Expected response | Result |
|---|---|---|
| `GET /` | 200 and welcome JSON | PASS |
| `GET /health` | 200 and health JSON | PASS |
| `GET /records` | 200 and a records JSON list | PASS (17 records) |
| `GET /records/1` | 200 and the first variety record | PASS (`Bhima Light Red`) |
| `GET /records/999` | 404 and `Variety not found` detail | PASS |
| `GET /search?q=Bhima` | 200 and search JSON | PASS (5 results) |
| `POST /questions` | 200 and question acknowledgement | PASS |
| `GET /docs` | 200 and Swagger UI HTML | PASS |

An additional validation check posted an empty question and received HTTP
422. The question endpoint currently acknowledges receipt; it does not yet
generate AI answers.

The dependency installation command completed successfully, with
requirements already present in `myenv`. Uvicorn printed OpenBLAS
memory-allocation warnings at startup, but the actual HTTP checks,
including search, passed. See
[`checkpoint-1-test-results.md`](./checkpoint-1-test-results.md) for the
recorded statuses and response details.

## How `smart_search()` works

[`smart_search()`](../app/smart_search.py) calls `load_records()` from
[`app/records.py`](../app/records.py) to load `data/records.json`. It
creates one search string per variety from its name, category, season,
maturity, yield, and storage fields. `TfidfVectorizer` turns those strings
and the query into weighted word and two-word-phrase vectors. Cosine
similarity compares the query vector with each record vector; results are
sorted from highest to lowest score. Zero-score matches are skipped, and
up to `top_k` records are returned with a similarity score.

This helps farmers find matching variety information quickly, but a
similarity score is not a fact check or personalized recommendation. The
longer explanation and code example are in
[`how_llms_work.md`](./how_llms_work.md).

## Run FastAPI

From the repository root in Windows PowerShell:

```powershell
myenv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

If PowerShell activation is restricted, run the environment executables
directly:

```powershell
.\myenv\Scripts\python.exe -m pip install -r requirements.txt
.\myenv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open Swagger UI at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Capture a Swagger UI screenshot

1. Start the API using one of the command sequences above.
2. Open `http://127.0.0.1:8000/docs` in a browser.
3. Wait for the Swagger UI page to finish loading.
4. Capture the page using the operating system screenshot shortcut or
   browser screenshot feature.
5. Save the screenshot in the location required for the project submission.

No screenshot was captured or added as part of this checkpoint.

## Farmer questions

No original six farmer questions were found in the existing tracked
documentation or source files, and none appeared in the repository issue
search. Therefore Q1–Q6 in the linked LLM documentation are new questions,
not reused wording. Q1–Q10 cover variety selection, seasons, maturity,
yield, storage, cultivation practices, and recommendations.

**Q6 is intentionally unanswerable:** “What is today's onion mandi price
per quintal in Lasalgaon?” The current dataset does not contain live mandi
prices, and KandaGuide must not invent one. The complete question list and
coverage notes are in [`how_llms_work.md`](./how_llms_work.md).

## Limitations and future work

- Search currently uses TF-IDF and cosine similarity over variety-record
  fields; it does not index the MANAGE reference text.
- The `/questions` endpoint only acknowledges a submitted question.
- Complete LLM/RAG retrieval, source-grounding, and citation behavior are
  not implemented.
- The dataset has no live mandi prices. Its availability or completeness
  must not be assumed for questions it does not cover.
- `smart_search()` is a textual search aid, not a personalized
  agronomic recommendation or verification system.
- Uvicorn emitted OpenBLAS memory-allocation warnings in this environment
  despite the successful endpoint checks; the environment warning should
  be investigated if it persists in normal use.

Future work includes indexing verified source documents, recording
retrieval citations, adding explicit unavailable-information behavior,
and validating any LLM answer against retrieved source text before showing
it to farmers.
