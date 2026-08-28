import pytest
from pydantic import ValidationError

import pantrypilot.catalog as catalog_module
from pantrypilot.ingredients import (
    INGREDIENT_REGISTRY,
    RAW_INGREDIENTS,
    CanonicalIngredient,
    IngredientResolution,
    load_ingredient_registry,
    resolve_ingredient,
    resolve_ingredients,
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

ORIGINAL_RAW_INGREDIENTS = (
    {"id": "eggs", "canonical_name": "eggs", "aliases": ["egg"]},
    {"id": "spinach", "canonical_name": "spinach", "aliases": []},
    {"id": "olive-oil", "canonical_name": "olive oil", "aliases": []},
    {
        "id": "black-beans",
        "canonical_name": "black beans",
        "aliases": ["black bean"],
    },
    {
        "id": "corn-tortillas",
        "canonical_name": "corn tortillas",
        "aliases": ["corn tortilla"],
    },
    {"id": "avocado", "canonical_name": "avocado", "aliases": []},
    {"id": "lime", "canonical_name": "lime", "aliases": []},
    {"id": "noodles", "canonical_name": "noodles", "aliases": []},
    {"id": "peanuts", "canonical_name": "peanuts", "aliases": ["peanut"]},
    {"id": "soy-sauce", "canonical_name": "soy sauce", "aliases": []},
    {"id": "lentils", "canonical_name": "lentils", "aliases": ["lentil"]},
    {"id": "carrots", "canonical_name": "carrots", "aliases": ["carrot"]},
    {"id": "celery", "canonical_name": "celery", "aliases": []},
    {
        "id": "vegetable-broth",
        "canonical_name": "vegetable broth",
        "aliases": ["vegetable stock"],
    },
)

NEW_CANONICAL_INGREDIENTS = {
    "oats": ("oats", ("oat",)),
    "bananas": ("bananas", ("banana",)),
    "berries": ("berries", ()),
    "milk": ("milk", ()),
    "yogurt": ("yogurt", ()),
    "bread": ("bread", ()),
    "tofu": ("tofu", ()),
    "rice": ("rice", ()),
    "broccoli": ("broccoli", ()),
    "garlic": ("garlic", ()),
    "ginger": ("ginger", ()),
    "onion": ("onion", ()),
    "ground-beef": ("ground beef", ()),
    "chickpeas": ("chickpeas", ("chickpea",)),
    "cucumbers": ("cucumbers", ("cucumber",)),
    "tomatoes": ("tomatoes", ("tomato",)),
    "salmon": ("salmon", ()),
    "quinoa": ("quinoa", ()),
    "potatoes": ("potatoes", ("potato",)),
    "coconut-milk": ("coconut milk", ()),
    "tuna": ("tuna", ()),
    "chicken": ("chicken", ()),
    "cabbage": ("cabbage", ()),
    "pasta": ("pasta", ()),
    "cheese": ("cheese", ()),
}

PROPOSED_ALIAS_CASES = (
    ("oat", "oats"),
    ("banana", "bananas"),
    ("chickpea", "chickpeas"),
    ("cucumber", "cucumbers"),
    ("tomato", "tomatoes"),
    ("potato", "potatoes"),
)

TARGETED_CONFUSABLE_NEGATIVES = (
    "oat milk",
    "banana peppers",
    "chickpea flour",
    "cucumber water",
    "tomato paste",
    "sweet potato",
)


def test_resolve_ingredient_returns_canonical_evidence_after_normalization():
    registry = load_ingredient_registry(VALID_INGREDIENTS)

    resolution = resolve_ingredient(" BLACK BEANS ", registry)

    assert resolution.model_dump() == {
        "input": " BLACK BEANS ",
        "normalized": "black beans",
        "ingredient_id": "black-beans",
        "canonical_name": "black beans",
        "match_type": "canonical",
    }


def test_resolve_ingredient_returns_explicit_alias_evidence():
    registry = load_ingredient_registry(VALID_INGREDIENTS)

    resolution = resolve_ingredient("Black Bean", registry)

    assert resolution.model_dump() == {
        "input": "Black Bean",
        "normalized": "black bean",
        "ingredient_id": "black-beans",
        "canonical_name": "black beans",
        "match_type": "alias",
    }


def test_resolve_ingredient_abstains_on_unsupported_text():
    registry = load_ingredient_registry(VALID_INGREDIENTS)

    resolution = resolve_ingredient("black bean sauce", registry)

    assert resolution.model_dump() == {
        "input": "black bean sauce",
        "normalized": "black bean sauce",
        "ingredient_id": None,
        "canonical_name": None,
        "match_type": "unresolved",
    }


@pytest.mark.parametrize(
    "fields",
    [
        {
            "ingredient_id": "black-beans",
            "canonical_name": "black beans",
            "match_type": "unresolved",
        },
        {
            "ingredient_id": None,
            "canonical_name": None,
            "match_type": "alias",
        },
    ],
)
def test_ingredient_resolution_rejects_contradictory_states(fields):
    with pytest.raises(ValidationError):
        IngredientResolution(
            input="black bean",
            normalized="black bean",
            **fields,
        )


def test_resolve_ingredients_preserves_every_input_in_order():
    registry = load_ingredient_registry(VALID_INGREDIENTS)

    resolutions = resolve_ingredients(
        ["black beans", "black bean", "BLACK BEANS", "unknown"],
        registry,
    )

    assert [resolution.input for resolution in resolutions] == [
        "black beans",
        "black bean",
        "BLACK BEANS",
        "unknown",
    ]
    assert [resolution.ingredient_id for resolution in resolutions] == [
        "black-beans",
        "black-beans",
        "black-beans",
        None,
    ]


def test_application_registry_preserves_the_original_canonical_identity_set():
    original_ids = {record["id"] for record in ORIGINAL_RAW_INGREDIENTS}

    assert RAW_INGREDIENTS[: len(ORIGINAL_RAW_INGREDIENTS)] == ORIGINAL_RAW_INGREDIENTS
    assert {
        ingredient.id: (ingredient.canonical_name, ingredient.aliases)
        for ingredient in INGREDIENT_REGISTRY.by_id.values()
        if ingredient.id in original_ids
    } == {
        "eggs": ("eggs", ("egg",)),
        "spinach": ("spinach", ()),
        "olive-oil": ("olive oil", ()),
        "black-beans": ("black beans", ("black bean",)),
        "corn-tortillas": ("corn tortillas", ("corn tortilla",)),
        "avocado": ("avocado", ()),
        "lime": ("lime", ()),
        "noodles": ("noodles", ()),
        "peanuts": ("peanuts", ("peanut",)),
        "soy-sauce": ("soy sauce", ()),
        "lentils": ("lentils", ("lentil",)),
        "carrots": ("carrots", ("carrot",)),
        "celery": ("celery", ()),
        "vegetable-broth": ("vegetable broth", ("vegetable stock",)),
    }


def test_application_registry_contains_only_the_needed_new_candidate_ids():
    new_records = RAW_INGREDIENTS[len(ORIGINAL_RAW_INGREDIENTS) :]

    assert tuple(record["id"] for record in new_records) == tuple(
        NEW_CANONICAL_INGREDIENTS
    )
    assert {
        ingredient.id: (ingredient.canonical_name, ingredient.aliases)
        for ingredient in INGREDIENT_REGISTRY.by_id.values()
        if ingredient.id in NEW_CANONICAL_INGREDIENTS
    } == NEW_CANONICAL_INGREDIENTS


def test_every_new_registry_id_is_used_by_the_candidate_catalog():
    catalog = getattr(catalog_module, "OFFICIAL_RECIPE_CATALOG", None)
    if catalog is None:
        pytest.fail("OFFICIAL_RECIPE_CATALOG is not implemented")
    used_ids = {
        ingredient_id
        for recipe in catalog
        for ingredient_id in recipe.required_ingredient_ids
    }

    assert set(NEW_CANONICAL_INGREDIENTS) <= used_ids


@pytest.mark.parametrize(("value", "ingredient_id"), PROPOSED_ALIAS_CASES)
def test_candidate_aliases_resolve_only_the_reviewed_exact_terms(value, ingredient_id):
    resolution = resolve_ingredient(value, INGREDIENT_REGISTRY)

    assert resolution.ingredient_id == ingredient_id
    assert resolution.match_type == "alias"


@pytest.mark.parametrize("value", TARGETED_CONFUSABLE_NEGATIVES)
def test_candidate_confusable_inputs_remain_unresolved(value):
    resolution = resolve_ingredient(value, INGREDIENT_REGISTRY)

    assert resolution.ingredient_id is None
    assert resolution.match_type == "unresolved"


def test_identical_input_and_registry_produce_identical_resolution():
    first = resolve_ingredients([" Black Bean ", "unknown"], INGREDIENT_REGISTRY)
    second = resolve_ingredients([" Black Bean ", "unknown"], INGREDIENT_REGISTRY)

    assert first == second


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
