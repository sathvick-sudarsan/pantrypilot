import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from pydantic import ValidationError

from pantrypilot.catalog import (
    FEATURE_003_RECIPE_CATALOG,
    INITIAL_RECIPE_CATALOG,
    load_catalog,
)
from pantrypilot.catalog_release import (
    CatalogRelease,
    build_catalog_release,
    catalog_manifest_digest,
)
from pantrypilot.catalog_store import (
    CatalogStoreError,
    connect_catalog,
    initialize_catalog,
    load_durable_catalog,
    migrate_catalog,
    reconcile_catalog,
    seed_catalog,
)
from pantrypilot.database import SCHEMA_MIGRATIONS
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


def insert_recipe_model(
    connection: sqlite3.Connection,
    recipe: Recipe,
    *,
    is_official: int = 0,
) -> None:
    connection.execute(
        "INSERT INTO recipes "
        "(id, name, calories, protein_g, prep_minutes, is_official) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            recipe.id,
            recipe.name,
            recipe.calories,
            recipe.protein_g,
            recipe.prep_minutes,
            is_official,
        ),
    )
    for position, ingredient_id in enumerate(recipe.required_ingredient_ids):
        connection.execute(
            "INSERT INTO recipe_ingredients VALUES (?, ?, ?)",
            (recipe.id, position, ingredient_id),
        )


def migrate_to_schema_two(connection: sqlite3.Connection) -> None:
    for version in (1, 2):
        connection.execute("BEGIN IMMEDIATE")
        for statement in dict(SCHEMA_MIGRATIONS)[version]:
            connection.execute(statement)
        connection.execute(f"PRAGMA user_version = {version}")
        connection.commit()


def catalog_rows(
    connection: sqlite3.Connection,
) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    return (
        [
            tuple(row)
            for row in connection.execute(
                "SELECT id, name, calories, protein_g, prep_minutes, is_official "
                "FROM recipes ORDER BY id"
            )
        ],
        [
            tuple(row)
            for row in connection.execute(
                "SELECT recipe_id, position, ingredient_id "
                "FROM recipe_ingredients ORDER BY recipe_id, position"
            )
        ],
    )


def saved_pantry_rows(
    connection: sqlite3.Connection,
) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    return (
        [tuple(row) for row in connection.execute("SELECT id FROM saved_pantry")],
        [
            tuple(row)
            for row in connection.execute(
                "SELECT pantry_id, ingredient_id FROM saved_pantry_items "
                "ORDER BY pantry_id, ingredient_id"
            )
        ],
    )


def release_for(
    recipes: tuple[Recipe, ...],
    retired_recipe_ids: tuple[str, ...] = (),
) -> CatalogRelease:
    digest = catalog_manifest_digest(recipes, retired_recipe_ids)
    return build_catalog_release(
        recipes,
        retired_recipe_ids,
        INGREDIENT_REGISTRY,
        1,
        {1: digest},
    )


def release_ledger(release: CatalogRelease) -> dict[int, str]:
    return {release.version: release.manifest_digest}


def synthetic_recipe(recipe_id: str) -> Recipe:
    return Recipe(
        id=recipe_id,
        name=recipe_id.replace("-", " ").title(),
        required_ingredient_ids=("eggs", "spinach"),
        calories=320,
        protein_g=21.0,
        prep_minutes=18,
    )


def schema_two_fixture(
    connection: sqlite3.Connection,
    legacy_recipe: Recipe,
) -> None:
    migrate_to_schema_two(connection)
    connection.execute(
        "INSERT INTO recipes "
        "(id, name, calories, protein_g, prep_minutes) VALUES (?, ?, ?, ?, ?)",
        (
            legacy_recipe.id,
            legacy_recipe.name,
            legacy_recipe.calories,
            legacy_recipe.protein_g,
            legacy_recipe.prep_minutes,
        ),
    )
    connection.executemany(
        "INSERT INTO recipe_ingredients VALUES (?, ?, ?)",
        [
            (legacy_recipe.id, position, ingredient_id)
            for position, ingredient_id in enumerate(
                legacy_recipe.required_ingredient_ids
            )
        ],
    )
    insert_recipe(
        connection,
        recipe_id="durable-only",
        name="Durable Only",
        ingredients=((2, "olive-oil"), (0, "eggs"), (1, "spinach")),
    )
    connection.execute("INSERT INTO saved_pantry VALUES (1)")
    connection.executemany(
        "INSERT INTO saved_pantry_items VALUES (?, ?)",
        [(1, "eggs"), (1, "spinach")],
    )
    connection.commit()


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


