"""Small, bounded hand-written KandaGuide agent loop."""

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from app.agent_planner import plan_agent_request
from app.rag import RAGError, answer_question
from app.records import load_records
from app.tools import (
    ToolInputError,
    arithmetic_calculation,
    cost_total_calculation,
    percentage_calculation,
    price_comparison_calculation,
    profit_calculation,
    storage_break_even,
    storage_loss_calculation,
)

MAX_AGENT_STEPS = 3
NUMBER = r"(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?)"
NUMBER_VALUE = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
UNIT = r"(?:kilograms?|kg|quintals?|qtl|metric\s+tons?|tonnes?|tons?)"
UNIT_FACTORS = {
    "kg": Decimal("1"),
    "kilogram": Decimal("1"),
    "kilograms": Decimal("1"),
    "quintal": Decimal("100"),
    "quintals": Decimal("100"),
    "qtl": Decimal("100"),
    "tonne": Decimal("1000"),
    "tonnes": Decimal("1000"),
    "ton": Decimal("1000"),
    "tons": Decimal("1000"),
    "metric_ton": Decimal("1000"),
    "metric_tons": Decimal("1000"),
}
PRICE_FACTORS = {
    "per_kg": Decimal("1"),
    "kg": Decimal("1"),
    "per_quintal": Decimal("0.01"),
    "quintal": Decimal("0.01"),
    "per_tonne": Decimal("0.001"),
    "tonne": Decimal("0.001"),
    "per_ton": Decimal("0.001"),
    "ton": Decimal("0.001"),
}


def calculation_intent(message: str) -> str | None:
    """Select the calculation operation requested by this message."""
    if re.search(r"\b(?:break.?even|break.?even\s+price)\b", message, re.I):
        return "storage_break_even"
    if re.search(r"\b(?:storage\s+loss|weight\s+loss)\b", message, re.I) or re.search(
        r"\b(?:calculate|compute)\s+(?:the\s+)?loss\b", message, re.I
    ):
        return "storage_loss"
    if re.search(r"\b(?:net\s+profit|profit|profitability|earnings)\b", message, re.I):
        return "profit"
    if re.search(r"\brevenue\b", message, re.I):
        return "revenue"
    if re.search(r"\b(calculate|calculation)\b", message, re.I) and re.search(
        r"\b(store|storing|storage)\b", message, re.I
    ):
        return "storage_break_even"
    return None


def _calculation_requested(message: str) -> bool:
    """Detect existing storage decisions plus explicit calculation intents."""
    return calculation_intent(message) is not None or _is_calculation(message)


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


