from pantrypilot.models import Recipe
from pantrypilot.ranking import is_eligible, match_ingredients


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
