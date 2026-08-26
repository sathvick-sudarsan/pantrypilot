from collections import Counter
from copy import deepcopy
from itertools import combinations
from types import MappingProxyType

import pytest
from pydantic import ValidationError

import pantrypilot.catalog as catalog_module
import pantrypilot.catalog_release as catalog_release_module
from pantrypilot.catalog import (
    FEATURE_003_RECIPE_CATALOG,
    INITIAL_RECIPE_CATALOG,
    load_catalog,
)
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

OFFICIAL_RECIPE_CATALOG = getattr(catalog_module, "OFFICIAL_RECIPE_CATALOG", None)
RETIRED_OFFICIAL_RECIPE_IDS = getattr(
    catalog_module, "RETIRED_OFFICIAL_RECIPE_IDS", None
)

RELEASE_V1_DIGEST = "f811853765a0732ae34521e47c2f7e3c691f5cb00bfec4e138f9ce08a01c9f2c"

RECIPE_REVIEW_TAGS = {
    "spinach-omelet": ({"breakfast"}, "American", "vegetarian"),
    "black-bean-tacos": ({"lunch/light-meal", "dinner"}, "Mexican", "vegan"),
    "peanut-noodles": (
        {"lunch/light-meal", "dinner"},
        "Southeast Asian",
        "vegan",
    ),
    "lentil-soup": (
        {"lunch/light-meal", "soup/stew/salad"},
        "Mediterranean",
        "vegan",
    ),
    "overnight-oats": ({"breakfast"}, "American", "vegetarian"),
    "avocado-egg-toast": ({"breakfast"}, "American", "vegetarian"),
    "yogurt-oat-bowl": ({"breakfast"}, "American", "vegetarian"),
    "tofu-rice-bowl": ({"lunch/light-meal", "dinner"}, "East Asian", "vegan"),
    "tofu-vegetable-soup": (
        {"lunch/light-meal", "soup/stew/salad"},
        "East Asian",
        "vegan",
    ),
    "beef-rice-bowl": ({"dinner"}, "East Asian", "meat"),
    "chickpea-cucumber-salad": (
        {"lunch/light-meal", "soup/stew/salad"},
        "Mediterranean",
        "vegan",
    ),
    "tomato-lentil-stew": (
        {"dinner", "soup/stew/salad"},
        "Mediterranean",
        "vegan",
    ),
    "salmon-quinoa-salad": (
        {"lunch/light-meal", "dinner", "soup/stew/salad"},
        "Mediterranean",
        "fish",
    ),
    "chickpea-rice-bowl": (
        {"lunch/light-meal", "dinner"},
        "Middle Eastern",
        "vegetarian",
    ),
    "lentil-cucumber-salad": (
        {"lunch/light-meal", "soup/stew/salad"},
        "Middle Eastern",
        "vegan",
    ),
    "potato-chickpea-curry": ({"dinner"}, "South Asian", "vegan"),
    "coconut-lentil-curry": ({"dinner"}, "South Asian", "vegan"),
    "tuna-avocado-salad": (
        {"lunch/light-meal", "soup/stew/salad"},
        "Latin American",
        "fish",
    ),
    "black-bean-quinoa-salad": (
        {"lunch/light-meal", "soup/stew/salad"},
        "Latin American",
        "vegan",
    ),
    "chicken-tacos": ({"dinner"}, "Mexican", "poultry"),
    "black-bean-rice-bowl": (
        {"lunch/light-meal", "dinner"},
        "Mexican",
        "vegan",
    ),
    "pasta-tomato-soup": (
        {"lunch/light-meal", "soup/stew/salad"},
        "Italian",
        "vegan",
    ),
    "chicken-pasta-bowl": ({"dinner"}, "Italian", "poultry"),
    "coconut-chicken-stew": (
        {"dinner", "soup/stew/salad"},
        "Southeast Asian",
        "poultry",
    ),
}


def _candidate_catalog() -> tuple[Recipe, ...]:
    if OFFICIAL_RECIPE_CATALOG is None:
        pytest.fail("OFFICIAL_RECIPE_CATALOG is not implemented")
    return OFFICIAL_RECIPE_CATALOG


def _band_counts(values, band_for_value):
    return Counter(band_for_value(value) for value in values)


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


