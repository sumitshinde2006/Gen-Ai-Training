# Prompt comparison: KandaGuide V1 and V2

## Status: comparison completed

- **Run date:** 2026-11-15
- **Provider/model:** Gemini / `gemini-3.5-flash-lite` (configured in the local
  `.env`; no credentials are recorded here)
- **Route:** All questions were sent to `POST /chat`. For this evaluation only,
  the prompt loader selected V1 or V2; the production route still defaults to
  V1.
- **Retries:** The first V2/Q2 request returned HTTP 503. Its retry returned
  HTTP 200; the successful retry is scored below.

The same question and deterministic top-five `smart_search()` results were
used for both prompt versions. Q6, Q8, and Q10 are handled by `/chat`'s
out-of-scope responses before retrieval or model generation, so those answers
are identical for both versions and do not test prompt behavior.

Scores are manual ratings from 1 (poor) to 5 (excellent), ordered as **factual /
grounding / complete / clear / low hallucination risk**. For hallucination
risk, 5 means very low risk. Ratings consider the returned top-five context,
not every record in the full dataset.

## Scores

| ID | V1 scores | V2 scores |
|---|---|---|
| Q1 | 5 / 5 / 2 / 4 / 4 | 5 / 5 / 2 / 4 / 4 |
| Q2 | 5 / 5 / 5 / 4 / 5 | 5 / 5 / 5 / 5 / 5 |
| Q3 | 5 / 5 / 2 / 4 / 4 | 5 / 4 / 3 / 5 / 4 |
| Q4 | 5 / 3 / 5 / 4 / 4 | 5 / 3 / 5 / 4 / 4 |
| Q5 | 5 / 3 / 5 / 4 / 4 | 5 / 3 / 5 / 4 / 4 |
| Q6 | 5 / 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 / 5 |
| Q7 | 5 / 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 / 5 |
| Q8 | 4 / 5 / 3 / 4 / 5 | 4 / 5 / 3 / 4 / 5 |
| Q9 | 5 / 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 / 5 |
| Q10 | 4 / 5 / 4 / 4 / 5 | 4 / 5 / 4 / 4 / 5 |
| **Mean** | **4.8 / 4.6 / 4.1 / 4.3 / 4.6** | **4.8 / 4.5 / 4.2 / 4.5 / 4.6** |

### Retrieved context

The following variety records were returned, in order, for each request that
reached the model. The same records were used for V1 and V2. Q6, Q8, and Q10
bypass retrieval in the route and therefore supplied no context to a model.

| ID | Retrieved records |
|---|---|
| Q1 | Bhima Prasanskaran; Bhima Shweta; Bhima Shakti; Bhima Raj; Bhima Red |
| Q2 | Bhima Prasanskaran; Bhima Purple; Bhima Omkar; Bhima Light Red; Bhima Kiran |
| Q3 | Bhima Shubra; Bhima Super; Bhima Red; Bhima Raj; Bhima Prasanskaran |
| Q4 | Bhima Light Red; Bhima Dark Red; Agrifound Dark Red; Bhima Red; Bhima Safed |
| Q5 | Bhima Light Red; Bhima Prasanskaran; Bhima Dark Red; Agrifound Dark Red; Bhima Red |
| Q6 | None; out-of-scope response |
| Q7 | Bhima Kiran; Bhima Light Red; Bhima Prasanskaran; Bhima Shakti; Bhima Safed |
| Q8 | None; out-of-scope response |
| Q9 | Bhima Prasanskaran; Bhima Purple; Bhima Safed; Bhima Dark Red; Bhima Light Red |
| Q10 | None; out-of-scope response |

Q1 and Q3 are incomplete because top-five retrieval does not include every
matching season record in the dataset. For Q4 and Q5, `/chat` appended the NHB
URL from an unrelated retrieved record in addition to the DOGR URL. The
variety-specific answer values are supported by the DOGR record, but the
extra citation is potentially misleading.

## Verbatim answers

### Q1 — Which onion varieties in the dataset are listed for the Rabi season?

**V1**
```text
Based on the available records, the onion varieties listed for the Rabi season (including those listed for multiple seasons containing Rabi) are: Bhima Prasanskaran (Season: Rabi, https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit), Bhima Shweta (Season: Kharif Rabi, https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit), Bhima Shakti (Season: Rabi Late Kharif, https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit), Bhima Raj (Season: Kharif Late Kharif Rabi, https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit), and Bhima Red (Season: Kharif Late Kharif Rabi, https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit).
```

**V2**
```text
Based on the provided records, the following onion varieties are listed for the Rabi season: 1) Bhima Prasanskaran (Season: Rabi; Yield: 27.359 t/ha or 273.59 q/ha; Storage losses: 31.11% after 4 months; Source: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit). 2) Bhima Shweta (Season: Kharif Rabi; Maturity: 110-120 days after transplanting; Yield: 26-30 t/ha in Rabi; Storage life: up to 3 months for Rabi harvest; Source: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit). 3) Bhima Shakti (Season: Rabi Late Kharif; Maturity: 125-135 days after transplanting; Yield: 28-30 t/ha in Rabi; Storage life: 5-6 months; Source: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit). 4) Bhima Raj (Season: Kharif Late Kharif Rabi; Maturity: 115-120 days after transplanting in Rabi; Yield: 25-30 t/ha in Rabi; Storage life: 2-3 months for Rabi harvest; Source: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit). 5) Bhima Red (Season: Kharif Late Kharif Rabi; Maturity: 110-120 days after transplanting in Rabi; Yield: 39 t/ha in Rabi; Storage life: 3 months for Rabi harvest; Source: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit).
```

