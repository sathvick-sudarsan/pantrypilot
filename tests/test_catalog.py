from copy import deepcopy

import pytest
from pydantic import ValidationError

import pantrypilot.catalog as catalog_module
from pantrypilot.catalog import load_catalog

VALID_RECIPE = {
    "id": "test-recipe",
    "name": "Test Recipe",
    "required_ingredients": [" Eggs ", "spinach", "EGGS"],
    "calories": 300,
    "protein_g": 20.0,
    "prep_minutes": 10,
}


def test_load_catalog_normalizes_ingredients_once_and_freezes_collection():
    catalog = load_catalog([VALID_RECIPE])

    assert isinstance(catalog, tuple)
    assert catalog[0].required_ingredients == ("eggs", "spinach")


def test_load_catalog_rejects_duplicate_recipe_ids():
    duplicate = {**VALID_RECIPE, "name": "Duplicate"}

    with pytest.raises(ValueError, match="duplicate recipe id"):
        load_catalog([VALID_RECIPE, duplicate])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "   "),
        ("name", ""),
        ("required_ingredients", []),
        ("required_ingredients", ["valid", "   "]),
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
        load_catalog([record])


def test_load_catalog_rejects_unknown_recipe_fields():
    record = {**VALID_RECIPE, "future_field": "not approved"}

    with pytest.raises(ValidationError):
        load_catalog([record])


def test_catalog_is_the_approved_immutable_recipe_set():
    assert [recipe.model_dump() for recipe in catalog_module.CATALOG] == [
        {
            "id": "spinach-omelet",
            "name": "Spinach Omelet",
            "required_ingredients": ("eggs", "spinach", "olive oil"),
            "calories": 410,
            "protein_g": 28.0,
            "prep_minutes": 15,
        },
        {
            "id": "black-bean-tacos",
            "name": "Black Bean Tacos",
            "required_ingredients": (
                "black beans",
                "corn tortillas",
                "avocado",
                "lime",
            ),
            "calories": 520,
            "protein_g": 19.0,
            "prep_minutes": 25,
        },
        {
            "id": "peanut-noodles",
            "name": "Peanut Noodles",
            "required_ingredients": ("noodles", "peanuts", "soy sauce"),
            "calories": 560,
            "protein_g": 20.0,
            "prep_minutes": 20,
        },
        {
            "id": "lentil-soup",
            "name": "Lentil Soup",
            "required_ingredients": (
                "lentils",
                "carrots",
                "celery",
                "vegetable broth",
            ),
            "calories": 360,
            "protein_g": 22.0,
            "prep_minutes": 45,
        },
    ]


def test_loaded_recipes_are_frozen():
    recipe = load_catalog([VALID_RECIPE])[0]

    with pytest.raises(ValidationError):
        recipe.name = "Changed Recipe"
