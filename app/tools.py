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
            raise ToolInputError("expected_storage_loss_percent must be between 0 and 100.")
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
