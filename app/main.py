
import json
import re
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.llm import LLMError, generate_response
from app.rag import RAGError, answer_question
from app.records import load_records, get_by_id
from app.smart_search import smart_search
from app.vectorstore import VectorStoreError, semantic_search as search_chunks

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
PRICE_LIMITATION = (
    "The available KandaGuide records do not contain live mandi prices, "
    "so I cannot provide a supported price."
)
LIVE_INFO_LIMITATION = (
    "The available KandaGuide variety records do not contain current weather "
    "or government-scheme information."
)
LOCAL_ADVICE_LIMITATION = (
    "The available KandaGuide variety records do not contain enough "
    "field-specific information to make a local farming recommendation."
)
PRACTICE_LIMITATION = (
    "The available KandaGuide variety records do not contain cultivation "
    "practices for this question."
)
NO_CONTEXT_ANSWER = (
    "I couldn't find relevant information in the available KandaGuide "
    "records, so I can't provide a supported answer."
)
PRICE_PATTERN = re.compile(r"\b(price|prices|mandi)\b", re.IGNORECASE)
LIVE_INFO_PATTERN = re.compile(
    r"\b(weather|forecast|government scheme|subsid(?:y|ies))\b",
    re.IGNORECASE,
)
LOCAL_ADVICE_PATTERN = re.compile(
    r"\b(?:for|on) my (?:farm|field|land)\b|\blocal market\b",
    re.IGNORECASE,
)
PRACTICE_PATTERN = re.compile(
    r"\b(cultivation practices?|cultivation methods?|how to grow|"
    r"irrigation|fertili[sz]er|pest control|disease control|soil preparation)\b",
    re.IGNORECASE,
)

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


class ChatQuestion(Question):
    model_config = ConfigDict(str_strip_whitespace=True)


class AskQuestion(Question):
    model_config = ConfigDict(str_strip_whitespace=True)


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    answer: str = Field(min_length=1)
    confidence: Literal["low", "medium", "high"]
    follow_up: str | None


class AgentRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=1000)
    thread_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    approval: Literal["approved", "rejected"] | None = None


class PromptLoadError(RuntimeError):
    """Raised when a required prompt file cannot be loaded."""


def load_chat_prompts(task_version: str = "v1") -> tuple[str, str]:
    """Load the shared system prompt and a selectable task prompt."""
    if task_version not in {"v1", "v2"}:
        raise ValueError("task_version must be 'v1' or 'v2'.")

    try:
        system_prompt = (PROMPTS_DIR / "system.txt").read_text(encoding="utf-8")
        task_prompt = (PROMPTS_DIR / f"task_prompt_{task_version}.txt").read_text(
            encoding="utf-8"
        )
    except OSError as error:
        raise PromptLoadError("KandaGuide prompt files could not be loaded.") from error

    return system_prompt, task_prompt


def _unavailable_response(answer: str) -> ChatResponse:
    return ChatResponse(answer=answer, confidence="low", follow_up=None)


def _out_of_scope_answer(question: str) -> str | None:
    if PRICE_PATTERN.search(question):
        return PRICE_LIMITATION
    if LIVE_INFO_PATTERN.search(question):
        return LIVE_INFO_LIMITATION
    if LOCAL_ADVICE_PATTERN.search(question):
        return LOCAL_ADVICE_LIMITATION
    if PRACTICE_PATTERN.search(question):
        return PRACTICE_LIMITATION
    return None


def _build_context(records: list[dict[str, Any]]) -> str:
    return json.dumps(
        [
            {
                key: value
                for key, value in record.items()
                if key != "similarity_score"
            }
            for record in records
        ],
        ensure_ascii=False,
        indent=2,
    )


def _include_source_references(
    answer: str, records: list[dict[str, Any]]
) -> str:
    sources = list(dict.fromkeys(
        record.get("source_url")
        for record in records
        if record.get("source_url")
    ))
    missing_sources = [source for source in sources if source not in answer]
    if missing_sources:
        answer = f"{answer.rstrip()} Source: {'; '.join(missing_sources)}"
    return answer


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


