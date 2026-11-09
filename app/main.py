
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from app.records import load_records, get_by_id
from app.smart_search import smart_search


app = FastAPI(
    title="KandaGuide API",
    description="Agricultural information API for onion and garlic farmers",
    version="1.0.0"
)


class Question(BaseModel):
    question: str = Field(
        min_length=3,
        max_length=1000,
        description="Ask an onion or garlic farming question"
    )


@app.get("/")
def home():
    return {
        "message": "Welcome to KandaGuide API",
        "documentation": "/docs",
        "health_check": "/health"
    }


@app.get("/health")
def health():
    return {
        "status": "OK",
        "message": "KandaGuide API is running"
    }


@app.get("/records")
def get_records(
    limit: int = Query(default=50, ge=1, le=500)
):
    records = load_records()

    return {
        "total": len(records),
        "returned": min(limit, len(records)),
        "records": records[:limit]
    }


@app.get("/records/{record_id}")
def get_record(record_id: int):
    record = get_by_id(record_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Variety not found"
        )

    return record


@app.get("/search")
def search_records(
    q: str = Query(min_length=1, max_length=200),
    top_k: int = Query(default=5, ge=1, le=20)
):
    results = smart_search(q, top_k)

    return {
        "query": q,
        "total_results": len(results),
        "results": results
    }


@app.post("/questions")
def ask_question(data: Question):
    return {
        "question": data.question,
        "status": "received",
        "message": (
            "Your question has been received. "
            "AI-powered answers will be added in a later milestone."
        )
    }
