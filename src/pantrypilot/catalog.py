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


FEATURE_003_RECIPE_CATALOG: tuple[Recipe, ...] = (
    Recipe(
        id="spinach-omelet",
        name="Spinach Omelet",
        required_ingredient_ids=("eggs", "spinach", "olive-oil"),
        calories=410,
        protein_g=28.0,
        prep_minutes=15,
    ),
    Recipe(
        id="black-bean-tacos",
        name="Black Bean Tacos",
        required_ingredient_ids=(
            "black-beans",
            "corn-tortillas",
            "avocado",
            "lime",
        ),
        calories=520,
        protein_g=19.0,
        prep_minutes=25,
    ),
    Recipe(
        id="peanut-noodles",
        name="Peanut Noodles",
        required_ingredient_ids=("noodles", "peanuts", "soy-sauce"),
        calories=560,
        protein_g=20.0,
        prep_minutes=20,
    ),
    Recipe(
        id="lentil-soup",
        name="Lentil Soup",
        required_ingredient_ids=(
            "lentils",
            "carrots",
            "celery",
            "vegetable-broth",
        ),
        calories=360,
        protein_g=22.0,
        prep_minutes=45,
    ),
)


OFFICIAL_RECIPE_CATALOG: tuple[Recipe, ...] = FEATURE_003_RECIPE_CATALOG + (
    Recipe(
        id="overnight-oats",
        name="Overnight Oats",
        required_ingredient_ids=("oats", "bananas", "milk", "peanuts", "yogurt"),
        calories=340,
        protein_g=14.0,
        prep_minutes=10,
    ),
    Recipe(
        id="avocado-egg-toast",
        name="Avocado Egg Toast",
        required_ingredient_ids=("bread", "eggs", "avocado", "spinach", "olive-oil"),
        calories=350,
        protein_g=18.0,
        prep_minutes=10,
    ),
    Recipe(
        id="yogurt-oat-bowl",
        name="Yogurt Oat Bowl",
        required_ingredient_ids=("yogurt", "oats", "bananas", "peanuts", "berries"),
        calories=380,
        protein_g=14.0,
        prep_minutes=5,
    ),
    Recipe(
        id="tofu-rice-bowl",
        name="Tofu Rice Bowl",
        required_ingredient_ids=(
            "tofu",
            "rice",
            "broccoli",
            "carrots",
            "soy-sauce",
            "garlic",
            "ginger",
        ),
        calories=510,
        protein_g=26.0,
        prep_minutes=35,
    ),
    Recipe(
        id="tofu-vegetable-soup",
        name="Tofu Vegetable Soup",
        required_ingredient_ids=(
            "tofu",
            "vegetable-broth",
            "carrots",
            "celery",
            "spinach",
            "soy-sauce",
            "ginger",
        ),
        calories=320,
        protein_g=25.0,
        prep_minutes=40,
    ),
    Recipe(
        id="beef-rice-bowl",
        name="Beef Rice Bowl",
        required_ingredient_ids=(
            "ground-beef",
            "rice",
            "broccoli",
            "carrots",
            "onion",
            "garlic",
            "soy-sauce",
            "ginger",
        ),
        calories=720,
        protein_g=42.0,
        prep_minutes=35,
    ),
    Recipe(
        id="chickpea-cucumber-salad",
        name="Chickpea Cucumber Salad",
        required_ingredient_ids=(
            "chickpeas",
            "cucumbers",
            "tomatoes",
            "onion",
            "lime",
            "olive-oil",
            "spinach",
        ),
        calories=390,
        protein_g=13.0,
        prep_minutes=15,
    ),
    Recipe(
        id="tomato-lentil-stew",
        name="Tomato Lentil Stew",
        required_ingredient_ids=(
            "lentils",
            "tomatoes",
            "onion",
            "garlic",
            "carrots",
            "vegetable-broth",
            "olive-oil",
            "spinach",
        ),
        calories=480,
        protein_g=24.0,
        prep_minutes=50,
    ),
    Recipe(
        id="salmon-quinoa-salad",
        name="Salmon Quinoa Salad",
        required_ingredient_ids=(
            "salmon",
            "quinoa",
            "cucumbers",
            "tomatoes",
            "spinach",
            "lime",
            "olive-oil",
        ),
        calories=570,
        protein_g=38.0,
        prep_minutes=30,
    ),
    Recipe(
        id="chickpea-rice-bowl",
        name="Chickpea Rice Bowl",
        required_ingredient_ids=(
            "chickpeas",
            "rice",
            "cucumbers",
            "tomatoes",
            "onion",
            "lime",
            "yogurt",
            "olive-oil",
        ),
        calories=540,
        protein_g=25.0,
        prep_minutes=30,
    ),
    Recipe(
        id="lentil-cucumber-salad",
        name="Lentil Cucumber Salad",
        required_ingredient_ids=(
            "lentils",
            "cucumbers",
            "tomatoes",
            "onion",
            "lime",
            "olive-oil",
        ),
        calories=370,
        protein_g=17.0,
        prep_minutes=20,
    ),
    Recipe(
        id="potato-chickpea-curry",
        name="Potato Chickpea Curry",
        required_ingredient_ids=(
            "potatoes",
            "chickpeas",
            "tomatoes",
            "onion",
            "garlic",
            "spinach",
            "coconut-milk",
            "rice",
        ),
        calories=680,
        protein_g=18.0,
        prep_minutes=55,
    ),
    Recipe(
        id="coconut-lentil-curry",
        name="Coconut Lentil Curry",
        required_ingredient_ids=(
            "lentils",
            "coconut-milk",
            "tomatoes",
            "onion",
            "garlic",
            "carrots",
            "rice",
            "spinach",
        ),
        calories=620,
        protein_g=24.0,
        prep_minutes=50,
    ),
    Recipe(
        id="tuna-avocado-salad",
        name="Tuna Avocado Salad",
        required_ingredient_ids=(
            "tuna",
            "avocado",
            "cucumbers",
            "tomatoes",
            "lime",
            "olive-oil",
            "onion",
        ),
        calories=430,
        protein_g=35.0,
        prep_minutes=15,
    ),
    Recipe(
        id="black-bean-quinoa-salad",
        name="Black Bean Quinoa Salad",
        required_ingredient_ids=(
            "black-beans",
            "quinoa",
            "avocado",
            "tomatoes",
            "onion",
            "lime",
            "olive-oil",
        ),
        calories=580,
        protein_g=23.0,
        prep_minutes=35,
    ),
    Recipe(
        id="chicken-tacos",
        name="Chicken Tacos",
        required_ingredient_ids=(
            "chicken",
            "corn-tortillas",
            "avocado",
            "tomatoes",
            "onion",
            "lime",
            "cabbage",
        ),
        calories=610,
        protein_g=40.0,
        prep_minutes=30,
    ),
    Recipe(
        id="black-bean-rice-bowl",
        name="Black Bean Rice Bowl",
        required_ingredient_ids=(
            "black-beans",
            "rice",
            "avocado",
            "tomatoes",
            "onion",
            "lime",
            "cabbage",
            "olive-oil",
        ),
        calories=650,
        protein_g=21.0,
        prep_minutes=35,
    ),
    Recipe(
        id="pasta-tomato-soup",
        name="Pasta Tomato Soup",
        required_ingredient_ids=(
            "pasta",
            "tomatoes",
            "onion",
            "garlic",
            "vegetable-broth",
            "carrots",
            "spinach",
            "olive-oil",
        ),
        calories=460,
        protein_g=14.0,
        prep_minutes=40,
    ),
    Recipe(
        id="chicken-pasta-bowl",
        name="Chicken Pasta Bowl",
        required_ingredient_ids=(
            "chicken",
            "pasta",
            "tomatoes",
            "spinach",
            "garlic",
            "olive-oil",
            "cheese",
        ),
        calories=710,
        protein_g=45.0,
        prep_minutes=45,
    ),
    Recipe(
        id="coconut-chicken-stew",
        name="Coconut Chicken Stew",
        required_ingredient_ids=(
            "chicken",
            "coconut-milk",
            "potatoes",
            "carrots",
            "onion",
            "garlic",
            "lime",
        ),
        calories=640,
        protein_g=37.0,
        prep_minutes=55,
    ),
)

RETIRED_OFFICIAL_RECIPE_IDS: tuple[str, ...] = ()


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
