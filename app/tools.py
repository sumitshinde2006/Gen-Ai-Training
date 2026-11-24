"""Deterministic storage break-even and profit/loss calculations for KandaGuide."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

DEFAULT_LOSS_RANGE = (Decimal("30"), Decimal("40"))
DEFAULT_LOSS_PROVENANCE = (
    "Unverified project-specification range. The local source records do not "
    "support this as a general DOGR default: the MANAGE reference attributes "
    "30–40% loss to Fusarium basal rot, while a DOGR variety page reports "
    "31.11% for Bhima Prasanskaran after four months."
)
DEFAULT_LOSS_CITATIONS = [
    {
        "source": "https://www.manage.gov.in/publications/eBooks/Good%20Agricultural%20Practices%20in%20Onion%20and%20Garlic.pdf",
        "title": "Good Agricultural Practices in Onion and Garlic, Fusarium basal rot section",
        "supports": "The cited 30–40% loss is in the context of Fusarium basal rot, not a general storage default.",
    },
    {
        "source": "https://www.dogr.res.in/index.php/research/varieties-developed?layout=edit",
        "title": "ICAR-DOGR varieties page, Bhima Prasanskaran",
        "supports": "A variety-specific report of 31.11% storage losses after four months.",
    },
]
CENT = Decimal("0.01")
KG_PER_QUINTAL = Decimal("100")


class ToolInputError(ValueError):
    """Raised when a required storage calculation input is invalid."""


def _decimal(value: Any, name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ToolInputError(f"{name} is required and must be numeric.")
    # Strip thousands-separator commas that may come from user input
    cleaned = str(value).replace(",", "") if isinstance(value, str) else str(value)
    try:
        result = Decimal(cleaned)
    except (InvalidOperation, TypeError, ValueError):
        raise ToolInputError(f"{name} must be numeric.") from None
    if not result.is_finite():
        raise ToolInputError(f"{name} must be a finite number.")
    return result


def _fmt(d: Decimal) -> str:
    """Format a Decimal to 2 decimal places as a plain string."""
    return str(d.quantize(CENT, rounding=ROUND_HALF_UP))


def _fmt_inr(d: Decimal) -> str:
    """Format a currency amount with Indian-style digit grouping."""
    whole, fraction = _fmt(d).split(".")
    sign = ""
    if whole.startswith("-"):
        sign, whole = "-", whole[1:]
    if len(whole) > 3:
        last = whole[-3:]
        leading = whole[:-3]
        groups = []
        while leading:
            groups.append(leading[-2:])
            leading = leading[:-2]
        whole = ",".join(reversed(groups)) + "," + last
    return f"{sign}{whole}.{fraction}"


def profit_calculation(
    quantity_kg: Any,
    selling_groups: list[dict[str, Any]],
    expenses: Any = None,
    *,
    operation: str = "profit",
    expense_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Calculate revenue or net profit from one or more sale-price groups.

    Each group has a percentage of total quantity and a selling price per kg.
    Profit calculations require expenses; revenue calculations do not.
    """
    quantity = _decimal(quantity_kg, "quantity_kg")
    if quantity <= 0:
        raise ToolInputError("quantity must be greater than zero.")
    if operation not in {"profit", "revenue"}:
        raise ToolInputError("operation must be 'profit' or 'revenue'.")
    if not isinstance(selling_groups, list) or not selling_groups:
        raise ToolInputError("At least one selling price is required.")
    if operation == "profit" and expenses is None and not expense_items:
        raise ToolInputError("expenses are required to calculate net profit.")

    parsed_groups = []
    total_percentage = Decimal("0")
    total_revenue = Decimal("0")
    for index, group in enumerate(selling_groups, start=1):
        if not isinstance(group, dict):
            raise ToolInputError(f"selling_groups[{index}] must be an object.")
        percentage = _decimal(group.get("percentage"), f"selling_groups[{index}].percentage")
        price = _decimal(group.get("price_per_kg"), f"selling_groups[{index}].price_per_kg")
        if percentage <= 0 or percentage > 100:
            raise ToolInputError("Each selling percentage must be greater than 0 and at most 100.")
        if price < 0:
            raise ToolInputError("Selling prices must not be negative.")
        quantity_for_group = quantity * percentage / 100
        revenue = (quantity_for_group * price).quantize(CENT, rounding=ROUND_HALF_UP)
        total_percentage += percentage
        total_revenue += revenue
        parsed_groups.append({
            "percentage": _fmt(percentage),
            "quantity_kg": _fmt(quantity_for_group),
            "selling_price_per_kg": _fmt(price),
            "revenue": _fmt(revenue),
        })

    if total_percentage != 100:
        raise ToolInputError(
            f"Selling percentages total {_fmt(total_percentage)}%, not 100%; "
            "please correct the percentages."
        )

    total_revenue = total_revenue.quantize(CENT, rounding=ROUND_HALF_UP)
    parsed_expenses = []
    if expense_items is not None:
        if not isinstance(expense_items, list):
            raise ToolInputError("expense_items must be a list.")
        for index, item in enumerate(expense_items, start=1):
            if not isinstance(item, dict):
                raise ToolInputError(f"expense_items[{index}] must be an object.")
            amount = _decimal(item.get("amount"), f"expense_items[{index}].amount")
            label = str(item.get("label") or f"Expense {index}")
            parsed_expenses.append({"label": label, "amount": amount})
        cost = sum(
            (item["amount"] for item in parsed_expenses), Decimal("0")
        )
    else:
        cost = _decimal(expenses, "expenses") if expenses is not None else Decimal("0")
    if cost < 0:
        raise ToolInputError("expenses must not be negative.")
    if any(item["amount"] < 0 for item in parsed_expenses):
        raise ToolInputError("Expenses must not be negative.")
    net_profit = (total_revenue - cost).quantize(CENT, rounding=ROUND_HALF_UP)

    result: dict[str, Any] = {
        "operation": operation,
        "quantity_kg": _fmt(quantity),
        "selling_groups": parsed_groups,
        "total_revenue": _fmt(total_revenue),
        "expenses": _fmt(cost),
        "expense_items": [
            {"label": item["label"], "amount": _fmt(item["amount"])}
            for item in parsed_expenses
        ],
        "net_profit": _fmt(net_profit) if operation == "profit" else None,
    }
    if operation == "profit":
        outcome = "profit" if net_profit >= 0 else "loss"
        result["step_by_step"] = (
            "Sales calculation:\n"
            + "\n".join(
                f"  {group['percentage']}%: {group['quantity_kg']} kg × "
                f"₹{_fmt_inr(Decimal(group['selling_price_per_kg']))}/kg "
                f"= ₹{_fmt_inr(Decimal(group['revenue']))}"
                for group in parsed_groups
            )
            + f"\nTotal revenue: ₹{_fmt_inr(total_revenue)}"
            + (
                "\n" + "\n".join(
                    f"{item['label']}: ₹{_fmt_inr(item['amount'])}"
                    for item in parsed_expenses
                )
                if parsed_expenses else ""
            )
            + f"\nExpenses: ₹{_fmt_inr(cost)}"
            + f"\nNet {outcome}: ₹{_fmt_inr(abs(net_profit))}"
        )
    else:
        result["step_by_step"] = f"Total revenue: ₹{_fmt_inr(total_revenue)}"
    return result


