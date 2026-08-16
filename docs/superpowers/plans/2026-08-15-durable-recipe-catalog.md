# Durable Recipe Catalog Implementation Plan

> **For the implementing agent:** Use Superpowers `subagent-driven-development` or `executing-plans` only after the owner separately authorizes implementation. Execute each behavior-producing increment test-first and use `verification-before-completion` before claiming success.

**Goal:** Make a file-backed SQLite catalog the only production recipe source while preserving the existing `Recipe`, ingredient-resolution, ranking, and API contracts exactly.

**Architecture:** Add one concrete standard-library `sqlite3` catalog-store module. It owns connection setup, schema version 1, atomic hand-written migrations, seed-only initialization, integrity checks, aggregation, and hydration through the existing `load_catalog` boundary. FastAPI initializes and reloads the store during lifespan, publishes a frozen `tuple[Recipe, ...]` on `app.state`, and performs no database I/O during requests; `rank_recipes` remains pure and unchanged.

**Tech Stack:** Python 3.12, standard-library `sqlite3`, `pathlib`, FastAPI lifespan, Pydantic v2 domain models, pytest, Ruff, uv. No dependency or lockfile change.

**Approved design:** `docs/superpowers/specs/2026-08-15-durable-recipe-catalog-design.md`

**Issue:** GitHub #5 — Feature 003: Durable recipe catalog and ranking parity

---

## Global Constraints

- This plan implements the approved design; it does not reopen its architecture.
- The SQLite file is the production recipe source of truth after startup initialization. Python recipe records are seed/reference/parity data only.
- `INGREDIENT_REGISTRY` remains code-owned. Pantry state and request history remain in memory.
- Keep `rank_recipes(request, recipes, ingredient_registry)` and all score, filtering, ordering, evidence, explanation, limit, and count behavior unchanged.
- Never use SQLite row order as application meaning. Relationship order comes from `recipe_ingredients.position`; ranking order remains score descending and recipe ID ascending.
- Use only `sqlite3`; do not add SQLAlchemy, SQLModel, Alembic, `aiosqlite`, an ORM, a repository protocol, a service layer, a connection pool, or a migration framework.
- Open application-owned catalog connections with `isolation_level=None` so Python does not implicitly begin transactions; `migrate_catalog` and `seed_catalog` alone own their explicit `BEGIN IMMEDIATE`/commit/rollback boundaries.
- Each schema migration executes every DDL statement and its `PRAGMA user_version` update inside one explicitly started transaction. Execute statements individually; never use `executescript`.
- SQLite constraints provide basic post-affinity storage checks only. Complete numeric, finite-value, identifier, relationship, and immutable-domain validation remains in `Recipe`/`load_catalog` hydration.
- A malformed durable row fails the complete load. Nothing invalid is skipped, returned partially, or sent to ranking.
- Never fall back to the Python seed after an unavailable, corrupt, incompatible, or malformed durable store.
- Use a short initialization connection, close it, then open a distinct short load connection. Requests use only the loaded immutable snapshot.
- Tests use real file-backed SQLite databases below `tmp_path`; no developer-local database participates.
- Do not modify `src/pantrypilot/ranking.py`, `src/pantrypilot/models.py`, `src/pantrypilot/ingredients.py`, `src/pantrypilot/evaluation.py`, `pyproject.toml`, or `uv.lock` unless implementation exposes a direct contradiction with the approved design. Stop for owner review if that happens.
- For every behavior-producing increment: write one focused failing test, run it and confirm the intended RED, implement the minimum behavior, rerun for GREEN, run neighboring tests, refactor only while green, verify the task, then make the planned conventional commit.
- The commit commands below are future implementation steps. Do not execute them during planning.

## Proposed Final File Structure and Responsibilities

| Path | Action | Final responsibility |
|---|---|---|
| `.gitignore` | Modify | Ignore local `*.sqlite3` catalog files. |
| `src/pantrypilot/catalog.py` | Modify | Keep `load_catalog`; rename raw records to `INITIAL_RECIPE_CATALOG`; remove production module-level `CATALOG`. |
| `src/pantrypilot/catalog_store.py` | Create | Concrete SQLite schema, connections, version checks, atomic migration runner, seed initialization, integrity checks, durable aggregation, hydration, and store-specific errors. |
| `src/pantrypilot/app.py` | Modify | Resolve default/environment DB path, provide `create_app`, initialize/load in non-deprecated lifespan, publish `app.state.recipe_catalog`, and rank the snapshot. |
| `tests/test_catalog.py` | Modify | Preserve pure seed/domain validation coverage without treating seed data as the production catalog. |
| `tests/test_catalog_store.py` | Create | Real file-backed schema, migration, constraint, seeding, hydration, corruption/failure, and reconnection evidence. |
| `tests/test_api.py` | Modify | Use `TestClient` as a lifespan context manager with isolated paths; prove startup, snapshot, restart, storage-failure, and no-fallback behavior while retaining API regressions. |
| `tests/test_ranking.py` | Modify | Build a direct domain catalog from seed records for persistence-independent ranking unit tests; keep ranking assertions unchanged. |
| `tests/test_ranking_parity.py` | Create | Compare complete ranking responses from direct and deliberately reordered durable catalogs. |
| `README.md` | Modify | Document Feature 003 status, durable catalog behavior, DB path/default/override, startup behavior, and local reset procedure. |
| `docs/product/vision.md` | Modify | Update the current product boundary from Feature 001/in-memory recipes to Feature 003/durable recipes with ranking still stateless. |
| `docs/learning/003-durable-recipe-catalog.md` | Create | Focused teaching guide, commands, examples, exercises, trade-offs, and guided mock-interview questions. |
| `docs/superpowers/specs/2026-08-15-durable-recipe-catalog-design.md` | Preserve and later commit | Owner-approved architecture record. |
| `docs/superpowers/plans/2026-08-15-durable-recipe-catalog.md` | Create and later commit | This implementation plan. |

No other production, test, dependency, configuration, or documentation file is planned to change.

## Final Interfaces

Define these interfaces once and use these names and types in every task:

```python
# src/pantrypilot/catalog.py
INITIAL_RECIPE_CATALOG: tuple[dict[str, object], ...]

def load_catalog(
    records: Iterable[Mapping[str, object]],
    ingredient_registry: IngredientRegistry,
) -> tuple[Recipe, ...]: ...  # existing signature and behavior
```

```python
# src/pantrypilot/catalog_store.py
CURRENT_SCHEMA_VERSION = 1
SCHEMA_MIGRATIONS: tuple[tuple[int, tuple[str, ...]], ...]

class CatalogStoreError(RuntimeError):
    """A deterministic catalog connection, schema, seed, or load failure."""

def connect_catalog(database_path: Path) -> sqlite3.Connection: ...

def migrate_catalog(
    connection: sqlite3.Connection,
    database_path: Path,
) -> None: ...

def seed_catalog(
    connection: sqlite3.Connection,
    database_path: Path,
    seed_records: Iterable[Mapping[str, object]],
    ingredient_registry: IngredientRegistry,
) -> None: ...

def initialize_catalog(
    database_path: Path,
    seed_records: Iterable[Mapping[str, object]],
    ingredient_registry: IngredientRegistry,
) -> None: ...

def load_durable_catalog(
    database_path: Path,
    ingredient_registry: IngredientRegistry,
) -> tuple[Recipe, ...]: ...
```

