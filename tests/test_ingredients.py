import pytest
from pydantic import ValidationError

from pantrypilot.ingredients import (
    CanonicalIngredient,
    load_ingredient_registry,
)

VALID_INGREDIENTS = (
    {
        "id": "black-beans",
        "canonical_name": " Black Beans ",
        "aliases": ["Black Bean"],
    },
    {
        "id": "vegetable-broth",
        "canonical_name": "vegetable broth",
        "aliases": ["vegetable stock"],
    },
)


def test_load_ingredient_registry_normalizes_terms_and_builds_read_only_indexes():
    registry = load_ingredient_registry(VALID_INGREDIENTS)

    assert tuple(registry.by_id) == ("black-beans", "vegetable-broth")
    assert registry.by_id["black-beans"] == CanonicalIngredient(
        id="black-beans",
        canonical_name="black beans",
        aliases=("black bean",),
    )
    assert dict(registry.by_term) == {
        "black beans": "black-beans",
        "black bean": "black-beans",
        "vegetable broth": "vegetable-broth",
        "vegetable stock": "vegetable-broth",
    }
    with pytest.raises(TypeError):
        registry.by_id["other"] = registry.by_id["black-beans"]
    with pytest.raises(TypeError):
        registry.by_term["beans"] = "black-beans"


@pytest.mark.parametrize("ingredient_id", ["", "Black-Beans", "black beans", "-beans"])
def test_registry_rejects_invalid_machine_ids(ingredient_id):
    record = {**VALID_INGREDIENTS[0], "id": ingredient_id}

    with pytest.raises(ValidationError):
        load_ingredient_registry([record])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("canonical_name", "   "),
        ("aliases", ["black bean", "  "]),
    ],
)
def test_registry_rejects_blank_terms(field, value):
    record = {**VALID_INGREDIENTS[0], field: value}

    with pytest.raises(ValidationError, match="must not be blank"):
        load_ingredient_registry([record])


def test_registry_rejects_unknown_record_fields():
    record = {**VALID_INGREDIENTS[0], "ontology_code": "future"}

    with pytest.raises(ValidationError):
        load_ingredient_registry([record])


def test_canonical_ingredient_records_are_frozen():
    ingredient = load_ingredient_registry([VALID_INGREDIENTS[0]]).by_id["black-beans"]

    with pytest.raises(ValidationError):
        ingredient.canonical_name = "beans"


def test_registry_rejects_duplicate_ids():
    duplicate = {**VALID_INGREDIENTS[0], "canonical_name": "beans"}

    with pytest.raises(ValueError, match="duplicate ingredient id: black-beans"):
        load_ingredient_registry([VALID_INGREDIENTS[0], duplicate])


def test_registry_rejects_duplicate_aliases_after_normalization():
    record = {
        **VALID_INGREDIENTS[0],
        "aliases": ["black bean", " BLACK BEAN "],
    }

    with pytest.raises(ValidationError, match="duplicate ingredient alias"):
        load_ingredient_registry([record])


def test_registry_rejects_alias_equal_to_its_canonical_name():
    record = {**VALID_INGREDIENTS[0], "aliases": [" BLACK BEANS "]}

    with pytest.raises(
        ValidationError, match="ingredient alias duplicates canonical name"
    ):
        load_ingredient_registry([record])


@pytest.mark.parametrize(
    "second_record",
    [
        {
            "id": "other",
            "canonical_name": "BLACK BEANS",
            "aliases": [],
        },
        {
            "id": "other",
            "canonical_name": "beans",
            "aliases": ["black beans"],
        },
        {
            "id": "other",
            "canonical_name": "beans",
            "aliases": ["black bean"],
        },
    ],
)
def test_registry_rejects_every_cross_identity_term_collision(second_record):
    with pytest.raises(ValueError, match="ingredient term"):
        load_ingredient_registry([VALID_INGREDIENTS[0], second_record])