def test_feature_003_recipe_catalog_is_pinned_immutable_history() -> None:
    assert FEATURE_003_RECIPE_CATALOG == (
        Recipe(
            id="spinach-omelet",
            name="Spinach Omelet",
            required_ingredient_ids=("eggs", "spinach", "olive-oil"),
            calories=410,
            protein_g=28.0,
            prep_minutes=15,
        ),
        Recipe(
            id="black-bean-tacos",
            name="Black Bean Tacos",
            required_ingredient_ids=(
                "black-beans",
                "corn-tortillas",
                "avocado",
                "lime",
            ),
            calories=520,
            protein_g=19.0,
            prep_minutes=25,
        ),
        Recipe(
            id="peanut-noodles",
            name="Peanut Noodles",
            required_ingredient_ids=("noodles", "peanuts", "soy-sauce"),
            calories=560,
            protein_g=20.0,
            prep_minutes=20,
        ),
        Recipe(
            id="lentil-soup",
            name="Lentil Soup",
            required_ingredient_ids=(
                "lentils",
                "carrots",
                "celery",
                "vegetable-broth",
            ),
            calories=360,
            protein_g=22.0,
            prep_minutes=45,
        ),
    )


def test_reconcile_catalog_installs_every_current_recipe_on_fresh_schema_three_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    release = release_for(
        (synthetic_recipe("recipe-one"), synthetic_recipe("recipe-two"))
    )
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)

        reconcile_catalog(
            connection,
            database_path,
            release,
            release_ledger(release),
            FEATURE_003_RECIPE_CATALOG,
            INGREDIENT_REGISTRY,
        )

        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT id, is_official FROM recipes ORDER BY id"
            )
        ] == [("recipe-one", 1), ("recipe-two", 1)]
        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT id, version, manifest_digest FROM catalog_content_state"
            )
        ] == [(1, release.version, release.manifest_digest)]
        assert (
            load_durable_catalog(database_path, INGREDIENT_REGISTRY) == release.recipes
        )


def test_reconcile_catalog_adopts_legacy_and_preserves_unowned_rows(
    tmp_path: Path,
) -> None:
    legacy_recipe = FEATURE_003_RECIPE_CATALOG[0]
    release = release_for((legacy_recipe, synthetic_recipe("new-official")))
    upgraded_path = tmp_path / "upgraded.sqlite3"
    with closing(connect_catalog(upgraded_path)) as connection:
        schema_two_fixture(connection, legacy_recipe)
        migrate_catalog(connection, upgraded_path)
        out_of_band_before = (
            [
                tuple(row)
                for row in connection.execute(
                    "SELECT id, name, calories, protein_g, prep_minutes, is_official "
                    "FROM recipes WHERE id = 'durable-only'"
                )
            ],
            [
                tuple(row)
                for row in connection.execute(
                    "SELECT recipe_id, position, ingredient_id "
                    "FROM recipe_ingredients WHERE recipe_id = 'durable-only' "
                    "ORDER BY position"
                )
            ],
        )
        pantry_before = saved_pantry_rows(connection)

        reconcile_catalog(
            connection,
            upgraded_path,
            release,
            release_ledger(release),
            FEATURE_003_RECIPE_CATALOG,
            INGREDIENT_REGISTRY,
        )

        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT id, is_official FROM recipes WHERE id = ?",
                (legacy_recipe.id,),
            )
        ] == [(legacy_recipe.id, 1)]
        assert (
            [
                tuple(row)
                for row in connection.execute(
                    "SELECT id, name, calories, protein_g, prep_minutes, is_official "
                    "FROM recipes WHERE id = 'durable-only'"
                )
            ],
            [
                tuple(row)
                for row in connection.execute(
                    "SELECT recipe_id, position, ingredient_id "
                    "FROM recipe_ingredients WHERE recipe_id = 'durable-only' "
                    "ORDER BY position"
                )
            ],
        ) == out_of_band_before
        assert saved_pantry_rows(connection) == pantry_before
        upgraded_official = (
            [
                tuple(row)
                for row in connection.execute(
                    "SELECT id, name, calories, protein_g, prep_minutes, is_official "
                    "FROM recipes WHERE is_official = 1 ORDER BY id"
                )
            ],
            [
                tuple(row)
                for row in connection.execute(
                    "SELECT recipe_id, position, ingredient_id "
                    "FROM recipe_ingredients WHERE recipe_id IN ("
                    "SELECT id FROM recipes WHERE is_official = 1) "
                    "ORDER BY recipe_id, position"
                )
            ],
            [
                tuple(row)
                for row in connection.execute(
                    "SELECT id, version, manifest_digest FROM catalog_content_state"
                )
            ],
        )

    fresh_path = tmp_path / "fresh.sqlite3"
    with closing(connect_catalog(fresh_path)) as connection:
        migrate_catalog(connection, fresh_path)
        reconcile_catalog(
            connection,
            fresh_path,
            release,
            release_ledger(release),
            FEATURE_003_RECIPE_CATALOG,
            INGREDIENT_REGISTRY,
        )
        fresh_official = (
            [
                tuple(row)
                for row in connection.execute(
                    "SELECT id, name, calories, protein_g, prep_minutes, is_official "
                    "FROM recipes WHERE is_official = 1 ORDER BY id"
                )
            ],
            [
                tuple(row)
                for row in connection.execute(
                    "SELECT recipe_id, position, ingredient_id "
                    "FROM recipe_ingredients ORDER BY recipe_id, position"
                )
            ],
            [
                tuple(row)
                for row in connection.execute(
                    "SELECT id, version, manifest_digest FROM catalog_content_state"
                )
            ],
        )

    assert upgraded_official == fresh_official