`connect_catalog` returns a caller-owned connection with `isolation_level is None`, `sqlite3.Row` rows, and `PRAGMA foreign_keys = ON` verified. Callers close it with `contextlib.closing`; no connection survives initialization/loading and there is no pool.

```python
# src/pantrypilot/app.py
DATABASE_PATH_ENV = "PANTRYPILOT_DB_PATH"
DEFAULT_DATABASE_PATH = Path("pantrypilot.sqlite3")

def create_app(database_path: Path) -> FastAPI: ...

app = create_app(
    Path(os.environ.get(DATABASE_PATH_ENV, str(DEFAULT_DATABASE_PATH)))
)
```

During a successful lifespan:

```python
app.state.recipe_catalog: tuple[Recipe, ...]
```

The endpoint continues to call the unchanged boundary:

```python
rank_recipes(ranking_request, http_request.app.state.recipe_catalog, INGREDIENT_REGISTRY)
```

`Path` is the only database-path representation. `CatalogStoreError` is the only new public exception type. There is no generic repository interface.

## Schema Version 1

Migration 1 executes these two statements individually, in this order, followed by `PRAGMA user_version = 1` in the same explicit transaction:

```sql
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
```

```sql
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
```

The explicit `NOT NULL` on `recipes.id` closes SQLite's ordinary-rowid-table exception that otherwise permits `NULL` in a non-`INTEGER PRIMARY KEY`; the blank-text check separately rejects empty and whitespace-only IDs. The numeric checks reject storage classes and basic negative/fractional values that violate the approved storage boundary after SQLite affinity has run. They intentionally do not reproduce the full `Recipe` contract. For example, a real positive infinity can legally satisfy the SQLite `typeof`/non-negative check but must fail Pydantic `FiniteFloat` validation during complete-catalog hydration.

## Artifact Commit Gate

Only after separate implementation authorization, preserve the reviewed artifacts before code work:

```powershell
git add docs/superpowers/specs/2026-08-15-durable-recipe-catalog-design.md
git commit -m "docs: design durable recipe catalog"
git add docs/superpowers/plans/2026-08-15-durable-recipe-catalog.md
git commit -m "docs: plan durable recipe catalog"
```

Expected: two documentation-only commits; the second contains this plan. Do not combine either with implementation.

---

## Task 1: Atomic SQLite Schema and Connection Foundation

**Files:**

- Create: `src/pantrypilot/catalog_store.py`
- Create: `tests/test_catalog_store.py`

**Interfaces established:** `CURRENT_SCHEMA_VERSION`, `SCHEMA_MIGRATIONS`, `CatalogStoreError`, `connect_catalog`, and `migrate_catalog` exactly as declared above.

### Step 1: Establish RED for the first store interface

Create `tests/test_catalog_store.py` with a temporary import guard so a missing module is an explicit test failure rather than an unexplained collection failure:

```python
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

try:
    from pantrypilot.catalog_store import connect_catalog
except ModuleNotFoundError:
    connect_catalog = None


def test_connect_catalog_uses_explicit_transactions_and_enables_foreign_keys(
    tmp_path: Path,
) -> None:
    if connect_catalog is None:
        pytest.fail("connect_catalog is not implemented")

    with closing(connect_catalog(tmp_path / "catalog.sqlite3")) as connection:
        enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        isolation_level = connection.isolation_level

    assert enabled == 1
    assert isolation_level is None
```

Run:

```powershell
uv run pytest tests/test_catalog_store.py::test_connect_catalog_uses_explicit_transactions_and_enables_foreign_keys -v
```

Expected RED: `connect_catalog is not implemented`.

### Step 2: Implement the minimum verified connection

Create `src/pantrypilot/catalog_store.py` with imports, the exception, and this connection function:

```python
import sqlite3
from pathlib import Path


class CatalogStoreError(RuntimeError):
    """Raised when the durable recipe catalog cannot be prepared or loaded."""


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
```

Remove the temporary import guard and use the normal import. Rerun the focused test.

Expected GREEN: the real file-backed connection reports foreign keys enabled and `isolation_level is None`, leaving transaction start under application control.

### Step 3: Add exact schema and version tests

Import `CatalogStoreError` plus `pantrypilot.catalog_store as catalog_store_module`. Temporarily bind both `CURRENT_SCHEMA_VERSION = getattr(catalog_store_module, "CURRENT_SCHEMA_VERSION", None)` and `migrate_catalog = getattr(catalog_store_module, "migrate_catalog", None)`, then add these focused tests:

```python
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
    if migrate_catalog is None or CURRENT_SCHEMA_VERSION is None:
        pytest.fail("migrate_catalog is not implemented")

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
    if migrate_catalog is None:
        pytest.fail("migrate_catalog is not implemented")

    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        schema_before = connection.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type IN ('table', 'index') ORDER BY name"
        ).fetchall()

        migrate_catalog(connection, database_path)

        assert connection.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type IN ('table', 'index') ORDER BY name"
        ).fetchall() == schema_before
        assert user_version(connection) == 1


def test_newer_schema_version_is_rejected(tmp_path: Path) -> None:
    if migrate_catalog is None:
        pytest.fail("migrate_catalog is not implemented")

    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        connection.execute("PRAGMA user_version = 2")

        with pytest.raises(CatalogStoreError, match="newer than supported"):
            migrate_catalog(connection, database_path)

        assert user_version(connection) == 2
        assert table_names(connection) == set()
```

Run each newly added test directly. Expected RED: `migrate_catalog` and the versioned schema are absent.

### Step 4: Implement migration 1 without implicit commits

Add the two exact SQL strings from **Schema Version 1**, then:

```python
CURRENT_SCHEMA_VERSION = 1
SCHEMA_MIGRATIONS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (1, (CREATE_RECIPES, CREATE_RECIPE_INGREDIENTS)),
)


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
```

Replace the temporary test bindings with direct imports of `CURRENT_SCHEMA_VERSION` and `migrate_catalog`. Run the three schema/version tests. Expected GREEN: exact schema version 1 exists, a rerun changes nothing, and version 2 is rejected without mutation.

### Step 5: Prove DDL and `user_version` rollback together

Add the required real partial-failure test. A pre-existing conflicting second table makes migration 1 create `recipes` successfully and then fail on its later DDL statement:

```python
def test_failed_migration_rolls_back_schema_and_user_version(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        connection.execute("CREATE TABLE recipe_ingredients (sentinel TEXT)")
        schema_before = connection.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type = 'table' ORDER BY name"
        ).fetchall()

        with pytest.raises(CatalogStoreError, match="schema version 1"):
            migrate_catalog(connection, database_path)

        assert connection.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type = 'table' ORDER BY name"
        ).fetchall() == schema_before
        assert "recipes" not in table_names(connection)
        assert user_version(connection) == 0
```

Run:

```powershell
uv run pytest tests/test_catalog_store.py::test_failed_migration_rolls_back_schema_and_user_version -v
```

Expected GREEN only if early DDL and `user_version` remain rolled back. This test must stay real and file-backed; do not mock `sqlite3` or replace individual `execute` calls with `executescript`.

### Step 6: Prove real storage constraints

Add direct SQL tests so SQLite—not a mock or Pydantic—owns this evidence:

```python
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
```

Run:

```powershell
uv run pytest tests/test_catalog_store.py -v
```

Expected GREEN: SQLite enforces explicit non-null and nonblank recipe identity, the approved basic type/non-negative checks, PK, FK, position, and unique-relationship boundaries. Do not add arbitrary calorie, protein, or time maxima.

