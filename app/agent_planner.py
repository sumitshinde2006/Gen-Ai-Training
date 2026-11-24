"""Structured intent and parameter planning for the KandaGuide agent."""

import json
import re
from pathlib import Path
from typing import Any

from app.llm import LLMError, generate_response

PLANNER_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "agent_planner.txt"
INTENTS = {"calculation", "knowledge", "mixed", "clarification"}
OPERATIONS = {
    "profit", "revenue", "storage_break_even", "storage_loss",
    "cost_total", "percentage", "price_comparison", "arithmetic",
}
MATH_FALLBACK_HINT = (
    "calculate", "compute", "compare", "difference", "percentage", "percent",
    "total", "cost", "earn", "make", "worth", "amount", "how much",
    "add", "sum", "subtract", "multiply", "divide", "profit", "revenue",
    "break-even", "loss", "net",
)


class AgentPlanningError(RuntimeError):
    """Raised when a user request cannot be safely converted into a plan."""


def _local_plan(message: str) -> dict[str, Any] | None:
    """Fast-path unambiguous supported requests before model-based planning."""
    from app.agent_loop import (
        _calculation_requested,
        _needs_rag,
        NUMBER_VALUE,
        UNIT,
        _canonical_quantity_unit,
        calculation_intent,
        extract_inputs,
        extract_profit_inputs,
    )
    import re

    operation = calculation_intent(message)
    if operation is None and _calculation_requested(message) and any(
        word in message.casefold()
        for word in ("month", "loss", "store", "storage")
    ):
        operation = "storage_break_even"
    if operation is None:
        return None
    is_mixed_request = _needs_rag(message)
    if ("?" in message and not is_mixed_request) or any(
        phrase in message.casefold()
        for phrase in ("compare", "difference", "how much", "worth", "change")
    ):
        return None
    arguments: dict[str, Any] = {
        "quantity": None,
        "sales": [],
        "expenses": [],
        "purchase_price": None,
        "months": None,
        "loss_percent": None,
        "values": [],
        "rate": None,
        "base": None,
        "operator": None,
        "operands": [],
    }

    if operation in {"profit", "revenue"}:
        values = extract_profit_inputs(message)
        price_mentions = re.findall(
            rf"(?:₹|rs\.?\s*)?{NUMBER_VALUE}\s*"
            rf"(?:/\s*(?:kg|kilograms?|quintals?|qtl|tons?|tonnes?)\b|"
            rf"per\s+(?:kg|kilograms?|quintals?|qtl|tons?|tonnes?)\b)",
            message,
            re.I,
        )
        if len(price_mentions) > len(values["selling_groups"]):
            return None
        if not values["selling_groups"] and re.search(
            r"\b(?:price|rate|sell(?:ing)?|at)\b|₹|rs\.?",
            message,
            re.I,
        ):
            return None
        if operation == "profit" and not values["expense_items"] and re.search(
            r"\b(?:expense|cost|charge|paid|spend|investment|transport|"
            r"labou?r|storage)\b",
            message,
            re.I,
        ):
            return None
        if values["quantity_value"] is not None:
            arguments["quantity"] = {
                "value": values["quantity_value"],
                "unit": values["quantity_unit"],
            }
        arguments["sales"] = [
            {
                "percentage": group["percentage"],
                "quantity": None,
                "price": group["price"],
                "price_unit": group["price_unit"],
            }
            for group in values["selling_groups"]
        ]
        arguments["expenses"] = values["expense_items"]
    elif operation == "storage_loss":
        quantity = re.search(
            rf"(?<![\w₹/])(?P<value>{NUMBER_VALUE})\s*(?P<unit>{UNIT})\b",
            message,
            re.I,
        )
        loss = re.search(
            r"(?P<loss>\d+(?:\.\d+)?)\s*%\s*(?:(?:weight|storage)\s+)?loss\b"
            r"|\bloss\s*(?:of|is|:|=)?\s*(?P<reverse>\d+(?:\.\d+)?)\s*%",
            message,
            re.I,
        )
        if quantity:
            arguments["quantity"] = {
                "value": quantity.group("value").replace(",", ""),
                "unit": quantity.group("unit").casefold(),
            }
        if loss:
            arguments["loss_percent"] = loss.group("loss") or loss.group("reverse")
    elif operation == "storage_break_even":
        values = extract_inputs(message)
        quantity = re.search(
            rf"(?<![\w₹/])(?P<value>{NUMBER_VALUE})\s*(?P<unit>{UNIT})\b",
            message,
            re.I,
        )
        if quantity:
            arguments["quantity"] = {
                "value": quantity.group("value").replace(",", ""),
                "unit": _canonical_quantity_unit(quantity.group("unit").casefold()),
            }
        profit_values = extract_profit_inputs(message)
        purchase_price = next(
            iter(profit_values["selling_groups"]), None
        )
        if purchase_price is not None:
            arguments["purchase_price"] = {
                "value": purchase_price["price"],
                "unit": purchase_price["price_unit"],
            }
        elif values["todays_price_per_quintal"] is not None:
            arguments["purchase_price"] = {
                "value": values["todays_price_per_quintal"],
                "unit": "per_quintal",
            }
        if values["months_of_storage"] is not None:
            arguments["months"] = values["months_of_storage"]
        if values["expected_storage_loss_percent"] is not None:
            arguments["loss_percent"] = values["expected_storage_loss_percent"]
        if values["additional_costs"]:
            arguments["expenses"] = [
                {"amount": amount, "label": label.title()}
                for label, amount in values["additional_costs"].items()
            ]

    intent = "mixed" if _needs_rag(message) else "calculation"
    knowledge_question = message if intent == "mixed" else None
    if intent == "mixed":
        calculation_start = re.search(
            r"\b(?:calculate|compute|work\s+out)\b", message, re.I
        )
        if calculation_start:
            question_prefix = message[: calculation_start.start()].strip(" ?.!;")
            if question_prefix:
                knowledge_question = question_prefix
    return {
        "intent": intent,
        "operation": operation,
        "arguments": arguments,
        "knowledge_question": knowledge_question,
        "clarification": None,
    }