def extract_profit_inputs(message: str) -> dict[str, Any]:
    """Extract quantity, sale groups, and expenses for profit or revenue."""
    quantity_match = re.search(
        rf"(?<![\w₹/])(?P<quantity>{NUMBER_VALUE})\s*(?P<unit>{UNIT})\b",
        message,
        re.I,
    )
    quantity_kg = None
    quantity_value = None
    quantity_unit = None
    if quantity_match:
        quantity = Decimal(quantity_match.group("quantity").replace(",", ""))
        unit = quantity_match.group("unit").casefold()
        quantity_value = quantity_match.group("quantity").replace(",", "")
        quantity_unit = _canonical_quantity_unit(unit)
        quantity_kg = quantity * 100 if unit in {"quintal", "quintals", "qtl"} else quantity
        if unit in {"tonne", "tonnes", "ton", "tons", "metric ton", "metric tons"}:
            quantity_kg = quantity * 1000

    currency = r"(?:₹|rs\.?\s*)?"
    group_pattern = re.compile(
        rf"(?P<percentage>{NUMBER_VALUE})\s*%\s*"
        rf"(?:(?:of\s+)?(?:(?:the\s+)?(?:quantity|produce|onions?|stock)\s*))?"
        rf"(?:(?:is|are)\s+)?(?:being\s+)?(?:sold\s+)?(?:at|for|@)\s*"
        rf"{currency}(?P<price>{NUMBER_VALUE})\s*"
        rf"(?:/\s*(?P<slash_unit>{UNIT})\b|per\s+(?P<per_unit>{UNIT})\b)",
        re.I,
    )
    selling_groups = []
    for match in group_pattern.finditer(message):
        group_unit = (match.group("slash_unit") or match.group("per_unit") or "").casefold()
        raw_price = match.group("price").replace(",", "")
        price = Decimal(raw_price)
        if group_unit in {"quintal", "quintals", "qtl"}:
            price /= 100
        elif group_unit in {"tonne", "tonnes", "ton", "tons", "metric ton", "metric tons"}:
            price /= 1000
        selling_groups.append({
            "percentage": match.group("percentage").replace(",", ""),
            "price_per_kg": str(price),
            "price": raw_price,
            "price_unit": _canonical_price_unit(group_unit),
        })

    if not selling_groups:
        price_pattern = re.compile(
            rf"(?:sell(?:ing)?(?:\s+(?:the\s+)?(?:quantity|produce|onions?|stock))?\s+)?"
            rf"(?:at|for|@)\s*{currency}(?P<price>{NUMBER_VALUE})\s*"
            rf"(?:/\s*(?P<slash_unit>{UNIT})\b|per\s+(?P<per_unit>{UNIT})\b)"
            rf"|{currency}(?P<bare_price>{NUMBER_VALUE})\s*"
            rf"(?:/\s*(?P<bare_slash_unit>{UNIT})\b|per\s+(?P<bare_per_unit>{UNIT})\b)",
            re.I,
        )
        match = price_pattern.search(message)
        if match:
            price_value = match.group("price") or match.group("bare_price")
            price_unit = (
                match.group("slash_unit") or match.group("per_unit")
                or match.group("bare_slash_unit") or match.group("bare_per_unit")
            ).casefold()
            price = Decimal(price_value.replace(",", ""))
            if price_unit in {"quintal", "quintals", "qtl"}:
                price /= 100
            elif price_unit in {"tonne", "tonnes", "ton", "tons", "metric ton", "metric tons"}:
                price /= 1000
            selling_groups = [{
                "percentage": None,
                "price_per_kg": str(price),
                "price": price_value.replace(",", ""),
                "price_unit": _canonical_price_unit(price_unit),
            }]

    total_expenses = re.search(
        rf"\btotal\s+expenses?\s*(?:are|is|of|:|=)?\s*{currency}(?P<amount>{NUMBER_VALUE})"
        rf"|{currency}(?P<reverse>{NUMBER_VALUE})\s*(?:in\s+)?total\s+expenses?\b",
        message,
        re.I,
    )
    if total_expenses:
        expense_amount = (
            total_expenses.group("amount") or total_expenses.group("reverse")
        ).replace(",", "")
        expenses = expense_amount
        expense_items = [{"amount": expense_amount, "label": "Expenses"}]
    else:
        expense_items = []
        labelled_expense_pattern = re.compile(
            rf"\b(?:purchase\s+cost|(?:additional\s+)?expenses?|expenditure)\s*"
            rf"(?:are|is|of|:|=)?\s*{currency}(?P<amount>{NUMBER_VALUE})"
            rf"|{currency}(?P<reverse>{NUMBER_VALUE})\s*"
            rf"(?:in\s+)?(?:purchase\s+cost|(?:additional\s+)?expenses?|expenditure)\b",
            re.I,
        )
        for match in labelled_expense_pattern.finditer(message):
            amount = (match.group("amount") or match.group("reverse")).replace(",", "")
            expense_items.append({"amount": amount, "label": "Expenses"})
        expenses = (
            str(sum((Decimal(item["amount"]) for item in expense_items), Decimal("0")))
            if expense_items else None
        )

    return {
        "quantity_kg": str(quantity_kg) if quantity_kg is not None else None,
        "quantity_value": quantity_value,
        "quantity_unit": quantity_unit,
        "selling_groups": selling_groups,
        "expenses": expenses,
        "expense_items": expense_items,
    }


def _canonical_quantity_unit(unit: str) -> str:
    if unit in {"kg", "kilogram", "kilograms"}:
        return "kg"
    if unit in {"quintal", "quintals", "qtl"}:
        return "quintal"
    return "tonne"


def _canonical_price_unit(unit: str) -> str:
    if unit in {"kg", "kilogram", "kilograms"}:
        return "per_kg"
    if unit in {"quintal", "quintals", "qtl"}:
        return "per_quintal"
    return "per_tonne"