def test_candidate_catalog_has_exact_current_and_legacy_identity_sets():
    catalog = _candidate_catalog()
    recipe_ids = tuple(recipe.id for recipe in catalog)

    assert len(catalog) == 24
    assert len(set(recipe_ids)) == 24
    assert set(recipe_ids) == set(RECIPE_REVIEW_TAGS)
    assert catalog[:4] == FEATURE_003_RECIPE_CATALOG
    assert tuple(recipe.id for recipe in FEATURE_003_RECIPE_CATALOG) == (
        "spinach-omelet",
        "black-bean-tacos",
        "peanut-noodles",
        "lentil-soup",
    )
    assert RETIRED_OFFICIAL_RECIPE_IDS == ()
    assert len(set(RETIRED_OFFICIAL_RECIPE_IDS)) == len(RETIRED_OFFICIAL_RECIPE_IDS)
    assert set(recipe_ids).isdisjoint(RETIRED_OFFICIAL_RECIPE_IDS)


def test_candidate_catalog_uses_only_registered_relationship_ids():
    catalog = _candidate_catalog()

    assert all(
        ingredient_id in INGREDIENT_REGISTRY.by_id
        for recipe in catalog
        for ingredient_id in recipe.required_ingredient_ids
    )


def test_candidate_review_tags_meet_meal_tradition_and_dietary_gates():
    catalog = _candidate_catalog()
    review_tags = {recipe.id: RECIPE_REVIEW_TAGS[recipe.id] for recipe in catalog}
    meal_counts = Counter(
        meal_tag for meal_tags, _, _ in review_tags.values() for meal_tag in meal_tags
    )
    tradition_counts = Counter(tradition for _, tradition, _ in review_tags.values())
    dietary_counts = Counter(dietary for _, _, dietary in review_tags.values())

    assert meal_counts["breakfast"] >= 4
    assert meal_counts["soup/stew/salad"] >= 4
    assert meal_counts["lunch/light-meal"] >= 1
    assert meal_counts["dinner"] >= 1
    assert len(tradition_counts) >= 8
    assert all(2 <= count <= 6 for count in tradition_counts.values())
    assert dietary_counts["vegan"] >= 6
    assert dietary_counts["vegan"] + dietary_counts["vegetarian"] >= 12
    assert sum(dietary_counts[tag] for tag in ("fish", "meat", "poultry")) >= 6


def test_candidate_recipe_fields_meet_all_numeric_coverage_bands():
    catalog = _candidate_catalog()
    preparation_counts = _band_counts(
        (recipe.prep_minutes for recipe in catalog),
        lambda value: (
            "<=15"
            if value <= 15
            else "16-30"
            if value <= 30
            else "31-45"
            if value <= 45
            else "46-60"
        ),
    )
    calorie_counts = _band_counts(
        (recipe.calories for recipe in catalog),
        lambda value: (
            "<=350"
            if value <= 350
            else "351-500"
            if value <= 500
            else "501-650"
            if value <= 650
            else ">650"
        ),
    )
    protein_counts = _band_counts(
        (recipe.protein_g for recipe in catalog),
        lambda value: (
            "<15"
            if value < 15
            else "15-24.9"
            if value < 25
            else "25-34.9"
            if value < 35
            else ">=35"
        ),
    )
    ingredient_count_bands = _band_counts(
        (len(recipe.required_ingredient_ids) for recipe in catalog),
        lambda value: "3-4" if value <= 4 else "5-6" if value <= 6 else "7-8",
    )

    assert all(recipe.prep_minutes <= 60 for recipe in catalog)
    assert all(
        preparation_counts[band] >= 4 for band in ("<=15", "16-30", "31-45", "46-60")
    )
    assert all(
        calorie_counts[band] >= 1 for band in ("<=350", "351-500", "501-650", ">650")
    )
    assert all(
        protein_counts[band] >= 4 for band in ("<15", "15-24.9", "25-34.9", ">=35")
    )
    assert all(3 <= len(recipe.required_ingredient_ids) <= 8 for recipe in catalog)
    assert all(ingredient_count_bands[band] >= 4 for band in ("3-4", "5-6", "7-8"))


