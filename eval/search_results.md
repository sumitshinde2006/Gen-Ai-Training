# KandaGuide semantic search evaluation

## Status: completed

- **Run date:** 2026-11-15
- **API:** `GET /search/semantic`, `top_k=3`; all ten requests returned HTTP 200.
- **Embedding model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Chroma collection:** `kandaguide_knowledge`
- **Persistent database:** `data/chroma/`
- **Source documents processed:** 3 (2 HTML and 1 PDF; the text sidecar is an
  exact normalized duplicate of the PDF extraction and was not indexed twice)
- **Chunks indexed:** 233
- **Score:** Chroma cosine distance; smaller values are closer vector matches,
  not confidence or proof that a source answers the question.
- **Repeatability:** These are the recorded results from one run. Chroma's
  approximate HNSW ranking can vary slightly after an index rebuild.

The entries below are the actual top-three API results. Chunk text is
summarized rather than reproduced; the API returns the full chunk text.

### Source identifiers

- **DOGR varieties:** <https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit>
- **DOGR garlic:** <https://dogr.res.in/index.php/component/content/article/garlicagropedia?layout=edit>
- **MANAGE PDF:** <https://www.manage.gov.in/publications/eBooks/Good%20Agricultural%20Practices%20in%20Onion%20and%20Garlic.pdf>

## Q1 — Which onion varieties in the dataset are listed for the Rabi season?

| Rank | Chunk ID | Source | Page | Document title | Distance | Relevance assessment |
|---:|---|---|---:|---|---:|---|
| 1 | `478173282c2516e7a7c07e09e02883d96a49dd0cf5b7c4b04255892164b2d3b6` | MANAGE PDF | 81 | Good Agricultural Practices in Onion and Garlic Production | 0.320656 | Broad onion-variety table; useful names, but not a complete Rabi answer by itself. |
| 2 | `b35873edfc253b085e90a0ead69c288ffd280538ce45f5ac8d2f45d5341b7ce5` | DOGR varieties | null | Varieties Developed | 0.331287 | Bhima Light Red variety card includes its Rabi season. |
| 3 | `8c625f0ceb72ce48813d2eadde34517f6da8b656b606a918b3dc9d5435829e43` | DOGR varieties | null | Varieties Developed | 0.334830 | Bhima Prasanskaran variety card includes Rabi details. |

**Assessment:** Related chunks were retrieved, but these results are not an
exhaustive list of all Rabi varieties in the dataset.

## Q2 — Which garlic varieties are listed, and what yield and storage-life values does the dataset record for each?

| Rank | Chunk ID | Source | Page | Document title | Distance | Relevance assessment |
|---:|---|---|---:|---|---:|---|
| 1 | `17b23a0906dd9c0b8d37d37227c17189032e4d221cc2922ffb8c38b2a7632862` | DOGR garlic | null | garlicagropedia | 0.329495 | Garlic-variety section with variety and production details; relevant, but compare values to the specific dataset record before answering. |
| 2 | `cefa48d1e78319e93b33368432549fb1415a29c02fe3f72f31e2b0cfa34014b9` | MANAGE PDF | 85 | Good Agricultural Practices in Onion and Garlic Production | 0.365468 | Image-caption/variety comparison context; not yield and storage values. |
| 3 | `3e6d7bc2ab148dac4aa3554c2cec369b1a4fef6c931eb66169a5cae77dc022bc` | DOGR garlic | null | garlicagropedia | 0.385493 | Garlic cultivation section index; broadly related, not the requested values. |

**Assessment:** The top result is relevant to garlic varieties, while the
other two do not directly answer the yield/storage part.

## Q3 — Which onion varieties are listed for the Kharif season?

| Rank | Chunk ID | Source | Page | Document title | Distance | Relevance assessment |
|---:|---|---|---:|---|---:|---|
| 1 | `478173282c2516e7a7c07e09e02883d96a49dd0cf5b7c4b04255892164b2d3b6` | MANAGE PDF | 81 | Good Agricultural Practices in Onion and Garlic Production | 0.304722 | Broad onion-variety table; related but not sufficient alone to identify Kharif entries. |
| 2 | `a4093fd6b6838f520cd2e9a306380af40977c86e56f40ef0de642047f7c307b0` | MANAGE PDF | 26 | Good Agricultural Practices in Onion and Garlic Production | 0.325628 | Chapter introduction to improved onion varieties; general context. |
| 3 | `e0d960df7459a73065cab10502486e2fc9242731fcc1278bd2a14b275671120a` | MANAGE PDF | 80 | Good Agricultural Practices in Onion and Garlic Production | 0.330942 | Specifically discusses Kharif onion varieties; strongest direct match. |

