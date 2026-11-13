# Prompt comparison: KandaGuide V1 and V2

## Status: actual model comparison pending

No model calls have been made for this evaluation. No provider credentials
were used, and no model outputs or scores are fabricated. Each answer and
score cell below remains pending until both prompt versions are run with
the same provider/model and retrieved context.

Use the exact farmer questions from
[`docs/how_llms_work.md`](../docs/how_llms_work.md). For each question,
provide the same retrieved context to V1 and V2, record the verbatim
answers, and score each category from 1 (Poor) to 5 (Excellent). For
hallucination risk, 5 means very low risk and 1 means high risk. Record
the model ID, date, and retrieval context when executing this evaluation.

| ID | Exact farmer question | Prompt V1 answer | Prompt V2 answer | V1 scores: factual / grounding / complete / clear / low hallucination risk | V2 scores: factual / grounding / complete / clear / low hallucination risk |
|---|---|---|---|---|---|
| Q1 | Which onion varieties in the dataset are listed for the Rabi season? | Pending | Pending | Pending | Pending |
| Q2 | Which garlic varieties are listed, and what yield and storage-life values does the dataset record for each? | Pending | Pending | Pending | Pending |
| Q3 | Which onion varieties are listed for the Kharif season? | Pending | Pending | Pending | Pending |
| Q4 | What maturity period is recorded for Bhima Light Red onion? | Pending | Pending | Pending | Pending |
| Q5 | What yield value is recorded for Bhima Light Red onion? | Pending | Pending | Pending | Pending |
| Q6 | What is today's onion mandi price per quintal in Lasalgaon? | Pending — must explicitly admit live mandi prices are unavailable in the dataset. | Pending — must explicitly admit live mandi prices are unavailable in the dataset. | Pending | Pending |
| Q7 | What storage-life information is recorded for Bhima Kiran onion? | Pending | Pending | Pending | Pending |
| Q8 | Which cultivation practices for onion and garlic should I follow on my farm? | Pending | Pending | Pending | Pending |
| Q9 | What region and season are recorded as recommended for Bhima Prasanskaran? | Pending | Pending | Pending | Pending |
| Q10 | Which onion variety should I choose for my field and local market? | Pending | Pending | Pending | Pending |

## Conclusion

There are no actual comparison results yet, so neither prompt can be
selected as more suitable based on evidence. V1 is configured as the
application default because it is designed to be conservative and
evidence-first; this is a design choice, not a result of an executed
evaluation. In particular, Q6 must be scored on whether the answer clearly
admits that current Lasalgaon mandi prices are absent and does not invent a
price.