def execute_calculation(message: str, intent: str) -> dict[str, Any]:
    """Execute the selected deterministic calculation or return a focused follow-up."""
    if intent in {"profit", "revenue"}:
        values = extract_profit_inputs(message)
        missing = []
        if values["quantity_kg"] is None:
            missing.append("quantity")
        if not values["selling_groups"]:
            missing.append("selling price")
        if intent == "profit" and values["expenses"] is None:
            missing.append("expenses")
        if missing:
            return _missing_calculation_inputs(intent, missing)
        try:
            result = profit_calculation(
                quantity_kg=values["quantity_kg"],
                selling_groups=values["selling_groups"],
                expenses=values["expenses"],
                operation=intent,
            )
        except ToolInputError as error:
            return {"error": str(error), "tool": "profit_calculation"}
        return {"result": result, "tool": f"{intent}_calculation"}

    if intent == "storage_loss":
        quantity_match = re.search(
            rf"(?<![\w₹/])(?P<quantity>{NUMBER_VALUE})\s*(?P<unit>{UNIT})\b",
            message,
            re.I,
        )
        loss_match = re.search(
            rf"(?P<loss>{NUMBER_VALUE})\s*%\s*(?:(?:weight|storage)\s+)?loss\b"
            rf"|\bloss\s*(?:of|is|:|=)?\s*(?P<reverse>{NUMBER_VALUE})\s*%",
            message,
            re.I,
        )
        missing = []
        if quantity_match is None:
            missing.append("quantity")
        if loss_match is None:
            missing.append("loss percentage")
        if missing:
            return _missing_calculation_inputs(intent, missing)
        unit = quantity_match.group("unit").casefold()
        try:
            result = storage_loss_calculation(
                quantity=quantity_match.group("quantity").replace(",", ""),
                loss_percent=(loss_match.group("loss") or loss_match.group("reverse")).replace(",", ""),
                unit=unit,
            )
        except ToolInputError as error:
            return {"error": str(error), "tool": "storage_loss"}
        return {"result": result, "tool": "storage_loss"}

    if intent == "storage_break_even":
        values = extract_inputs(message)
        missing = [
            label for key, label in (
                ("quantity_quintals", "quantity"),
                ("todays_price_per_quintal", "purchase price"),
            )
            if values[key] is None
        ]
        if missing:
            return _missing_calculation_inputs(intent, missing)
        try:
            months = values["months_of_storage"] or "0"
            variety_citation = None
            if values["expected_storage_loss_percent"] is None:
                variety_loss, variety_citation = _variety_loss(message, months)
                values["expected_storage_loss_percent"] = variety_loss
            result = storage_break_even(
                quantity_quintals=values["quantity_quintals"],
                todays_price_per_quintal=values["todays_price_per_quintal"],
                months_of_storage=months,
                expected_storage_loss_percent=values["expected_storage_loss_percent"],
                additional_costs=values.get("additional_costs"),
                expected_selling_price_per_quintal=values.get("expected_selling_price_per_quintal"),
                loss_source_citation=variety_citation,
            )
        except ToolInputError as error:
            return {"error": str(error), "tool": "storage_break_even"}
        return {"result": result, "tool": "storage_break_even"}

    return {"error": "Unsupported calculation request.", "tool": None}


