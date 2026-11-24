"""Small, bounded hand-written KandaGuide agent loop."""

import re
from decimal import Decimal
from typing import Any, Callable

from app.rag import RAGError, answer_question
from app.records import load_records
from app.tools import ToolInputError, storage_break_even

MAX_AGENT_STEPS = 3
NUMBER = r"(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?)"


def _clean(value: str | tuple | None) -> str | None:
    """Strip thousands-separator commas; handle tuple results from findall."""
    if value is None:
        return None
    # re.findall returns tuples when pattern has >1 capture group; take first non-empty
    if isinstance(value, tuple):
        value = next((v for v in value if v), None)
    if not value:
        return None
    return value.replace(",", "")


def _latest(pattern: str, text: str) -> str | None:
    hits = re.findall(pattern, text, flags=re.IGNORECASE)
    return _clean(hits[-1]) if hits else None


def _first(pattern: str, text: str) -> str | None:
    hits = re.findall(pattern, text, flags=re.IGNORECASE)
    return _clean(hits[0]) if hits else None


def extract_inputs(message: str) -> dict[str, Any]:
    """Extract all numeric inputs from a farmer's storage calculation message.

    Handles:
    - Quantity in kg (auto-converted to quintals) or quintals directly.
    - Price per kg (multiplied ×100) or per quintal. Uses FIRST match so the
      purchase price is not confused with a later selling price.
    - Additional costs: storage, transport, labour, etc.  Each keyword is
      matched with what follows (not precedes) so costs don't bleed into each
      other.
    - Storage duration in months.
    - Loss percent.
    - Expected selling price per kg or per quintal.
    """
    # ── Quantity ──────────────────────────────────────────────────────────────
    qty_qtl = _first(rf"{NUMBER}\s*(?:quintals?|qtl)\b", message)
    qty_kg  = _first(rf"{NUMBER}\s*kg\b", message)
    if qty_qtl is not None:
        quantity_quintals = qty_qtl
    elif qty_kg is not None:
        quantity_quintals = str(float(qty_kg) / 100)
    else:
        quantity_quintals = None

    # ── Purchase price ────────────────────────────────────────────────────────
    # Always use FIRST price match so the sell price (which appears later)
    # is not mistaken for the purchase price.
    # Try per-quintal patterns first, then per-kg (×100).
    price_per_qtl = (
        _first(rf"(?:today(?:'s)?\s+price|price)\s*(?:is|of|:|=)?\s*(?:₹|rs\.?\s*)?{NUMBER}\s*(?:per\s+quintal|/\s*quintal|/\s*qtl|per\s*qtl)\b", message)
        or _first(rf"(?:₹|rs\.?\s*)?{NUMBER}\s*/?\s*(?:quintal|qtl)\b", message)
    )
    price_per_kg = (
        _first(rf"(?:purchased?|bought|price)\s*(?:at|is|of|:|=)?\s*(?:₹|rs\.?\s*)?{NUMBER}\s*(?:per\s+kg|/\s*kg|per\s*kg)\b", message)
        or _first(rf"(?:at|@)\s*(?:₹|rs\.?\s*)?{NUMBER}\s*per\s+kg\b", message)
        or _first(rf"(?:₹|rs\.?\s*)?{NUMBER}\s*per\s+kg\b", message)
    )
    if price_per_qtl is not None:
        todays_price_per_quintal = price_per_qtl
    elif price_per_kg is not None:
        todays_price_per_quintal = str(float(price_per_kg) * 100)
    else:
        todays_price_per_quintal = (
            _first(rf"(?:₹|rs\.?\s*){NUMBER}\b", message)
            or _first(rf"price\s*(?:is|of|:|=)?\s*(?:₹|rs\.?\s*)?{NUMBER}\b", message)
        )

    # ── Additional costs ──────────────────────────────────────────────────────
    # Anchor each cost keyword to what FOLLOWS it (not what precedes it).
    storage_cost = _first(
        rf"(?:₹|rs\.?\s*)?{NUMBER}\s*on\s+storage"
        rf"|spending\s+(?:₹|rs\.?\s*)?{NUMBER}\s*on\s+storage"
        rf"|storage\s+(?:cost|charges?|expense)?\s*(?:of|is|:|=)?\s*(?:₹|rs\.?\s*)?{NUMBER}",
        message,
    )
    transport_cost = _first(
        rf"(?:₹|rs\.?\s*)?{NUMBER}\s*on\s+transport(?:ation)?"
        rf"|transport(?:ation)?\s+(?:cost|charges?|expense)?\s*(?:of|is|:|=)?\s*(?:₹|rs\.?\s*)?{NUMBER}",
        message,
    )
    labour_cost = _first(
        rf"labour\s+(?:cost|charges?|expense)?\s*(?:of|is|:|=)?\s*(?:₹|rs\.?\s*)?{NUMBER}"
        rf"|(?:₹|rs\.?\s*)?{NUMBER}\s*on\s+labour",
        message,
    )

    additional_costs: dict[str, str] = {}
    if storage_cost:
        additional_costs["storage"] = storage_cost
    if transport_cost:
        additional_costs["transport"] = transport_cost
    if labour_cost:
        additional_costs["labour"] = labour_cost

    # ── Selling price ─────────────────────────────────────────────────────────
    sell_per_kg = _first(
        rf"sell\s+(?:the\s+)?(?:remaining\s+)?(?:onions?|garlic|produce|stock|them|it)?\s*at\s*(?:₹|rs\.?\s*)?{NUMBER}\s*per\s+kg\b"
        rf"|sell(?:ing)?\s*(?:at|@)\s*(?:₹|rs\.?\s*)?{NUMBER}\s*per\s+kg\b",
        message,
    )
    sell_per_qtl = _first(
        rf"sell\s+(?:the\s+)?(?:remaining\s+)?(?:onions?|garlic|produce|stock|them|it)?\s*at\s*(?:₹|rs\.?\s*)?{NUMBER}\s*per\s+quintal\b"
        rf"|sell(?:ing)?\s*(?:at|@)\s*(?:₹|rs\.?\s*)?{NUMBER}\s*per\s+quintal\b",
        message,
    )
    if sell_per_qtl:
        expected_selling_price_per_quintal = sell_per_qtl
    elif sell_per_kg:
        expected_selling_price_per_quintal = str(float(sell_per_kg) * 100)
    else:
        expected_selling_price_per_quintal = None

    return {
        "quantity_quintals": quantity_quintals,
        "todays_price_per_quintal": todays_price_per_quintal,
        "months_of_storage": _latest(rf"{NUMBER}\s*months?\b", message),
        "expected_storage_loss_percent": (
            _latest(rf"{NUMBER}\s*%\s*(?:weight\s+)?(?:storage\s+)?loss", message)
            or _latest(rf"{NUMBER}\s*%", message)
        ),
        "additional_costs": additional_costs if additional_costs else None,
        "expected_selling_price_per_quintal": expected_selling_price_per_quintal,
    }