### Step 7: Refactor while green and verify Task 1

Keep SQL and migration logic in this one module. Extract only the two SQL constants already needed by `SCHEMA_MIGRATIONS`; do not add migration classes or a generic transaction helper.

Run:

```powershell
uv run pytest tests/test_catalog_store.py -v
uv run pytest tests/test_catalog.py tests/test_ranking.py tests/test_api.py -q
uv run ruff format --check src/pantrypilot/catalog_store.py tests/test_catalog_store.py
uv run ruff check src/pantrypilot/catalog_store.py tests/test_catalog_store.py
git diff --check
```

Expected: all focused and neighboring tests pass; format, lint, and whitespace checks pass.

### Step 8: Planned commit

```powershell
git add src/pantrypilot/catalog_store.py tests/test_catalog_store.py
git commit -m "feat: add atomic catalog schema migrations"
```

---

## Task 2: Complete Durable Catalog Hydration and Integrity

**Files:**

- Modify: `src/pantrypilot/catalog_store.py`
- Modify: `tests/test_catalog_store.py`

**Interface established:** `load_durable_catalog(database_path, ingredient_registry) -> tuple[Recipe, ...]`.

### Step 1: Add a test-only insertion helper and valid hydration test

Add a temporary `load_durable_catalog = getattr(catalog_store_module, "load_durable_catalog", None)` binding after `import pantrypilot.catalog_store as catalog_store_module`, then add this helper to `tests/test_catalog_store.py`; it deliberately inserts relationship rows in the supplied order while persisting their semantic positions:

```python
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
        "INSERT INTO recipes VALUES (?, ?, ?, ?, ?)",
        (recipe_id, name, calories, protein_g, prep_minutes),
    )
    for position, ingredient_id in ingredients:
        connection.execute(
            "INSERT INTO recipe_ingredients VALUES (?, ?, ?)",
            (recipe_id, position, ingredient_id),
        )


def test_load_durable_catalog_hydrates_frozen_recipes_in_position_order(
    tmp_path: Path,
) -> None:
    if load_durable_catalog is None:
        pytest.fail("load_durable_catalog is not implemented")

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
```

Add the exact imports for `ValidationError`, `INGREDIENT_REGISTRY`, and `Recipe`; use the temporary guarded loader binding described above until the production symbol exists.

Run:

```powershell
uv run pytest tests/test_catalog_store.py::test_load_durable_catalog_hydrates_frozen_recipes_in_position_order -v
```

Expected RED: `load_durable_catalog is not implemented`, without a collection failure.

### Step 2: Implement aggregate-then-validate loading

Add the following flow to `catalog_store.py`:

```python
from contextlib import closing
from collections.abc import Iterable, Mapping

from pydantic import ValidationError

from pantrypilot.catalog import load_catalog
from pantrypilot.ingredients import IngredientRegistry
from pantrypilot.models import Recipe


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
        raise CatalogStoreError(
            f"catalog load failed for '{database_path}'"
        ) from error
```

Keep the two-table queries separate so a recipe with zero relationships remains present for Pydantic to reject. The `ORDER BY` clauses make hydration deterministic; neither ordering controls ranking.

Replace the temporary test binding with a normal `from pantrypilot.catalog_store import load_durable_catalog` import. Run the focused test. Expected GREEN: positions, not insertion/fetch order, determine the immutable ingredient tuple.

### Step 3: Add complete-load domain failure cases

Add these tests one at a time and run each before any corrective implementation. The current minimal loader should already satisfy them; if one fails, preserve it as RED and make only the smallest loader correction.

```python
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
    assert "unknown ingredient IDs" in str(error.value.__cause__)


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
```

Expected GREEN: SQLite-rejected inputs fail at insertion; SQLite-permitted but domain-invalid values fail deterministic complete hydration; no partial tuple is observable.

### Step 4: Add schema and foreign-key failure cases

```python
def test_current_version_with_missing_schema_fails_load(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA user_version = 1")

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


@pytest.mark.parametrize("version", [0, 2])
def test_wrong_schema_version_fails_load(tmp_path: Path, version: int) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute(f"PRAGMA user_version = {version}")

    with pytest.raises(CatalogStoreError, match="does not match supported"):
        load_durable_catalog(database_path, INGREDIENT_REGISTRY)
```

Run each focused test. Expected GREEN: incomplete, foreign-key-invalid, older, and newer stores fail with stable path/version context and never reach ranking.

### Step 5: Refactor while green and verify Task 2

Keep the local typed ingredient accumulator; do not introduce a stored-row model. Keep `load_catalog` as the single domain hydration seam.

Run:

```powershell
uv run pytest tests/test_catalog_store.py -v
uv run pytest tests/test_catalog.py tests/test_ranking.py -q
uv run ruff format --check src/pantrypilot/catalog_store.py tests/test_catalog_store.py
uv run ruff check src/pantrypilot/catalog_store.py tests/test_catalog_store.py
git diff --check
```

Expected: complete persistence/hydration suite and neighboring pure catalog/ranking tests pass.

### Step 6: Planned commit

```powershell
git add src/pantrypilot/catalog_store.py tests/test_catalog_store.py
git commit -m "feat: hydrate durable recipe catalog"
```

---

## Task 3: Seed-Only Initialization and Reconnection Durability

**Files:**

- Modify: `src/pantrypilot/catalog.py`
- Modify: `src/pantrypilot/catalog_store.py`
- Modify: `tests/test_catalog.py`
- Modify: `tests/test_catalog_store.py`

**Interfaces established:** `INITIAL_RECIPE_CATALOG`, `seed_catalog`, and `initialize_catalog` exactly as declared above.

### Step 1: Rename the raw records without changing domain behavior

In `tests/test_catalog.py`, replace the production-catalog assertion with a seed/reference assertion. For the first RED, import `pantrypilot.catalog as catalog_module` and bind `INITIAL_RECIPE_CATALOG = getattr(catalog_module, "INITIAL_RECIPE_CATALOG", None)` so collection succeeds:

```python
import pantrypilot.catalog as catalog_module
from pantrypilot.catalog import load_catalog

INITIAL_RECIPE_CATALOG = getattr(
    catalog_module,
    "INITIAL_RECIPE_CATALOG",
    None,
)


def test_initial_recipe_catalog_loads_the_approved_recipes() -> None:
    if INITIAL_RECIPE_CATALOG is None:
        pytest.fail("INITIAL_RECIPE_CATALOG is not implemented")

    catalog = load_catalog(INITIAL_RECIPE_CATALOG, INGREDIENT_REGISTRY)

    assert [recipe.id for recipe in catalog] == [
        "spinach-omelet",
        "black-bean-tacos",
        "peanut-noodles",
        "lentil-soup",
    ]
    assert all(recipe.required_ingredient_ids for recipe in catalog)
```

Run:

```powershell
uv run pytest tests/test_catalog.py::test_initial_recipe_catalog_loads_the_approved_recipes -v
```

Expected RED: `INITIAL_RECIPE_CATALOG is not implemented`, without a collection failure.

Rename `RAW_CATALOG` to `INITIAL_RECIPE_CATALOG` in `catalog.py` and annotate it as `tuple[dict[str, object], ...]`. Replace the temporary test binding with a direct import. Temporarily define the existing `CATALOG` from that renamed constant so the branch stays green until Task 4 moves the application and ranking tests atomically. Add a comment stating that this compatibility binding is removed in Task 4; it must not exist in the final tree.