**Assessment:** The third result is directly useful; the top two are broader
context and a chapter heading.

## Q4 — What maturity period is recorded for Bhima Light Red onion?

| Rank | Chunk ID | Source | Page | Document title | Distance | Relevance assessment |
|---:|---|---|---:|---|---:|---|
| 1 | `b35873edfc253b085e90a0ead69c288ffd280538ce45f5ac8d2f45d5341b7ce5` | DOGR varieties | null | Varieties Developed | 0.231307 | Exact Bhima Light Red variety card, including maturity information. |
| 2 | `50dc14caaecc4f9331742bf2ead189227e953561f1086c1a99dda246c3865515` | DOGR varieties | null | Varieties Developed | 0.303953 | Another onion variety card; not Bhima Light Red. |
| 3 | `81edc26fb616a8b787d41a64ec693f3374624f2761238ebb7cddc89f78cebc54` | DOGR varieties | null | Varieties Developed | 0.354019 | Bhima Kiran variety card; not the requested variety. |

**Assessment:** The top result is an exact variety match; lower-ranked results
are related onion records but should not be used for this answer.

## Q5 — What yield value is recorded for Bhima Light Red onion?

| Rank | Chunk ID | Source | Page | Document title | Distance | Relevance assessment |
|---:|---|---|---:|---|---:|---|
| 1 | `b35873edfc253b085e90a0ead69c288ffd280538ce45f5ac8d2f45d5341b7ce5` | DOGR varieties | null | Varieties Developed | 0.279979 | Exact Bhima Light Red variety card, including its recorded yield. |
| 2 | `41ad1a3a3273cc8fddc9261742a5afb7e46127a257d3bb54ac6670ff608d789d` | MANAGE PDF | 168 | Good Agricultural Practices in Onion and Garlic Production | 0.280120 | Onion field-demonstration results, not the requested variety record. |
| 3 | `ecd45a5bbf4c0faf8e954d679558e04298235cde0399a24195983cb6588ef315` | MANAGE PDF | 167 | Good Agricultural Practices in Onion and Garlic Production | 0.306180 | Onion field-demonstration results; not a direct Bhima Light Red yield entry. |

**Assessment:** The top result directly matches the requested variety; the
other chunks are related to onion yields but not to this specific record.

## Q6 — What is today's onion mandi price per quintal in Lasalgaon?

| Rank | Chunk ID | Source | Page | Document title | Distance | Relevance assessment |
|---:|---|---|---:|---|---:|---|
| 1 | `0a5e5dbad76c0e16788b6f7a96b41a3045ebd89ba40f94a0c027896dcd924361` | MANAGE PDF | 136 | Good Agricultural Practices in Onion and Garlic Production | 0.402699 | Discusses historical Maharashtra market-price data from 2016–2018; not today's Lasalgaon price. |
| 2 | `71951bb854ae266197893dd31703b9709c83c9bcd1b03facf73abb2d83007e00` | MANAGE PDF | 162 | Good Agricultural Practices in Onion and Garlic Production | 0.462137 | Mentions price changes in a production context; no current mandi quote. |
| 3 | `ecd45a5bbf4c0faf8e954d679558e04298235cde0399a24195983cb6588ef315` | MANAGE PDF | 167 | Good Agricultural Practices in Onion and Garlic Production | 0.465666 | Onion demonstration data; not a mandi-price source. |

**Q6 limitation:** The closest result is historical and does not provide a
current Lasalgaon price. A similarity match does not prove that the requested
answer exists. Live mandi prices remain unavailable in this dataset; no price
is inferred or supplied.

## Q7 — What storage-life information is recorded for Bhima Kiran onion?

| Rank | Chunk ID | Source | Page | Document title | Distance | Relevance assessment |
|---:|---|---|---:|---|---:|---|
| 1 | `81edc26fb616a8b787d41a64ec693f3374624f2761238ebb7cddc89f78cebc54` | DOGR varieties | null | Varieties Developed | 0.387022 | Exact Bhima Kiran variety card, including storage information. |
| 2 | `ea3134a101b5e5583dfa4d759eb81230f719106b2d8ee702666a53dcfa859cbd` | MANAGE PDF | 169 | Good Agricultural Practices in Onion and Garlic Production | 0.407137 | Mentions Bhima Kiran in demonstration results, but not its storage life. |
| 3 | `b35873edfc253b085e90a0ead69c288ffd280538ce45f5ac8d2f45d5341b7ce5` | DOGR varieties | null | Varieties Developed | 0.413371 | Bhima Light Red record; wrong variety. |

