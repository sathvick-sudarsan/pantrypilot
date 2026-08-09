from decimal import Decimal

import pytest

from pantrypilot.catalog import CATALOG
from pantrypilot.ingredients import INGREDIENT_REGISTRY
from pantrypilot.models import RankingRequest, Recipe
from pantrypilot.ranking import (
    UnresolvedExcludedIngredientsError,
    calculate_score,
    is_eligible,
    match_ingredients,
    rank_recipes,
    render_explanation,
)


def make_recipe(
    *,
    recipe_id: str = "recipe",
    required: tuple[str, ...] = ("eggs", "spinach", "olive-oil"),
    protein_g: float = 20.0,
    prep_minutes: int = 10,
) -> Recipe:
    return Recipe(
        id=recipe_id,
        name=recipe_id.replace("-", " ").title(),
        required_ingredient_ids=required,
        calories=300,
        protein_g=protein_g,
        prep_minutes=prep_minutes,
    )


def make_request(
    *,
    pantry_items: list[str] | None = None,
    min_protein_g: float = 20.0,
    max_prep_minutes: int = 30,
    excluded_ingredients: list[str] | None = None,
    limit: int = 5,
) -> RankingRequest:
    return RankingRequest(
        pantry_items=[] if pantry_items is None else pantry_items,
        min_protein_g=min_protein_g,
        max_prep_minutes=max_prep_minutes,
        excluded_ingredients=(
            [] if excluded_ingredients is None else excluded_ingredients
        ),
        limit=limit,
    )


def test_empty_pantry_marks_every_required_ingredient_missing():
    matched, missing = match_ingredients(make_recipe(), set(), INGREDIENT_REGISTRY)

    assert matched == ()
    assert missing == ("eggs", "spinach", "olive oil")


def test_matching_uses_only_resolved_canonical_ids():
    recipe = make_recipe(required=("olive-oil", "black-beans"))

    matched, missing = match_ingredients(
        recipe,
        {"oil", "beans"},
        INGREDIENT_REGISTRY,
    )

    assert matched == ()
    assert missing == ("olive oil", "black beans")


def test_matching_compares_ids_and_returns_canonical_names_in_recipe_order():
    matched, missing = match_ingredients(
        make_recipe(),
        {"spinach", "eggs"},
        INGREDIENT_REGISTRY,
    )

    assert matched == ("eggs", "spinach")
    assert missing == ("olive oil",)


def test_excluded_ingredient_makes_recipe_ineligible():
    assert not is_eligible(make_recipe(), {"spinach"}, 30)


def test_exclusion_takes_precedence_over_pantry_presence():
    recipe = make_recipe()
    matched, _ = match_ingredients(recipe, {"spinach"}, INGREDIENT_REGISTRY)

    assert matched == ("spinach",)
    assert not is_eligible(recipe, {"spinach"}, 30)


def test_maximum_preparation_time_is_inclusive():
    assert is_eligible(make_recipe(prep_minutes=30), set(), 30)


def test_recipe_over_maximum_preparation_time_is_ineligible():
    assert not is_eligible(make_recipe(prep_minutes=31), set(), 30)


@pytest.mark.parametrize(
    ("matched_count", "expected"),
    [(0, 0.0), (1, 0.3333), (3, 1.0)],
)
def test_pantry_coverage_handles_empty_partial_and_complete_matches(
    matched_count, expected
):
    _, breakdown = calculate_score(
        make_recipe(), matched_count, min_protein_g=20.0, max_prep_minutes=20
    )

    assert breakdown.pantry_coverage.value == expected


@pytest.mark.parametrize(
    ("protein_g", "target", "expected"),
    [
        (10.0, 20.0, 0.5),
        (20.0, 20.0, 1.0),
        (30.0, 20.0, 1.0),
    ],
)
def test_protein_fit_is_capped(protein_g, target, expected):
    _, breakdown = calculate_score(
        make_recipe(protein_g=protein_g),
        matched_count=0,
        min_protein_g=target,
        max_prep_minutes=20,
    )

    assert breakdown.protein_fit.value == expected


@pytest.mark.parametrize(
    ("prep_minutes", "maximum", "expected"),
    [
        (0, 30, 1.0),
        (15, 30, 0.5),
        (30, 30, 0.0),
    ],
)
def test_time_fit_handles_zero_between_and_maximum(prep_minutes, maximum, expected):
    _, breakdown = calculate_score(
        make_recipe(prep_minutes=prep_minutes),
        matched_count=0,
        min_protein_g=20.0,
        max_prep_minutes=maximum,
    )

    assert breakdown.time_fit.value == expected


