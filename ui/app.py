"""KandaGuide Streamlit frontend."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DATA_FILE = ROOT / "data" / "records.json"
FEEDBACK_DB = Path(os.getenv("FEEDBACK_DB_PATH", str(ROOT / "data" / "feedback.sqlite")))
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
REQUEST_TIMEOUT = (3.05, 30)
SEASONS = ("Kharif", "Late Kharif", "Rabi")


def load_varieties(path: Path = DATA_FILE) -> list[dict[str, Any]]:
    """Load the project's verified records dataset without changing its values."""
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
        raise ValueError("The variety dataset must be a list of records.")
    return data


def matching_seasons(record: dict[str, Any]) -> set[str]:
    value = record.get("season")
    if not isinstance(value, str):
        return set()
    normalized = value.lower()
    seasons: set[str] = set()
    if re.search(r"\blate[\s-]+kharif\b", normalized):
        seasons.add("Late Kharif")
    # Remove the compound label first so Late Kharif does not imply Kharif.
    without_late_kharif = re.sub(r"\blate[\s-]+kharif\b", " ", normalized)
    if re.search(r"\bkharif\b", without_late_kharif):
        seasons.add("Kharif")
    if re.search(r"\brabi\b", normalized):
        seasons.add("Rabi")
    return seasons


def storage_months(record: dict[str, Any], season: str | None = None) -> float | None:
    """Return an explicit storage duration in months for the selected season."""
    value = record.get("storage_life")
    if not isinstance(value, str):
        return None
    text = value.lower()
    duration_pattern = re.compile(
        r"(?P<low>\d+(?:\.\d+)?)(?:\s*[-–]\s*(?P<high>\d+(?:\.\d+)?))?\s*months?"
    )
    matches = list(duration_pattern.finditer(text))
    if not matches:
        return None
    if len(matches) == 1 and re.fullmatch(duration_pattern, text.strip()):
        return float(matches[0].group("high") or matches[0].group("low"))

    durations: list[float] = []
    previous_end = 0
    for match in matches:
        context = text[previous_end:match.start()]
        previous_end = match.end()
        # A preceding day-based storage claim may belong to another season.
        # Keep only season labels that follow that duration.
        day_durations = list(re.finditer(
            r"\d+(?:\s*(?:-|to)\s*\d+)?\s*days?\b", context
        ))
        if day_durations:
            context = context[day_durations[-1].end():]
        # Require a storage statement or a storage continuation like "rabi
        # harvest for 3 months". This excludes "31% loss after four months".
        explicit = bool(
            re.search(r"\b(?:up\s+to|for)\s*$", context)
            or re.search(
                r"(?:stored|stores|storage(?:\s+life)?|suitable\s+for\s+storage)"
                r"[^.;,]*\b(?:up\s+to|for)\s*$",
                context,
            )
        )
        if not explicit:
            continue
        stated_seasons = matching_seasons({"season": context})
        if season and stated_seasons and season not in stated_seasons:
            continue
        durations.append(float(match.group("high") or match.group("low")))
    return max(durations) if durations else None


def sort_varieties(records: list[dict[str, Any]], season: str | None = None) -> list[dict[str, Any]]:
    """Sort records by verified numeric storage months, highest first."""
    return sorted(
        records,
        key=lambda row: (
            storage_months(row, season) is None,
            -(storage_months(row, season) or 0),
            str(row.get("variety_name") or "").casefold(),
        ),
    )


def filter_varieties(
    records: list[dict[str, Any]], season: str, crop: str = "All"
) -> list[dict[str, Any]]:
    result = [row for row in records if season in matching_seasons(row)]
    if crop != "All":
        result = [row for row in result if str(row.get("category", "")).casefold() == crop.casefold()]
    return sort_varieties(result, season)


def _connect_feedback() -> sqlite3.Connection:
    FEEDBACK_DB.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(FEEDBACK_DB, timeout=10)
    connection.execute(
        """CREATE TABLE IF NOT EXISTS feedback (
            feedback_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            response_id TEXT NOT NULL UNIQUE,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            feedback_type TEXT NOT NULL CHECK(feedback_type IN ('up', 'down')),
            comment TEXT NOT NULL DEFAULT '',
            selected_mode TEXT NOT NULL
        )"""
    )
    return connection


def feedback_saved(response_id: str) -> bool:
    connection = _connect_feedback()
    try:
        return connection.execute(
            "SELECT 1 FROM feedback WHERE response_id = ?", (response_id,)
        ).fetchone() is not None
    finally:
        connection.close()