def test_candidate_catalog_meets_recipe_and_ingredient_overlap_gates():
    catalog = _candidate_catalog()
    ingredient_sets = {
        recipe.id: set(recipe.required_ingredient_ids) for recipe in catalog
    }
    overlapping_pairs = [
        (first_id, second_id)
        for first_id, second_id in combinations(ingredient_sets, 2)
        if len(ingredient_sets[first_id] & ingredient_sets[second_id]) >= 2
    ]
    ingredient_usage = Counter(
        ingredient_id
        for recipe in catalog
        for ingredient_id in recipe.required_ingredient_ids
    )

    assert all(
        any(
            recipe_id != other_id
            and bool(ingredient_sets[recipe_id] & ingredient_sets[other_id])
            for other_id in ingredient_sets
        )
        for recipe_id in ingredient_sets
    )
    assert len(overlapping_pairs) >= 6
    assert sum(4 <= count < len(catalog) for count in ingredient_usage.values()) >= 10


def test_candidate_recipes_have_distinct_unordered_ingredient_sets():
    recipes_by_ingredient_set: dict[frozenset[str], str] = {}

    for recipe in _candidate_catalog():
        ingredient_set = frozenset(recipe.required_ingredient_ids)
        existing_recipe_id = recipes_by_ingredient_set.get(ingredient_set)
        if existing_recipe_id is not None:
            pytest.fail(
                f"recipes '{existing_recipe_id}' and '{recipe.id}' share identical "
                f"required ingredient set: {sorted(ingredient_set)}"
            )
        recipes_by_ingredient_set[ingredient_set] = recipe.id


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


def test_current_catalog_release_pins_the_approved_version_one_manifest():
    assert catalog_release_module.CURRENT_CATALOG_CONTENT_VERSION == 1
    assert catalog_release_module.CATALOG_RELEASE_DIGESTS == {1: RELEASE_V1_DIGEST}
    assert isinstance(catalog_release_module.CATALOG_RELEASE_DIGESTS, MappingProxyType)
    with pytest.raises(TypeError):
        catalog_release_module.CATALOG_RELEASE_DIGESTS[1] = "a" * 64

    release = catalog_release_module.current_catalog_release(INGREDIENT_REGISTRY)

    assert release.version == 1
    assert release.manifest_digest == RELEASE_V1_DIGEST
    assert len(release.recipes) == 24
    assert release.recipes == tuple(
        sorted(OFFICIAL_RECIPE_CATALOG, key=lambda recipe: recipe.id)
    )
    with pytest.raises(ValidationError):
        release.recipes[0].name = "Changed Recipe"


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
def test_current_catalog_release_rejects_scalar_manifest_drift(
    monkeypatch, field, value
):
    changed = OFFICIAL_RECIPE_CATALOG[0].model_copy(update={field: value})
    monkeypatch.setattr(
        catalog_release_module,
        "OFFICIAL_RECIPE_CATALOG",
        (changed, *OFFICIAL_RECIPE_CATALOG[1:]),
    )

    with pytest.raises(
        ValueError, match="current manifest digest does not match ledger"
    ):
        catalog_release_module.current_catalog_release(INGREDIENT_REGISTRY)


@pytest.mark.parametrize(
    "recipes, retired_recipe_ids",
    [
        (
            lambda: (
                OFFICIAL_RECIPE_CATALOG[0].model_copy(
                    update={
                        "required_ingredient_ids": tuple(
                            reversed(OFFICIAL_RECIPE_CATALOG[0].required_ingredient_ids)
                        )
                    }
                ),
                *OFFICIAL_RECIPE_CATALOG[1:],
            ),
            (),
        ),
        (lambda: (*OFFICIAL_RECIPE_CATALOG, _release_recipe("added-recipe")), ()),
        (lambda: OFFICIAL_RECIPE_CATALOG[:-1], ()),
        (lambda: OFFICIAL_RECIPE_CATALOG, ("retired-recipe",)),
    ],
)
def test_current_catalog_release_rejects_non_scalar_manifest_drift(
    monkeypatch, recipes, retired_recipe_ids
):
    monkeypatch.setattr(catalog_release_module, "OFFICIAL_RECIPE_CATALOG", recipes())
    monkeypatch.setattr(
        catalog_release_module, "RETIRED_OFFICIAL_RECIPE_IDS", retired_recipe_ids
    )

    with pytest.raises(
        ValueError, match="current manifest digest does not match ledger"
    ):
        catalog_release_module.current_catalog_release(INGREDIENT_REGISTRY)
