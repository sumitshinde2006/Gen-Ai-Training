
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.records import load_records, get_by_id
from app.smart_search import smart_search


app = FastAPI(
    title="KandaGuide API",
    description="Onion and Garlic Agricultural Information API",
    version="1.0.0"
)


class Question(BaseModel):
    question: str


# 1. Health check

@app.get("/health")
def health():

    return {
        "status": "OK",
        "message": "KandaGuide API is running"
    }


# 2. Get all records

@app.get("/records")
def get_records(limit: int = 50):

    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 500"
        )

    records = load_records()

    return {
        "total": len(records),
        "records": records[:limit]
    }


# 3. Get record by ID

@app.get("/records/{record_id}")
def get_record(record_id: int):

    record = get_by_id(record_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Variety not found"
        )

    return record


# 4. Search varieties

@app.get("/search")
def search_records(q: str):

    results = smart_search(q)

    return {
        "query": q,
        "total_results": len(results),
        "results": results
    }


# 5. Submit agricultural question

@app.post("/questions")
def ask_question(data: Question):

    return {
        "question": data.question,
        "status": "received",
        "message": (
            "Your question has been received. "
            "AI-powered answering will be added "
            "in a future KandaGuide milestone."
        )
    }
