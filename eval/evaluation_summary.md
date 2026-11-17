# RAG evaluation summary

Evaluation date: generated at execution time. The script evaluates each configuration in its own temporary Chroma directory and deletes that directory afterward; the existing persistent collection is untouched.

| Metric | Configuration A | Configuration B |
|---|---:|---:|
| Chunk size | 400 words | 600 words |
| Top-k | 3 | 5 |
| Questions evaluated | 15 | 15 |
| Answerable / unanswerable | 13 / 2 | 13 / 2 |
| Retrieval hit rate | 84.62% | 100.0% |
| Citation accuracy | Pending | Pending |
| Answer correctness proxy | Pending | Pending |
| Unsupported-answer rate | 0.0% | 0.0% |
| Q6 refusal correct | True | True |
| Average retrieval latency | 30.13 ms | 29.84 ms |
| Execution errors | 12 | 12 |

## Winner

**Pending actual LLM evaluation.** Retrieval measurements are available, but generated-answer and citation metrics could not be completed because the configured LLM provider was unavailable.

The answer-correctness figure is keyword coverage against the dataset's manually written keywords. It is a reproducible screening proxy, not an LLM judge and not objective ground truth. Citation accuracy checks that every citation matches a retrieved chunk and an expected source. Retrieval hit rate checks whether any expected source URL was retrieved for an answerable row. Unsupported-answer rate is the share of unanswerable rows that received anything other than the exact refusal.

See [the evaluation dataset](eval_set.json), [Configuration A results](results_config_a.json), and [Configuration B results](results_config_b.json).