@app.get("/search/semantic")
def semantic_search_records(
    q: str = Query(min_length=1, max_length=500),
    top_k: int = Query(default=5, ge=1, le=20),
):
    if not q.strip():
        raise HTTPException(
            status_code=422,
            detail="Query must contain non-whitespace characters.",
        )

    try:
        results = search_chunks(q, top_k=top_k)
    except VectorStoreError:
        raise HTTPException(
            status_code=503,
            detail="Semantic search is temporarily unavailable.",
        ) from None

    return {
        "query": q,
        "total_results": len(results),
        "results": results,
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


@app.post("/ask")
def ask_rag(data: AskQuestion, top_k: int = Query(default=5, ge=1, le=20)):
    """Answer using retrieved agricultural chunks and return their citations."""
    if not data.question.strip():
        raise HTTPException(status_code=422, detail="Question must not be empty.")
    try:
        result = answer_question(data.question, top_k=top_k)
    except RAGError:
        raise HTTPException(
            status_code=503,
            detail="KandaGuide could not answer this question right now.",
        ) from None
    return {key: value for key, value in result.items() if key != "retrieved_chunks"}


@app.post("/agent")
def agent_endpoint(data: AgentRequest):
    """Run or resume a per-thread LangGraph agent conversation."""
    try:
        from app.graph import graph, invoke
    except ImportError:
        raise HTTPException(status_code=503, detail="Agent workflow dependencies are unavailable.") from None

    config = {"configurable": {"thread_id": data.thread_id}}
    if data.approval is not None:
        snapshot = graph.get_state(config)
        if not snapshot or "approval" not in snapshot.next:
            raise HTTPException(status_code=409, detail="This thread has no pending approval to resume.")
        result = invoke(data.message, data.thread_id, approval_response=data.approval)
    else:
        snapshot = graph.get_state(config)
        if snapshot and snapshot.next:
            raise HTTPException(status_code=409, detail="This thread has a pending workflow; resume it with an approval response.")
        result = invoke(data.message, data.thread_id)

    interrupts = result.get("__interrupt__", ())
    if interrupts:
        pending = interrupts[0].value if hasattr(interrupts[0], "value") else {}
        return {
            "thread_id": data.thread_id,
            "status": "awaiting_approval",
            "answer": pending.get("message", "Please review the proposed storage calculation."),
            "tools_used": result.get("tools_used", []),
            "citations": result.get("citations", []),
            "calculation_result": pending.get("calculation_result"),
            "requires_approval": True,
        }
    return {
        "thread_id": data.thread_id,
        "status": result.get("status", "completed"),
        "answer": result.get("answer", "The workflow did not produce an answer."),
        "tools_used": result.get("tools_used", []),
        "citations": result.get("citations", []),
        "calculation_result": result.get("calculation_result"),
        "requires_approval": False,
        "follow_up": result.get("follow_up"),
    }


@app.post("/chat", response_model=ChatResponse)
def chat(data: ChatQuestion):
    out_of_scope_answer = _out_of_scope_answer(data.question)
    if out_of_scope_answer:
        return _unavailable_response(out_of_scope_answer)

    records = smart_search(data.question, top_k=5)
    if not records:
        return _unavailable_response(NO_CONTEXT_ANSWER)

    system_prompt, task_prompt = load_chat_prompts()
    user_prompt = task_prompt.format(
        question=data.question,
        context=_build_context(records),
    )

    try:
        raw_response = generate_response(system_prompt, user_prompt)
        response = ChatResponse.model_validate_json(raw_response)
        response.answer = _include_source_references(response.answer, records)
    except LLMError:
        return JSONResponse(
            status_code=503,
            content=_unavailable_response(
                "KandaGuide could not generate an answer right now. Please try again later."
            ).model_dump(),
        )
    except ValidationError:
        return JSONResponse(
            status_code=503,
            content=_unavailable_response(
                "KandaGuide received an unusable answer and cannot provide a supported response."
            ).model_dump(),
        )

    return response