Run all catalog tests. Expected GREEN with the same approved four `Recipe` values.

### Step 2: Establish RED for empty-store initialization

Before adding the test, bind `initialize_catalog = getattr(catalog_store_module, "initialize_catalog", None)` in `tests/test_catalog_store.py`. Add:

```python
def test_initialize_catalog_seeds_approved_recipes_and_survives_reopen(
    tmp_path: Path,
) -> None:
    if initialize_catalog is None:
        pytest.fail("initialize_catalog is not implemented")

    database_path = tmp_path / "catalog.sqlite3"

    initialize_catalog(
        database_path,
        INITIAL_RECIPE_CATALOG,
        INGREDIENT_REGISTRY,
    )
    recipes = load_durable_catalog(database_path, INGREDIENT_REGISTRY)

    assert recipes == load_catalog(INITIAL_RECIPE_CATALOG, INGREDIENT_REGISTRY)
    with sqlite3.connect(database_path) as reopened:
        assert reopened.execute("PRAGMA user_version").fetchone()[0] == 1
        assert reopened.execute("SELECT COUNT(*) FROM recipes").fetchone()[0] == 4
        assert reopened.execute(
            "SELECT COUNT(*) FROM recipe_ingredients"
        ).fetchone()[0] == sum(
            len(record["required_ingredient_ids"])
            for record in INITIAL_RECIPE_CATALOG
        )
```

Run the focused test. Expected RED: `initialize_catalog is not implemented`, without a collection failure.

### Step 3: Implement atomic seed initialization

Implement these exact rules in `catalog_store.py`:

1. `initialize_catalog` opens one connection using `connect_catalog`, calls `migrate_catalog`, calls `seed_catalog`, and closes the connection with `closing`.
2. `seed_catalog` runs `PRAGMA foreign_key_check`, counts both tables, and finds recipes lacking relationships.
3. Both counts zero means seedable. Validate all seed records first with `load_catalog`.
4. Both tables non-empty with no FK violations and no zero-relationship recipe means authoritative durable data; return without comparing to seed.
5. Any other shape is partial/corrupt and raises `CatalogStoreError`.
6. Insert every validated recipe and every ordered ingredient under one explicit `BEGIN IMMEDIATE`; commit only after all inserts. Roll back on any `sqlite3.Error`.

Use this implementation shape:

```python
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
        raise CatalogStoreError(
            f"catalog seed failed for '{database_path}'"
        ) from error


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
```

Replace the temporary test binding with direct imports of `initialize_catalog` and `seed_catalog`. Rerun the focused test. Expected GREEN: a fresh file migrates, seeds once, closes, reopens, and hydrates the approved immutable catalog.

### Step 4: Prove validation-before-insertion and atomic rollback

Add one test for domain validation before insertion and one real transaction-failure test:

```python
def test_invalid_seed_is_validated_before_any_insert(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    invalid_seed = ({**INITIAL_RECIPE_CATALOG[0], "id": ""},)

    with pytest.raises(CatalogStoreError, match="seed validation failed"):
        initialize_catalog(database_path, invalid_seed, INGREDIENT_REGISTRY)

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM recipes").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM recipe_ingredients"
        ).fetchone()[0] == 0


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
        assert connection.execute(
            "SELECT COUNT(*) FROM recipe_ingredients"
        ).fetchone()[0] == 0
```

Run each focused test. Expected GREEN: invalid domain input never starts insertion; a real later SQLite failure rolls back earlier recipe and relationship inserts.

### Step 5: Prove idempotence, no reconciliation, and partial-state failure

Add:

```python
def test_second_initialization_does_not_duplicate_or_overwrite(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    initialize_catalog(database_path, INITIAL_RECIPE_CATALOG, INGREDIENT_REGISTRY)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE recipes SET name = ? WHERE id = ?",
            ("Durable Name", "spinach-omelet"),
        )

    initialize_catalog(
        database_path,
        INITIAL_RECIPE_CATALOG,
        INGREDIENT_REGISTRY,
    )

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM recipes").fetchone()[0] == 4
        assert connection.execute(
            "SELECT name FROM recipes WHERE id = 'spinach-omelet'"
        ).fetchone()[0] == "Durable Name"


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


def test_valid_non_empty_catalog_is_not_reconciled_or_seed_validated(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with closing(connect_catalog(database_path)) as connection:
        migrate_catalog(connection, database_path)
        insert_recipe(
            connection,
            recipe_id="durable-only",
            name="Durable Only",
            ingredients=((0, "eggs"),),
        )
        connection.commit()
    invalid_unused_seed = ({**INITIAL_RECIPE_CATALOG[0], "id": ""},)

    initialize_catalog(database_path, invalid_unused_seed, INGREDIENT_REGISTRY)

    assert load_durable_catalog(database_path, INGREDIENT_REGISTRY) == (
        Recipe(
            id="durable-only",
            name="Durable Only",
            required_ingredient_ids=("eggs",),
            calories=100,
            protein_g=10.0,
            prep_minutes=10,
        ),
    )
```

Run each focused test. Expected GREEN: the approved seed is used only for a genuinely empty store; valid non-empty durable data wins; incomplete shapes fail.

### Step 6: Refactor while green and verify Task 3

Keep validation and transaction boundaries visible inside `seed_catalog`; do not generalize them. Remove any duplicated test setup only when a small local test helper makes the failure scenario clearer.

Run:

```powershell
uv run pytest tests/test_catalog.py tests/test_catalog_store.py -v
uv run pytest tests/test_ranking.py tests/test_api.py -q
uv run ruff format --check src/pantrypilot/catalog.py src/pantrypilot/catalog_store.py tests/test_catalog.py tests/test_catalog_store.py
uv run ruff check src/pantrypilot/catalog.py src/pantrypilot/catalog_store.py tests/test_catalog.py tests/test_catalog_store.py
git diff --check
```

Expected: pure catalog validation, migration, initialization, hydration, and existing regression suites all pass.

### Step 7: Planned commit

```powershell
git add src/pantrypilot/catalog.py src/pantrypilot/catalog_store.py tests/test_catalog.py tests/test_catalog_store.py
git commit -m "feat: initialize durable recipe catalog"
```

---

## Task 4: FastAPI Lifespan and Durable Snapshot Integration

**Files:**

- Modify: `.gitignore`
- Modify: `src/pantrypilot/app.py`
- Modify: `src/pantrypilot/catalog.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_ranking.py`

**Interface established:** `create_app(database_path: Path) -> FastAPI`, plus `DATABASE_PATH_ENV`, `DEFAULT_DATABASE_PATH`, and `app.state.recipe_catalog` as declared above.

### Step 1: Establish RED for the application factory and lifespan

Replace the module-level API clients with an isolated context-managed fixture and add a first lifespan test:

```python
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import pantrypilot.app as app_module
from pantrypilot.models import Recipe

create_app = getattr(app_module, "create_app", None)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(tmp_path / "catalog.sqlite3")) as test_client:
        yield test_client


@pytest.fixture
def safe_client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(
        create_app(tmp_path / "safe-catalog.sqlite3"),
        raise_server_exceptions=False,
    ) as test_client:
        yield test_client


def test_lifespan_initializes_and_publishes_frozen_catalog(tmp_path: Path) -> None:
    if create_app is None:
        pytest.fail("create_app is not implemented")

    database_path = tmp_path / "catalog.sqlite3"
    application = create_app(database_path)

    assert not database_path.exists()
    with TestClient(application) as client:
        assert database_path.exists()
        assert isinstance(client.app.state.recipe_catalog, tuple)
        assert all(
            isinstance(recipe, Recipe)
            for recipe in client.app.state.recipe_catalog
        )
        assert len(client.app.state.recipe_catalog) == 4
```

