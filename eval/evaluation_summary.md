# RAG evaluation summary

Evaluation timestamp (UTC): 2026-11-18T01:01:47+00:00. Both configurations use isolated temporary Chroma indexes; the existing persistent collection is untouched. The evaluation set contains the original 15 questions.

| Metric | Configuration A | Configuration B |
|---|---:|---:|
| Chunk size | 400 words | 600 words |
| Top-k | 3 | 5 |
| Questions | 15 | 15 |
| Retrieval hit rate | 84.62% | 100.0% |
| Answer correctness (scored responses) | 66.67% (2/3) | 66.67% (2/3) |
| Citation correctness (scored responses) | 66.67% (2/3) | 66.67% (2/3) |
| Grounded answer rate (successful answerable responses) | 0.0% (0/1) | 0.0% (0/1) |
| Correct abstention rate (successful unanswerable responses) | 100.0% (2/2) | 100.0% (2/2) |
| Unsupported-answer rate (unanswerable questions) | 0.0% | 0.0% |
| Groq answer calls completed / failed | 1 / 12 | 1 / 12 |
| All answer evaluations completed / failed / skipped | 3 / 12 / 0 | 3 / 12 / 0 |
| Q6 exact refusal | True | True |
| Mean retrieval latency | 21.34 ms | 20.37 ms |
| Failed or skipped questions | failed: Q1 (RAGError), Q2 (RAGError), Q3 (RAGError), Q4 (RAGError), Q5 (RAGError), Q7 (RAGError), Q8 (RAGError), Q11 (RAGError), Q12 (RAGError), Q13 (RAGError), Q14 (RAGError), Q15 (RAGError) | failed: Q1 (RAGError), Q2 (RAGError), Q3 (RAGError), Q4 (RAGError), Q5 (RAGError), Q7 (RAGError), Q8 (RAGError), Q11 (RAGError), Q12 (RAGError), Q13 (RAGError), Q14 (RAGError), Q15 (RAGError) |

## Winner

**Pending.** At least one configuration did not complete all 15 Groq answer evaluations without errors.

## Scoring and comparison method

- **Retrieval hit:** at least one retrieved chunk has a URL in that question's `expected_sources`; denominator is all 13 answerable questions.
- **Answer correctness:** for answerable questions, at least 60% of manually prepared `expected_keywords` appear in the answer; for the two unanswerable questions, only the exact `I don't know.` is correct. This is a transparent keyword/refusal proxy, not semantic ground truth.
- **Citation correctness:** every citation must reference a retrieved chunk ID, match that chunk's source, and use an expected source. Missing citations fail the citation check.
- **Supported by retrieved context:** at least 60% of expected keywords occur in retrieved chunk text. A grounded answer must also pass answer correctness and citation correctness. This is not claim-level entailment.
- **Correct abstention:** exact `I don't know.` for each unanswerable question, denominator 2. Failed calls do not count as correct.
- **Winner:** both runs must complete all 15 answer evaluations without errors. Then compare the unweighted mean of answer correctness, citation correctness, grounded answers, and correct abstention. Retrieval hit rate breaks a primary-score tie; lower unsupported-answer rate breaks the next tie. If all tie, report a tie.

Errors and exception type chains are recorded per question in the JSON results. Failed calls are excluded from answer metric denominators and cannot count as successful answers; the completed/failed counts show coverage. Retrieval-only runs leave answer metrics pending and do not select a winner.

See [the evaluation dataset](eval_set.json), [Configuration A results](results_config_A.json), and [Configuration B results](results_config_B.json).
