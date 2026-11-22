# RAG evaluation summary

Evaluation timestamp (UTC): 2026-11-22T00:53:27+00:00. Both configurations use isolated temporary Chroma indexes; the existing persistent collection is untouched. The evaluation set contains the original 15 questions.

| Metric | Configuration A | Configuration B |
|---|---:|---:|
| Chunk size | 400 words | 600 words |
| Top-k | 3 | 5 |
| Questions | 15 | 15 |
| Retrieval hit rate | 84.62% | 100.0% |
| Answer correctness (all 15 questions) | 40.0% | 53.33% |
| Citation correctness (all 15 questions) | 26.67% | 26.67% |
| Grounded answer rate (all answerable questions) | 7.69% | 7.69% |
| Correct abstention rate (both unanswerable questions) | 100.0% (2/2) | 100.0% (2/2) |
| Unsupported-answer rate (unanswerable questions) | 0.0% | 0.0% |
| Groq answer calls completed / failed | 13 / 0 | 13 / 0 |
| All answer evaluations completed / failed / skipped | 15 / 0 / 0 | 15 / 0 / 0 |
| Partial completed-response observations | 6/15 passed the answer proxy; grounded 1/13 | 8/15 passed the answer proxy; grounded 1/13 |
| Q6 exact refusal | True | True |
| Mean retrieval latency | 26.94 ms | 27.23 ms |
| Failed or skipped questions | None | None |

## Winner

**Configuration B.** It had the higher primary quality score (43.59% vs. 46.92%).

## Scoring and comparison method

- **Retrieval hit:** at least one retrieved chunk has a URL in that question's `expected_sources`; denominator is all 13 answerable questions.
- **Answer correctness:** for answerable questions, at least 60% of manually prepared `expected_keywords` appear in the answer; for the two unanswerable questions, only the exact `I don't know.` is correct. This is a transparent keyword/refusal proxy, not semantic ground truth.
- **Citation correctness:** every citation must reference a retrieved chunk ID, match that chunk's source, and use an expected source. Missing citations fail the citation check.
- **Supported by retrieved context:** at least 60% of expected keywords occur in retrieved chunk text. A grounded answer must also pass answer correctness and citation correctness. This is not claim-level entailment.
- **Correct abstention:** exact `I don't know.` for each unanswerable question, denominator 2. Failed calls do not count as correct.
- **Winner:** both runs must complete all 15 answer evaluations without errors. Then compare the unweighted mean of answer correctness, citation correctness, grounded answers, and correct abstention. Retrieval hit rate breaks a primary-score tie; lower unsupported-answer rate breaks the next tie. If all tie, report a tie.

Errors and exception type chains are recorded per question in the JSON results. Failed calls are excluded from answer metric denominators and cannot count as successful answers; the completed/failed counts show coverage. Retrieval-only runs leave answer metrics pending and do not select a winner.

See [the evaluation dataset](eval_set.json), [Configuration A results](results_config_a.json), and [Configuration B results](results_config_b.json).
