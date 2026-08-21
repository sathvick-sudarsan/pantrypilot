import sqlite3
from pathlib import Path


class DatabaseError(RuntimeError):
    """Raised when application-owned SQLite setup or migration fails."""


CREATE_RECIPES = """
CREATE TABLE recipes (
    id TEXT PRIMARY KEY NOT NULL
        CHECK (length(trim(id)) > 0),
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    calories NUMERIC NOT NULL
        CHECK (typeof(calories) IN ('integer', 'real') AND calories >= 0),
    protein_g NUMERIC NOT NULL
        CHECK (typeof(protein_g) IN ('integer', 'real') AND protein_g >= 0),
    prep_minutes INTEGER NOT NULL
        CHECK (typeof(prep_minutes) = 'integer' AND prep_minutes >= 0)
)
"""

CREATE_RECIPE_INGREDIENTS = """
CREATE TABLE recipe_ingredients (
    recipe_id TEXT NOT NULL
        REFERENCES recipes(id) ON DELETE CASCADE,
    position INTEGER NOT NULL
        CHECK (typeof(position) = 'integer' AND position >= 0),
    ingredient_id TEXT NOT NULL
        CHECK (length(trim(ingredient_id)) > 0),
    PRIMARY KEY (recipe_id, position),
    UNIQUE (recipe_id, ingredient_id)
)
"""

CREATE_SAVED_PANTRY = """
CREATE TABLE saved_pantry (
    id INTEGER PRIMARY KEY NOT NULL
        CHECK (id = 1)
)
"""

CREATE_SAVED_PANTRY_ITEMS = """
CREATE TABLE saved_pantry_items (
    pantry_id INTEGER NOT NULL
        CHECK (typeof(pantry_id) = 'integer' AND pantry_id = 1)
        REFERENCES saved_pantry(id) ON DELETE CASCADE,
    ingredient_id TEXT NOT NULL
        CHECK (length(trim(ingredient_id)) > 0),
    PRIMARY KEY (pantry_id, ingredient_id)
)
"""

CURRENT_SCHEMA_VERSION = 2
SCHEMA_MIGRATIONS = (
    (1, (CREATE_RECIPES, CREATE_RECIPE_INGREDIENTS)),
    (2, (CREATE_SAVED_PANTRY, CREATE_SAVED_PANTRY_ITEMS)),
)


def connect_database(database_path: Path) -> sqlite3.Connection:
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(database_path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            connection.close()
            raise DatabaseError("database foreign key enforcement is unavailable")
        return connection
    except sqlite3.Error as exc:
        if connection is not None:
            connection.close()
        raise DatabaseError(
            f"database connection failed for '{database_path}'"
        ) from exc


def migrate_database(
    connection: sqlite3.Connection,
    database_path: Path,
) -> None:
    current_version = connection.execute("PRAGMA user_version").fetchone()[0]
    if current_version > CURRENT_SCHEMA_VERSION:
        raise DatabaseError(
            f"database schema version {current_version} is newer than supported "
            f"version {CURRENT_SCHEMA_VERSION} for '{database_path}'"
        )

    for target_version, statements in SCHEMA_MIGRATIONS:
        if target_version <= current_version:
            continue
        if target_version != current_version + 1:
            raise DatabaseError(
                f"database migration sequence for '{database_path}' cannot "
                f"advance from {current_version} to {target_version}"
            )
        try:
            connection.execute("BEGIN IMMEDIATE")
            for statement in statements:
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version = {target_version}")
            connection.commit()
            current_version = target_version
        except sqlite3.Error as exc:
            connection.rollback()
            raise DatabaseError(
                f"database migration failed for '{database_path}' "
                f"at schema version {target_version}"
            ) from exc