def save_feedback(
    *, response_id: str, question: str, answer: str, feedback_type: str,
    comment: str, selected_mode: str,
) -> bool:
    """Persist one vote per assistant response. Return False for duplicate votes."""
    if feedback_type not in {"up", "down"}:
        raise ValueError("feedback_type must be 'up' or 'down'.")
    connection = _connect_feedback()
    try:
        cursor = connection.execute(
            """INSERT OR IGNORE INTO feedback
            (feedback_id, timestamp, response_id, question, answer, feedback_type, comment, selected_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), datetime.now(timezone.utc).isoformat(), response_id,
                question, answer, feedback_type, comment.strip(), selected_mode,
            ),
        )
        connection.commit()
        return cursor.rowcount == 1
    finally:
        connection.close()


def check_backend() -> tuple[bool, bool, str]:
    """Return health, agent route availability, and a friendly status detail."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or str(payload.get("status", "")).upper() != "OK":
            return False, False, "Backend returned an unexpected health response."
    except (requests.RequestException, ValueError) as error:
        return False, False, f"Backend unavailable at {API_BASE_URL}: {error}"
    agent_available = False
    try:
        schema_response = requests.get(f"{API_BASE_URL}/openapi.json", timeout=REQUEST_TIMEOUT)
        schema_response.raise_for_status()
        schema = schema_response.json()
        agent_available = isinstance(schema, dict) and "/agent" in schema.get("paths", {})
    except (requests.RequestException, ValueError):
        pass
    return True, agent_available, "Connected to KandaGuide API."


def _request_answer(question: str, mode: str, thread_id: str) -> dict[str, Any]:
    try:
        if mode == "Agent":
            response = requests.post(
                f"{API_BASE_URL}/agent",
                json={"message": question, "thread_id": thread_id, "approval": None},
                timeout=REQUEST_TIMEOUT,
            )
        else:
            response = requests.post(
                f"{API_BASE_URL}/ask", json={"question": question}, timeout=REQUEST_TIMEOUT
            )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("answer"), str):
            raise ValueError("The backend response did not contain a valid answer.")
        citations = payload.get("citations", [])
        if not isinstance(citations, list):
            citations = []
        return {"answer": payload["answer"], "citations": citations, "error": None}
    except requests.Timeout:
        return {"answer": "The backend took too long to respond. Please try again.", "citations": [], "error": "timeout"}
    except requests.HTTPError as error:
        detail = ""
        try:
            detail = response.json().get("detail", "")  # type: ignore[possibly-undefined]
        except (ValueError, AttributeError, UnboundLocalError):
            pass
        message = f"The backend could not answer this question (HTTP {error.response.status_code if error.response else 'error'})."
        if detail:
            message += f" {detail}"
        return {"answer": message, "citations": [], "error": "http"}
    except (requests.RequestException, ValueError) as error:
        return {"answer": f"Could not reach the backend or read its response: {error}", "citations": [], "error": "connection"}


def _citation_url(citation: dict[str, Any]) -> str | None:
    for key in ("source_url", "url", "source"):
        value = citation.get(key)
        if isinstance(value, str) and value.startswith(("https://", "http://")):
            return value
    return None


def render_citations(citations: list[Any]) -> None:
    valid = [item for item in citations if isinstance(item, dict)]
    if not valid:
        st.caption("No supporting citations were returned for this answer.")
        return
    st.caption("Sources returned by KandaGuide")
    for citation in valid:
        title = citation.get("title") or citation.get("source") or "Agricultural source"
        page = citation.get("page")
        label = f"{title} · page {page}" if page is not None else str(title)
        url = _citation_url(citation)
        if url:
            st.markdown(f"[{label}]({url})")
        else:
            st.write(label)


def render_feedback(message: dict[str, Any]) -> None:
    rid = message["response_id"]
    if message.get("error"):
        return
    if feedback_saved(rid):
        st.caption("Thanks — your feedback has been saved.")
        return
    comment = st.text_input("Optional feedback comment", key=f"comment-{rid}", max_chars=1000)
    up, down = st.columns(2)
    selected = "up" if up.button("👍 Thumbs up", key=f"thumb-up-{rid}") else None
    if down.button("👎 Thumbs down", key=f"thumb-down-{rid}"):
        selected = "down"
    if selected:
        save_feedback(
            response_id=rid, question=message["question"], answer=message["content"],
            feedback_type=selected, comment=comment, selected_mode=message["mode"],
        )
        st.rerun()