def test_reconcile_catalog_removes_exact_legacy_recipe_at_retired_id(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    legacy_recipe = FEATURE_003_RECIPE_CATALOG[0]
    release = release_for((), (legacy_recipe.id,))
    with closing(connect_catalog(database_path)) as connection:
        schema_two_fixture(connection, legacy_recipe)
        migrate_catalog(connection, database_path)
        out_of_band_before = [
            tuple(row)
            for row in connection.execute(
                "SELECT recipe_id, position, ingredient_id "
                "FROM recipe_ingredients WHERE recipe_id = 'durable-only' "
                "ORDER BY position"
            )
        ]
        pantry_before = saved_pantry_rows(connection)

        reconcile_catalog(
            connection,
            database_path,
            release,
            release_ledger(release),
            FEATURE_003_RECIPE_CATALOG,
            INGREDIENT_REGISTRY,
        )

        assert (
            connection.execute(
                "SELECT id FROM recipes WHERE id = ?", (legacy_recipe.id,)
            ).fetchall()
            == []
        )
        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT recipe_id, position, ingredient_id "
                "FROM recipe_ingredients WHERE recipe_id = 'durable-only' "
                "ORDER BY position"
            )
        ] == out_of_band_before
        assert saved_pantry_rows(connection) == pantry_before
        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT id, version, manifest_digest FROM catalog_content_state"
            )
        ] == [(1, release.version, release.manifest_digest)]


