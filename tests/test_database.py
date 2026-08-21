import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import pantrypilot.database as database_module
from pantrypilot.database import (
    CURRENT_SCHEMA_VERSION,
    SCHEMA_MIGRATIONS,
    DatabaseError,
    connect_database,
    migrate_database,
)


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


def user_version(connection: sqlite3.Connection) -> int:
    return connection.execute("PRAGMA user_version").fetchone()[0]


def create_populated_v1(connection: sqlite3.Connection) -> None:
    migration_one = dict(SCHEMA_MIGRATIONS)[1]
    connection.execute("BEGIN IMMEDIATE")
    for statement in migration_one:
        connection.execute(statement)
    connection.execute(
        "INSERT INTO recipes VALUES (?, ?, ?, ?, ?)",
        ("v1-recipe", "V1 Recipe", 420, 28.0, 20),
    )
    connection.executemany(
        "INSERT INTO recipe_ingredients VALUES (?, ?, ?)",
        [
            ("v1-recipe", 0, "eggs"),
            ("v1-recipe", 1, "spinach"),
        ],
    )
    connection.execute("PRAGMA user_version = 1")
    connection.commit()


def recipe_rows(
    connection: sqlite3.Connection,
) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
    return (
        connection.execute("SELECT * FROM recipes ORDER BY id").fetchall(),
        connection.execute(
            "SELECT * FROM recipe_ingredients ORDER BY recipe_id, position"
        ).fetchall(),
    )


def test_connect_database_uses_explicit_transactions_and_foreign_keys(
    tmp_path: Path,
) -> None:
    with closing(connect_database(tmp_path / "pantrypilot.sqlite3")) as connection:
        assert connection.isolation_level is None
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("SELECT 1 AS value").fetchone()["value"] == 1


def test_fresh_database_migrates_from_zero_to_exact_version_two_schema(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "pantrypilot.sqlite3"
    with closing(connect_database(database_path)) as connection:
        assert user_version(connection) == 0

        migrate_database(connection, database_path)

        assert user_version(connection) == CURRENT_SCHEMA_VERSION == 2
        assert table_names(connection) == {
            "recipes",
            "recipe_ingredients",
            "saved_pantry",
            "saved_pantry_items",
        }
        assert {
            row[1]: (row[2], row[3], row[5])
            for row in connection.execute("PRAGMA table_info(recipes)")
        } == {
            "id": ("TEXT", 1, 1),
            "name": ("TEXT", 1, 0),
            "calories": ("NUMERIC", 1, 0),
            "protein_g": ("NUMERIC", 1, 0),
            "prep_minutes": ("INTEGER", 1, 0),
        }
        assert {
            row[1]: (row[2], row[3], row[5])
            for row in connection.execute("PRAGMA table_info(recipe_ingredients)")
        } == {
            "recipe_id": ("TEXT", 1, 1),
            "position": ("INTEGER", 1, 2),
            "ingredient_id": ("TEXT", 1, 0),
        }
        recipe_foreign_key = connection.execute(
            "PRAGMA foreign_key_list(recipe_ingredients)"
        ).fetchone()
        assert (
            recipe_foreign_key[2],
            recipe_foreign_key[3],
            recipe_foreign_key[4],
            recipe_foreign_key[6],
        ) == ("recipes", "recipe_id", "id", "CASCADE")
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
        assert connection.execute("SELECT * FROM saved_pantry").fetchall() == []
        assert connection.execute("SELECT * FROM saved_pantry_items").fetchall() == []
        assert {
            row[1]: (row[2], row[3], row[5])
            for row in connection.execute("PRAGMA table_info(saved_pantry)")
        } == {"id": ("INTEGER", 1, 1)}
        assert {
            row[1]: (row[2], row[3], row[5])
            for row in connection.execute("PRAGMA table_info(saved_pantry_items)")
        } == {
            "pantry_id": ("INTEGER", 1, 1),
            "ingredient_id": ("TEXT", 1, 2),
        }
        foreign_key = connection.execute(
            "PRAGMA foreign_key_list(saved_pantry_items)"
        ).fetchone()
        assert (foreign_key[2], foreign_key[3], foreign_key[4], foreign_key[6]) == (
            "saved_pantry",
            "pantry_id",
            "id",
            "CASCADE",
        )


def test_populated_version_one_migrates_to_two_without_changing_recipes(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "pantrypilot.sqlite3"
    with closing(connect_database(database_path)) as connection:
        create_populated_v1(connection)
        before = recipe_rows(connection)

        migrate_database(connection, database_path)

        assert user_version(connection) == 2
        assert recipe_rows(connection) == before
        assert connection.execute("SELECT * FROM saved_pantry").fetchall() == []


def test_current_version_migration_is_a_no_op(tmp_path: Path) -> None:
    database_path = tmp_path / "pantrypilot.sqlite3"
    with closing(connect_database(database_path)) as connection:
        migrate_database(connection, database_path)
        schema_before = connection.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type IN ('table', 'index') ORDER BY name"
        ).fetchall()

        migrate_database(connection, database_path)

        assert (
            connection.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type IN ('table', 'index') ORDER BY name"
            ).fetchall()
            == schema_before
        )
        assert user_version(connection) == 2


