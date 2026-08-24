import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from pydantic import ValidationError

from pantrypilot.catalog import INITIAL_RECIPE_CATALOG, load_catalog
from pantrypilot.catalog_store import (
    CatalogStoreError,
    connect_catalog,
    initialize_catalog,
    load_durable_catalog,
    migrate_catalog,
    seed_catalog,
)
from pantrypilot.ingredients import INGREDIENT_REGISTRY
from pantrypilot.models import Recipe


def insert_recipe(
    connection: sqlite3.Connection,
    *,
    recipe_id: str = "recipe-a",
    name: str = "Recipe A",
    calories: object = 100,
    protein_g: object = 10.0,
    prep_minutes: object = 10,
    ingredients: tuple[tuple[int, str], ...] = ((0, "eggs"),),
) -> None:
    connection.execute(
        "INSERT INTO recipes "
        "(id, name, calories, protein_g, prep_minutes) "
        "VALUES (?, ?, ?, ?, ?)",
        (recipe_id, name, calories, protein_g, prep_minutes),
    )
    for position, ingredient_id in ingredients:
        connection.execute(
            "INSERT INTO recipe_ingredients VALUES (?, ?, ?)",
            (recipe_id, position, ingredient_id),
        )


def test_initialize_catalog_seeds_approved_recipes_and_survives_reopen(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"

    initialize_catalog(
        database_path,
        INITIAL_RECIPE_CATALOG,
        INGREDIENT_REGISTRY,
    )
    recipes = load_durable_catalog(database_path, INGREDIENT_REGISTRY)

    assert sorted(recipes, key=lambda recipe: recipe.id) == sorted(
        load_catalog(INITIAL_RECIPE_CATALOG, INGREDIENT_REGISTRY),
        key=lambda recipe: recipe.id,
    )
    with sqlite3.connect(database_path) as reopened:
        assert reopened.execute("PRAGMA user_version").fetchone()[0] == 3
        assert {
            row[0]
            for row in reopened.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        } == {
            "recipes",
            "recipe_ingredients",
            "saved_pantry",
            "saved_pantry_items",
            "catalog_content_state",
        }
        assert reopened.execute("SELECT COUNT(*) FROM recipes").fetchone()[0] == 4
        assert reopened.execute("SELECT COUNT(*) FROM recipe_ingredients").fetchone()[
            0
        ] == sum(
            len(record["required_ingredient_ids"]) for record in INITIAL_RECIPE_CATALOG
        )


def test_invalid_seed_is_validated_before_any_insert(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    invalid_seed = ({**INITIAL_RECIPE_CATALOG[0], "id": ""},)

    with pytest.raises(CatalogStoreError, match="seed validation failed"):
        initialize_catalog(database_path, invalid_seed, INGREDIENT_REGISTRY)

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM recipes").fetchone()[0] == 0
        assert (
            connection.execute("SELECT COUNT(*) FROM recipe_ingredients").fetchone()[0]
            == 0
        )


def test_seed_failure_rolls_back_every_recipe_and_relationship(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        connection.execute(
            "CREATE TRIGGER reject_peanut_noodles "
            "BEFORE INSERT ON recipes "
            "WHEN NEW.id = 'peanut-noodles' "
            "BEGIN SELECT RAISE(FAIL, 'injected seed failure'); END"
        )
        connection.commit()

        with pytest.raises(CatalogStoreError, match="catalog seed failed"):
            seed_catalog(
                connection,
                database_path,
                INITIAL_RECIPE_CATALOG,
                INGREDIENT_REGISTRY,
            )

        assert connection.execute("SELECT COUNT(*) FROM recipes").fetchone()[0] == 0
        assert (
            connection.execute("SELECT COUNT(*) FROM recipe_ingredients").fetchone()[0]
            == 0
        )


def test_second_initialization_does_not_duplicate_or_overwrite(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    initialize_catalog(database_path, INITIAL_RECIPE_CATALOG, INGREDIENT_REGISTRY)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE recipes SET name = ? WHERE id = ?",
            ("Durable Name", "spinach-omelet"),
        )

    initialize_catalog(
        database_path,
        INITIAL_RECIPE_CATALOG,
        INGREDIENT_REGISTRY,
    )

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM recipes").fetchone()[0] == 4
        assert (
            connection.execute(
                "SELECT name FROM recipes WHERE id = 'spinach-omelet'"
            ).fetchone()[0]
            == "Durable Name"
        )


def test_recipe_rows_without_any_relationship_rows_fail_initialization(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        insert_recipe(connection, ingredients=())
        connection.commit()

    with pytest.raises(CatalogStoreError, match="partially initialized"):
        initialize_catalog(database_path, INITIAL_RECIPE_CATALOG, INGREDIENT_REGISTRY)


def test_one_zero_relationship_recipe_fails_non_empty_initialization(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        insert_recipe(connection, recipe_id="valid", ingredients=((0, "eggs"),))
        insert_recipe(connection, recipe_id="incomplete", ingredients=())
        connection.commit()

    with pytest.raises(CatalogStoreError, match="partially initialized"):
        initialize_catalog(database_path, INITIAL_RECIPE_CATALOG, INGREDIENT_REGISTRY)


def test_valid_non_empty_catalog_is_not_reconciled_or_seed_validated(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        insert_recipe(
            connection,
            recipe_id="durable-only",
            name="Durable Only",
            ingredients=((0, "eggs"),),
        )
        connection.commit()
    invalid_unused_seed = ({**INITIAL_RECIPE_CATALOG[0], "id": ""},)

    initialize_catalog(database_path, invalid_unused_seed, INGREDIENT_REGISTRY)

    assert load_durable_catalog(database_path, INGREDIENT_REGISTRY) == (
        Recipe(
            id="durable-only",
            name="Durable Only",
            required_ingredient_ids=("eggs",),
            calories=100,
            protein_g=10.0,
            prep_minutes=10,
        ),
    )


def test_load_durable_catalog_hydrates_frozen_recipes_in_position_order(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        insert_recipe(
            connection,
            ingredients=((2, "olive-oil"), (0, "eggs"), (1, "spinach")),
        )
        connection.commit()

    recipes = load_durable_catalog(database_path, INGREDIENT_REGISTRY)

    assert recipes == (
        Recipe(
            id="recipe-a",
            name="Recipe A",
            required_ingredient_ids=("eggs", "spinach", "olive-oil"),
            calories=100,
            protein_g=10.0,
            prep_minutes=10,
        ),
    )
    with pytest.raises(ValidationError):
        recipes[0].name = "Changed"


def test_zero_relationship_recipe_fails_instead_of_vanishing(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        insert_recipe(connection, ingredients=())
        connection.commit()

    with pytest.raises(CatalogStoreError, match="catalog load failed") as error:
        load_durable_catalog(database_path, INGREDIENT_REGISTRY)

    assert isinstance(error.value.__cause__, ValidationError)


def test_unknown_canonical_ingredient_fails_complete_load(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        insert_recipe(connection, ingredients=((0, "unknown-ingredient"),))
        connection.commit()

    with pytest.raises(CatalogStoreError, match="catalog load failed") as error:
        load_durable_catalog(database_path, INGREDIENT_REGISTRY)

    assert isinstance(error.value.__cause__, ValueError)
    assert "unknown ingredient id" in str(error.value.__cause__)


def test_sqlite_permitted_non_finite_value_fails_domain_hydration(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        insert_recipe(connection, protein_g=float("inf"))
        connection.commit()

    with pytest.raises(CatalogStoreError, match="catalog load failed") as error:
        load_durable_catalog(database_path, INGREDIENT_REGISTRY)

    assert isinstance(error.value.__cause__, ValidationError)


def test_one_invalid_recipe_fails_catalog_instead_of_skipping_it(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        insert_recipe(connection, recipe_id="valid")
        insert_recipe(
            connection,
            recipe_id="invalid",
            ingredients=((0, "unknown-ingredient"),),
        )
        connection.commit()

    with pytest.raises(CatalogStoreError, match="catalog load failed"):
        load_durable_catalog(database_path, INGREDIENT_REGISTRY)


def test_current_version_with_missing_schema_fails_load(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA user_version = 3")

    with pytest.raises(CatalogStoreError, match="catalog load failed"):
        load_durable_catalog(database_path, INGREDIENT_REGISTRY)


def test_foreign_key_violation_fails_before_hydration(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            "INSERT INTO recipe_ingredients VALUES (?, ?, ?)",
            ("missing", 0, "eggs"),
        )

    with pytest.raises(CatalogStoreError, match="foreign-key check failed"):
        load_durable_catalog(database_path, INGREDIENT_REGISTRY)


@pytest.mark.parametrize("version", [0, 1, 2])
def test_wrong_schema_version_fails_load(tmp_path: Path, version: int) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(f"PRAGMA user_version = {version}")

    with pytest.raises(CatalogStoreError, match="does not match supported"):
        load_durable_catalog(database_path, INGREDIENT_REGISTRY)


def test_connect_catalog_uses_explicit_transactions_and_enables_foreign_keys(
    tmp_path: Path,
) -> None:
    with closing(connect_catalog(tmp_path / "catalog.sqlite3")) as connection:
        enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        isolation_level = connection.isolation_level
        assert connection.execute("SELECT 1 AS value").fetchone()["value"] == 1

    assert enabled == 1
    assert isolation_level is None


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("calories", "not-numeric"),
        ("protein_g", b"not-numeric"),
        ("prep_minutes", 10.5),
        ("calories", -1),
        ("protein_g", -1),
    ],
)
def test_recipe_storage_constraints_reject_invalid_values(
    tmp_path: Path,
    column: str,
    value: object,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        values = {
            "id": "recipe-a",
            "name": "Recipe A",
            "calories": 100,
            "protein_g": 10.0,
            "prep_minutes": 10,
        }
        values[column] = value

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO recipes "
                "(id, name, calories, protein_g, prep_minutes) "
                "VALUES (:id, :name, :calories, :protein_g, :prep_minutes)",
                values,
            )


def test_recipe_relationship_keys_and_checks_reject_duplicates(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        connection.execute(
            "INSERT INTO recipes "
            "(id, name, calories, protein_g, prep_minutes) "
            "VALUES (?, ?, ?, ?, ?)",
            ("recipe-a", "Recipe A", 100, 10.0, 10),
        )
        connection.execute(
            "INSERT INTO recipe_ingredients VALUES (?, ?, ?)",
            ("recipe-a", 0, "eggs"),
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO recipes "
                "(id, name, calories, protein_g, prep_minutes) "
                "VALUES (?, ?, ?, ?, ?)",
                ("recipe-a", "Duplicate", 200, 20.0, 20),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO recipe_ingredients VALUES (?, ?, ?)",
                ("recipe-a", 0, "spinach"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO recipe_ingredients VALUES (?, ?, ?)",
                ("recipe-a", 1, "eggs"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO recipe_ingredients VALUES (?, ?, ?)",
                ("missing", 0, "eggs"),
            )


@pytest.mark.parametrize(
    ("recipe_id", "name"),
    [("", "Recipe A"), ("recipe-a", "   ")],
)
def test_recipe_text_checks_reject_blank_values(
    tmp_path: Path,
    recipe_id: str,
    name: str,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO recipes "
                "(id, name, calories, protein_g, prep_minutes) "
                "VALUES (?, ?, ?, ?, ?)",
                (recipe_id, name, 100, 10.0, 10),
            )


def test_recipe_id_not_null_constraint_rejects_null(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO recipes "
                "(id, name, calories, protein_g, prep_minutes) "
                "VALUES (?, ?, ?, ?, ?)",
                (None, "Recipe A", 100, 10.0, 10),
            )


@pytest.mark.parametrize(
    ("position", "ingredient_id"),
    [(-1, "spinach"), (1.5, "spinach"), (1, "   ")],
)
def test_relationship_checks_reject_invalid_position_and_blank_ingredient(
    tmp_path: Path,
    position: object,
    ingredient_id: str,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        connection.execute(
            "INSERT INTO recipes "
            "(id, name, calories, protein_g, prep_minutes) "
            "VALUES (?, ?, ?, ?, ?)",
            ("recipe-a", "Recipe A", 100, 10.0, 10),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO recipe_ingredients VALUES (?, ?, ?)",
                ("recipe-a", position, ingredient_id),
            )
