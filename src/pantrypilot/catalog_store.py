import sqlite3
from contextlib import closing
from pathlib import Path

from pydantic import ValidationError

from pantrypilot.catalog import load_catalog
from pantrypilot.ingredients import IngredientRegistry
from pantrypilot.models import Recipe


class CatalogStoreError(RuntimeError):
    """Raised when the durable recipe catalog cannot be prepared or loaded."""


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

CURRENT_SCHEMA_VERSION = 1
SCHEMA_MIGRATIONS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (1, (CREATE_RECIPES, CREATE_RECIPE_INGREDIENTS)),
)


def connect_catalog(database_path: Path) -> sqlite3.Connection:
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(database_path, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            connection.close()
            raise CatalogStoreError(
                f"catalog connection failed for '{database_path}': "
                "foreign keys are disabled"
            )
        return connection
    except sqlite3.Error as error:
        if connection is not None:
            connection.close()
        raise CatalogStoreError(
            f"catalog connection failed for '{database_path}'"
        ) from error


def migrate_catalog(
    connection: sqlite3.Connection,
    database_path: Path,
) -> None:
    current_version = connection.execute("PRAGMA user_version").fetchone()[0]
    if current_version > CURRENT_SCHEMA_VERSION:
        raise CatalogStoreError(
            f"catalog schema version {current_version} at '{database_path}' "
            f"is newer than supported version {CURRENT_SCHEMA_VERSION}"
        )

    for version, statements in SCHEMA_MIGRATIONS:
        if version <= current_version:
            continue
        if version != current_version + 1:
            raise CatalogStoreError(
                f"catalog migration sequence at '{database_path}' "
                f"cannot advance from {current_version} to {version}"
            )
        try:
            connection.execute("BEGIN IMMEDIATE")
            for statement in statements:
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version = {version}")
            connection.commit()
        except sqlite3.Error as error:
            connection.rollback()
            raise CatalogStoreError(
                f"catalog migration failed for '{database_path}' "
                f"at schema version {version}"
            ) from error
        current_version = version


def load_durable_catalog(
    database_path: Path,
    ingredient_registry: IngredientRegistry,
) -> tuple[Recipe, ...]:
    try:
        with closing(connect_catalog(database_path)) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version != CURRENT_SCHEMA_VERSION:
                raise CatalogStoreError(
                    f"catalog schema version {version} at '{database_path}' "
                    f"does not match supported version {CURRENT_SCHEMA_VERSION}"
                )

            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise CatalogStoreError(
                    f"catalog integrity check failed for '{database_path}'"
                )
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise CatalogStoreError(
                    f"catalog foreign-key check failed for '{database_path}'"
                )

            records: dict[str, dict[str, object]] = {}
            ingredients_by_recipe: dict[str, list[str]] = {}
            for row in connection.execute(
                "SELECT id, name, calories, protein_g, prep_minutes "
                "FROM recipes ORDER BY id"
            ):
                ingredient_ids: list[str] = []
                records[row["id"]] = {
                    "id": row["id"],
                    "name": row["name"],
                    "required_ingredient_ids": ingredient_ids,
                    "calories": row["calories"],
                    "protein_g": row["protein_g"],
                    "prep_minutes": row["prep_minutes"],
                }
                ingredients_by_recipe[row["id"]] = ingredient_ids

            for row in connection.execute(
                "SELECT recipe_id, ingredient_id "
                "FROM recipe_ingredients ORDER BY recipe_id, position"
            ):
                ingredient_ids = ingredients_by_recipe.get(row["recipe_id"])
                if ingredient_ids is None:
                    raise CatalogStoreError(
                        f"catalog relationship references missing recipe "
                        f"'{row['recipe_id']}' at '{database_path}'"
                    )
                ingredient_ids.append(row["ingredient_id"])

        return load_catalog(records.values(), ingredient_registry)
    except CatalogStoreError:
        raise
    except (sqlite3.Error, ValidationError, ValueError, TypeError) as error:
        raise CatalogStoreError(f"catalog load failed for '{database_path}'") from error
