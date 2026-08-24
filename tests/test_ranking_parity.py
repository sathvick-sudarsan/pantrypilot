import sqlite3
from pathlib import Path

import pytest

from pantrypilot.catalog import INITIAL_RECIPE_CATALOG, load_catalog
from pantrypilot.catalog_store import initialize_catalog, load_durable_catalog
from pantrypilot.ingredients import INGREDIENT_REGISTRY
from pantrypilot.models import RankingRequest, Recipe
from pantrypilot.ranking import UnresolvedExcludedIngredientsError, rank_recipes


def direct_catalog() -> tuple[Recipe, ...]:
    return load_catalog(INITIAL_RECIPE_CATALOG, INGREDIENT_REGISTRY)


def reordered_durable_catalog(database_path: Path) -> tuple[Recipe, ...]:
    initialize_catalog(database_path, INITIAL_RECIPE_CATALOG, INGREDIENT_REGISTRY)
    with sqlite3.connect(database_path) as connection:
        relationships = connection.execute(
            "SELECT recipe_id, position, ingredient_id "
            "FROM recipe_ingredients ORDER BY recipe_id, position DESC"
        ).fetchall()
        recipes = connection.execute(
            "SELECT id, name, calories, protein_g, prep_minutes "
            "FROM recipes ORDER BY id DESC"
        ).fetchall()
        connection.execute("DELETE FROM recipe_ingredients")
        connection.execute("DELETE FROM recipes")
        connection.executemany(
            "INSERT INTO recipes "
            "(id, name, calories, protein_g, prep_minutes) "
            "VALUES (?, ?, ?, ?, ?)",
            recipes,
        )
        connection.executemany(
            "INSERT INTO recipe_ingredients VALUES (?, ?, ?)",
            relationships,
        )
    return load_durable_catalog(database_path, INGREDIENT_REGISTRY)


def make_request(
    *,
    pantry_items: list[str],
    min_protein_g: float = 0.0,
    max_prep_minutes: int = 45,
    excluded_ingredients: list[str] | None = None,
    limit: int = 50,
) -> RankingRequest:
    return RankingRequest(
        pantry_items=pantry_items,
        min_protein_g=min_protein_g,
        max_prep_minutes=max_prep_minutes,
        excluded_ingredients=(
            [] if excluded_ingredients is None else excluded_ingredients
        ),
        limit=limit,
    )


PARITY_REQUESTS = (
    make_request(
        pantry_items=["eggs", "spinach", "olive oil"],
        min_protein_g=25.0,
        max_prep_minutes=30,
    ),
    make_request(
        pantry_items=["egg", "black bean", "mystery item"],
    ),
    make_request(
        pantry_items=["noodles", "peanuts", "soy sauce"],
        excluded_ingredients=["peanuts"],
    ),
    make_request(
        pantry_items=["noodles", "peanuts", "soy sauce"],
        excluded_ingredients=["peanut"],
    ),
    make_request(
        pantry_items=["eggs"],
        limit=2,
    ),
)


@pytest.mark.parametrize("ranking_request", PARITY_REQUESTS)
def test_durable_catalog_preserves_complete_ranking_response(
    tmp_path: Path,
    ranking_request: RankingRequest,
) -> None:
    direct = rank_recipes(ranking_request, direct_catalog(), INGREDIENT_REGISTRY)
    durable = rank_recipes(
        ranking_request,
        reordered_durable_catalog(tmp_path / "catalog.sqlite3"),
        INGREDIENT_REGISTRY,
    )

    assert durable == direct


def test_durable_catalog_preserves_fail_closed_unresolved_exclusion(
    tmp_path: Path,
) -> None:
    request = make_request(
        pantry_items=["egg", "spinach"],
        excluded_ingredients=["groundnut"],
    )
    catalogs = (
        direct_catalog(),
        reordered_durable_catalog(tmp_path / "catalog.sqlite3"),
    )

    errors: list[UnresolvedExcludedIngredientsError] = []
    for catalog in catalogs:
        with pytest.raises(UnresolvedExcludedIngredientsError) as error:
            rank_recipes(request, catalog, INGREDIENT_REGISTRY)
        errors.append(error.value)

    assert errors[1].ingredient_resolution == errors[0].ingredient_resolution


def test_durable_catalog_preserves_recipe_id_tie_break(tmp_path: Path) -> None:
    tied_records = (
        {
            "id": "z-recipe",
            "name": "Z Recipe",
            "required_ingredient_ids": ("eggs",),
            "calories": 100,
            "protein_g": 5.0,
            "prep_minutes": 10,
        },
        {
            "id": "a-recipe",
            "name": "A Recipe",
            "required_ingredient_ids": ("eggs",),
            "calories": 100,
            "protein_g": 5.0,
            "prep_minutes": 10,
        },
    )
    database_path = tmp_path / "catalog.sqlite3"
    initialize_catalog(database_path, reversed(tied_records), INGREDIENT_REGISTRY)
    request = make_request(pantry_items=["eggs"])

    direct = rank_recipes(
        request,
        load_catalog(tied_records, INGREDIENT_REGISTRY),
        INGREDIENT_REGISTRY,
    )
    durable = rank_recipes(
        request,
        load_durable_catalog(database_path, INGREDIENT_REGISTRY),
        INGREDIENT_REGISTRY,
    )

    assert durable == direct
    assert [result.id for result in durable.results] == [
        "a-recipe",
        "z-recipe",
    ]