def test_newer_schema_version_fails_without_mutation(tmp_path: Path) -> None:
    database_path = tmp_path / "pantrypilot.sqlite3"
    with closing(connect_database(database_path)) as connection:
        connection.execute("CREATE TABLE sentinel (value TEXT)")
        connection.execute("PRAGMA user_version = 3")
        before = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()

        with pytest.raises(DatabaseError, match="newer than supported"):
            migrate_database(connection, database_path)

        assert user_version(connection) == 3
        assert (
            connection.execute(
                "SELECT name, sql FROM sqlite_master WHERE type = 'table' ORDER BY name"
            ).fetchall()
            == before
        )


def test_migration_one_ddl_conflict_rolls_back_first_table_and_keeps_v0(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "pantrypilot.sqlite3"
    with closing(connect_database(database_path)) as connection:
        connection.execute("CREATE TABLE recipe_ingredients (sentinel TEXT)")
        sentinel_schema = connection.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name = 'recipe_ingredients'"
        ).fetchone()["sql"]

        with pytest.raises(DatabaseError, match="schema version 1"):
            migrate_database(connection, database_path)

        assert user_version(connection) == 0
        assert "recipes" not in table_names(connection)
        assert (
            connection.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type = 'table' AND name = 'recipe_ingredients'"
            ).fetchone()["sql"]
            == sentinel_schema
        )
        assert "saved_pantry" not in table_names(connection)
        assert "saved_pantry_items" not in table_names(connection)


def test_migration_two_ddl_conflict_rolls_back_first_table_and_keeps_v1(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "pantrypilot.sqlite3"
    with closing(connect_database(database_path)) as connection:
        create_populated_v1(connection)
        before_recipes = recipe_rows(connection)
        connection.execute("CREATE TABLE saved_pantry_items (sentinel TEXT)")

        with pytest.raises(DatabaseError, match="schema version 2"):
            migrate_database(connection, database_path)

        assert user_version(connection) == 1
        assert "saved_pantry" not in table_names(connection)
        assert (
            connection.execute("PRAGMA table_info(saved_pantry_items)").fetchall()[0][1]
            == "sentinel"
        )
        assert recipe_rows(connection) == before_recipes


def test_commit_failure_after_version_update_restores_schema_data_and_v1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "pantrypilot.sqlite3"
    with closing(connect_database(database_path)) as connection:
        create_populated_v1(connection)
        before_recipes = recipe_rows(connection)
        synthetic_migration_two = (
            "CREATE TABLE migration_parents (id INTEGER PRIMARY KEY)",
            """
            CREATE TABLE migration_children (
                parent_id INTEGER NOT NULL
                    REFERENCES migration_parents(id)
                    DEFERRABLE INITIALLY DEFERRED
            )
            """,
            "INSERT INTO migration_children (parent_id) VALUES (1)",
        )
        monkeypatch.setattr(
            database_module,
            "SCHEMA_MIGRATIONS",
            ((1, dict(SCHEMA_MIGRATIONS)[1]), (2, synthetic_migration_two)),
        )
        traced: list[str] = []
        connection.set_trace_callback(traced.append)

        with pytest.raises(DatabaseError) as exc_info:
            migrate_database(connection, database_path)

        connection.set_trace_callback(None)
        normalized = [" ".join(statement.upper().split()) for statement in traced]
        assert normalized.index("PRAGMA USER_VERSION = 2") < normalized.index("COMMIT")
        assert isinstance(exc_info.value.__cause__, sqlite3.IntegrityError)
        assert user_version(connection) == 1
        assert "migration_parents" not in table_names(connection)
        assert "migration_children" not in table_names(connection)
        assert recipe_rows(connection) == before_recipes
