import importlib
import sqlite3
from pathlib import Path
from types import ModuleType

import pytest

from pantrypilot.catalog import INITIAL_RECIPE_CATALOG
from pantrypilot.catalog_store import initialize_catalog
from pantrypilot.ingredients import INGREDIENT_REGISTRY


def pantry_store_module() -> ModuleType:
    return importlib.import_module("pantrypilot.pantry_store")


def initialized_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "pantrypilot.sqlite3"
    initialize_catalog(database_path, INITIAL_RECIPE_CATALOG, INGREDIENT_REGISTRY)
    return database_path


def test_load_distinguishes_absent_from_deliberately_empty(tmp_path: Path) -> None:
    pantry_store = pantry_store_module()
    database_path = initialized_database(tmp_path)

    assert pantry_store.load_saved_pantry(database_path, INGREDIENT_REGISTRY) is None

    assert (
        pantry_store.replace_saved_pantry(database_path, [], INGREDIENT_REGISTRY) == ()
    )
    assert pantry_store.load_saved_pantry(database_path, INGREDIENT_REGISTRY) == ()


def test_replace_deduplicates_sorts_and_persists_across_reopen(tmp_path: Path) -> None:
    pantry_store = pantry_store_module()
    database_path = initialized_database(tmp_path)

    saved = pantry_store.replace_saved_pantry(
        database_path,
        ["spinach", "eggs", "spinach"],
        INGREDIENT_REGISTRY,
    )

    assert saved == ("eggs", "spinach")
    assert pantry_store.load_saved_pantry(database_path, INGREDIENT_REGISTRY) == (
        "eggs",
        "spinach",
    )
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT id FROM saved_pantry").fetchall() == [(1,)]
        assert connection.execute(
            "SELECT pantry_id, ingredient_id FROM saved_pantry_items "
            "ORDER BY ingredient_id"
        ).fetchall() == [(1, "eggs"), (1, "spinach")]


def test_replace_validates_every_canonical_id_before_connecting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantry_store = pantry_store_module()

    def fail_if_connected(_database_path: Path) -> sqlite3.Connection:
        raise AssertionError("invalid IDs must fail before database I/O")

    monkeypatch.setattr(pantry_store, "connect_database", fail_if_connected)

    with pytest.raises(
        pantry_store.PantryStoreError, match="unknown canonical ingredient id"
    ):
        pantry_store.replace_saved_pantry(
            tmp_path / "must-not-exist.sqlite3",
            ["eggs", "not-registered"],
            INGREDIENT_REGISTRY,
        )

    assert not (tmp_path / "must-not-exist.sqlite3").exists()


def test_read_orders_by_canonical_id_not_insertion_order(tmp_path: Path) -> None:
    pantry_store = pantry_store_module()
    database_path = initialized_database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("INSERT INTO saved_pantry (id) VALUES (1)")
        connection.executemany(
            "INSERT INTO saved_pantry_items VALUES (1, ?)",
            [("spinach",), ("eggs",), ("black-beans",)],
        )

    assert pantry_store.load_saved_pantry(database_path, INGREDIENT_REGISTRY) == (
        "black-beans",
        "eggs",
        "spinach",
    )


def test_load_starts_the_consistent_transaction_before_schema_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantry_store = pantry_store_module()
    database_path = initialized_database(tmp_path)
    traced: list[str] = []
    real_connect_database = pantry_store.connect_database

    def traced_connect_database(path: Path) -> sqlite3.Connection:
        connection = real_connect_database(path)
        connection.set_trace_callback(traced.append)
        return connection

    monkeypatch.setattr(pantry_store, "connect_database", traced_connect_database)

    assert pantry_store.load_saved_pantry(database_path, INGREDIENT_REGISTRY) is None

    normalized = [" ".join(statement.upper().split()) for statement in traced]
    assert normalized.index("BEGIN") < normalized.index("PRAGMA USER_VERSION")


def test_schema_rejects_duplicate_blank_and_orphan_items(tmp_path: Path) -> None:
    database_path = initialized_database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("INSERT INTO saved_pantry (id) VALUES (1)")
        connection.execute("INSERT INTO saved_pantry_items VALUES (1, 'eggs')")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO saved_pantry_items VALUES (1, 'eggs')")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO saved_pantry_items VALUES (1, '   ')")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO saved_pantry_items VALUES (2, 'spinach')")


@pytest.mark.parametrize(
    "corruption_sql",
    [
        "INSERT INTO saved_pantry_items VALUES (1, 'not-registered')",
        "INSERT INTO saved_pantry_items VALUES (1, '   ')",
        "INSERT INTO saved_pantry (id) VALUES (2)",
    ],
)
def test_corrupt_or_unknown_durable_state_fails_the_complete_read(
    tmp_path: Path,
    corruption_sql: str,
) -> None:
    pantry_store = pantry_store_module()
    database_path = initialized_database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute("INSERT OR IGNORE INTO saved_pantry (id) VALUES (1)")
        connection.execute(
            "INSERT OR IGNORE INTO saved_pantry_items VALUES (1, 'eggs')"
        )
        connection.execute(corruption_sql)

    with pytest.raises(pantry_store.PantryStoreError):
        pantry_store.load_saved_pantry(database_path, INGREDIENT_REGISTRY)


def test_orphaned_item_fails_the_complete_read(tmp_path: Path) -> None:
    pantry_store = pantry_store_module()
    database_path = initialized_database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("INSERT INTO saved_pantry_items VALUES (1, 'eggs')")

    with pytest.raises(pantry_store.PantryStoreError, match="foreign key integrity"):
        pantry_store.load_saved_pantry(database_path, INGREDIENT_REGISTRY)


def test_missing_runtime_schema_fails_deterministically(tmp_path: Path) -> None:
    pantry_store = pantry_store_module()
    database_path = tmp_path / "wrong-schema.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA user_version = 1")

    with pytest.raises(pantry_store.PantryStoreError, match="schema version"):
        pantry_store.load_saved_pantry(database_path, INGREDIENT_REGISTRY)
