# KandaGuide Progress

## Historical milestones

The existing project history is retained here; deployment and CI statements below are historical entries from the project README, not a new live-service verification.
The prior Day 14 checklist marked every item complete; the release and validation statuses below were rechecked rather than carried forward as current evidence.

- [x] Day 1-4: Python introduction, variety records and operations, data ingestion, FastAPI, and smart search.
- [x] Checkpoint 1: LLM/RAG learning documentation and recorded HTTP checks for the existing API.
- [x] Checkpoint 2: Streamlit farming-assistant milestone and its recorded test/demo materials.
- [x] Semantic-search milestone: HTML/PDF chunking, source/page metadata, sentence-transformer embeddings, and persistent Chroma indexing.
- [x] Agentic-AI milestone: structured request planning, deterministic calculation tools, LangGraph routing, and approval flow.
- [x] CI/deployment configuration: GitHub Actions, Docker, Docker Compose, and Render configuration are present. The README records a historical API health check; it explicitly says the public UI URL was not verified.

## Day 14 verification

- [x] Inspected the implementation, source data, existing task record, branch, remote, history, and tags.
- [x] Rewrote `docs/interview.md` with the project pitch, an evidence-bounded data/provenance challenge, and ten implementation-grounded Q&As.
- [x] Ran `python -m pytest -q`: **120 passed**, one Starlette/AnyIO deprecation warning.
- [x] Ran `python -m ruff check .`: **passed**.
- [x] Ran the credentialed Groq evaluation (`eval/run_eval.py`): both 15-question configurations completed; no answer evaluations failed or were skipped. Latest metrics and scoring limitations are recorded in `eval/evaluation_summary.md`.
- [ ] Build the Docker image locally: **blocked** because the Docker CLI could not connect to `dockerDesktopLinuxEngine`; the Docker daemon was unavailable.
- [x] Inspected the existing `final` tag. The local and remote tag already point to commit `91da6990b2895e70a00bfb530e25395c806936ce`. It is being left untouched; moving an existing remote tag would require rewriting the tag and is not authorized by the current instructions.
- [x] Created and pushed Day 14 documentation/evaluation commit `9a623652e21938d412e2628c49f5da4e995dbaf4` (`day-14: complete KandaGuide interview documentation`). The `origin/main` ref was verified at that commit before this tracker update.
- [ ] Retarget `final` to the new Day 14 commit: not done because the existing remote tag would have to be rewritten, and no authorization to replace it was given.

## Data quality and evaluation limitations

- The DOGR and NHB structured records preserve a record-level source URL, and some values retain season/reference wording. The current record shape does not preserve exact source and season metadata independently for every numeric claim.
- `app/ingest.py` converts common `q/ha` and `quintals/ha` text to `t/ha`, but the yield values remain strings and source/trial conditions are not normalized into claim-level fields.
- The document chunker preserves source, title, and PDF page, but retrieval does not automatically reconcile conflicting agricultural claims.
- The latest RAG evaluation uses expected-keyword and citation-matching proxies, not semantic or claim-level verification. It reported weak citation correctness and grounded-answer scores despite strong retrieval and answer-keyword scores; see `eval/evaluation_summary.md`.
- The existing worktree contains a pre-existing edit to `ui/app.py`. It is outside this documentation task and must not be included in the Day 14 commit.
