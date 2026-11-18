"""Deterministic gross-revenue break-even calculations for storage."""

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


class ToolInputError(ValueError):
    """Raised when a required storage calculation input is invalid."""


def _decimal(value: Any, name: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ToolInputError(f"{name} is required and must be numeric.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ToolInputError(f"{name} must be numeric.") from None
    if not result.is_finite():
        raise ToolInputError(f"{name} must be a finite number.")
    return result


def _price(today_price: Decimal, loss: Decimal) -> Decimal:
    return (today_price / (Decimal("1") - loss / 100)).quantize(
        CENT, rounding=ROUND_HALF_UP
    )


def storage_break_even(
    quantity_quintals: Any,
    todays_price_per_quintal: Any,
    months_of_storage: Any,
    expected_storage_loss_percent: Any = None,
    *,
    loss_source_citation: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return gross-revenue break-even price using an exact loss or 30–40% range.

    The unverified range is explicitly labeled as such and is never represented
    as a verified DOGR fact. Pass ``expected_storage_loss_percent`` to use an
    exact user or variety-specific figure.
    """
    quantity = _decimal(quantity_quintals, "quantity_quintals")
    today_price = _decimal(todays_price_per_quintal, "todays_price_per_quintal")
    months = _decimal(months_of_storage, "months_of_storage")
    if quantity <= 0:
        raise ToolInputError("quantity_quintals must be greater than zero.")
    if today_price < 0:
        raise ToolInputError("todays_price_per_quintal must not be negative.")
    if months < 0:
        raise ToolInputError("months_of_storage must not be negative.")

    original_revenue = quantity * today_price
    if expected_storage_loss_percent is None:
        losses = DEFAULT_LOSS_RANGE
        is_range = True
        expected_loss: Any = {"minimum_percent": "30", "maximum_percent": "40"}
        provenance = DEFAULT_LOSS_PROVENANCE
    else:
        loss = _decimal(expected_storage_loss_percent, "expected_storage_loss_percent")
        if loss < 0 or loss >= 100:
            raise ToolInputError("expected_storage_loss_percent must be at least 0 and below 100.")
        losses = (loss,)
        is_range = False
        expected_loss = str(loss)
        if loss_source_citation:
            provenance = "Variety-specific percentage from the cited project record; applies to its stated variety and storage duration."
        else:
            provenance = "User-provided or explicitly selected loss percentage; not independently verified."

    scenarios = []
    for loss in losses:
        lost_quantity = quantity * loss / 100
        saleable = quantity - lost_quantity
        scenarios.append({
            "loss_percent": str(loss),
            "expected_lost_quantity_quintals": str(lost_quantity.quantize(CENT, rounding=ROUND_HALF_UP)),
            "remaining_saleable_quantity_quintals": str(saleable.quantize(CENT, rounding=ROUND_HALF_UP)),
            "break_even_selling_price_per_quintal": str(_price(today_price, loss)),
        })

    common = {
        "original_quantity_quintals": str(quantity),
        "todays_price_per_quintal": str(today_price),
        "todays_gross_revenue": str(original_revenue.quantize(CENT, rounding=ROUND_HALF_UP)),
        "storage_duration_months": str(months),
        "expected_storage_loss_percent": expected_loss,
        "loss_input_status": "unverified_range" if is_range else ("variety_specific_record" if loss_source_citation else "explicit_percentage"),
        "loss_provenance": provenance,
        "loss_source_citations": DEFAULT_LOSS_CITATIONS if is_range else ([loss_source_citation] if loss_source_citation else []),
        "calculation_explanation": (
            "Today's gross revenue is quantity × today's price. For each loss "
            "scenario, saleable quantity is quantity × (1 − loss/100), and "
            "break-even price is today's gross revenue ÷ saleable quantity."
        ),
        "assumptions_and_limitations": [
            "This is a gross-revenue break-even calculation, not a complete profit calculation.",
            "Storage months are informational; no time-based loss rate is applied.",
            "Storage, transport, interest, inflation, quality discounts, and other costs are excluded.",
            "The 30–40% range is not verified as a general DOGR default; source context is stated in loss_provenance.",
        ],
    }
    if is_range:
        common.update({
            "expected_lost_quantity_quintals": {
                "minimum": scenarios[0]["expected_lost_quantity_quintals"],
                "maximum": scenarios[1]["expected_lost_quantity_quintals"],
            },
            "remaining_saleable_quantity_quintals": {
                "minimum": scenarios[1]["remaining_saleable_quantity_quintals"],
                "maximum": scenarios[0]["remaining_saleable_quantity_quintals"],
            },
            "break_even_selling_price_per_quintal": {
                "minimum": scenarios[0]["break_even_selling_price_per_quintal"],
                "maximum": scenarios[1]["break_even_selling_price_per_quintal"],
            },
            "scenarios": scenarios,
        })
    else:
        common.update({
            "expected_lost_quantity_quintals": scenarios[0]["expected_lost_quantity_quintals"],
            "remaining_saleable_quantity_quintals": scenarios[0]["remaining_saleable_quantity_quintals"],
            "break_even_selling_price_per_quintal": scenarios[0]["break_even_selling_price_per_quintal"],
        })
    return common
