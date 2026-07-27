from collections.abc import Collection

from pantrypilot.models import Recipe, ScoreBreakdown, ScoreComponent

PANTRY_WEIGHT = 0.70
PROTEIN_WEIGHT = 0.20
TIME_WEIGHT = 0.10
SCORE_DECIMALS = 4


def is_eligible(
    recipe: Recipe,
    excluded_ingredients: Collection[str],
    max_prep_minutes: int,
) -> bool:
    return recipe.prep_minutes <= max_prep_minutes and not set(
        recipe.required_ingredients
    ).intersection(excluded_ingredients)


def match_ingredients(
    recipe: Recipe,
    pantry_items: Collection[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    pantry = set(pantry_items)
    matched = tuple(
        ingredient for ingredient in recipe.required_ingredients if ingredient in pantry
    )
    missing = tuple(
        ingredient
        for ingredient in recipe.required_ingredients
        if ingredient not in pantry
    )
    return matched, missing


def _score_component(value: float, weight: float) -> ScoreComponent:
    return ScoreComponent(
        value=round(value, SCORE_DECIMALS),
        weight=weight,
        contribution=round(value * weight, SCORE_DECIMALS),
    )


def calculate_score(
    recipe: Recipe,
    matched_count: int,
    min_protein_g: float,
    max_prep_minutes: int,
) -> tuple[float, ScoreBreakdown]:
    pantry = _score_component(
        matched_count / len(recipe.required_ingredients), PANTRY_WEIGHT
    )
    protein = _score_component(
        1.0 if min_protein_g == 0 else min(recipe.protein_g / min_protein_g, 1.0),
        PROTEIN_WEIGHT,
    )
    time = _score_component(
        1.0 if max_prep_minutes == 0 else 1 - recipe.prep_minutes / max_prep_minutes,
        TIME_WEIGHT,
    )
    breakdown = ScoreBreakdown(
        pantry_coverage=pantry,
        protein_fit=protein,
        time_fit=time,
    )
    final_score = round(
        pantry.contribution + protein.contribution + time.contribution,
        SCORE_DECIMALS,
    )
    return final_score, breakdown


def render_explanation(
    recipe: Recipe,
    matched_count: int,
    min_protein_g: float,
    max_prep_minutes: int,
    score_breakdown: ScoreBreakdown,
) -> str:
    protein_phrase = "meets" if recipe.protein_g >= min_protein_g else "is below"
    return (
        f"Matched {matched_count} of {len(recipe.required_ingredients)} required "
        f"ingredients (coverage {score_breakdown.pantry_coverage.value:.4f}); "
        f"{recipe.protein_g:.1f}g protein {protein_phrase} the "
        f"{min_protein_g:.1f}g target (fit {score_breakdown.protein_fit.value:.4f}); "
        f"{recipe.prep_minutes} minutes is within the {max_prep_minutes}-minute "
        f"limit (fit {score_breakdown.time_fit.value:.4f})."
    )
