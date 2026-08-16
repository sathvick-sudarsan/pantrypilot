import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from pantrypilot.catalog_store import (
    CURRENT_SCHEMA_VERSION,
    CatalogStoreError,
    connect_catalog,
    migrate_catalog,
)


def test_connect_catalog_uses_explicit_transactions_and_enables_foreign_keys(
    tmp_path: Path,
) -> None:
    with closing(connect_catalog(tmp_path / "catalog.sqlite3")) as connection:
        enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        isolation_level = connection.isolation_level
        assert connection.execute("SELECT 1 AS value").fetchone()["value"] == 1

    assert enabled == 1
    assert isolation_level is None


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


def user_version(connection: sqlite3.Connection) -> int:
    return connection.execute("PRAGMA user_version").fetchone()[0]


def test_migration_creates_version_one_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        assert user_version(connection) == 0

        migrate_catalog(connection, database_path)

        assert user_version(connection) == CURRENT_SCHEMA_VERSION == 1
        assert table_names(connection) == {"recipes", "recipe_ingredients"}

        recipe_columns = {
            row[1]: (row[2], row[3], row[5])
            for row in connection.execute("PRAGMA table_info(recipes)")
        }
        assert recipe_columns == {
            "id": ("TEXT", 1, 1),
            "name": ("TEXT", 1, 0),
            "calories": ("NUMERIC", 1, 0),
            "protein_g": ("NUMERIC", 1, 0),
            "prep_minutes": ("INTEGER", 1, 0),
        }

        relationship_columns = {
            row[1]: (row[2], row[3], row[5])
            for row in connection.execute("PRAGMA table_info(recipe_ingredients)")
        }
        assert relationship_columns == {
            "recipe_id": ("TEXT", 1, 1),
            "position": ("INTEGER", 1, 2),
            "ingredient_id": ("TEXT", 1, 0),
        }

        foreign_key = connection.execute(
            "PRAGMA foreign_key_list(recipe_ingredients)"
        ).fetchone()
        assert (foreign_key[2], foreign_key[3], foreign_key[4], foreign_key[6]) == (
            "recipes",
            "recipe_id",
            "id",
            "CASCADE",
        )

        unique_indexes = {
            tuple(
                column[2]
                for column in connection.execute(f"PRAGMA index_info('{row[1]}')")
            )
            for row in connection.execute("PRAGMA index_list(recipe_ingredients)")
            if row[2] == 1
        }
        assert unique_indexes == {
            ("recipe_id", "position"),
            ("recipe_id", "ingredient_id"),
        }


def test_current_migration_rerun_is_a_no_op(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        schema_before = connection.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type IN ('table', 'index') ORDER BY name"
        ).fetchall()

        migrate_catalog(connection, database_path)

        assert (
            connection.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type IN ('table', 'index') ORDER BY name"
            ).fetchall()
            == schema_before
        )
        assert user_version(connection) == 1


def test_newer_schema_version_is_rejected(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        connection.execute("PRAGMA user_version = 2")

        with pytest.raises(CatalogStoreError, match="newer than supported"):
            migrate_catalog(connection, database_path)

        assert user_version(connection) == 2
        assert table_names(connection) == set()


def test_failed_migration_rolls_back_schema_and_user_version(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        connection.execute("CREATE TABLE recipe_ingredients (sentinel TEXT)")
        schema_before = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()

        with pytest.raises(CatalogStoreError, match="schema version 1"):
            migrate_catalog(connection, database_path)

        assert (
            connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name"
            ).fetchall()
            == schema_before
        )
        assert "recipes" not in table_names(connection)
        assert user_version(connection) == 0


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
            "INSERT INTO recipes VALUES (?, ?, ?, ?, ?)",
            ("recipe-a", "Recipe A", 100, 10.0, 10),
        )
        connection.execute(
            "INSERT INTO recipe_ingredients VALUES (?, ?, ?)",
            ("recipe-a", 0, "eggs"),
        )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO recipes VALUES (?, ?, ?, ?, ?)",
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
                "INSERT INTO recipes VALUES (?, ?, ?, ?, ?)",
                (recipe_id, name, 100, 10.0, 10),
            )


def test_recipe_id_not_null_constraint_rejects_null(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO recipes VALUES (?, ?, ?, ?, ?)",
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
            "INSERT INTO recipes VALUES (?, ?, ?, ?, ?)",
            ("recipe-a", "Recipe A", 100, 10.0, 10),
        )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO recipe_ingredients VALUES (?, ?, ?)",
                ("recipe-a", position, ingredient_id),
            )
