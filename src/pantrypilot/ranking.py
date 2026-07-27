from collections.abc import Collection, Iterable, Sequence

from pantrypilot.models import (
    RankedRecipe,
    RankingRequest,
    Recipe,
    ScoreBreakdown,
    ScoreComponent,
)
from pantrypilot.normalization import normalize_ingredients

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


def rank_recipes(
    request: RankingRequest,
    recipes: Sequence[Recipe],
) -> list[RankedRecipe]:
    pantry_items = set(normalize_ingredients(request.pantry_items))
    excluded_ingredients = set(normalize_ingredients(request.excluded_ingredients))
    ranked_recipes = []

    for recipe in recipes:
        if not is_eligible(recipe, excluded_ingredients, request.max_prep_minutes):
            continue
        matched_ingredients, missing_ingredients = match_ingredients(
            recipe, pantry_items
        )
        final_score, score_breakdown = calculate_score(
            recipe,
            len(matched_ingredients),
            request.min_protein_g,
            request.max_prep_minutes,
        )
        ranked_recipes.append(
            RankedRecipe(
                id=recipe.id,
                name=recipe.name,
                required_ingredients=recipe.required_ingredients,
                calories=recipe.calories,
                protein_g=recipe.protein_g,
                prep_minutes=recipe.prep_minutes,
                final_score=final_score,
                matched_ingredients=matched_ingredients,
                missing_ingredients=missing_ingredients,
                score_breakdown=score_breakdown,
                explanation=render_explanation(
                    recipe,
                    len(matched_ingredients),
                    request.min_protein_g,
                    request.max_prep_minutes,
                    score_breakdown,
                ),
            )
        )

    return limit_ranked_recipes(
        sort_ranked_recipes(ranked_recipes),
        request.limit,
    )


def sort_ranked_recipes(recipes: Iterable[RankedRecipe]) -> list[RankedRecipe]:
    return sorted(recipes, key=lambda recipe: (-recipe.final_score, recipe.id))


def limit_ranked_recipes(
    recipes: Sequence[RankedRecipe], limit: int
) -> list[RankedRecipe]:
    return list(recipes[:limit])
