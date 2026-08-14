from collections.abc import Collection, Iterable, Sequence

from pantrypilot.ingredients import (
    IngredientRegistry,
    IngredientResolutionEvidence,
    resolve_ingredients,
)
from pantrypilot.models import (
    RankedRecipe,
    RankingRequest,
    RankingResponse,
    Recipe,
    ScoreBreakdown,
    ScoreComponent,
)

PANTRY_WEIGHT = 0.70
PROTEIN_WEIGHT = 0.20
TIME_WEIGHT = 0.10
SCORE_DECIMALS = 4


class UnresolvedExcludedIngredientsError(ValueError):
    ingredient_resolution: IngredientResolutionEvidence

    def __init__(
        self,
        ingredient_resolution: IngredientResolutionEvidence,
    ) -> None:
        super().__init__("all excluded ingredients must resolve before ranking")
        self.ingredient_resolution = ingredient_resolution


def is_eligible(
    recipe: Recipe,
    excluded_ingredient_ids: Collection[str],
    max_prep_minutes: int,
) -> bool:
    return recipe.prep_minutes <= max_prep_minutes and not set(
        recipe.required_ingredient_ids
    ).intersection(excluded_ingredient_ids)


def match_ingredients(
    recipe: Recipe,
    pantry_ingredient_ids: Collection[str],
    ingredient_registry: IngredientRegistry,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    pantry_ids = set(pantry_ingredient_ids)
    matched_ids = tuple(
        ingredient_id
        for ingredient_id in recipe.required_ingredient_ids
        if ingredient_id in pantry_ids
    )
    missing_ids = tuple(
        ingredient_id
        for ingredient_id in recipe.required_ingredient_ids
        if ingredient_id not in pantry_ids
    )
    return (
        tuple(
            ingredient_registry.by_id[ingredient_id].canonical_name
            for ingredient_id in matched_ids
        ),
        tuple(
            ingredient_registry.by_id[ingredient_id].canonical_name
            for ingredient_id in missing_ids
        ),
    )


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
    """Require an eligible recipe within ``max_prep_minutes``."""
    pantry = _score_component(
        matched_count / len(recipe.required_ingredient_ids), PANTRY_WEIGHT
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
    """Require an eligible recipe within ``max_prep_minutes``."""
    protein_phrase = "meets" if recipe.protein_g >= min_protein_g else "is below"
    return (
        f"Matched {matched_count} of {len(recipe.required_ingredient_ids)} required "
        f"ingredients (coverage {score_breakdown.pantry_coverage.value:.4f}); "
        f"{recipe.protein_g:.1f}g protein {protein_phrase} the "
        f"{min_protein_g:.1f}g target (fit {score_breakdown.protein_fit.value:.4f}); "
        f"{recipe.prep_minutes} minutes is within the {max_prep_minutes}-minute "
        f"limit (fit {score_breakdown.time_fit.value:.4f})."
    )


def rank_recipes(
    request: RankingRequest,
    recipes: Sequence[Recipe],
    ingredient_registry: IngredientRegistry,
) -> RankingResponse:
    pantry_resolutions = resolve_ingredients(request.pantry_items, ingredient_registry)
    excluded_resolutions = resolve_ingredients(
        request.excluded_ingredients, ingredient_registry
    )
    ingredient_resolution = IngredientResolutionEvidence(
        pantry_items=pantry_resolutions,
        excluded_ingredients=excluded_resolutions,
    )
    if any(
        resolution.match_type == "unresolved"
        for resolution in ingredient_resolution.excluded_ingredients
    ):
        raise UnresolvedExcludedIngredientsError(ingredient_resolution)
    pantry_ids = {
        resolution.ingredient_id
        for resolution in pantry_resolutions
        if resolution.ingredient_id is not None
    }
    excluded_ids = {
        resolution.ingredient_id
        for resolution in excluded_resolutions
        if resolution.ingredient_id is not None
    }
    ranked_recipes: list[RankedRecipe] = []

    for recipe in recipes:
        if not is_eligible(recipe, excluded_ids, request.max_prep_minutes):
            continue
        matched_ingredients, missing_ingredients = match_ingredients(
            recipe, pantry_ids, ingredient_registry
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
                required_ingredients=tuple(
                    ingredient_registry.by_id[ingredient_id].canonical_name
                    for ingredient_id in recipe.required_ingredient_ids
                ),
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

    results = limit_ranked_recipes(sort_ranked_recipes(ranked_recipes), request.limit)
    return RankingResponse(
        results=results,
        returned_count=len(results),
        ingredient_resolution=ingredient_resolution,
    )


def sort_ranked_recipes(recipes: Iterable[RankedRecipe]) -> list[RankedRecipe]:
    return sorted(recipes, key=lambda recipe: (-recipe.final_score, recipe.id))


def limit_ranked_recipes(
    recipes: Sequence[RankedRecipe], limit: int
) -> list[RankedRecipe]:
    return list(recipes[:limit])
