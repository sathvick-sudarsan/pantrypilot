import pytest

from pantrypilot.normalization import normalize_ingredients


def test_normalize_ingredients_trims_lowercases_and_stably_deduplicates():
    assert normalize_ingredients([" Eggs ", "spinach", "EGGS", "Olive  Oil"]) == (
        "eggs",
        "spinach",
        "olive  oil",
    )


def test_normalize_ingredients_rejects_blank_values():
    with pytest.raises(ValueError, match="must not be blank"):
        normalize_ingredients(["eggs", "   "])