@pytest.mark.parametrize(
    ("stored_recipe", "retired_recipe_id"),
    [
        (
            FEATURE_003_RECIPE_CATALOG[0].model_copy(update={"name": "Changed"}),
            FEATURE_003_RECIPE_CATALOG[0].id,
        ),
        (synthetic_recipe("retired-out-of-band"), "retired-out-of-band"),
    ],
    ids=("divergent-legacy", "non-legacy"),
)
def test_reconcile_catalog_rejects_divergent_or_nonlegacy_retired_id(
    tmp_path: Path,
    stored_recipe: Recipe,
    retired_recipe_id: str,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    release = release_for((), (retired_recipe_id,))
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        insert_recipe_model(connection, stored_recipe)
        connection.commit()
        before = catalog_rows(connection)

        with pytest.raises(CatalogStoreError, match="reserved recipe id collision"):
            reconcile_catalog(
                connection,
                database_path,
                release,
                release_ledger(release),
                FEATURE_003_RECIPE_CATALOG,
                INGREDIENT_REGISTRY,
            )

        assert catalog_rows(connection) == before


def test_reconcile_catalog_scans_retired_ids_before_any_recipe_write(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    legacy_recipe = FEATURE_003_RECIPE_CATALOG[0]
    out_of_band_recipe = synthetic_recipe("z-retired-out-of-band")
    release = release_for((), (legacy_recipe.id, out_of_band_recipe.id))
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        insert_recipe_model(connection, legacy_recipe)
        insert_recipe_model(connection, out_of_band_recipe)
        connection.execute(
            "CREATE TRIGGER reject_retired_recipe_write "
            "BEFORE UPDATE ON recipes "
            "BEGIN SELECT RAISE(FAIL, 'write before retired collision'); END"
        )
        connection.commit()

        with pytest.raises(CatalogStoreError, match="reserved recipe id collision"):
            reconcile_catalog(
                connection,
                database_path,
                release,
                release_ledger(release),
                FEATURE_003_RECIPE_CATALOG,
                INGREDIENT_REGISTRY,
            )

        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT id, is_official FROM recipes ORDER BY id"
            )
        ] == [(legacy_recipe.id, 0), (out_of_band_recipe.id, 0)]


def test_reconcile_catalog_rolls_back_partial_recipe_mutation_and_state_update(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    legacy_recipe = FEATURE_003_RECIPE_CATALOG[0]
    release = release_for((legacy_recipe,))
    with closing(connect_catalog(database_path)) as connection:
        schema_two_fixture(connection, legacy_recipe)
        migrate_catalog(connection, database_path)
        catalog_before = catalog_rows(connection)
        pantry_before = saved_pantry_rows(connection)
        state_before = [
            tuple(row)
            for row in connection.execute(
                "SELECT id, version, manifest_digest FROM catalog_content_state"
            )
        ]
        connection.execute(
            "CREATE TRIGGER reject_reconciled_relationship "
            "BEFORE INSERT ON recipe_ingredients "
            "WHEN NEW.recipe_id = 'spinach-omelet' AND NEW.position = 1 "
            "BEGIN SELECT RAISE(FAIL, 'synthetic relationship failure'); END"
        )
        connection.commit()

        with pytest.raises(CatalogStoreError, match="synthetic relationship failure"):
            reconcile_catalog(
                connection,
                database_path,
                release,
                release_ledger(release),
                FEATURE_003_RECIPE_CATALOG,
                INGREDIENT_REGISTRY,
            )

        assert catalog_rows(connection) == catalog_before
        assert saved_pantry_rows(connection) == pantry_before
        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT id, version, manifest_digest FROM catalog_content_state"
            )
        ] == state_before