**Assessment:** The top result is a direct match. The other results demonstrate
that a close vector distance can still return a different fact or variety.

## Q8 — Which cultivation practices for onion and garlic should I follow on my farm?

| Rank | Chunk ID | Source | Page | Document title | Distance | Relevance assessment |
|---:|---|---|---:|---|---:|---|
| 1 | `285c0234ca45db37f59bcf7ddf89f6b0f219cc2627ceaea98f78db05b0ac66d4` | MANAGE PDF | 2 | Good Agricultural Practices in Onion and Garlic Production | 0.194263 | Cover/title material; the low distance is not an answer with cultivation steps. |
| 2 | `609f890104d7d76534c5b77a86f636f7333c9a322546777a665c41cfa199fd33` | MANAGE PDF | 3 | Good Agricultural Practices in Onion and Garlic Production | 0.262989 | Publication and citation metadata; no specific practice. |
| 3 | `b157776cfeed964df6001fa5db6e8a4ac6c858217b9f09320b2b1cfbf1f87265` | MANAGE PDF | 114 | Good Agricultural Practices in Onion and Garlic Production | 0.271382 | Agricultural table content, but not a direct set of farm practices. |

**Assessment:** The actual top results are weak for this question. Do not treat
the document title or distance as a specific farm recommendation.

## Q9 — What region and season are recorded as recommended for Bhima Prasanskaran?

| Rank | Chunk ID | Source | Page | Document title | Distance | Relevance assessment |
|---:|---|---|---:|---|---:|---|
| 1 | `0d3c101768d971ee396627f73710799d524ac192845e3dfb45f147f0224bb37d` | MANAGE PDF | 84 | Good Agricultural Practices in Onion and Garlic Production | 0.532192 | Registered-variety figure; not the Bhima Prasanskaran recommendation. |
| 2 | `eadf047df6bd1788e73ee16b5557c916e55699fa1a8fe8dadedf4e51742c8549` | DOGR varieties | null | Varieties Developed | 0.550330 | Bhima Super card; wrong variety. |
| 3 | `d3fa5300191b9f2b4683cceafaa57e78514111e8261fe7c2882ebb6f3cd2e8bb` | MANAGE PDF | 154 | Good Agricultural Practices in Onion and Garlic Production | 0.551422 | Demonstration information, not the requested recommendation. |

**Assessment:** The target variety's recommendation did not appear in the top
three. These results are insufficient to answer; retrieve more or improve
retrieval before presenting a recommendation.

## Q10 — Which onion variety should I choose for my field and local market?

| Rank | Chunk ID | Source | Page | Document title | Distance | Relevance assessment |
|---:|---|---|---:|---|---:|---|
| 1 | `a4093fd6b6838f520cd2e9a306380af40977c86e56f40ef0de642047f7c307b0` | MANAGE PDF | 26 | Good Agricultural Practices in Onion and Garlic Production | 0.376140 | Improved-varieties chapter; relevant background, not a local recommendation. |
| 2 | `d38aeb07ccd40739e53ee43213b0f2ab5a04739c0f4fc633317435dc457ce751` | MANAGE PDF | 18 | Good Agricultural Practices in Onion and Garlic Production | 0.394645 | General varietal-selection discussion; no field or current market assessment. |
| 3 | `975090e20534d16667abcd5a3e193837636c0029873ae930d316eb601aef9242` | MANAGE PDF | 17 | Good Agricultural Practices in Onion and Garlic Production | 0.399020 | General season/storage discussion, not a personalized choice. |

**Assessment:** Results provide general variety-selection context only.
KandaGuide has no field-condition or live local-market data to make the
requested personalized recommendation.

## Evaluation summary

The endpoint returned three real chunks for every question and preserved
source, page, title, chunk ID, and distance. Q4, Q5, and Q7 retrieved their
exact DOGR variety records at rank 1. Q1 and Q3 retrieved useful season and
variety material but not a guaranteed exhaustive list. Q2 retrieved a
relevant garlic page, with other results less direct. Q8 and Q9 show
important relevance failures; Q10 returns general selection material but
cannot support a personalized decision.

Q6 retrieves historical market material, not live Lasalgaon mandi data.
Semantic similarity is only a ranking signal: it must not be used to
manufacture a current price or treat a weak match as proof.