def plan_agent_request(message: str) -> dict[str, Any]:
    """Ask the configured model to classify a request and extract direct inputs.

    The planner returns data only. It never performs calculations or supplies
    missing values; deterministic Python tools own execution and validation.
    """
    local_plan = _local_plan(message)
    if local_plan is not None:
        return local_plan
    has_math_hint = any(
        re.search(rf"\b{re.escape(hint)}\b", message, re.I)
        for hint in MATH_FALLBACK_HINT
    )
    has_number = any(character.isdigit() for character in message)
    has_math_notation = bool(
        re.search(r"[₹$%]|\bper\s+|/(?:kg|qtl|quintal|ton)", message, re.I)
    )
    multiple_values = len(re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", message)) > 1
    if not (
        has_math_hint
        or has_math_notation
        or multiple_values
        or (has_number and "?" in message)
    ):
        return {
            "intent": "clarification" if has_number else "knowledge",
            "operation": None,
            "arguments": {},
            "knowledge_question": message if not has_number else None,
            "clarification": (
                "What would you like to calculate or find out about those values?"
                if has_number else None
            ),
        }

    try:
        system_prompt = PLANNER_PROMPT.read_text(encoding="utf-8")
    except OSError as error:
        raise AgentPlanningError("KandaGuide could not load its planning instructions.") from error

    try:
        raw = generate_response(
            system_prompt,
            "Plan this current farmer request only. Do not use prior requests "
            "unless the request explicitly refers to them.\n\n"
            f"Current request:\n{message}",
        )
        plan = json.loads(raw)
    except (LLMError, ValueError, TypeError) as error:
        raise AgentPlanningError("KandaGuide could not understand this request safely.") from error

    if not isinstance(plan, dict):
        raise AgentPlanningError("The request planner returned an invalid plan.")
    intent = plan.get("intent")
    operation = plan.get("operation")
    arguments = plan.get("arguments")
    if intent not in INTENTS:
        raise AgentPlanningError("The request planner returned an unsupported intent.")
    if intent in {"calculation", "mixed"}:
        if operation not in OPERATIONS or not isinstance(arguments, dict):
            raise AgentPlanningError("The request planner returned an incomplete calculation plan.")
    elif operation is not None and operation not in OPERATIONS:
        raise AgentPlanningError("The request planner returned an unsupported operation.")
    if intent == "mixed" and not isinstance(plan.get("knowledge_question"), str):
        raise AgentPlanningError("A mixed request is missing its agricultural question.")
    if intent == "clarification" and not isinstance(plan.get("clarification"), str):
        raise AgentPlanningError("The request planner did not provide a clarification.")
    return {
        "intent": intent,
        "operation": operation,
        "arguments": arguments if isinstance(arguments, dict) else {},
        "knowledge_question": plan.get("knowledge_question"),
        "clarification": plan.get("clarification"),
    }