def test_reconcile_catalog_preserves_caller_transaction_when_preflight_fails(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    release = release_for((synthetic_recipe("current-official"),))
    invalid_release = CatalogRelease(
        version=release.version,
        manifest_digest="0" * 64,
        recipes=release.recipes,
        retired_recipe_ids=release.retired_recipe_ids,
    )
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        connection.execute("BEGIN")
        insert_recipe(connection, recipe_id="caller-pending")

        with pytest.raises(CatalogStoreError, match="does not match its digest ledger"):
            reconcile_catalog(
                connection,
                database_path,
                invalid_release,
                release_ledger(invalid_release),
                FEATURE_003_RECIPE_CATALOG,
                INGREDIENT_REGISTRY,
            )

        assert connection.in_transaction
        assert connection.execute(
            "SELECT id FROM recipes WHERE id = 'caller-pending'"
        ).fetchall()
        connection.rollback()


def test_reconcile_catalog_preserves_caller_transaction_when_begin_fails(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    release = release_for((synthetic_recipe("current-official"),))
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        connection.execute("BEGIN")
        insert_recipe(connection, recipe_id="caller-pending")

        with pytest.raises(CatalogStoreError, match="cannot start a transaction"):
            reconcile_catalog(
                connection,
                database_path,
                release,
                release_ledger(release),
                FEATURE_003_RECIPE_CATALOG,
                INGREDIENT_REGISTRY,
            )

        assert connection.in_transaction
        assert connection.execute(
            "SELECT id FROM recipes WHERE id = 'caller-pending'"
        ).fetchall()
        connection.rollback()


@pytest.mark.parametrize(
    "changed_legacy",
    [
        FEATURE_003_RECIPE_CATALOG[0].model_copy(update={"name": "Changed"}),
        FEATURE_003_RECIPE_CATALOG[0].model_copy(
            update={"required_ingredient_ids": ("eggs", "spinach")}
        ),
        FEATURE_003_RECIPE_CATALOG[0].model_copy(
            update={
                "required_ingredient_ids": (
                    "eggs",
                    "spinach",
                    "olive-oil",
                    "black-beans",
                )
            }
        ),
        FEATURE_003_RECIPE_CATALOG[0].model_copy(
            update={"required_ingredient_ids": ("spinach", "eggs", "olive-oil")}
        ),
    ],
    ids=("changed-scalar", "missing-ingredient", "extra-ingredient", "reordered"),
)
def test_reconcile_catalog_rejects_divergent_legacy_without_changes(
    tmp_path: Path,
    changed_legacy: Recipe,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    release = release_for((FEATURE_003_RECIPE_CATALOG[0],))
    with closing(connect_catalog(database_path)) as connection:
        schema_two_fixture(connection, changed_legacy)
        migrate_catalog(connection, database_path)
        catalog_before = catalog_rows(connection)
        pantry_before = saved_pantry_rows(connection)

        with pytest.raises(CatalogStoreError, match="reserved recipe id collision"):
            reconcile_catalog(
                connection,
                database_path,
                release,
                release_ledger(release),
                FEATURE_003_RECIPE_CATALOG,
                INGREDIENT_REGISTRY,
            )

        assert catalog_rows(connection) == catalog_before
        assert saved_pantry_rows(connection) == pantry_before


def test_reconcile_catalog_rejects_new_current_id_already_present_out_of_band(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    release = release_for((synthetic_recipe("new-official"),))
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        insert_recipe_model(connection, release.recipes[0])
        connection.commit()
        before = catalog_rows(connection)

        with pytest.raises(CatalogStoreError, match="reserved recipe id collision"):
            reconcile_catalog(
                connection,
                database_path,
                release,
                release_ledger(release),
                FEATURE_003_RECIPE_CATALOG,
                INGREDIENT_REGISTRY,
            )

        assert catalog_rows(connection) == before


def test_reconcile_catalog_scans_every_reserved_row_before_any_recipe_write(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    legacy_recipe = FEATURE_003_RECIPE_CATALOG[0]
    new_recipe = synthetic_recipe("z-new-official")
    release = release_for((legacy_recipe, new_recipe))
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        insert_recipe_model(connection, legacy_recipe)
        insert_recipe_model(connection, new_recipe)
        connection.execute(
            "CREATE TRIGGER reject_recipe_write "
            "BEFORE UPDATE ON recipes "
            "BEGIN SELECT RAISE(FAIL, 'write before collision'); END"
        )
        connection.commit()

        with pytest.raises(CatalogStoreError, match="reserved recipe id collision"):
            reconcile_catalog(
                connection,
                database_path,
                release,
                release_ledger(release),
                FEATURE_003_RECIPE_CATALOG,
                INGREDIENT_REGISTRY,
            )

        assert [
            tuple(row)
            for row in connection.execute(
                "SELECT id, is_official FROM recipes ORDER BY id"
            )
        ] == [(legacy_recipe.id, 0), ("z-new-official", 0)]


def test_reconcile_catalog_successful_rerun_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    release = release_for(
        (synthetic_recipe("recipe-one"), synthetic_recipe("recipe-two"))
    )
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        reconcile_catalog(
            connection,
            database_path,
            release,
            release_ledger(release),
            FEATURE_003_RECIPE_CATALOG,
            INGREDIENT_REGISTRY,
        )
        before = (
            catalog_rows(connection),
            [
                tuple(row)
                for row in connection.execute(
                    "SELECT id, version, manifest_digest FROM catalog_content_state"
                )
            ],
        )

        reconcile_catalog(
            connection,
            database_path,
            release,
            release_ledger(release),
            FEATURE_003_RECIPE_CATALOG,
            INGREDIENT_REGISTRY,
        )

        assert (
            catalog_rows(connection),
            [
                tuple(row)
                for row in connection.execute(
                    "SELECT id, version, manifest_digest FROM catalog_content_state"
                )
            ],
        ) == before


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