def variety_picker() -> None:
    st.header("Find the Best Onion & Garlic Variety for Your Season")
    st.write("Explore varieties using the project's source-linked dataset.")
    a, b = st.columns([1, 1])
    season = a.selectbox("Select season", SEASONS, key="picker-season")
    crop = b.selectbox("Crop type", ("All", "Onion", "Garlic"), key="picker-crop")
    try:
        records = load_varieties()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        st.error(f"The variety dataset could not be loaded: {error}")
        return
    matches = filter_varieties(records, season, crop)
    if not matches:
        st.info(f"No {crop.lower()} varieties in the dataset are listed for {season}.")
        return
    st.caption(f"{len(matches)} variety record(s) · sorted by explicit storage duration, longest first")
    columns = st.columns(2)
    for index, record in enumerate(matches):
        with columns[index % 2]:
            with st.container(border=True):
                st.subheader(record.get("variety_name") or "Unnamed variety")
                st.markdown(f"`{str(record.get('category') or 'Crop').title()}`  ·  {season}")
                maturity = record.get("maturity_days_after_transplanting") or record.get("maturity_note")
                if record.get("maturity_days_after_transplanting") and not re.search(
                    r"after\s+(?:transplanting|planting|sowing)|from\s+(?:transplanting|planting|sowing)",
                    str(maturity), re.IGNORECASE,
                ):
                    maturity = f"{maturity} (after transplanting, as recorded in the dataset field)"
                st.write(f"**Maturity:** {maturity if maturity else 'Maturity data unavailable'}")
                storage = record.get("storage_life")
                st.write(f"**Storage:** {storage if storage else 'Storage data unavailable'}")
                months = storage_months(record, season)
                if months is not None:
                    st.success(f"Stores up to {months:g} months")
                yield_value = record.get("yield_t_ha")
                if yield_value:
                    st.write(f"**Yield:** {yield_value}")
                source = record.get("source_url")
                if isinstance(source, str) and source.startswith(("https://", "http://")):
                    st.markdown(f"[Source attribution]({source})")
                else:
                    st.caption("Source attribution unavailable")


def chat_page(agent_available: bool) -> None:
    st.header("Ask KandaGuide")
    st.write("Ask a question about onion and garlic farming. Answers and citations come from the connected KandaGuide backend.")
    modes = ["RAG", "Agent"] if agent_available else ["RAG"]
    mode = st.radio("Answer mode", modes, horizontal=True, key="answer-mode")
    if "messages" not in st.session_state:
        st.session_state.messages = []
    for item in st.session_state.messages:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])
            if item["role"] == "assistant":
                if item.get("citations"):
                    render_citations(item["citations"])
                elif not item.get("error"):
                    st.warning("This answer has no supporting evidence citations.")
                render_feedback(item)
    prompt = st.chat_input("Ask about a variety, season, maturity, or storage…")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        thread_id = st.session_state.setdefault("thread_id", f"ui-{uuid.uuid4().hex}")
        with st.chat_message("assistant"):
            with st.spinner("Checking the KandaGuide knowledge base…"):
                result = _request_answer(prompt, mode, thread_id)
            st.markdown(result["answer"])
            if result["citations"]:
                render_citations(result["citations"])
            elif not result["error"]:
                st.warning("This answer has no supporting evidence citations.")
            assistant_message = {
                "role": "assistant", "content": result["answer"],
                "citations": result["citations"], "question": prompt,
                "response_id": hashlib.sha256(f"{uuid.uuid4()}:{prompt}".encode()).hexdigest(),
                "mode": mode, "error": result["error"],
            }
            st.session_state.messages.append(assistant_message)
            render_feedback(assistant_message)


def main() -> None:
    st.set_page_config(page_title="KandaGuide – Your AI Farming Assistant", page_icon="🌱", layout="wide")
    st.markdown("""<style>
    .stApp { background: #f7faf6; }
    [data-testid="stSidebar"] { background: #edf5ec; }
    h1, h2, h3 { color: #205c39; }
    div[data-testid="stMetric"] { background: white; border-radius: 12px; padding: 14px; }
    </style>""", unsafe_allow_html=True)
    st.title("KandaGuide – Your AI Farming Assistant")
    st.caption("AI-powered guidance for onion and garlic farmers.")
    with st.sidebar:
        st.markdown("## 🌱 KandaGuide")
        page = st.radio("Navigation", ("Chat", "Season-to-variety picker", "About KandaGuide"), label_visibility="collapsed")
        st.divider()
        st.caption(f"Backend: `{API_BASE_URL}`")
        with st.spinner("Checking backend…"):
            healthy, agent_available, detail = check_backend()
        if healthy:
            st.success("Backend connected")
            st.caption("Agent mode available" if agent_available else "RAG mode available")
        else:
            st.error("Backend unavailable")
            st.caption("Start FastAPI and check API_BASE_URL. The picker remains available offline.")
    if page == "Chat":
        chat_page(agent_available if healthy else False)
    elif page == "Season-to-variety picker":
        variety_picker()
    else:
        st.header("About KandaGuide")
        st.write("KandaGuide is an AI-powered agricultural information assistant for onion and garlic farmers. It combines a source-grounded RAG service, a bounded agent workflow, and a verified variety dataset.")
        st.write("The season picker uses the project's existing dataset and keeps maturity wording and source attribution intact. Storage badges appear only for explicit numeric month durations.")
        st.markdown("**Architecture:** Streamlit frontend → FastAPI (`/ask`, `/agent`, `/health`) → existing RAG, agent, and variety data components.")


if __name__ == "__main__":
    main()
