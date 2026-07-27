from decimal import Decimal

import pytest

from pantrypilot.models import Recipe
from pantrypilot.ranking import (
    calculate_score,
    is_eligible,
    match_ingredients,
    render_explanation,
)


def make_recipe(
    *,
    recipe_id: str = "recipe",
    required: tuple[str, ...] = ("eggs", "spinach", "olive oil"),
    protein_g: float = 20.0,
    prep_minutes: int = 10,
) -> Recipe:
    return Recipe(
        id=recipe_id,
        name=recipe_id.replace("-", " ").title(),
        required_ingredients=required,
        calories=300,
        protein_g=protein_g,
        prep_minutes=prep_minutes,
    )


def test_empty_pantry_marks_every_required_ingredient_missing():
    matched, missing = match_ingredients(make_recipe(), set())

    assert matched == ()
    assert missing == ("eggs", "spinach", "olive oil")


def test_matching_is_exact_not_substring_plural_or_synonym_based():
    recipe = make_recipe(required=("tomatoes", "olive oil", "garbanzo beans"))

    matched, missing = match_ingredients(recipe, {"tomato", "oil", "chickpeas"})

    assert matched == ()
    assert missing == recipe.required_ingredients


def test_matching_preserves_normalized_recipe_order():
    matched, missing = match_ingredients(make_recipe(), {"spinach", "eggs"})

    assert matched == ("eggs", "spinach")
    assert missing == ("olive oil",)


def test_excluded_ingredient_makes_recipe_ineligible():
    assert not is_eligible(make_recipe(), {"spinach"}, 30)


def test_exclusion_takes_precedence_over_pantry_presence():
    recipe = make_recipe()
    matched, _ = match_ingredients(recipe, {"spinach"})

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
