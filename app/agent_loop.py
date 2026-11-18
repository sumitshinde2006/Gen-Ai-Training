"""Small, bounded hand-written KandaGuide agent loop."""

import re
from decimal import Decimal
from typing import Any, Callable

from app.rag import RAGError, answer_question
from app.records import load_records
from app.tools import ToolInputError, storage_break_even

MAX_AGENT_STEPS = 3
NUMBER = r"(-?\d+(?:\.\d+)?)"


def _latest(pattern: str, text: str) -> str | None:
    hits = re.findall(pattern, text, flags=re.IGNORECASE)
    return hits[-1] if hits else None


def extract_inputs(message: str) -> dict[str, Any]:
    return {
        "quantity_quintals": _latest(rf"{NUMBER}\s*(?:quintals?|qtl)\b", message),
        "todays_price_per_quintal": _latest(
            rf"(?:today(?:'s)?\s+price|price)\s*(?:is|of|:|=)?\s*(?:₹|rs\.?\s*)?{NUMBER}\s*(?:per\s+quintal|/\s*q(?:tl)?|per\s*q(?:tl)?)?", message
        ),
        "months_of_storage": _latest(rf"{NUMBER}\s*months?\b", message),
        "expected_storage_loss_percent": _latest(rf"{NUMBER}\s*%\s*(?:storage\s+)?loss", message)
        or _latest(rf"{NUMBER}\s*%", message),
    }


def _is_calculation(message: str) -> bool:
    return bool(re.search(r"\b(calculate|break.?even|storage loss|storage calculation|sell after storage)\b", message, re.I))


def _needs_rag(message: str) -> bool:
    if not message.strip():
        return False
    if _is_calculation(message):
        return bool(re.search(
            r"\b(variet(?:y|ies)|disease|fusarium|DOGR|MANAGE|documented|"
            r"agricultural facts?|storage method|how to store|cultivation|season)\b",
            message,
            re.I,
        ))
    return True


def _variety_loss(message: str, months: Any) -> tuple[str | None, dict[str, str] | None]:
    """Use a recorded variety value only at the duration stated by its record."""
    try:
        records = load_records()
    except (OSError, ValueError):
        return None, None
    try:
        requested_months = Decimal(str(months))
    except Exception:
        return None, None
    for record in records:
        name = str(record.get("variety_name", ""))
        storage_text = str(record.get("storage_life", ""))
        if not name or not re.search(rf"\b{re.escape(name)}\b", message, re.I):
            continue
        hit = re.search(r"(\d+(?:\.\d+)?)%.*?after\s+(\d+(?:\.\d+)?|one|two|three|four|five|six)\s+months?", storage_text, re.I)
        if hit:
            month_word = hit.group(2).lower()
            recorded_months = Decimal({"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}.get(month_word, month_word))
        else:
            recorded_months = None
        if hit and requested_months == recorded_months:
            return hit.group(1), {
                "source": record.get("source_url", ""),
                "title": f"ICAR-DOGR varieties page, {name}",
                "supports": f"{hit.group(1)}% storage losses after {hit.group(2)} months for {name}.",
            }
    return None, None


def run_agent(
    message: str,
    *,
    history: list[str] | None = None,
    rag_fn: Callable[..., dict[str, Any]] = answer_question,
    max_steps: int = MAX_AGENT_STEPS,
) -> dict[str, Any]:
    """Route one message to existing RAG, the deterministic tool, or both."""
    if not isinstance(message, str) or not message.strip():
        return _error("Please enter a message.")
    if max_steps < 1 or max_steps > MAX_AGENT_STEPS:
        return _error(f"max_steps must be between 1 and {MAX_AGENT_STEPS}.")

    calculation = _is_calculation(message)
    wants_rag = _needs_rag(message)
    tools_used: list[str] = []
    citations: list[dict[str, Any]] = []
    calculation_result = None
    sections: list[str] = []
    follow_up = None
    combined = " ".join((history or []) + [message])

    if calculation:
        tools_used.append("storage_break_even")
        values = extract_inputs(combined)
        missing = [key for key in ("quantity_quintals", "todays_price_per_quintal", "months_of_storage") if values[key] is None]
        if missing:
            follow_up = {
                "missing_inputs": missing,
                "question": "Please provide " + ", ".join(missing).replace("_", " ") + ". You may give an explicit storage-loss percentage; otherwise the available 30–40% range is unverified as a general DOGR figure.",
            }
            sections.append(follow_up["question"])
        else:
            try:
                variety_citation = None
                if values["expected_storage_loss_percent"] is None:
                    variety_loss, variety_citation = _variety_loss(combined, values["months_of_storage"])
                    values["expected_storage_loss_percent"] = variety_loss
                calculation_result = storage_break_even(**values, loss_source_citation=variety_citation)
                citations.extend(calculation_result.get("loss_source_citations", []))
                sections.append("Calculated gross-revenue break-even result: " + str(calculation_result["break_even_selling_price_per_quintal"]) + " per quintal. This is calculated, not a source-derived agricultural fact.")
            except ToolInputError as error:
                return _error(str(error), tools_used=tools_used)

    if wants_rag and len(tools_used) < max_steps:
        tools_used.append("rag")
        try:
            result = rag_fn(message)
            sections.append("Agricultural source answer: " + result.get("answer", "I couldn't produce a supported answer."))
            citations.extend(result.get("citations", []))
            if result.get("answer") == "I don't know.":
                sections.append("No supported agricultural evidence was found for that part.")
        except (RAGError, ValueError, RuntimeError):
            sections.append("Agricultural retrieval is temporarily unavailable; no unsupported fact was substituted.")

    return {
        "answer": "\n\n".join(sections) or "I couldn't determine which KandaGuide capability is needed.",
        "tools_used": tools_used,
        "citations": citations,
        "calculation_result": calculation_result,
        "requires_approval": bool(calculation_result and re.search(r"\b(should|recommend|decide|store)\b", message, re.I)),
        "follow_up": follow_up,
    }


def _error(message: str, *, tools_used: list[str] | None = None) -> dict[str, Any]:
    return {"answer": message, "tools_used": tools_used or [], "citations": [], "calculation_result": None, "requires_approval": False, "follow_up": None}