Run:

```powershell
uv run pytest tests/test_api.py::test_lifespan_initializes_and_publishes_frozen_catalog -v
```

Expected RED: `create_app is not implemented`, without a collection failure. After Step 2 is green, replace the temporary `getattr` binding with `from pantrypilot.app import create_app`; keep the existing `app_module` import for monkeypatch tests.

### Step 2: Implement non-deprecated lifespan and snapshot ranking

Refactor `app.py` into an app factory without changing route schemas or exception mapping:

```python
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pantrypilot.catalog import INITIAL_RECIPE_CATALOG
from pantrypilot.catalog_store import initialize_catalog, load_durable_catalog
from pantrypilot.ingredients import INGREDIENT_REGISTRY
from pantrypilot.models import RankingRequest, RankingResponse
from pantrypilot.ranking import UnresolvedExcludedIngredientsError, rank_recipes

DATABASE_PATH_ENV = "PANTRYPILOT_DB_PATH"
DEFAULT_DATABASE_PATH = Path("pantrypilot.sqlite3")


def create_app(database_path: Path) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        initialize_catalog(
            database_path,
            INITIAL_RECIPE_CATALOG,
            INGREDIENT_REGISTRY,
        )
        application.state.recipe_catalog = load_durable_catalog(
            database_path,
            INGREDIENT_REGISTRY,
        )
        yield

    application = FastAPI(title="PantryPilot", lifespan=lifespan)

    @application.exception_handler(RequestValidationError)
    def request_validation_exception_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        detail = _replace_non_finite_values(jsonable_encoder(exc.errors()))
        return JSONResponse(status_code=422, content={"detail": detail})

    @application.post("/v1/meal-rankings", response_model=RankingResponse)
    def create_meal_ranking(
        ranking_request: RankingRequest,
        http_request: Request,
    ) -> RankingResponse:
        try:
            return rank_recipes(
                ranking_request,
                http_request.app.state.recipe_catalog,
                INGREDIENT_REGISTRY,
            )
        except UnresolvedExcludedIngredientsError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "type": "unresolved_excluded_ingredients",
                    "message": (
                        "All excluded ingredients must resolve before ranking."
                    ),
                    "ingredient_resolution": (
                        exc.ingredient_resolution.model_dump(mode="json")
                    ),
                },
            ) from exc

    return application


app = create_app(
    Path(os.environ.get(DATABASE_PATH_ENV, str(DEFAULT_DATABASE_PATH)))
)
```

Keep the existing module-level `_replace_non_finite_values` helper unchanged above `create_app`. FastAPI's existing generic unexpected-error response remains unchanged; do not add a new catch-all handler.

Run the focused lifespan test. Expected GREEN: constructing/importing the app causes no database I/O; entering lifespan initializes and publishes the tuple.

### Step 3: Move every existing API test onto real lifespan

Change each existing test to accept `client` or `safe_client` as a fixture argument. Retain every existing assertion, including the exact known ranking response, invalid-body 422 response, resolver evidence, exclusion behavior, and safe generic 500 body. Update monkeypatch targets to patch `pantrypilot.app.rank_recipes` before the request inside an active `safe_client` context.

Run:

```powershell
uv run pytest tests/test_api.py -v
```

Expected GREEN: all Feature 001/002 API behavior is unchanged under real lifespan.

### Step 4: Prove import safety, durable restart behavior, and no fallback

Add:

```python
def test_importing_app_does_not_create_database(tmp_path: Path) -> None:
    database_path = tmp_path / "import-only.sqlite3"
    environment = os.environ.copy()
    environment["PANTRYPILOT_DB_PATH"] = str(database_path)

    completed = subprocess.run(
        [sys.executable, "-c", "import pantrypilot.app"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert not database_path.exists()


def test_persisted_non_empty_change_is_visible_after_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with TestClient(create_app(database_path)):
        pass
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE recipes SET name = ? WHERE id = ?",
            ("Durable Omelet", "spinach-omelet"),
        )

    with TestClient(create_app(database_path)) as restarted:
        response = restarted.post(
            "/v1/meal-rankings",
            json=VALID_REQUEST,
        )

    assert response.status_code == 200
    result = next(
        item for item in response.json()["results"]
        if item["id"] == "spinach-omelet"
    )
    assert result["name"] == "Durable Omelet"


def test_unavailable_storage_prevents_startup(tmp_path: Path) -> None:
    application = create_app(tmp_path)  # A directory cannot be a SQLite file.

    with pytest.raises(CatalogStoreError, match="catalog connection failed"):
        with TestClient(application):
            pass


def test_incomplete_current_schema_prevents_startup_without_seed_fallback(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "catalog.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA user_version = 1")

    with pytest.raises(CatalogStoreError):
        with TestClient(create_app(database_path)):
            pass
```

Add `os`, `sqlite3`, `subprocess`, and `sys` imports at the top of `tests/test_api.py`. The subprocess isolates the import-only assertion from the test process's already imported module state.

Run each focused test. Expected GREEN: only lifespan touches storage, a persisted change survives reconnection and becomes the new snapshot, and storage/schema failures abort startup rather than using Python seed data.

### Step 5: Prove requests perform no database I/O

```python
def test_request_uses_snapshot_without_database_io(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pantrypilot.app as app_module

    application = create_app(tmp_path / "catalog.sqlite3")
    with TestClient(application) as client:
        def fail_if_called(*args: object, **kwargs: object) -> None:
            raise AssertionError("request attempted database I/O")

        monkeypatch.setattr(app_module, "initialize_catalog", fail_if_called)
        monkeypatch.setattr(app_module, "load_durable_catalog", fail_if_called)

        response = client.post(
            "/v1/meal-rankings",
            json=VALID_REQUEST,
        )

    assert response.status_code == 200
    assert response.json()["returned_count"] >= 1
```

Run the focused test. Expected GREEN: startup functions can be made unusable after entry without affecting a request.

### Step 6: Remove the legacy production catalog and keep ranking units direct

Delete the temporary `CATALOG` binding and the now-unused registry import from `catalog.py`. In `tests/test_ranking.py`, replace `from pantrypilot.catalog import CATALOG` with:

```python
from pantrypilot.catalog import INITIAL_RECIPE_CATALOG, load_catalog

TEST_CATALOG = load_catalog(INITIAL_RECIPE_CATALOG, INGREDIENT_REGISTRY)
```

Replace test-only `CATALOG` arguments with `TEST_CATALOG`; do not change expected rankings. Search for stale authority:

```powershell
rg -n "\b(RAW_CATALOG|CATALOG)\b" src tests
```

Expected: no production module-level `CATALOG`; only `INITIAL_RECIPE_CATALOG`, local test catalog names, and intentional explanatory text remain.

Add `*.sqlite3` to `.gitignore`.

Run:

```powershell
uv run pytest tests/test_catalog.py tests/test_catalog_store.py tests/test_ranking.py tests/test_api.py -v
```

Expected GREEN: ranking units remain persistence-independent, application requests use durable snapshots, and local database files are untracked.

