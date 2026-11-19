import pytest

from app.tools import ToolInputError, storage_break_even


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