### Q2 — Which garlic varieties are listed, and what yield and storage-life values does the dataset record for each?

**V1**
```text
Based on the available records, the listed garlic varieties and their recorded values are: 1) Bhima Purple, with a yield of 6-8 t/ha and a storage-life of 6-8 months (Source: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit). 2) Bhima Omkar, with a yield of 10-12 t/ha and a storage-life of 6-8 months (Source: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit).
```

**V2**
```text
Based on the available records, the garlic varieties listed are:

1. Bhima Purple
- Yield: 6-8 t/ha
- Storage life: 6-8 months
- Source URL: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit

2. Bhima Omkar
- Yield: 10-12 t/ha
- Storage life: 6-8 months
- Source URL: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit

(Note: Onion varieties such as Bhima Prasanskaran, Bhima Light Red, and Bhima Kiran are also in the dataset, but garlic and onion details are kept separate as requested.)
```

### Q3 — Which onion varieties are listed for the Kharif season?

**V1**
```text
Based on the available records, the onion varieties listed for the Kharif season are Bhima Shubra, Bhima Super, Bhima Red, and Bhima Raj (sources: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit).
```

**V2**
```text
Based on the available records, the onion varieties listed for the Kharif season are:

1. Bhima Shubra
- Season: Kharif and Late Kharif
- Maturity: 110-115 days after transplanting (Kharif)
- Yield: 18-20 tonnes per hectare (Kharif)
- Storage life: 30 to 45 days (Kharif harvest)
- Source URL: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit

2. Bhima Super
- Season: Kharif and Late Kharif
- Maturity: 100-105 days after transplanting (Kharif)
- Yield: 20-22 tonnes per hectare (Kharif)
- Storage life: 30-35 days (Kharif harvest)
- Source URL: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit

3. Bhima Red
- Season: Kharif, Late Kharif, and Rabi
- Maturity: 105-110 days after transplanting (Kharif)
- Yield: 19-21 tonnes per hectare (Kharif)
- Storage life: 30-45 days (Kharif harvest)
- Source URL: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit

4. Bhima Raj
- Season: Kharif, Late Kharif, and Rabi
- Maturity: 100-105 days after transplanting (Kharif)
- Yield: 24-26 tonnes per hectare (Kharif)
- Storage life: Not specified for the Kharif harvest
- Source URL: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit
```

### Q4 — What maturity period is recorded for Bhima Light Red onion?

**V1**
```text
For the Bhima Light Red onion variety, the recorded maturity period is 115 days after transplanting (Source: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit). Source: https://nhb.gov.in/pdf/vegetable/onion/oni013.pdf
```

**V2**
```text
For the Bhima Light Red onion variety, the recorded maturity period is 115 days after transplanting. Source: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit Source: https://nhb.gov.in/pdf/vegetable/onion/oni013.pdf
```

### Q5 — What yield value is recorded for Bhima Light Red onion?

**V1**
```text
For the Bhima Light Red onion variety, the recorded yield is 38.5 t/ha (Source: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit). Source: https://nhb.gov.in/pdf/vegetable/onion/oni013.pdf
```

**V2**
```text
For the Bhima Light Red onion variety, the recorded yield is 38.5 t/ha (Source: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit). Source: https://nhb.gov.in/pdf/vegetable/onion/oni013.pdf
```

### Q6 — What is today's onion mandi price per quintal in Lasalgaon?

**V1 and V2**
```text
The available KandaGuide records do not contain live mandi prices, so I cannot provide a supported price.
```

### Q7 — What storage-life information is recorded for Bhima Kiran onion?

**V1**
```text
For the Bhima Kiran onion variety, the recorded storage life is suitable for storage up to 5-6 months (Source: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit).
```

**V2**
```text
For the Bhima Kiran onion variety, the recorded storage-life information is that it is suitable for storage up to 5-6 months. Source: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit
```

### Q8 — Which cultivation practices for onion and garlic should I follow on my farm?

**V1 and V2**
```text
The available KandaGuide variety records do not contain enough field-specific information to make a local farming recommendation.
```

### Q9 — What region and season are recorded as recommended for Bhima Prasanskaran?

**V1**
```text
For the onion variety Bhima Prasanskaran, the recommended season is Rabi and the recommended region includes Gujarat, Maharashtra, Karnataka, Telangana, Andhra Pradesh, and Tamil Nadu (Source: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit).
```

**V2**
```text
For the onion variety Bhima Prasanskaran, the recorded season is Rabi. The recorded regions are Gujarat, Maharashtra, Karnataka, Telangana, Andhra Pradesh, and Tamil Nadu (Source: https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit).
```

### Q10 — Which onion variety should I choose for my field and local market?

**V1 and V2**
```text
The available KandaGuide variety records do not contain enough field-specific information to make a local farming recommendation.
```

## Conclusion

V2 has a marginally higher overall mean (4.52 versus 4.48), with better
average completeness and clarity but slightly lower grounding. This is not
enough evidence to declare it the better production prompt: the ten-question
set is small, three answers bypass the model, and top-five retrieval makes
the season-list questions incomplete for both versions. Both prompts avoid
inventing a live price. V1 remains the application default pending a broader
evaluation and improvements to retrieval coverage and source attribution.
