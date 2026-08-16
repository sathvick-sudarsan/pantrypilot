from copy import deepcopy

import pytest
from pydantic import ValidationError

from pantrypilot.catalog import INITIAL_RECIPE_CATALOG, load_catalog
from pantrypilot.ingredients import INGREDIENT_REGISTRY

VALID_RECIPE = {
    "id": "test-recipe",
    "name": "Test Recipe",
    "required_ingredient_ids": ["eggs", "spinach"],
    "calories": 300,
    "protein_g": 20.0,
    "prep_minutes": 10,
}


def test_load_catalog_stores_valid_canonical_ids_and_freezes_collection():
    catalog = load_catalog([VALID_RECIPE], INGREDIENT_REGISTRY)

    assert isinstance(catalog, tuple)
    assert catalog[0].required_ingredient_ids == ("eggs", "spinach")


def test_load_catalog_rejects_unknown_ingredient_ids():
    record = {**VALID_RECIPE, "required_ingredient_ids": ["eggs", "unknown"]}

    with pytest.raises(
        ValueError,
        match="unknown ingredient id 'unknown' in recipe 'test-recipe'",
    ):
        load_catalog([record], INGREDIENT_REGISTRY)


def test_load_catalog_rejects_duplicate_required_ingredient_ids():
    record = {**VALID_RECIPE, "required_ingredient_ids": ["eggs", "eggs"]}

    with pytest.raises(ValidationError, match="duplicate required ingredient id"):
        load_catalog([record], INGREDIENT_REGISTRY)


def test_load_catalog_rejects_duplicate_recipe_ids():
    duplicate = {**VALID_RECIPE, "name": "Duplicate"}

    with pytest.raises(ValueError, match="duplicate recipe id"):
        load_catalog([VALID_RECIPE, duplicate], INGREDIENT_REGISTRY)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "   "),
        ("name", ""),
        ("required_ingredient_ids", []),
        ("required_ingredient_ids", ["eggs", "   "]),
        ("calories", -1),
        ("calories", float("inf")),
        ("protein_g", -0.1),
        ("protein_g", float("nan")),
        ("calories", "300"),
        ("calories", True),
        ("protein_g", "20.0"),
        ("protein_g", True),
        ("prep_minutes", -1),
        ("prep_minutes", True),
        ("prep_minutes", 10.5),
        ("prep_minutes", "10"),
    ],
)
def test_load_catalog_rejects_invalid_recipe_records(field, value):
    record = deepcopy(VALID_RECIPE)
    record[field] = value

    with pytest.raises((ValidationError, ValueError)):
        load_catalog([record], INGREDIENT_REGISTRY)


def test_load_catalog_rejects_unknown_recipe_fields():
    record = {**VALID_RECIPE, "future_field": "not approved"}

    with pytest.raises(ValidationError):
        load_catalog([record], INGREDIENT_REGISTRY)


def test_initial_recipe_catalog_loads_the_approved_recipes() -> None:
    if INITIAL_RECIPE_CATALOG is None:
        pytest.fail("INITIAL_RECIPE_CATALOG is not implemented")

    catalog = load_catalog(INITIAL_RECIPE_CATALOG, INGREDIENT_REGISTRY)

    assert [recipe.id for recipe in catalog] == [
        "spinach-omelet",
        "black-bean-tacos",
        "peanut-noodles",
        "lentil-soup",
    ]
    assert all(recipe.required_ingredient_ids for recipe in catalog)


def test_loaded_recipes_are_frozen():
    recipe = load_catalog([VALID_RECIPE], INGREDIENT_REGISTRY)[0]

    with pytest.raises(ValidationError):
        recipe.name = "Changed Recipe"
