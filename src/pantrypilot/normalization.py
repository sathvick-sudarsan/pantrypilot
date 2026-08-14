from collections.abc import Iterable


def normalize_ingredient(value: str) -> str:
    ingredient = value.strip().lower()
    if not ingredient:
        raise ValueError("ingredient values must not be blank")
    return ingredient


def normalize_ingredients(values: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        ingredient = normalize_ingredient(value)
        if ingredient not in seen:
            seen.add(ingredient)
            normalized.append(ingredient)
    return tuple(normalized)
