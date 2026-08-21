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


def immediate_timeout_connection(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, isolation_level=None, timeout=0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def saved_pantry_rows(
    database_path: Path,
) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    with sqlite3.connect(database_path) as connection:
        return (
            connection.execute("SELECT id FROM saved_pantry ORDER BY id").fetchall(),
            connection.execute(
                "SELECT pantry_id, ingredient_id FROM saved_pantry_items "
                "ORDER BY pantry_id, ingredient_id"
            ).fetchall(),
        )


def test_load_distinguishes_absent_from_deliberately_empty(tmp_path: Path) -> None:
    pantry_store = pantry_store_module()
    database_path = initialized_database(tmp_path)

    assert pantry_store.load_saved_pantry(database_path, INGREDIENT_REGISTRY) is None

    assert (
        pantry_store.replace_saved_pantry(database_path, [], INGREDIENT_REGISTRY) == ()
    )
    assert pantry_store.load_saved_pantry(database_path, INGREDIENT_REGISTRY) == ()
    assert pantry_store.replace_saved_pantry(
        database_path,
        ["spinach"],
        INGREDIENT_REGISTRY,
    ) == ("spinach",)


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


@pytest.mark.parametrize(
    ("setup_sql", "bypass_checks", "expected_rows"),
    [
        (
            ("INSERT INTO saved_pantry_items VALUES (1, 'eggs')",),
            False,
            ([], [(1, "eggs")]),
        ),
        (
            (
                "INSERT INTO saved_pantry VALUES (1)",
                "INSERT INTO saved_pantry_items VALUES (1, 'not-registered')",
            ),
            False,
            ([(1,)], [(1, "not-registered")]),
        ),
        (
            (
                "INSERT INTO saved_pantry VALUES (1)",
                "INSERT INTO saved_pantry_items VALUES (1, '   ')",
            ),
            True,
            ([(1,)], [(1, "   ")]),
        ),
        (
            ("INSERT INTO saved_pantry VALUES (2)",),
            True,
            ([(2,)], []),
        ),
    ],
    ids=("orphan-item", "unknown-id", "blank-id", "malformed-marker"),
)
def test_replace_rejects_corrupt_state_without_adopting_or_repairing_rows(
    tmp_path: Path,
    setup_sql: tuple[str, ...],
    bypass_checks: bool,
    expected_rows: tuple[list[tuple[object, ...]], list[tuple[object, ...]]],
) -> None:
    pantry_store = pantry_store_module()
    database_path = initialized_database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        if bypass_checks:
            connection.execute("PRAGMA ignore_check_constraints = ON")
        for statement in setup_sql:
            connection.execute(statement)

    before = saved_pantry_rows(database_path)
    assert before == expected_rows

    with pytest.raises(pantry_store.PantryStoreError):
        pantry_store.replace_saved_pantry(
            database_path,
            ["spinach"],
            INGREDIENT_REGISTRY,
        )

    assert saved_pantry_rows(database_path) == before


def test_missing_runtime_schema_fails_deterministically(tmp_path: Path) -> None:
    pantry_store = pantry_store_module()
    database_path = tmp_path / "wrong-schema.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA user_version = 1")

    with pytest.raises(pantry_store.PantryStoreError, match="schema version"):
        pantry_store.load_saved_pantry(database_path, INGREDIENT_REGISTRY)


def test_failed_replacement_rolls_back_marker_and_items(tmp_path: Path) -> None:
    pantry_store = pantry_store_module()
    database_path = initialized_database(tmp_path)
    pantry_store.replace_saved_pantry(database_path, ["eggs"], INGREDIENT_REGISTRY)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TRIGGER reject_spinach
            BEFORE INSERT ON saved_pantry_items
            WHEN NEW.ingredient_id = 'spinach'
            BEGIN
                SELECT RAISE(ABORT, 'synthetic replacement failure');
            END
            """
        )

    with pytest.raises(pantry_store.PantryStoreError) as exc_info:
        pantry_store.replace_saved_pantry(
            database_path,
            ["black-beans", "spinach"],
            INGREDIENT_REGISTRY,
        )

    assert isinstance(exc_info.value.__cause__, sqlite3.IntegrityError)
    assert pantry_store.load_saved_pantry(database_path, INGREDIENT_REGISTRY) == (
        "eggs",
    )


def test_real_write_lock_preserves_state_and_later_replacement_is_visible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantry_store = pantry_store_module()
    database_path = initialized_database(tmp_path)
    pantry_store.replace_saved_pantry(database_path, ["eggs"], INGREDIENT_REGISTRY)
    blocker = sqlite3.connect(database_path, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    monkeypatch.setattr(
        pantry_store,
        "connect_database",
        immediate_timeout_connection,
    )

    try:
        with pytest.raises(pantry_store.PantryStoreError) as exc_info:
            pantry_store.replace_saved_pantry(
                database_path,
                ["spinach"],
                INGREDIENT_REGISTRY,
            )
        assert isinstance(exc_info.value.__cause__, sqlite3.OperationalError)
        assert "database is locked" in str(exc_info.value.__cause__)
    finally:
        blocker.rollback()
        blocker.close()

    assert pantry_store.load_saved_pantry(database_path, INGREDIENT_REGISTRY) == (
        "eggs",
    )
    assert pantry_store.replace_saved_pantry(
        database_path,
        ["black-beans", "spinach"],
        INGREDIENT_REGISTRY,
    ) == ("black-beans", "spinach")
    assert pantry_store.load_saved_pantry(database_path, INGREDIENT_REGISTRY) == (
        "black-beans",
        "spinach",
    )
