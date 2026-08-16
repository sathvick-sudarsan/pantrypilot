from collections.abc import Iterable, Mapping

from pantrypilot.ingredients import IngredientRegistry
from pantrypilot.models import Recipe


def load_catalog(
    records: Iterable[Mapping[str, object]],
    ingredient_registry: IngredientRegistry,
) -> tuple[Recipe, ...]:
    catalog: list[Recipe] = []
    recipe_ids: set[str] = set()
    for record in records:
        recipe = Recipe.model_validate(record)
        for ingredient_id in recipe.required_ingredient_ids:
            if ingredient_id not in ingredient_registry.by_id:
                raise ValueError(
                    f"unknown ingredient id '{ingredient_id}' in recipe '{recipe.id}'"
                )
        if recipe.id in recipe_ids:
            raise ValueError(f"duplicate recipe id: {recipe.id}")
        recipe_ids.add(recipe.id)
        catalog.append(recipe)
    return tuple(catalog)


INITIAL_RECIPE_CATALOG: tuple[dict[str, object], ...] = (
    {
        "id": "spinach-omelet",
        "name": "Spinach Omelet",
        "required_ingredient_ids": ["eggs", "spinach", "olive-oil"],
        "calories": 410,
        "protein_g": 28.0,
        "prep_minutes": 15,
    },
    {
        "id": "black-bean-tacos",
        "name": "Black Bean Tacos",
        "required_ingredient_ids": [
            "black-beans",
            "corn-tortillas",
            "avocado",
            "lime",
        ],
        "calories": 520,
        "protein_g": 19.0,
        "prep_minutes": 25,
    },
    {
        "id": "peanut-noodles",
        "name": "Peanut Noodles",
        "required_ingredient_ids": ["noodles", "peanuts", "soy-sauce"],
        "calories": 560,
        "protein_g": 20.0,
        "prep_minutes": 20,
    },
    {
        "id": "lentil-soup",
        "name": "Lentil Soup",
        "required_ingredient_ids": [
            "lentils",
            "carrots",
            "celery",
            "vegetable-broth",
        ],
        "calories": 360,
        "protein_g": 22.0,
        "prep_minutes": 45,
    },
)
