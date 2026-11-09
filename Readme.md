
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

### Create virtual environment

```bash
python -m venv .venv
```

### Activate on Windows

```bash
.venv\Scripts\activate
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Download agricultural documents

```bash
python -m app.fetch
```

### Process agricultural data

```bash
python -m app.ingest
```

### Run data analysis

```bash
python -m analysis.explore
```

### Start FastAPI

```bash
uvicorn app.main:app --reload
```

### Open API documentation

http://127.0.0.1:8000/docs

## 9. API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | /health | Check API status |
| GET | /records | Get agricultural records |
| GET | /records/{id} | Get one variety |
| GET | /search?q=Bhima | Search varieties |
| POST | /questions | Submit a farming question |

## 10. Development Progress

- Day 1: Project introduction and Python fundamentals.
- Day 2: Variety dataset and record operations.
- Day 3: Agricultural data ingestion pipeline.
- Day 4: FastAPI, Pandas and smart search.

## 11. Expected Outcome

KandaGuide aims to provide farmers with an accessible,
searchable and source-backed agricultural information assistant.

**Developed by Sumit Gorakshanath Shinde**  
Sanjivani University – SJ-09 Agriculture