def execute_planned_calculation(message: str, plan: dict[str, Any]) -> dict[str, Any]:
    """Validate planner-extracted values and dispatch to deterministic tools."""
    operation = plan.get("operation")
    arguments = plan.get("arguments")
    if not isinstance(arguments, dict):
        return {"error": "The calculation plan is missing its parameters.", "tool": None}
    try:
        if operation in {"profit", "revenue"}:
            quantity = _planned_quantity_kg(arguments.get("quantity"), message, "quantity")
            sales = arguments.get("sales")
            expense_items = _planned_cost_items(arguments.get("expenses") or [], message)
            missing = []
            if quantity is None:
                missing.append("quantity")
            if not isinstance(sales, list) or not sales:
                missing.append("selling price")
            if operation == "profit" and not expense_items:
                missing.append("expenses")
            if missing:
                return _missing_calculation_inputs(operation, missing)
            groups = _planned_sales(sales, quantity, message)
            result = profit_calculation(
                quantity,
                groups,
                expenses=None if operation == "profit" else 0,
                operation=operation,
                expense_items=expense_items or None,
            )
            tool = f"{operation}_calculation"
        elif operation == "storage_loss":
            quantity_value = arguments.get("quantity")
            quantity = _planned_quantity(quantity_value, message, "quantity")
            loss = _planned_decimal(arguments.get("loss_percent"), message, "loss percentage")
            if quantity_value is None:
                return _missing_calculation_inputs(operation, ["quantity"])
            if loss is None:
                return _missing_calculation_inputs(operation, ["loss percentage"])
            if not isinstance(quantity_value, dict):
                raise ToolInputError("Quantity must include a value and unit.")
            result = storage_loss_calculation(
                quantity=_planned_decimal(
                    quantity_value.get("value"), message, "quantity"
                ),
                loss_percent=loss,
                unit=str(quantity_value.get("unit") or ""),
            )
            tool = "storage_loss"
        elif operation == "storage_break_even":
            quantity = _planned_quantity_kg(arguments.get("quantity"), message, "quantity")
            purchase_price = arguments.get("purchase_price")
            if quantity is None:
                return _missing_calculation_inputs(operation, ["quantity"])
            price = _planned_price_per_kg(purchase_price, message, "purchase price")
            if price is None:
                return _missing_calculation_inputs(operation, ["purchase price"])
            expenses = _planned_cost_items(arguments.get("expenses") or [], message)
            cost_map = {
                item["label"]: item["amount"] for item in expenses
            }
            months = _planned_decimal(arguments.get("months"), message, "months")
            loss_percent = _planned_decimal(
                arguments.get("loss_percent"), message, "loss percentage"
            )
            variety_citation = None
            if loss_percent is None:
                variety_loss, variety_citation = _variety_loss(
                    message, months if months is not None else 0
                )
                if variety_loss is not None:
                    loss_percent = Decimal(variety_loss)
            result = storage_break_even(
                quantity_quintals=quantity / 100,
                todays_price_per_quintal=price * 100,
                months_of_storage=months or 0,
                expected_storage_loss_percent=loss_percent,
                additional_costs=cost_map or None,
                loss_source_citation=variety_citation,
            )
            tool = "storage_break_even"
        elif operation == "cost_total":
            items = _planned_cost_items(arguments.get("expenses") or [], message)
            if not items:
                return _missing_calculation_inputs(operation, ["cost amounts"])
            result = cost_total_calculation(items)
            tool = "cost_total"
        elif operation == "percentage":
            rate = _planned_decimal(arguments.get("rate"), message, "percentage")
            base = _planned_decimal(arguments.get("base"), message, "base amount")
            missing = []
            if rate is None:
                missing.append("percentage")
            if base is None:
                missing.append("base amount")
            if missing:
                return _missing_calculation_inputs(operation, missing)
            result = percentage_calculation(rate, base)
            tool = "percentage_calculation"
        elif operation == "price_comparison":
            raw_values = arguments.get("values")
            if not isinstance(raw_values, list) or len(raw_values) < 2:
                return _missing_calculation_inputs(operation, ["two prices or values"])
            values = []
            for index, item in enumerate(raw_values, start=1):
                if not isinstance(item, dict):
                    raise ToolInputError(f"Value {index} is invalid.")
                value = _planned_decimal(
                    item.get("value"), message, f"value {index}"
                )
                if value is None:
                    raise ToolInputError(f"Value {index} is missing.")
                values.append({
                    "value": value,
                    "unit": item.get("unit") or "",
                    "label": item.get("label") or f"Value {index}",
                })
            result = price_comparison_calculation(values)
            tool = "price_comparison"
        elif operation == "arithmetic":
            operator = arguments.get("operator")
            raw_operands = arguments.get("operands")
            if not isinstance(raw_operands, list) or len(raw_operands) < 2:
                return _missing_calculation_inputs(operation, ["calculation values"])
            operands = [
                _planned_decimal(value, message, f"value {index}")
                for index, value in enumerate(raw_operands, start=1)
            ]
            result = arithmetic_calculation(operator, operands)
            tool = "arithmetic"
        else:
            return {"error": "The requested calculation is not supported.", "tool": None}
    except ToolInputError as error:
        return {"error": str(error), "tool": _tool_for_operation(operation)}
    return {"result": result, "tool": tool}


def _raw_numbers(message: str) -> set[Decimal]:
    scales = {
        "k": Decimal("1000"),
        "thousand": Decimal("1000"),
        "lakh": Decimal("100000"),
        "lac": Decimal("100000"),
        "million": Decimal("1000000"),
        "crore": Decimal("10000000"),
    }
    values = set()
    pattern = re.compile(
        r"(?<![\w.])(?P<number>-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
        r"(?:\s*(?P<scale>k|thousand|lakh|lac|million|crore)\b)?",
        re.I,
    )
    for match in pattern.finditer(message):
        number = Decimal(match.group("number").replace(",", ""))
        scale = match.group("scale")
        values.add(number * scales[scale.casefold()] if scale else number)
    return values


