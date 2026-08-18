import sqlite3
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path

from pantrypilot.database import (
    CURRENT_SCHEMA_VERSION,
    DatabaseError,
    connect_database,
)
from pantrypilot.ingredients import IngredientRegistry


class PantryStoreError(RuntimeError):
    """Raised when saved pantry storage cannot safely complete."""


def _validated_ids(
    ingredient_ids: Iterable[str],
    ingredient_registry: IngredientRegistry,
) -> tuple[str, ...]:
    submitted_ids = tuple(ingredient_ids)
    for ingredient_id in submitted_ids:
        if not isinstance(ingredient_id, str) or not ingredient_id.strip():
            raise PantryStoreError("saved pantry contains a malformed ingredient id")
        if ingredient_id not in ingredient_registry.by_id:
            raise PantryStoreError(
                "saved pantry contains unknown canonical ingredient id: "
                f"{ingredient_id}"
            )
    return tuple(sorted(set(submitted_ids)))


def _require_current_schema(connection: sqlite3.Connection) -> None:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version != CURRENT_SCHEMA_VERSION:
        raise PantryStoreError(
            f"saved pantry schema version {version} is not supported"
        )


def replace_saved_pantry(
    database_path: Path,
    ingredient_ids: Iterable[str],
    ingredient_registry: IngredientRegistry,
) -> tuple[str, ...]:
    canonical_ids = _validated_ids(ingredient_ids, ingredient_registry)
    try:
        with closing(connect_database(database_path)) as connection:
            _require_current_schema(connection)
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM saved_pantry WHERE id = 1")
                connection.execute("INSERT INTO saved_pantry (id) VALUES (1)")
                connection.executemany(
                    "INSERT INTO saved_pantry_items (pantry_id, ingredient_id) "
                    "VALUES (1, ?)",
                    ((ingredient_id,) for ingredient_id in canonical_ids),
                )
                connection.commit()
            except sqlite3.Error:
                connection.rollback()
                raise
    except PantryStoreError:
        raise
    except (DatabaseError, sqlite3.Error) as exc:
        raise PantryStoreError("saved pantry replacement failed") from exc
    return canonical_ids


def load_saved_pantry(
    database_path: Path,
    ingredient_registry: IngredientRegistry,
) -> tuple[str, ...] | None:
    try:
        with closing(connect_database(database_path)) as connection:
            try:
                connection.execute("BEGIN")
                _require_current_schema(connection)
                if (
                    connection.execute(
                        "PRAGMA foreign_key_check(saved_pantry_items)"
                    ).fetchone()
                    is not None
                ):
                    raise PantryStoreError("saved pantry foreign key integrity failed")
                marker_rows = connection.execute(
                    "SELECT id FROM saved_pantry ORDER BY id"
                ).fetchall()
                item_rows = connection.execute(
                    "SELECT pantry_id, ingredient_id FROM saved_pantry_items "
                    "ORDER BY ingredient_id"
                ).fetchall()
                if not marker_rows:
                    if item_rows:
                        raise PantryStoreError("saved pantry items have no marker")
                    connection.commit()
                    return None
                if [row["id"] for row in marker_rows] != [1]:
                    raise PantryStoreError("saved pantry marker is malformed")
                if any(row["pantry_id"] != 1 for row in item_rows):
                    raise PantryStoreError("saved pantry item marker is malformed")
                canonical_ids = _validated_ids(
                    (row["ingredient_id"] for row in item_rows),
                    ingredient_registry,
                )
                if len(canonical_ids) != len(item_rows):
                    raise PantryStoreError("saved pantry contains duplicate items")
                connection.commit()
                return canonical_ids
            except (PantryStoreError, sqlite3.Error):
                connection.rollback()
                raise
    except PantryStoreError:
        raise
    except (DatabaseError, sqlite3.Error) as exc:
        raise PantryStoreError("saved pantry read failed") from exc