### Step 7: Refactor while green and verify Task 4

Keep the app factory concrete; do not add a settings class or dependency-injection framework. Ensure `http_request.app.state.recipe_catalog` is the only route catalog source.

Run:

```powershell
uv run pytest tests/test_api.py tests/test_catalog_store.py tests/test_ranking.py -v
uv run pytest -q
uv run ruff format --check src/pantrypilot tests
uv run ruff check src/pantrypilot tests
git diff --check
```

Expected: focused and full regressions pass; formatting, lint, and whitespace checks pass.

### Step 8: Planned commit

```powershell
git add .gitignore src/pantrypilot/app.py src/pantrypilot/catalog.py tests/test_api.py tests/test_ranking.py
git commit -m "feat: load durable catalog during app lifespan"
```

---

## Task 5: Ranking Parity and Regression Evidence

**Files:**

- Create: `tests/test_ranking_parity.py`

No production interface changes. This is a contract-test task: its tests should be GREEN against Tasks 1–4. If a test exposes a defect, preserve that failure as RED, make the smallest correction in the owning earlier module, rerun to GREEN, and include that correction explicitly in this task's commit.

### Step 1: Build direct and deliberately reordered durable catalogs

Create local helpers in `tests/test_ranking_parity.py`:

```python
import sqlite3
from pathlib import Path

import pytest

from pantrypilot.catalog import INITIAL_RECIPE_CATALOG, load_catalog
from pantrypilot.catalog_store import (
    initialize_catalog,
    load_durable_catalog,
)
from pantrypilot.ingredients import INGREDIENT_REGISTRY
from pantrypilot.models import RankingRequest, Recipe
from pantrypilot.ranking import UnresolvedExcludedIngredientsError, rank_recipes


def direct_catalog() -> tuple[Recipe, ...]:
    return load_catalog(INITIAL_RECIPE_CATALOG, INGREDIENT_REGISTRY)


def reordered_durable_catalog(database_path: Path) -> tuple[Recipe, ...]:
    initialize_catalog(database_path, INITIAL_RECIPE_CATALOG, INGREDIENT_REGISTRY)
    with sqlite3.connect(database_path) as connection:
        relationships = connection.execute(
            "SELECT recipe_id, position, ingredient_id "
            "FROM recipe_ingredients ORDER BY recipe_id, position DESC"
        ).fetchall()
        recipes = connection.execute(
            "SELECT id, name, calories, protein_g, prep_minutes "
            "FROM recipes ORDER BY id DESC"
        ).fetchall()
        connection.execute("DELETE FROM recipe_ingredients")
        connection.execute("DELETE FROM recipes")
        connection.executemany(
            "INSERT INTO recipes VALUES (?, ?, ?, ?, ?)",
            recipes,
        )
        connection.executemany(
            "INSERT INTO recipe_ingredients VALUES (?, ?, ?)",
            relationships,
        )
    return load_durable_catalog(database_path, INGREDIENT_REGISTRY)
```

`executemany` is allowed for test data mutation; the migration runner itself must continue to execute migration statements individually.

### Step 2: Compare complete responses across representative contracts

Add parameterized requests covering canonical input, aliases, unresolved pantry abstention, resolved exclusions, multiple eligible recipes, and post-sort limits:

```python
def make_request(
    *,
    pantry_items: list[str],
    min_protein_g: float = 0.0,
    max_prep_minutes: int = 45,
    excluded_ingredients: list[str] | None = None,
    limit: int = 50,
) -> RankingRequest:
    return RankingRequest(
        pantry_items=pantry_items,
        min_protein_g=min_protein_g,
        max_prep_minutes=max_prep_minutes,
        excluded_ingredients=(
            [] if excluded_ingredients is None else excluded_ingredients
        ),
        limit=limit,
    )


PARITY_REQUESTS = (
    make_request(
        pantry_items=["eggs", "spinach", "olive oil"],
        min_protein_g=25.0,
        max_prep_minutes=30,
    ),
    make_request(
        pantry_items=["egg", "black bean", "mystery item"],
    ),
    make_request(
        pantry_items=["noodles", "peanuts", "soy sauce"],
        excluded_ingredients=["peanuts"],
    ),
    make_request(
        pantry_items=["noodles", "peanuts", "soy sauce"],
        excluded_ingredients=["peanut"],
    ),
    make_request(
        pantry_items=["eggs"],
        limit=2,
    ),
)


@pytest.mark.parametrize("request", PARITY_REQUESTS)
def test_durable_catalog_preserves_complete_ranking_response(
    tmp_path: Path,
    request: RankingRequest,
) -> None:
    direct = rank_recipes(request, direct_catalog(), INGREDIENT_REGISTRY)
    durable = rank_recipes(
        request,
        reordered_durable_catalog(tmp_path / "catalog.sqlite3"),
        INGREDIENT_REGISTRY,
    )

    assert durable == direct
```

Because equality is over the complete frozen `RankingResponse`, this single assertion protects final order, recipe-ID tie breaks where present, score components/rounding/final score, explanations, matched/missing/required ingredient evidence and its order, returned count, post-sort limit, and pantry/exclusion resolution evidence.

Run:

```powershell
uv run pytest tests/test_ranking_parity.py::test_durable_catalog_preserves_complete_ranking_response -v
```

Expected GREEN. A row-order-dependent implementation will fail with response or ingredient-order differences.

### Step 3: Prove fail-closed unresolved exclusions and explicit tie-breaking

Add:

```python
def test_durable_catalog_preserves_fail_closed_unresolved_exclusion(
    tmp_path: Path,
) -> None:
    request = make_request(
        pantry_items=["egg", "spinach"],
        excluded_ingredients=["groundnut"],
    )
    catalogs = (
        direct_catalog(),
        reordered_durable_catalog(tmp_path / "catalog.sqlite3"),
    )

    errors: list[UnresolvedExcludedIngredientsError] = []
    for catalog in catalogs:
        with pytest.raises(UnresolvedExcludedIngredientsError) as error:
            rank_recipes(request, catalog, INGREDIENT_REGISTRY)
        errors.append(error.value)

    assert errors[1].ingredient_resolution == errors[0].ingredient_resolution


def test_durable_catalog_preserves_recipe_id_tie_break(tmp_path: Path) -> None:
    tied_records = (
        {
            "id": "z-recipe",
            "name": "Z Recipe",
            "required_ingredient_ids": ("eggs",),
            "calories": 100,
            "protein_g": 5.0,
            "prep_minutes": 10,
        },
        {
            "id": "a-recipe",
            "name": "A Recipe",
            "required_ingredient_ids": ("eggs",),
            "calories": 100,
            "protein_g": 5.0,
            "prep_minutes": 10,
        },
    )
    database_path = tmp_path / "catalog.sqlite3"
    initialize_catalog(database_path, reversed(tied_records), INGREDIENT_REGISTRY)
    request = make_request(pantry_items=["eggs"])

    direct = rank_recipes(
        request,
        load_catalog(tied_records, INGREDIENT_REGISTRY),
        INGREDIENT_REGISTRY,
    )
    durable = rank_recipes(
        request,
        load_durable_catalog(database_path, INGREDIENT_REGISTRY),
        INGREDIENT_REGISTRY,
    )

    assert durable == direct
    assert [result.id for result in durable.results] == [
        "a-recipe",
        "z-recipe",
    ]
```