def _planned_decimal(value: Any, message: str, label: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ToolInputError(f"{label} is invalid.")
    try:
        decimal_value = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, TypeError, ValueError):
        raise ToolInputError(f"{label} is invalid.") from None
    if not decimal_value.is_finite():
        raise ToolInputError(f"{label} must be finite.")
    if decimal_value not in _raw_numbers(message):
        raise ToolInputError(f"{label} was not explicitly provided in the current request.")
    return decimal_value


def _planned_quantity(value: Any, message: str, label: str) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ToolInputError(f"{label} must include a value and unit.")
    number = _planned_decimal(value.get("value"), message, label)
    if number is None:
        return None
    unit = str(value.get("unit") or "").casefold().replace(" ", "_")
    factor = UNIT_FACTORS.get(unit)
    if factor is None:
        raise ToolInputError(f"{label} unit must be kg, quintal, or tonne.")
    if number <= 0:
        raise ToolInputError(f"{label} must be greater than zero.")
    return number * factor


def _planned_quantity_kg(value: Any, message: str, label: str) -> Decimal | None:
    return _planned_quantity(value, message, label)


def _planned_price_per_kg(value: Any, message: str, label: str) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ToolInputError(f"{label} must include a value and unit.")
    number = _planned_decimal(value.get("value"), message, label)
    if number is None:
        return None
    unit = str(value.get("unit") or "").casefold().replace(" ", "_")
    factor = PRICE_FACTORS.get(unit)
    if factor is None:
        raise ToolInputError(f"{label} unit must be per kg, per quintal, or per tonne.")
    return number * factor


def _planned_sales(
    sales: list[Any], total_quantity_kg: Decimal, message: str
) -> list[dict[str, str]]:
    parsed = []
    for index, sale in enumerate(sales, start=1):
        if not isinstance(sale, dict):
            raise ToolInputError(f"Sale group {index} is invalid.")
        price = _planned_price_per_kg(
            {
                "value": sale.get("price"),
                "unit": sale.get("price_unit"),
            },
            message,
            f"selling price {index}",
        )
        if price is None:
            raise ToolInputError(f"Selling price {index} is required.")
        percentage = _planned_decimal(
            sale.get("percentage"), message, f"sale percentage {index}"
        )
        sale_quantity = _planned_quantity_kg(
            sale.get("quantity"), message, f"sale quantity {index}"
        )
        quantity_percentage = (
            sale_quantity / total_quantity_kg * 100
            if sale_quantity is not None else None
        )
        if percentage is not None and quantity_percentage is not None:
            if abs(percentage - quantity_percentage) > Decimal("0.01"):
                raise ToolInputError(
                    f"Sale group {index} percentage and quantity do not agree."
                )
        if percentage is None:
            percentage = quantity_percentage
        parsed.append({
            "percentage": percentage,
            "price_per_kg": str(price),
        })

    missing_indices = [
        index for index, group in enumerate(parsed)
        if group["percentage"] is None
    ]
    if len(missing_indices) == 1:
        known_percentage = sum(
            (
                group["percentage"]
                for group in parsed
                if group["percentage"] is not None
            ),
            Decimal("0"),
        )
        remaining_percentage = Decimal("100") - known_percentage
        if remaining_percentage <= 0:
            raise ToolInputError("Selling percentages must total 100%.")
        parsed[missing_indices[0]]["percentage"] = remaining_percentage
    elif len(missing_indices) == len(parsed) == 1:
        parsed[0]["percentage"] = Decimal("100")
    elif missing_indices:
        raise ToolInputError(
            "Each sale group needs a percentage or an explicit quantity."
        )
    return [
        {
            "percentage": str(group["percentage"]),
            "price_per_kg": group["price_per_kg"],
        }
        for group in parsed
    ]


def _planned_cost_items(items: Any, message: str) -> list[dict[str, str]]:
    if not isinstance(items, list):
        raise ToolInputError("Cost items must be a list.")
    normalized = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ToolInputError(f"Cost item {index} is invalid.")
        amount = _planned_decimal(item.get("amount"), message, f"cost amount {index}")
        if amount is None:
            continue
        normalized.append({
            "amount": str(amount),
            "label": str(item.get("label") or f"Cost {index}"),
        })
    return normalized