def storage_loss_calculation(
    quantity: Any, loss_percent: Any, *, unit: str = "kg"
) -> dict[str, Any]:
    """Calculate lost and remaining stock from a quantity and loss percentage."""
    amount = _decimal(quantity, "quantity")
    percent = _decimal(loss_percent, "loss_percent")
    normalized_unit = unit.casefold()
    if normalized_unit not in {
        "kg", "kilogram", "kilograms", "quintal", "quintals", "qtl",
        "ton", "tons", "tonne", "tonnes", "metric ton", "metric tons",
    }:
        raise ToolInputError("unit must be kilograms, quintals, or tonnes.")
    if normalized_unit in {"quintal", "quintals", "qtl"}:
        normalized_unit = "quintals"
    elif normalized_unit in {"ton", "tons", "tonne", "tonnes", "metric ton", "metric tons"}:
        normalized_unit = "tonnes"
    else:
        normalized_unit = "kg"
    if amount <= 0:
        raise ToolInputError("quantity must be greater than zero.")
    if percent < 0 or percent >= 100:
        raise ToolInputError("loss_percent must be at least 0 and below 100.")
    lost = (amount * percent / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    remaining = (amount - lost).quantize(CENT, rounding=ROUND_HALF_UP)
    return {
        "quantity": _fmt(amount),
        "unit": normalized_unit,
        "loss_percent": _fmt(percent),
        "lost_quantity": _fmt(lost),
        "remaining_quantity": _fmt(remaining),
        "remaining_stock_kg": (
            _fmt(remaining * KG_PER_QUINTAL)
            if normalized_unit == "quintals"
            else _fmt(remaining * 1000) if normalized_unit == "tonnes"
            else _fmt(remaining)
        ),
        "step_by_step": (
            f"Storage loss: { _fmt(amount) } {normalized_unit} × "
            f"{_fmt(percent)}% = {_fmt(lost)} {normalized_unit} lost. "
            f"Remaining stock: {_fmt(remaining)} {normalized_unit}."
        ),
    }


def cost_total_calculation(cost_items: list[dict[str, Any]]) -> dict[str, Any]:
    """Sum explicitly supplied cost items without estimating missing expenses."""
    if not isinstance(cost_items, list) or not cost_items:
        raise ToolInputError("At least one cost amount is required.")
    parsed = []
    total = Decimal("0")
    for index, item in enumerate(cost_items, start=1):
        if not isinstance(item, dict):
            raise ToolInputError(f"cost_items[{index}] must be an object.")
        amount = _decimal(item.get("amount"), f"cost_items[{index}].amount")
        if amount < 0:
            raise ToolInputError("Costs must not be negative.")
        label = str(item.get("label") or f"Cost {index}")
        parsed.append({"label": label, "amount": _fmt(amount)})
        total += amount
    return {
        "cost_items": parsed,
        "total_cost": _fmt(total),
        "step_by_step": (
            "\n".join(f"{item['label']}: ₹{item['amount']}" for item in parsed)
            + f"\nTotal cost: ₹{_fmt_inr(total)}"
        ),
    }


def percentage_calculation(rate: Any, base: Any) -> dict[str, Any]:
    """Calculate a stated percentage of a base amount."""
    percentage = _decimal(rate, "rate")
    amount = _decimal(base, "base")
    if percentage < 0:
        raise ToolInputError("rate must not be negative.")
    result = (amount * percentage / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    return {
        "rate": _fmt(percentage),
        "base": _fmt(amount),
        "result": _fmt(result),
        "step_by_step": (
            f"{_fmt(percentage)}% of {_fmt_inr(amount)} = ₹{_fmt_inr(result)}"
        ),
    }


def price_comparison_calculation(values: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare two or more values after converting compatible units."""
    if not isinstance(values, list) or len(values) < 2:
        raise ToolInputError("At least two comparable values are required.")
    parsed = []
    normalized_unit = None
    for index, item in enumerate(values, start=1):
        if not isinstance(item, dict):
            raise ToolInputError(f"values[{index}] must be an object.")
        value = _decimal(item.get("value"), f"values[{index}].value")
        unit = str(item.get("unit") or "").strip().casefold().replace(" ", "_")
        if unit in {"per_quintal", "quintal_price", "rs_per_quintal", "inr_per_quintal"}:
            value /= KG_PER_QUINTAL
            unit = "per_kg"
        elif unit in {
            "per_tonne", "per_ton", "tonne_price", "ton_price",
            "rs_per_tonne", "inr_per_tonne", "rs_per_ton", "inr_per_ton",
        }:
            value /= 1000
            unit = "per_kg"
        elif unit in {"quintal", "quintals", "qtl"}:
            value *= KG_PER_QUINTAL
            unit = "kg"
        elif unit in {"kilogram", "kilograms"}:
            unit = "kg"
        if normalized_unit is None:
            normalized_unit = unit
        elif unit != normalized_unit:
            raise ToolInputError("Values must use comparable units.")
        parsed.append({
            "label": str(item.get("label") or f"Value {index}"),
            "value": value,
            "unit": unit,
        })

    low = min(parsed, key=lambda item: item["value"])
    high = max(parsed, key=lambda item: item["value"])
    difference = high["value"] - low["value"]
    baseline = parsed[0]["value"]
    percentage_change = (
        ((parsed[-1]["value"] - baseline) / abs(baseline) * 100).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        if baseline != 0 else None
    )
    return {
        "values": [
            {
                "label": item["label"],
                "value": _fmt(item["value"]),
                "unit": item["unit"],
            }
            for item in parsed
        ],
        "difference": _fmt(difference),
        "unit": normalized_unit,
        "percentage_change_from_first": (
            _fmt(percentage_change) if percentage_change is not None else None
        ),
        "step_by_step": (
            f"{high['label']} is higher than {low['label']} by "
            f"{_fmt_inr(difference)} {normalized_unit}."
            + (
                f" Change from {parsed[0]['label']} to {parsed[-1]['label']}: "
                f"{_fmt(percentage_change)}%."
                if percentage_change is not None else ""
            )
        ),
    }


def arithmetic_calculation(operator: str, operands: list[Any]) -> dict[str, Any]:
    """Evaluate a basic arithmetic sequence using Decimal, never eval()."""
    if operator not in {"add", "subtract", "multiply", "divide"}:
        raise ToolInputError("operator must be add, subtract, multiply, or divide.")
    if not isinstance(operands, list) or len(operands) < 2:
        raise ToolInputError("At least two operands are required.")
    numbers = [_decimal(value, f"operands[{index}]") for index, value in enumerate(operands)]
    result = numbers[0]
    for value in numbers[1:]:
        if operator == "add":
            result += value
        elif operator == "subtract":
            result -= value
        elif operator == "multiply":
            result *= value
        else:
            if value == 0:
                raise ToolInputError("Division by zero is not allowed.")
            result /= value
    result = result.quantize(CENT, rounding=ROUND_HALF_UP)
    symbol = {"add": "+", "subtract": "−", "multiply": "×", "divide": "÷"}[operator]
    return {
        "operator": operator,
        "operands": [_fmt(number) for number in numbers],
        "result": _fmt(result),
        "step_by_step": f" {symbol} ".join(_fmt(number) for number in numbers) + f" = {_fmt(result)}",
    }


def storage_break_even(
    quantity_quintals: Any,
    todays_price_per_quintal: Any,
    months_of_storage: Any,
    expected_storage_loss_percent: Any = None,
    *,
    additional_costs: dict[str, Any] | None = None,
    expected_selling_price_per_quintal: Any = None,
    loss_source_citation: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Full step-by-step storage calculation.

    Computes:
      1. Purchase cost
      2. Additional costs (storage, transport, labour, etc.)
      3. Total investment
      4. Weight loss and remaining saleable quantity
      5. Break-even price per kg and per quintal
      6. Profit / loss if an expected selling price is provided

    ``additional_costs`` is a dict of {label: amount_str}, e.g.
    {"storage": "12000", "transport": "5000"}.
    ``expected_selling_price_per_quintal`` triggers profit/loss calculation.
    """
    # ── Parse and validate core inputs ────────────────────────────────────────
    quantity   = _decimal(quantity_quintals, "quantity_quintals")
    buy_price  = _decimal(todays_price_per_quintal, "todays_price_per_quintal")
    months     = _decimal(months_of_storage, "months_of_storage")

    if quantity <= 0:
        raise ToolInputError("quantity_quintals must be greater than zero.")
    if buy_price < 0:
        raise ToolInputError("todays_price_per_quintal must not be negative.")
    if months < 0:
        raise ToolInputError("months_of_storage must not be negative.")

    quantity_kg = quantity * KG_PER_QUINTAL

    # ── Step 1: Purchase cost ─────────────────────────────────────────────────
    purchase_cost = quantity * buy_price

    # ── Step 2: Additional costs ──────────────────────────────────────────────
    parsed_additional: dict[str, Decimal] = {}
    if additional_costs:
        for label, raw in additional_costs.items():
            val = _decimal(raw, f"additional_costs[{label}]")
            if val < 0:
                raise ToolInputError(f"additional_costs[{label}] must not be negative.")
            parsed_additional[label] = val

    total_additional = sum(parsed_additional.values(), Decimal("0"))

    # ── Step 3: Total investment ──────────────────────────────────────────────
    total_investment = purchase_cost + total_additional

    # ── Step 4: Loss and saleable quantity ────────────────────────────────────
    if expected_storage_loss_percent is None:
        # Use the unverified 30–40% range
        loss_percents  = DEFAULT_LOSS_RANGE
        is_range       = True
        loss_display   = {"minimum_percent": "30", "maximum_percent": "40"}
        loss_provenance = DEFAULT_LOSS_PROVENANCE
        loss_citations = DEFAULT_LOSS_CITATIONS
    else:
        loss_pct = _decimal(expected_storage_loss_percent, "expected_storage_loss_percent")
        if loss_pct < 0 or loss_pct >= 100:
            raise ToolInputError(
                "expected_storage_loss_percent must be between 0 and 100 "
                "(loss must be below 100 percent)."
            )
        loss_percents  = (loss_pct,)
        is_range       = False
        loss_display   = _fmt(loss_pct)
        if loss_source_citation:
            loss_provenance = "Variety-specific percentage from the cited project record."
            loss_citations  = [loss_source_citation]
        else:
            loss_provenance = "User-provided loss percentage; not independently verified."
            loss_citations  = []

    # ── Build scenario(s) ─────────────────────────────────────────────────────
    scenarios = []
    for lp in loss_percents:
        lost_qtl  = quantity * lp / 100
        lost_kg   = lost_qtl * KG_PER_QUINTAL
        sale_qtl  = quantity - lost_qtl
        sale_kg   = sale_qtl * KG_PER_QUINTAL

        # Break-even: total investment ÷ saleable quantity
        be_per_qtl = (total_investment / sale_qtl).quantize(CENT, rounding=ROUND_HALF_UP)
        be_per_kg  = (be_per_qtl / KG_PER_QUINTAL).quantize(CENT, rounding=ROUND_HALF_UP)

        scenario: dict[str, Any] = {
            "loss_percent": _fmt(lp),
            "lost_quantity_kg": _fmt(lost_kg),
            "lost_quantity_quintals": _fmt(lost_qtl),
            "remaining_saleable_quantity_kg": _fmt(sale_kg),
            "remaining_saleable_quantity_quintals": _fmt(sale_qtl),
            "break_even_selling_price_per_kg": _fmt(be_per_kg),
            "break_even_selling_price_per_quintal": _fmt(be_per_qtl),
        }

        # Profit / loss if selling price provided
        if expected_selling_price_per_quintal is not None:
            sell_qtl  = _decimal(expected_selling_price_per_quintal, "expected_selling_price_per_quintal")
            sell_kg   = (sell_qtl / KG_PER_QUINTAL).quantize(CENT, rounding=ROUND_HALF_UP)
            revenue   = (sale_qtl * sell_qtl).quantize(CENT, rounding=ROUND_HALF_UP)
            profit    = (revenue - total_investment).quantize(CENT, rounding=ROUND_HALF_UP)
            outcome   = "profit" if profit >= 0 else "loss"
            scenario.update({
                "expected_selling_price_per_kg": _fmt(sell_kg),
                "expected_selling_price_per_quintal": _fmt(sell_qtl),
                "expected_revenue": _fmt(revenue),
                "profit_or_loss": _fmt(abs(profit)),
                "profit_or_loss_direction": outcome,
            })

        scenarios.append(scenario)

    # ── Build the step-by-step explanation string ──────────────────────────────
    buy_per_kg = (buy_price / KG_PER_QUINTAL).quantize(CENT, rounding=ROUND_HALF_UP)
    steps: list[str] = [
        f"Step 1 — Purchase cost\n"
        f"  Quantity      : {_fmt(quantity_kg)} kg = {_fmt(quantity)} quintals\n"
        f"  Purchase price: ₹{_fmt(buy_per_kg)}/kg  (₹{_fmt(buy_price)}/quintal)\n"
        f"  Purchase cost : {_fmt(quantity_kg)} kg × ₹{_fmt(buy_per_kg)} = ₹{_fmt(purchase_cost)}",
    ]

    if parsed_additional:
        lines = "\n".join(
            f"  {label.title():12s}: ₹{_fmt(v)}" for label, v in parsed_additional.items()
        )
        steps.append(
            f"Step 2 — Additional costs\n{lines}\n"
            f"  Total additional costs: ₹{_fmt(total_additional)}"
        )
    else:
        steps.append("Step 2 — Additional costs\n  None provided.")

    steps.append(
        f"Step 3 — Total investment\n"
        f"  Purchase cost ₹{_fmt(purchase_cost)} + Additional ₹{_fmt(total_additional)}"
        f" = ₹{_fmt(total_investment)}"
    )

    for sc in scenarios:
        lp_label = f"{sc['loss_percent']}% weight loss"
        steps.append(
            f"Step 4 — Remaining quantity after {lp_label}\n"
            f"  Lost  : {sc['lost_quantity_kg']} kg = {sc['lost_quantity_quintals']} quintals\n"
            f"  Saleable: {sc['remaining_saleable_quantity_kg']} kg = {sc['remaining_saleable_quantity_quintals']} quintals"
        )
        steps.append(
            f"Step 5 — Break-even selling price\n"
            f"  Total investment ₹{_fmt(total_investment)} ÷ {sc['remaining_saleable_quantity_kg']} kg\n"
            f"  = ₹{sc['break_even_selling_price_per_kg']}/kg  (₹{sc['break_even_selling_price_per_quintal']}/quintal)\n"
            f"  You must sell above ₹{sc['break_even_selling_price_per_kg']}/kg to avoid a loss."
        )
        if "expected_revenue" in sc:
            direction = sc["profit_or_loss_direction"].upper()
            steps.append(
                f"Step 6 — Profit / Loss at ₹{sc['expected_selling_price_per_kg']}/kg\n"
                f"  Revenue : {sc['remaining_saleable_quantity_kg']} kg × ₹{sc['expected_selling_price_per_kg']}"
                f" = ₹{sc['expected_revenue']}\n"
                f"  Investment: ₹{_fmt(total_investment)}\n"
                f"  {direction}: ₹{sc['profit_or_loss']}"
            )

    # ── Assemble final result ─────────────────────────────────────────────────
    result: dict[str, Any] = {
        # Inputs echoed back
        "original_quantity_kg": _fmt(quantity_kg),
        "original_quantity_quintals": _fmt(quantity),
        "purchase_price_per_kg": _fmt(buy_per_kg),
        "purchase_price_per_quintal": _fmt(buy_price),
        "storage_duration_months": _fmt(months),
        # Steps
        "purchase_cost": _fmt(purchase_cost),
        "additional_costs_breakdown": {k: _fmt(v) for k, v in parsed_additional.items()},
        "total_additional_costs": _fmt(total_additional),
        "total_investment": _fmt(total_investment),
        "todays_gross_revenue": _fmt(purchase_cost),
        # Loss metadata
        "expected_storage_loss_percent": loss_display,
        "loss_input_status": (
            "unverified_range" if is_range
            else ("variety_specific_record" if loss_source_citation else "explicit_percentage")
        ),
        "loss_provenance": loss_provenance,
        "loss_source_citations": loss_citations,
        # Step-by-step narrative
        "step_by_step": "\n\n".join(steps),
        "assumptions_and_limitations": [
            "Break-even is total-investment based: purchase cost + all additional costs provided.",
            "Storage months are informational only; no time-based loss rate is applied.",
            "Costs not mentioned (interest, inflation, quality discounts) are excluded.",
        ],
    }

    # Flatten single-scenario vs range results
    if is_range:
        result.update({
            "scenarios": scenarios,
            "break_even_selling_price_per_kg": {
                "minimum": scenarios[0]["break_even_selling_price_per_kg"],
                "maximum": scenarios[1]["break_even_selling_price_per_kg"],
            },
            "break_even_selling_price_per_quintal": {
                "minimum": scenarios[0]["break_even_selling_price_per_quintal"],
                "maximum": scenarios[1]["break_even_selling_price_per_quintal"],
            },
            "remaining_saleable_quantity_kg": {
                "minimum": scenarios[1]["remaining_saleable_quantity_kg"],
                "maximum": scenarios[0]["remaining_saleable_quantity_kg"],
            },
            "remaining_saleable_quantity_quintals": {
                "minimum": scenarios[1]["remaining_saleable_quantity_quintals"],
                "maximum": scenarios[0]["remaining_saleable_quantity_quintals"],
            },
        })
    else:
        sc = scenarios[0]
        result.update({
            "lost_quantity_kg": sc["lost_quantity_kg"],
            "lost_quantity_quintals": sc["lost_quantity_quintals"],
            "expected_lost_quantity_kg": sc["lost_quantity_kg"],
            "expected_lost_quantity_quintals": sc["lost_quantity_quintals"],
            "remaining_saleable_quantity_kg": sc["remaining_saleable_quantity_kg"],
            "remaining_saleable_quantity_quintals": sc["remaining_saleable_quantity_quintals"],
            "break_even_selling_price_per_kg": sc["break_even_selling_price_per_kg"],
            "break_even_selling_price_per_quintal": sc["break_even_selling_price_per_quintal"],
        })
        if "expected_revenue" in sc:
            result.update({
                "expected_selling_price_per_kg": sc["expected_selling_price_per_kg"],
                "expected_selling_price_per_quintal": sc["expected_selling_price_per_quintal"],
                "expected_revenue": sc["expected_revenue"],
                "profit_or_loss": sc["profit_or_loss"],
                "profit_or_loss_direction": sc["profit_or_loss_direction"],
            })

    return result