def test_contributions_use_full_precision_before_four_decimal_rounding():
    recipe = make_recipe(required=tuple(f"item-{i}" for i in range(9)))

    final_score, breakdown = calculate_score(
        recipe,
        matched_count=2,
        min_protein_g=20.0,
        max_prep_minutes=20,
    )

    assert breakdown.pantry_coverage.value == 0.2222
    assert breakdown.pantry_coverage.contribution == 0.1556
    assert final_score == 0.4056


def test_final_score_is_exactly_reconstructable_from_returned_contributions():
    final_score, breakdown = calculate_score(
        make_recipe(protein_g=28.0, prep_minutes=15),
        matched_count=2,
        min_protein_g=25.0,
        max_prep_minutes=30,
    )
    contributions = (
        breakdown.pantry_coverage.contribution,
        breakdown.protein_fit.contribution,
        breakdown.time_fit.contribution,
    )

    assert final_score == 0.7167
    assert Decimal(str(final_score)) == sum(
        (Decimal(str(value)) for value in contributions),
        start=Decimal("0"),
    )
    assert 0.0 <= final_score <= 1.0


def test_protein_fit_is_one_when_target_is_zero():
    _, breakdown = calculate_score(
        make_recipe(protein_g=0.0),
        matched_count=0,
        min_protein_g=0.0,
        max_prep_minutes=20,
    )

    assert breakdown.protein_fit.value == 1.0


def test_time_fit_is_one_when_maximum_is_zero():
    _, breakdown = calculate_score(
        make_recipe(prep_minutes=0),
        matched_count=0,
        min_protein_g=20.0,
        max_prep_minutes=0,
    )

    assert breakdown.time_fit.value == 1.0


@pytest.mark.parametrize(
    ("protein_g", "target", "phrase"),
    [
        (28.0, 25.0, "meets"),
        (20.0, 25.0, "is below"),
    ],
)
def test_explanation_uses_one_exact_template(protein_g, target, phrase):
    recipe = make_recipe(protein_g=protein_g, prep_minutes=15)
    _, breakdown = calculate_score(
        recipe,
        matched_count=2,
        min_protein_g=target,
        max_prep_minutes=30,
    )

    explanation = render_explanation(
        recipe,
        matched_count=2,
        min_protein_g=target,
        max_prep_minutes=30,
        score_breakdown=breakdown,
    )

    assert explanation == (
        "Matched 2 of 3 required ingredients (coverage 0.6667); "
        f"{protein_g:.1f}g protein {phrase} the {target:.1f}g target "
        f"(fit {breakdown.protein_fit.value:.4f}); 15 minutes is within "
        "the 30-minute limit (fit 0.5000)."
    )


def test_rank_recipes_resolves_aliases_and_unknown_pantry_terms_before_matching():
    request = make_request(
        pantry_items=[
            "black bean",
            "corn tortillas",
            "avocado",
            "lime",
            "mystery ingredient",
            "black beans",
        ],
        min_protein_g=0.0,
        max_prep_minutes=30,
        excluded_ingredients=["peanut"],
        limit=50,
    )

    response = rank_recipes(request, CATALOG, INGREDIENT_REGISTRY)
    tacos = next(
        result for result in response.results if result.id == "black-bean-tacos"
    )

    assert [result.id for result in response.results] == [
        "black-bean-tacos",
        "spinach-omelet",
    ]
    assert tacos.matched_ingredients == (
        "black beans",
        "corn tortillas",
        "avocado",
        "lime",
    )
    assert tacos.missing_ingredients == ()
    assert tacos.score_breakdown.pantry_coverage.value == 1.0
    assert tacos.score_breakdown.pantry_coverage.contribution == 0.7
    assert tacos.final_score == 0.9167
    assert [
        item.match_type for item in response.ingredient_resolution.pantry_items
    ] == [
        "alias",
        "canonical",
        "canonical",
        "canonical",
        "unresolved",
        "canonical",
    ]
    assert response.ingredient_resolution.excluded_ingredients[0].ingredient_id == (
        "peanuts"
    )