def _is_calculation(message: str) -> bool:
    """Return True when the message requests a storage break-even calculation.

    Matches both explicit calculator keywords and natural-language phrasing a
    farmer would use: "should I store?", "if I store for 3 months", "worth
    storing", etc.  A numeric quantity or duration in the same message makes
    the intent unambiguous and avoids false positives on pure RAG questions.
    """
    # Explicit calculator vocabulary — always a calculation request.
    if re.search(
        r"\b(calculate|break.?even|storage loss|storage calculation|sell after storage)\b",
        message,
        re.I,
    ):
        return True

    # Natural-language storage-decision phrasing: needs at least one number so
    # "how to store onions?" (pure RAG question) is not misclassified.
    has_number = bool(re.search(r"\b\d+\b", message))
    has_storage_intent = bool(re.search(
        r"\b(should\s+i\s+store|worth\s+storing|store\s+(?:it|them|my)|"
        r"(?:store|storing)\s+for\s+\d|if\s+i\s+store|"
        r"sell\s+(?:now|after|later)|profit\s+(?:from|after)\s+stor)"
        r"\b",
        message,
        re.I,
    ))
    return has_number and has_storage_intent


def _needs_rag(message: str) -> bool:
    if not message.strip():
        return False
    if _is_calculation(message):
        # For calculation requests, only add RAG when the message also asks
        # about documented agricultural facts (variety traits, disease, etc.).
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
                "question": (
                    "Please provide: "
                    + ", ".join(m.replace("_", " ") for m in missing)
                    + ". An explicit loss percentage is preferred; otherwise the available 30–40% range is unverified as a general DOGR figure."
                ),
            }
            sections.append(follow_up["question"])
        else:
            try:
                variety_citation = None
                if values["expected_storage_loss_percent"] is None:
                    variety_loss, variety_citation = _variety_loss(combined, values["months_of_storage"])
                    values["expected_storage_loss_percent"] = variety_loss
                calculation_result = storage_break_even(
                    quantity_quintals=values["quantity_quintals"],
                    todays_price_per_quintal=values["todays_price_per_quintal"],
                    months_of_storage=values["months_of_storage"],
                    expected_storage_loss_percent=values["expected_storage_loss_percent"],
                    additional_costs=values.get("additional_costs"),
                    expected_selling_price_per_quintal=values.get("expected_selling_price_per_quintal"),
                    loss_source_citation=variety_citation,
                )
                citations.extend(calculation_result.get("loss_source_citations", []))
                if calculation_result.get("step_by_step"):
                    sections.append(calculation_result["step_by_step"])
                else:
                    sections.append(
                        "Break-even: ₹"
                        + str(calculation_result["break_even_selling_price_per_quintal"])
                        + "/quintal. This is a deterministic calculation, not a source-derived fact."
                    )
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
