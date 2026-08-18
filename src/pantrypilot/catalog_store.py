import sqlite3
from collections.abc import Iterable, Mapping
from contextlib import closing
from pathlib import Path

from pydantic import ValidationError

from pantrypilot.catalog import load_catalog
from pantrypilot.database import (
    CURRENT_SCHEMA_VERSION,
    DatabaseError,
    connect_database,
    migrate_database,
)
from pantrypilot.ingredients import IngredientRegistry
from pantrypilot.models import Recipe


class CatalogStoreError(RuntimeError):
    """Raised when the durable recipe catalog cannot be prepared or loaded."""


def connect_catalog(database_path: Path) -> sqlite3.Connection:
    try:
        return connect_database(database_path)
    except DatabaseError as exc:
        raise CatalogStoreError(
            f"catalog connection failed for '{database_path}'"
        ) from exc


def migrate_catalog(
    connection: sqlite3.Connection,
    database_path: Path,
) -> None:
    try:
        migrate_database(connection, database_path)
    except DatabaseError as exc:
        raise CatalogStoreError(
            f"catalog migration failed for '{database_path}'"
        ) from exc


def seed_catalog(
    connection: sqlite3.Connection,
    database_path: Path,
    seed_records: Iterable[Mapping[str, object]],
    ingredient_registry: IngredientRegistry,
) -> None:
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise CatalogStoreError(
            f"catalog is partially initialized at '{database_path}': "
            "foreign-key violations exist"
        )

    recipe_count = connection.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
    relationship_count = connection.execute(
        "SELECT COUNT(*) FROM recipe_ingredients"
    ).fetchone()[0]
    recipe_without_ingredients = connection.execute(
        "SELECT recipes.id FROM recipes "
        "LEFT JOIN recipe_ingredients "
        "ON recipe_ingredients.recipe_id = recipes.id "
        "GROUP BY recipes.id HAVING COUNT(recipe_ingredients.position) = 0 "
        "LIMIT 1"
    ).fetchone()

    if recipe_count and relationship_count and recipe_without_ingredients is None:
        return
    if recipe_count or relationship_count or recipe_without_ingredients is not None:
        raise CatalogStoreError(
            f"catalog is partially initialized at '{database_path}'"
        )

    try:
        recipes = load_catalog(seed_records, ingredient_registry)
    except (ValidationError, ValueError, TypeError) as error:
        raise CatalogStoreError(
            f"catalog seed validation failed for '{database_path}'"
        ) from error

    try:
        connection.execute("BEGIN IMMEDIATE")
        for recipe in recipes:
            connection.execute(
                "INSERT INTO recipes "
                "(id, name, calories, protein_g, prep_minutes) VALUES (?, ?, ?, ?, ?)",
                (
                    recipe.id,
                    recipe.name,
                    recipe.calories,
                    recipe.protein_g,
                    recipe.prep_minutes,
                ),
            )
            for position, ingredient_id in enumerate(recipe.required_ingredient_ids):
                connection.execute(
                    "INSERT INTO recipe_ingredients "
                    "(recipe_id, position, ingredient_id) VALUES (?, ?, ?)",
                    (recipe.id, position, ingredient_id),
                )
        connection.commit()
    except sqlite3.Error as error:
        connection.rollback()
        raise CatalogStoreError(f"catalog seed failed for '{database_path}'") from error


def initialize_catalog(
    database_path: Path,
    seed_records: Iterable[Mapping[str, object]],
    ingredient_registry: IngredientRegistry,
) -> None:
    try:
        with closing(connect_catalog(database_path)) as connection:
            migrate_catalog(connection, database_path)
            seed_catalog(
                connection,
                database_path,
                seed_records,
                ingredient_registry,
            )
    except CatalogStoreError:
        raise
    except sqlite3.Error as error:
        raise CatalogStoreError(
            f"catalog initialization failed for '{database_path}'"
        ) from error


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
