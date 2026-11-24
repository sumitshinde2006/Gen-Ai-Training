import pytest

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


def test_storage_break_even_calculates_explicit_loss():
    result = storage_break_even(100, 2000, 3, 30)

    assert result["todays_gross_revenue"] == "200000.00"
    assert result["expected_lost_quantity_quintals"] == "30.00"
    assert result["remaining_saleable_quantity_quintals"] == "70.00"
    assert result["break_even_selling_price_per_quintal"] == "2857.14"


def test_storage_break_even_rejects_invalid_quantity():
    with pytest.raises(ToolInputError, match="quantity_quintals must be greater than zero"):
        storage_break_even(0, 2000, 3, 30)


def test_storage_break_even_rejects_loss_of_one_hundred_percent():
    with pytest.raises(ToolInputError, match="below 100"):
        storage_break_even(100, 2000, 3, 100)


def test_profit_tool_sums_multiple_price_groups_deterministically():
    result = profit_calculation(
        6500,
        [
            {"percentage": 70, "price_per_kg": 25},
            {"percentage": 30, "price_per_kg": 18},
        ],
        20000,
    )

    assert result["total_revenue"] == "148850.00"
    assert result["net_profit"] == "128850.00"


def test_profit_tool_rejects_incomplete_percentages():
    with pytest.raises(ToolInputError, match="not 100%"):
        profit_calculation(
            1000,
            [
                {"percentage": 70, "price_per_kg": 25},
                {"percentage": 20, "price_per_kg": 18},
            ],
            2000,
        )


def test_storage_loss_tool_returns_remaining_stock():
    result = storage_loss_calculation(10000, 10, unit="kg")

    assert result["lost_quantity"] == "1000.00"
    assert result["remaining_quantity"] == "9000.00"


def test_cost_percentage_price_comparison_and_arithmetic_tools():
    assert cost_total_calculation([
        {"label": "Transport", "amount": 500},
        {"label": "Labour", "amount": 250},
    ])["total_cost"] == "750.00"
    assert percentage_calculation(15, 20000)["result"] == "3000.00"
    comparison = price_comparison_calculation([
        {"label": "Offer A", "value": 20, "unit": "per_kg"},
        {"label": "Offer B", "value": 2000, "unit": "per_quintal"},
    ])
    assert comparison["difference"] == "0.00"
    assert arithmetic_calculation("add", [12, 3])["result"] == "15.00"


def test_arithmetic_tool_rejects_division_by_zero():
    with pytest.raises(ToolInputError, match="Division by zero"):
        arithmetic_calculation("divide", [5, 0])