Run both tests. Expected GREEN: unresolved exclusions abstain identically and recipe ID, never row order, resolves equal scores.

### Step 4: Run Feature 001/002 regressions and evaluation

Run:

```powershell
uv run pytest tests/test_ranking_parity.py tests/test_ranking.py tests/test_api.py -v
uv run pytest tests/test_ingredients.py tests/test_evaluation.py -v
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
```

Expected: all tests pass. Evaluation output reports canonical-alias resolver precision `1.0`, recall `1.0`, `false_positives` `0`, and `zero_false_positives` true; it never opens or initializes a database.

### Step 5: Refactor while green and verify Task 5

Keep parity helpers local to this test module. Do not add production utilities for test data or change ranking code.

```powershell
uv run ruff format --check tests/test_ranking_parity.py
uv run ruff check tests/test_ranking_parity.py
git diff --check
```

Expected: format, lint, and whitespace checks pass.

### Step 6: Planned commit

```powershell
git add tests/test_ranking_parity.py
git commit -m "test: prove durable ranking parity"
```

---

## Task 6: Documentation, Learning Guide, and Whole-Branch Verification

**Files:**

- Modify: `README.md`
- Modify: `docs/product/vision.md`
- Create: `docs/learning/003-durable-recipe-catalog.md`

No production interface changes.

### Step 1: Update README product and operating instructions

Change the current-status section to Feature 003 and document this concrete path:

````markdown
## Durable recipe catalog

PantryPilot stores recipes in a local SQLite file. On startup it migrates a
fresh store, seeds the approved four recipes only when both catalog tables are
empty, reloads the complete catalog as validated immutable `Recipe` objects,
and serves ranking requests from that in-memory snapshot. Ranking requests do
not query SQLite, and startup never falls back to Python seed data after a
storage failure.

The default file is `pantrypilot.sqlite3` in the process working directory.
Override it on PowerShell with:

```powershell
$env:PANTRYPILOT_DB_PATH = "C:\path\to\catalog.sqlite3"
uv run uvicorn pantrypilot.app:app --reload
```

Stop the application before moving or deleting the local database. Deleting a
development database is an explicit reset: the next successful startup creates
and seeds a fresh store. Never commit the database file.
````

Also retain existing setup, API, Feature 001/002 learning links, and evaluation commands; add links to the approved Feature 003 design and learning document.

### Step 2: Correct the product vision's current boundary

Replace the stale Feature 001 paragraph with a precise Feature 003 boundary:

```markdown
## Current boundary

Feature 003 keeps the approved recipe catalog in a local durable SQLite store.
Application startup migrates and initializes that store, validates the complete
catalog into immutable domain objects, and ranks an in-memory snapshot through
the existing deterministic Feature 002 ingredient-resolution and ranking
pipeline. The ingredient registry remains code-owned, and pantry state,
ranking/request history, analytics, users, CRUD, quantities, retrieval, and
optimization are not persisted or implemented yet.
```

Do not rewrite the product direction or roadmap.

### Step 3: Create the focused Feature 003 learning guide

Create `docs/learning/003-durable-recipe-catalog.md` with these exact sections and teaching boundaries:

1. **What changed and what did not** — process-memory catalog versus durable SQLite source; ranking formula and registry unchanged.
2. **Stable identifiers are contracts** — recipe IDs, canonical ingredient IDs, PK/FK relationships, and why display names are not keys.
3. **The two-table model** — show `recipes` and `recipe_ingredients`; explain PK, FK, `UNIQUE`, `CHECK`, `ON DELETE CASCADE`, and explicit `position` with the spinach-omelet's eggs/spinach/olive-oil rows.
4. **SQLite affinity is not static typing** — demonstrate `typeof`, post-affinity checks, numeric text coercion, and positive infinity reaching domain validation; state why SQL does not duplicate `Recipe`.
5. **Versioning and atomic migrations** — explain `user_version`, ordered migration 1, `BEGIN IMMEDIATE`, individual DDL, version update in the same transaction, rollback, and why `executescript` is excluded.
6. **Migration, seeding, loading, and runtime mutation** — define each separately; explain the both-empty sentinel and why a non-empty catalog is never reconciled from seed.
7. **Connections and transactions** — show short connection ownership, `isolation_level=None` to disable Python's implicit transaction starts, explicit `BEGIN IMMEDIATE` ownership in migration/seeding, `foreign_keys = ON` per connection, initialization close/reopen, commit versus rollback, and no request-time DB I/O.
8. **Hydration and defense in depth** — map storage checks to Pydantic/registry checks; show complete-catalog failure rather than row skipping.
9. **FastAPI lifespan and snapshot flow** — include `construct app -> enter lifespan -> migrate -> seed if empty -> close -> reopen -> validate tuple -> app.state -> request -> rank_recipes`.
10. **Row order is not ranking order** — distinguish relationship `position`, hydration query order, and score/ID ranking order.
11. **Testing layers** — contrast domain/unit, real persistence, real migration rollback, integration/lifespan, reconnection, parity, regressions, and registry evaluation.
12. **Why `sqlite3` is sufficient now** — zero dependency, one process/local file, explicit learning value; state that multiple writers, a server database, a large migration graph, or complex cross-database deployment could justify an ORM/Alembic later.
13. **Explicit deferrals** — pantry/history persistence, CRUD, retrieval/indexing, quantities/units, optimization, auth/users, analytics, external ingestion, ML/LLMs, frontend, and microservices.

Include these runnable inspection commands:

```powershell
uv run python -c "import sqlite3; c=sqlite3.connect('pantrypilot.sqlite3'); print(c.execute('PRAGMA user_version').fetchone()[0]); print(c.execute('SELECT id, name FROM recipes ORDER BY id').fetchall()); c.close()"
uv run pytest tests/test_catalog_store.py -v
uv run pytest tests/test_ranking_parity.py -v
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
```

Include three exercises with answers immediately below each:

- Predict which rows remain after the injected migration failure and explain why `user_version` remains zero.
- Predict whether reversed insertion order changes ingredient evidence or ranking result order and name the two explicit ordering rules.
- Classify five changes—new schema column, first-run initial rows, an admin edit, a Pydantic validation failure, and an alias addition—as migration, seed, runtime mutation, hydration failure, or code-owned registry change.

End with at least these guided mock-interview questions and concise answer keys:

1. Why is the SQLite file the source of truth if requests use an in-memory tuple?
2. Why is seeding not a migration?
3. How does migration 1 keep DDL and `user_version` atomic?
4. What does `PRAGMA foreign_keys = ON` guarantee, and why is it set for every connection?
5. Which invariants belong to SQLite and which remain in `Recipe` hydration?
6. Why can positive infinity pass the approved SQL check but still be rejected safely?
7. Why are two queries used instead of an inner join during hydration?
8. How is recipe ingredient order preserved independently of row order?
9. How do parity tests prove ranking meaning did not change?
10. When would an ORM and Alembic earn their added complexity?

Keep the guide tied to the implemented Feature 003 code; do not expand it into a general SQL textbook.

### Step 4: Verify documentation and scope before commit

Run:

```powershell
rg -n "Feature 001|in-memory recipe catalog|RAW_CATALOG|\bCATALOG\b" README.md docs/product/vision.md docs/learning/003-durable-recipe-catalog.md src tests
rg -n "SQLAlchemy|SQLModel|Alembic|aiosqlite|Repository" src tests pyproject.toml
git diff -- README.md docs/product/vision.md docs/learning/003-durable-recipe-catalog.md
git diff --check
```