def _tool_for_operation(operation: str) -> str:
    return {
        "profit": "profit_calculation",
        "revenue": "revenue_calculation",
        "storage_break_even": "storage_break_even",
        "storage_loss": "storage_loss",
        "cost_total": "cost_total",
        "percentage": "percentage_calculation",
        "price_comparison": "price_comparison",
        "arithmetic": "arithmetic",
    }.get(operation, "calculation")


def _missing_calculation_inputs(intent: str, missing: list[str]) -> dict[str, Any]:
    labels = ", ".join(missing)
    if intent == "profit":
        prompt = f"To calculate net profit, please provide the missing {labels}."
    elif intent == "revenue":
        prompt = f"To calculate revenue, please provide the missing {labels}."
    elif intent == "storage_loss":
        prompt = f"To calculate storage loss, please provide the missing {labels}."
    elif intent == "cost_total":
        prompt = f"To calculate the total cost, please provide the missing {labels}."
    elif intent == "percentage":
        prompt = f"To calculate the percentage, please provide the missing {labels}."
    elif intent == "price_comparison":
        prompt = f"To compare prices, please provide the missing {labels}."
    elif intent == "arithmetic":
        prompt = f"To complete the calculation, please provide the missing {labels}."
    else:
        prompt = f"To calculate break-even, please provide the missing {labels}."
    return {
        "follow_up": {"missing_inputs": missing, "question": prompt},
        "tool": {
            "profit": "profit_calculation",
            "revenue": "revenue_calculation",
            "storage_loss": "storage_loss",
            "storage_break_even": "storage_break_even",
        }[intent],
    }


def _is_calculation(message: str) -> bool:
    """Return True when a message requests a supported calculation.

    The LangGraph agent uses the structured planner for ambiguous requests;
    this local predicate supports clear legacy calculations and mixed routing.
    """
    # Explicit calculator vocabulary — always a calculation request.
    if calculation_intent(message):
        return True
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
    except (InvalidOperation, TypeError, ValueError):
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
    planner_fn: Callable[[str], dict[str, Any]] = plan_agent_request,
    max_steps: int = MAX_AGENT_STEPS,
) -> dict[str, Any]:
    """Route one message to existing RAG, the deterministic tool, or both."""
    if not isinstance(message, str) or not message.strip():
        return _error("Please enter a message.")
    if max_steps < 1 or max_steps > MAX_AGENT_STEPS:
        return _error(f"max_steps must be between 1 and {MAX_AGENT_STEPS}.")

    calculation_text = " ".join((history or []) + [message])
    try:
        plan = planner_fn(calculation_text)
    except RuntimeError as error:
        return _error(str(error))
    calculation = plan.get("intent") in {"calculation", "mixed"}
    wants_rag = plan.get("intent") in {"knowledge", "mixed"}
    tools_used: list[str] = []
    citations: list[dict[str, Any]] = []
    calculation_result = None
    sections: list[str] = []
    follow_up = None

    if calculation:
        outcome = execute_planned_calculation(calculation_text, plan)
        if outcome.get("tool"):
            tools_used.append(outcome["tool"])
        if outcome.get("follow_up"):
            follow_up = outcome["follow_up"]
            sections.append(follow_up["question"])
        elif outcome.get("error"):
            return _error(outcome["error"], tools_used=tools_used)
        else:
            calculation_result = outcome.get("result")
            if calculation_result:
                citations.extend(calculation_result.get("loss_source_citations", []))
                if calculation_result.get("step_by_step"):
                    sections.append(calculation_result["step_by_step"])
                elif calculation_result.get("break_even_selling_price_per_quintal"):
                    sections.append(
                        "Break-even: ₹"
                        + str(calculation_result["break_even_selling_price_per_quintal"])
                        + "/quintal. This is a deterministic calculation, not a source-derived fact."
                    )

    if wants_rag and len(tools_used) < max_steps:
        tools_used.append("rag")
        try:
            result = rag_fn(plan.get("knowledge_question") or message)
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
        "requires_approval": bool(
            calculation_result
            and plan.get("operation") == "storage_break_even"
            and re.search(r"\b(should|recommend|decide|store)\b", message, re.I)
        ),
        "follow_up": follow_up,
    }


def _error(message: str, *, tools_used: list[str] | None = None) -> dict[str, Any]:
    return {"answer": message, "tools_used": tools_used or [], "citations": [], "calculation_result": None, "requires_approval": False, "follow_up": None}
