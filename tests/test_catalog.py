from copy import deepcopy

import pytest
from pydantic import ValidationError

from pantrypilot.catalog import INITIAL_RECIPE_CATALOG, load_catalog
from pantrypilot.catalog_release import (
    build_catalog_release,
    canonical_manifest_bytes,
    catalog_manifest_digest,
)
from pantrypilot.ingredients import INGREDIENT_REGISTRY
from pantrypilot.models import Recipe

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


def _release_recipe(
    recipe_id: str = "a-recipe",
    *,
    name: str = "A Recipe",
    calories: int | float = 100,
    protein_g: float = 10.0,
    prep_minutes: int = 15,
    required_ingredient_ids: tuple[str, ...] = ("eggs", "spinach"),
) -> Recipe:
    return Recipe(
        id=recipe_id,
        name=name,
        required_ingredient_ids=required_ingredient_ids,
        calories=calories,
        protein_g=protein_g,
        prep_minutes=prep_minutes,
    )


def test_canonical_manifest_bytes_uses_the_approved_shape_and_encoding():
    recipe = _release_recipe()

    assert canonical_manifest_bytes([recipe], ["retired-recipe"]) == (
        b'{"recipes":[{"id":"a-recipe","name":"A Recipe","calories":100,'
        b'"protein_g":10.0,"prep_minutes":15,"required_ingredient_ids":'
        b'["eggs","spinach"]}],"retired_official_recipe_ids":'
        b'["retired-recipe"]}'
    )


def test_manifest_ordering_is_canonical_but_relationship_order_is_preserved():
    first = _release_recipe("a-recipe")
    second = _release_recipe("b-recipe", name="B Recipe")
    reversed_recipes = [second, first]

    assert canonical_manifest_bytes([first, second], []) == canonical_manifest_bytes(
        reversed_recipes, []
    )
    assert catalog_manifest_digest([first, second], ["retired-b", "retired-a"]) == (
        catalog_manifest_digest(reversed_recipes, ["retired-a", "retired-b"])
    )
    reordered = _release_recipe(required_ingredient_ids=("spinach", "eggs"))
    assert catalog_manifest_digest([first], []) != catalog_manifest_digest(
        [reordered], []
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "changed-recipe"),
        ("name", "Changed Recipe"),
        ("calories", 101),
        ("protein_g", 10.1),
        ("prep_minutes", 16),
    ],
)
def test_each_manifest_scalar_changes_the_digest(field, value):
    recipe = _release_recipe()
    changed = recipe.model_copy(update={field: value})

    assert catalog_manifest_digest([recipe], []) != catalog_manifest_digest(
        [changed], []
    )


def test_adding_or_removing_a_recipe_changes_the_digest():
    first = _release_recipe()
    second = _release_recipe("b-recipe", name="B Recipe")

    assert catalog_manifest_digest([first], []) != catalog_manifest_digest(
        [first, second], []
    )


def test_adding_or_removing_a_retired_id_changes_the_digest():
    recipe = _release_recipe()

    assert catalog_manifest_digest([recipe], []) != catalog_manifest_digest(
        [recipe], ["retired-recipe"]
    )


TWO_RECIPE_RELEASE_DIGEST = (
    "f763e3d4db7b4b17aa4103eff3b6f4b8f090e29d65827f0ee2361a02eeb76226"
)


def test_build_catalog_release_freezes_and_sorts_recipes_and_retired_ids():
    recipes = [_release_recipe("b-recipe", name="B Recipe"), _release_recipe()]
    release = build_catalog_release(
        reversed(recipes),
        ["retired-b", "retired-a"],
        INGREDIENT_REGISTRY,
        1,
        {1: TWO_RECIPE_RELEASE_DIGEST},
    )

    assert [recipe.id for recipe in release.recipes] == ["a-recipe", "b-recipe"]
    assert release.retired_recipe_ids == ("retired-a", "retired-b")
    assert release.version == 1
    assert release.manifest_digest == TWO_RECIPE_RELEASE_DIGEST


@pytest.mark.parametrize(
    ("recipes", "retired_recipe_ids", "match"),
    [
        ([_release_recipe(), _release_recipe()], [], "duplicate current recipe id"),
        (
            [_release_recipe()],
            ["retired-recipe", "retired-recipe"],
            "duplicate retired recipe id",
        ),
        ([_release_recipe()], ["a-recipe"], "current and retired recipe id overlap"),
        (
            [_release_recipe("Not-Kebab")],
            [],
            "official recipe id must be lowercase kebab-case",
        ),
        (
            [_release_recipe(required_ingredient_ids=("unknown",))],
            [],
            "unknown ingredient id",
        ),
    ],
)
def test_build_catalog_release_rejects_invalid_catalog_identity(
    recipes, retired_recipe_ids, match
):
    with pytest.raises(ValueError, match=match):
        build_catalog_release(
            recipes,
            retired_recipe_ids,
            INGREDIENT_REGISTRY,
            1,
            {1: "0" * 64},
        )


def test_build_catalog_release_rejects_malformed_retired_id():
    recipes = [_release_recipe()]

    with pytest.raises(
        ValueError, match="retired recipe id must be lowercase kebab-case"
    ):
        build_catalog_release(
            recipes,
            ["Retired Recipe"],
            INGREDIENT_REGISTRY,
            1,
            {1: "0" * 64},
        )


@pytest.mark.parametrize(
    ("current_version", "release_digests", "match"),
    [
        (0, {}, "current version must be positive"),
        (2, {1: "a" * 64}, "release digest versions must be consecutive"),
        (1, {1: "a" * 64, 2: "a" * 64}, "release digest versions must be consecutive"),
        (1, {1: "A" * 64}, "release ledger digest must be lowercase 64-hex"),
        (1, {1: "not-a-digest"}, "release ledger digest must be lowercase 64-hex"),
    ],
)
def test_build_catalog_release_rejects_invalid_release_ledger(
    current_version, release_digests, match
):
    recipes = [_release_recipe()]

    with pytest.raises(ValueError, match=match):
        build_catalog_release(
            recipes,
            [],
            INGREDIENT_REGISTRY,
            current_version,
            release_digests,
        )


def test_build_catalog_release_rejects_current_digest_mismatch():
    recipes = [_release_recipe()]

    with pytest.raises(
        ValueError, match="current manifest digest does not match ledger"
    ):
        build_catalog_release(
            recipes,
            [],
            INGREDIENT_REGISTRY,
            1,
            {1: "a" * 64},
        )