Expected: stale current-boundary claims and production catalog bindings are absent; advanced persistence terms appear only in explicit trade-off/deferral teaching; no unrelated documentation changed.

### Step 5: Planned documentation commit

```powershell
git add README.md docs/product/vision.md docs/learning/003-durable-recipe-catalog.md
git commit -m "docs: explain durable recipe catalog"
```

### Step 6: Fresh whole-branch verification

Run from a clean process after all planned commits; do not reuse earlier results:

```powershell
uv lock --check
uv run pytest tests/test_catalog_store.py tests/test_ranking_parity.py tests/test_api.py -v
uv run pytest
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
uv run ruff format --check .
uv run ruff check .
git diff --check
git status --short --branch
```

Expected:

- Lock check succeeds without changing `uv.lock`.
- Focused persistence/migration/parity/API tests pass against isolated file-backed stores.
- Entire Feature 001/002/003 suite passes.
- Evaluation reports resolver precision `1.0`, recall `1.0`, and zero false positives without creating a catalog database.
- Ruff format and lint checks pass.
- No whitespace errors, SQLite files, secrets, caches, or unrelated changes appear.
- Branch status contains only intentional commits and no untracked implementation artifacts.

### Step 7: Final review and publication gate

Review the branch against the acceptance map below for correctness, scope, security, test quality, and explainability. If review finds a defect, add a focused reproducing test before the fix and repeat all fresh verification.

The eventual pull-request description must contain:

```text
Closes #5
```

Do not push or create the pull request without separate owner authorization.

---

## Planned Commit Boundaries

1. `docs: design durable recipe catalog` — approved design only.
2. `docs: plan durable recipe catalog` — this implementation plan only.
3. `feat: add atomic catalog schema migrations` — connection, exact schema, real atomic migration evidence.
4. `feat: hydrate durable recipe catalog` — complete ordered hydration and deterministic integrity failures.
5. `feat: initialize durable recipe catalog` — approved seed/reference rename, seed-only initialization, atomic persistence/reconnection tests.
6. `feat: load durable catalog during app lifespan` — FastAPI/app-state source-of-truth switch, API/regression migration, DB ignore rule.
7. `test: prove durable ranking parity` — reordered durable catalog contract evidence only.
8. `docs: explain durable recipe catalog` — README, product boundary, learning guide, exercises, and interview questions.

Each boundary is independently reviewable and must be green before the next begins.

## Acceptance and Evidence Map

| Approved requirement | Planned evidence |
|---|---|
| SQLite is the durable recipe authority; seed is not fallback | Tasks 3–4 non-empty/no-reconciliation, restart, unavailable/incomplete-startup tests; final search removes `CATALOG`. |
| Registry remains code-owned | Task 2 unknown-ID hydration failure; no registry schema/table. |
| Exact two-table schema and ordered relationships | Task 1 PRAGMA/schema/constraint assertions, including `recipes.id` `NOT NULL` plus real null/blank rejection; Tasks 2 and 5 reverse insertion while preserving `position`. |
| Explicit transaction ownership | Task 1 connection test requires `isolation_level is None`; migration and seed code retain explicit `BEGIN IMMEDIATE` with direct commit/rollback and no `executescript`. |
| Real atomic migrations and version update | Task 1 real file-backed later-DDL failure proves early DDL rollback and `user_version == 0`; rerun/no-op and newer-version tests. |
| SQLite typing claims remain precise | Task 1 real constraint failures; Task 2 positive-infinity domain failure; learning guide affinity section. |
| Migration and seed are separate | Separate `migrate_catalog` and `seed_catalog` interfaces/transactions; Task 3 teaching/tests. |
| Fresh empty seed, idempotence, valid non-empty authority, partial failure | Task 3 empty/reopen, second init, custom durable catalog, partial-shape, validation-before-insert, and rollback tests. |
| Complete validated immutable hydration | Task 2 frozen Recipe equality, zero-relationship, unknown ID, one-invalid-fails-all, wrong-schema, and FK tests. |
| FastAPI non-deprecated lifespan and snapshot | Task 4 factory/context-manager tests, state tuple, import safety, no request DB I/O. |
| Startup failure has context and no fallback | `CatalogStoreError` path/version messages; Task 4 unavailable/incomplete startup failures. |
| Ranking semantics unchanged | Task 5 complete `RankingResponse` equality plus fail-closed and explicit tie tests; unchanged ranking source. |
| Existing API/error behavior unchanged | Task 4 retains all current API assertions including generic safe 500. |
| Restart durability | Tasks 3–4 close/reopen catalog equality and persisted-name restart behavior. |
| Isolated real stores and real migration mechanism | All persistence/API/parity tests use `tmp_path`; no mocks for SQLite schema, transactions, or constraints. |
| Evaluation remains database-independent | Tasks 5–6 run the existing registry evaluation and assert 1.0/1.0/zero false positives. |
| README, product boundary, learning portfolio | Task 6 exact documents, commands, examples, exercises, trade-offs, and interview questions. |
| Explicit non-goals remain deferred | Global constraints, minimal file map, dependency checks, and learning guide deferrals. |

## Plan Self-Review

- **Spec coverage:** Every significant approved-design and Issue #5 acceptance condition maps to a concrete task and runnable evidence above.
- **Placeholder scan:** No unresolved marker or unspecified test/implementation step remains.
- **Schema/test consistency:** Schema version 1 declares `recipes.id` as `TEXT PRIMARY KEY NOT NULL`; PRAGMA evidence expects `notnull == 1`, and real inserts prove null, empty, and whitespace-only identities fail.
- **Transaction consistency:** Every application-owned catalog connection uses `isolation_level=None`; only migration and seed explicitly begin transactions, and their existing commit/rollback evidence remains unchanged.
- **Type consistency:** Database paths are always `Path`; the immutable catalog is always `tuple[Recipe, ...]`; seed inputs are always `Iterable[Mapping[str, object]]`; the single store exception is always `CatalogStoreError`; app construction is always `create_app(database_path: Path)`.
- **TDD order:** Every behavior-producing task begins with a focused failing test, names the intended failure, adds minimum implementation, reruns for green, exercises neighbors, refactors only while green, verifies, then commits. The parity/documentation tasks add contract evidence or prose and do not invent production behavior.
- **Architecture consistency:** One concrete stdlib module owns persistence; `load_catalog` owns domain hydration; FastAPI owns lifespan/state; ranking stays pure. No new dependency or speculative abstraction appears.
- **Failure coverage:** Connection, foreign-key enablement, old/new/missing/partial schema, mid-migration failure, invalid seed, mid-seed failure, duplicate keys/relationships, unknown ingredients, SQLite-rejected types, SQLite-permitted domain-invalid values, zero relationships, invalid sibling, unavailable storage, and safe API failures are explicit.
- **Ordering review:** Ingredient order is always `position`; hydration uses explicit SQL ordering; ranking order remains existing score/ID logic; parity data is deliberately inserted in the opposite physical order.
- **Authority review:** The final tree has no production `RAW_CATALOG`/`CATALOG`, no non-empty reconciliation, no seed fallback, and no request-time database access.
- **Scope review:** Pantry/history/auth/CRUD/retrieval/quantities/optimization/ML/frontend/microservices and advanced persistence tooling remain deferred. No production, test, migration, dependency, or commit action occurs merely by creating this plan.

No design contradiction was found during planning.
