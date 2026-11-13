# Checkpoint 1 — Automated API Test Results

These results were collected by sending HTTP requests to the running
FastAPI server at `http://127.0.0.1:8000`. They are not estimates.

## Environment and command

- Python environment: repository `myenv` (Python 3.11.7).
- Dependency command: `.\myenv\Scripts\python.exe -m pip install -r requirements.txt`
- Result: success; all requirements were already installed.
- Server command used:
  `.\myenv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`

## HTTP checks

| Request | Expected | Actual | Result |
|---|---:|---:|---|
| `GET /` | 200 | 200 | PASS |
| `GET /health` | 200 | 200 | PASS |
| `GET /records` | 200 | 200 | PASS |
| `GET /records/1` | 200 | 200 | PASS |
| `GET /records/999` | 404 | 404 | PASS |
| `GET /search?q=Bhima` | 200 | 200 | PASS |
| `POST /questions` with a valid question | 200 | 200 | PASS |
| `POST /questions` with an empty question | 422 | 422 | PASS |
| `GET /docs` | 200 | 200 | PASS |

Observed response details:

- `GET /` returned JSON linking to `/docs` and `/health`.
- `GET /health` returned `{"status":"OK","message":"KandaGuide API is running"}`.
- `GET /records` returned all 17 records (`total: 17`, `returned: 17`).
- `GET /records/1` returned the `Bhima Light Red` record.
- `GET /records/999` returned `{"detail":"Variety not found"}`.
- `GET /search?q=Bhima` returned 5 matching results.
- A valid `POST /questions` returned the submitted question with status
  `received`; it did not generate an agricultural answer.
- An empty `question` was rejected with HTTP 422 by request validation.
- `GET /docs` returned Swagger UI HTML.

The successful HTTP checks verified the app imports, record loading, and
the search path using the installed project dependencies. Uvicorn also
printed OpenBLAS memory-allocation warnings during startup in this
environment; the tested endpoints, including search, still returned the
expected responses. No code change was made for that environment warning.
