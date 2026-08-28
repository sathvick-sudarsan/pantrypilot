import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from contextlib import closing
from pathlib import Path

from pydantic import ValidationError

from pantrypilot.catalog import FEATURE_003_RECIPE_CATALOG, load_catalog
from pantrypilot.catalog_release import (
    CATALOG_RELEASE_DIGESTS,
    CatalogRelease,
    catalog_manifest_digest,
    current_catalog_release,
)
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
    if (
        connection.execute("PRAGMA foreign_key_check(recipe_ingredients)").fetchone()
        is not None
    ):
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
    ingredient_registry: IngredientRegistry,
) -> None:
    try:
        release = current_catalog_release(ingredient_registry)
    except (ValidationError, ValueError, TypeError) as error:
        raise CatalogStoreError(
            f"catalog release validation failed for '{database_path}'"
        ) from error

    try:
        with closing(connect_catalog(database_path)) as connection:
            migrate_catalog(connection, database_path)
            reconcile_catalog(
                connection,
                database_path,
                release,
                CATALOG_RELEASE_DIGESTS,
                FEATURE_003_RECIPE_CATALOG,
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

            if (
                connection.execute("PRAGMA quick_check(recipes)").fetchone()[0] != "ok"
                or connection.execute(
                    "PRAGMA quick_check(recipe_ingredients)"
                ).fetchone()[0]
                != "ok"
            ):
                raise CatalogStoreError(
                    f"catalog integrity check failed for '{database_path}'"
                )
            if (
                connection.execute(
                    "PRAGMA foreign_key_check(recipe_ingredients)"
                ).fetchone()
                is not None
            ):
                raise CatalogStoreError(
                    f"catalog foreign-key check failed for '{database_path}'"
                )

            return _load_catalog_from_connection(
                connection,
                database_path,
                ingredient_registry,
            )
    except CatalogStoreError:
        raise
    except (sqlite3.Error, ValidationError, ValueError, TypeError) as error:
        raise CatalogStoreError(f"catalog load failed for '{database_path}'") from error


def _load_catalog_from_connection(
    connection: sqlite3.Connection,
    database_path: Path,
    ingredient_registry: IngredientRegistry,
    *,
    official_only: bool = False,
) -> tuple[Recipe, ...]:
    where_clause = " WHERE is_official = 1" if official_only else ""
    records: dict[str, dict[str, object]] = {}
    ingredients_by_recipe: dict[str, list[str]] = {}
    for row in connection.execute(
        "SELECT id, name, calories, protein_g, prep_minutes FROM recipes"
        f"{where_clause} ORDER BY id"
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

    relationship_query = (
        "SELECT recipe_id, ingredient_id FROM recipe_ingredients "
        "ORDER BY recipe_id, position"
    )
    if official_only:
        relationship_query = (
            "SELECT recipe_id, ingredient_id FROM recipe_ingredients "
            "WHERE recipe_id IN (SELECT id FROM recipes WHERE is_official = 1) "
            "ORDER BY recipe_id, position"
        )
    for row in connection.execute(relationship_query):
        ingredient_ids = ingredients_by_recipe.get(row["recipe_id"])
        if ingredient_ids is None:
            raise ValueError(
                f"catalog relationship references missing recipe "
                f"'{row['recipe_id']}' at '{database_path}'"
            )
        ingredient_ids.append(row["ingredient_id"])

    return load_catalog(records.values(), ingredient_registry)


def reconcile_catalog(
    connection: sqlite3.Connection,
    database_path: Path,
    release: CatalogRelease,
    release_digests: Mapping[int, str],
    legacy_recipes: Sequence[Recipe],
    ingredient_registry: IngredientRegistry,
) -> None:
    transaction_started = False
    try:
        if (
            release_digests.get(release.version) != release.manifest_digest
            or catalog_manifest_digest(
                release.recipes,
                release.retired_recipe_ids,
            )
            != release.manifest_digest
        ):
            raise ValueError("catalog release does not match its digest ledger")

        connection.execute("BEGIN IMMEDIATE")
        transaction_started = True
        state_rows = connection.execute(
            "SELECT id, version, manifest_digest FROM catalog_content_state"
        ).fetchall()
        if len(state_rows) != 1 or state_rows[0]["id"] != 1:
            raise ValueError("catalog content state must contain exactly one row")
        stored_version = state_rows[0]["version"]
        stored_digest = state_rows[0]["manifest_digest"]
        if stored_version > release.version:
            raise ValueError(
                f"catalog content version {stored_version} is newer than "
                f"application version {release.version}"
            )
        if stored_version == 0:
            if stored_digest != "unmanaged":
                raise ValueError("catalog content version 0 must be unmanaged")
        else:
            historical_digest = release_digests.get(stored_version)
            if historical_digest is None:
                raise ValueError(f"unknown catalog content version: {stored_version}")
            if stored_digest != historical_digest:
                raise ValueError(
                    "stored catalog content digest does not match release digest ledger"
                )

        official_markers = {
            row["id"]: row["is_official"]
            for row in connection.execute("SELECT id, is_official FROM recipes")
        }
        current_ids = {recipe.id for recipe in release.recipes}
        retired_ids = set(release.retired_recipe_ids)
        reserved_ids = current_ids | retired_ids
        deletion_eligible_ids: set[str] = set()
        if stored_version == 0:
            durable_recipes = _load_catalog_from_connection(
                connection,
                database_path,
                ingredient_registry,
            )
            legacy_by_id = {recipe.id: recipe for recipe in legacy_recipes}
            for durable_recipe in durable_recipes:
                if durable_recipe.id not in reserved_ids:
                    continue
                legacy_recipe = legacy_by_id.get(durable_recipe.id)
                if legacy_recipe is None or durable_recipe != legacy_recipe:
                    raise ValueError(
                        f"reserved recipe id collision: '{durable_recipe.id}'"
                    )
                if durable_recipe.id in retired_ids:
                    deletion_eligible_ids.add(durable_recipe.id)
        else:
            for recipe_id in reserved_ids:
                marker = official_markers.get(recipe_id)
                if marker == 0 or (
                    recipe_id in retired_ids
                    and marker is not None
                    and stored_version == release.version
                ):
                    raise ValueError(f"reserved recipe id collision: '{recipe_id}'")
                if recipe_id in retired_ids and marker == 1:
                    deletion_eligible_ids.add(recipe_id)

        for recipe_id, marker in official_markers.items():
            if marker == 1 and recipe_id not in current_ids:
                if recipe_id not in deletion_eligible_ids:
                    raise ValueError(
                        f"official recipe id is not current or retired: '{recipe_id}'"
                    )

        for recipe in release.recipes:
            if recipe.id in official_markers:
                connection.execute(
                    "UPDATE recipes SET name = ?, calories = ?, protein_g = ?, "
                    "prep_minutes = ?, is_official = 1 WHERE id = ?",
                    (
                        recipe.name,
                        recipe.calories,
                        recipe.protein_g,
                        recipe.prep_minutes,
                        recipe.id,
                    ),
                )
                connection.execute(
                    "DELETE FROM recipe_ingredients WHERE recipe_id = ?",
                    (recipe.id,),
                )
            else:
                connection.execute(
                    "INSERT INTO recipes "
                    "(id, name, calories, protein_g, prep_minutes, is_official) "
                    "VALUES (?, ?, ?, ?, ?, 1)",
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
        for recipe_id in deletion_eligible_ids:
            connection.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))

        official_recipes = _load_catalog_from_connection(
            connection,
            database_path,
            ingredient_registry,
            official_only=True,
        )
        if (
            catalog_manifest_digest(official_recipes, release.retired_recipe_ids)
            != release.manifest_digest
        ):
            raise ValueError(
                "reconciled official catalog digest does not match release"
            )
        connection.execute(
            "UPDATE catalog_content_state SET version = ?, manifest_digest = ? "
            "WHERE id = 1",
            (release.version, release.manifest_digest),
        )
        connection.commit()
    except (sqlite3.Error, ValidationError, ValueError, TypeError) as error:
        if transaction_started:
            connection.rollback()
        raise CatalogStoreError(
            f"catalog reconciliation failed for '{database_path}': {error}"
        ) from error