def test_black_bean_taco_exact_match_baseline_score_remains_reconstructable():
    tacos = next(recipe for recipe in CATALOG if recipe.id == "black-bean-tacos")

    final_score, breakdown = calculate_score(
        tacos,
        matched_count=3,
        min_protein_g=0.0,
        max_prep_minutes=30,
    )

    assert breakdown.pantry_coverage.value == 0.75
    assert breakdown.pantry_coverage.contribution == 0.525
    assert breakdown.protein_fit.contribution == 0.2
    assert breakdown.time_fit.contribution == 0.0167
    assert final_score == 0.7417


def test_rank_recipes_rejects_unresolved_exclusions_with_complete_evidence():
    request = make_request(
        pantry_items=["black bean"],
        excluded_ingredients=["groundnut"],
    )

    with pytest.raises(UnresolvedExcludedIngredientsError) as exc_info:
        rank_recipes(request, CATALOG, INGREDIENT_REGISTRY)

    evidence = exc_info.value.ingredient_resolution
    assert evidence.pantry_items[0].ingredient_id == "black-beans"
    assert evidence.excluded_ingredients[0].model_dump() == {
        "input": "groundnut",
        "normalized": "groundnut",
        "ingredient_id": None,
        "canonical_name": None,
        "match_type": "unresolved",
    }


def test_rank_recipes_normalizes_request_and_builds_stable_result_fields():
    recipe = make_recipe()

    response = rank_recipes(
        make_request(
            pantry_items=[" Spinach ", "EGGS", "spinach"],
            excluded_ingredients=[],
        ),
        [recipe],
        INGREDIENT_REGISTRY,
    )
    result = response.results[0]

    assert result.matched_ingredients == ("eggs", "spinach")
    assert result.missing_ingredients == ("olive oil",)
    assert result.required_ingredients == ("eggs", "spinach", "olive oil")
    assert result.score_breakdown.pantry_coverage.value == 0.6667
    assert result.explanation.startswith("Matched 2 of 3")


def test_rank_recipes_applies_exclusion_before_scoring():
    recipe = make_recipe()

    assert (
        rank_recipes(
            make_request(
                pantry_items=["spinach"],
                excluded_ingredients=[" SPINACH "],
            ),
            [recipe],
            INGREDIENT_REGISTRY,
        ).results
        == []
    )


def test_rank_recipes_applies_time_filter_but_not_protein_as_hard_filter():
    too_slow = make_recipe(recipe_id="slow", protein_g=100.0, prep_minutes=31)
    low_protein = make_recipe(recipe_id="low-protein", protein_g=1.0, prep_minutes=30)

    response = rank_recipes(
        make_request(min_protein_g=50.0, max_prep_minutes=30),
        [too_slow, low_protein],
        INGREDIENT_REGISTRY,
    )
    results = response.results

    assert [result.id for result in results] == ["low-protein"]
    assert results[0].score_breakdown.protein_fit.value == 0.02


def test_rank_recipes_with_empty_pantry_returns_zero_coverage_results():
    response = rank_recipes(
        make_request(pantry_items=[]),
        [make_recipe()],
        INGREDIENT_REGISTRY,
    )
    result = response.results[0]

    assert result.matched_ingredients == ()
    assert result.missing_ingredients == ("eggs", "spinach", "olive oil")
    assert result.score_breakdown.pantry_coverage.value == 0.0


def test_repeated_identical_rankings_are_equal():
    request = make_request(pantry_items=["eggs"])
    recipes = [make_recipe(recipe_id="b"), make_recipe(recipe_id="a")]

    assert rank_recipes(request, recipes, INGREDIENT_REGISTRY) == rank_recipes(
        request, recipes, INGREDIENT_REGISTRY
    )


def test_equal_exposed_scores_tie_break_by_recipe_id():
    recipes = [
        make_recipe(recipe_id="z-recipe", protein_g=10.002),
        make_recipe(recipe_id="a-recipe", protein_g=10.001),
    ]

    response = rank_recipes(
        make_request(min_protein_g=20.0),
        recipes,
        INGREDIENT_REGISTRY,
    )
    results = response.results

    assert results[0].final_score == results[1].final_score
    assert [result.id for result in results] == ["a-recipe", "z-recipe"]


def test_limit_is_applied_after_sorting():
    recipes = [
        make_recipe(recipe_id="low", required=("celery",), protein_g=0.0),
        make_recipe(recipe_id="high", required=("eggs",), protein_g=20.0),
    ]

    response = rank_recipes(
        make_request(pantry_items=["eggs"], limit=1),
        recipes,
        INGREDIENT_REGISTRY,
    )
    results = response.results

    assert [result.id for result in results] == ["high"]
