from collections.abc import Collection

from pantrypilot.models import Recipe


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
