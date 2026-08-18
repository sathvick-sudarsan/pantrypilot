# Durable Saved Pantry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one durable application-local saved pantry that can be atomically replaced, inspected, and used by a separate meal-ranking endpoint without changing inline ranking semantics.

**Architecture:** Advance the existing SQLite database from schema version 1 to 2 through a narrowly shared `database.py`, while leaving recipe seeding and hydration in `catalog_store.py` and putting singleton pantry reads/writes in `pantry_store.py`. Resolve writes before storage, persist only canonical ingredient IDs, read the pantry on every saved-pantry request, and adapt validated saved IDs into the unchanged `RankingRequest`/`rank_recipes` path.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, standard-library `sqlite3`, pytest, Ruff, uv.

**Spec:** `docs/superpowers/specs/2026-08-16-durable-saved-pantry-design.md`

## Global Constraints

- The approved design is authoritative. Stop and return to architecture review if implementation exposes a contradiction; do not redesign while executing this plan.
- Work only on `feat/durable-saved-pantry` from approved design commit `3ae0a124e3cb7252472d020f000a0d448031c060`.
- Use strict RED → GREEN → refactor TDD and commit only coherent, independently testable increments.
- Keep `POST /v1/meal-rankings`, `RankingRequest`, `rank_recipes`, the ranking formula, hard constraints, soft protein target, explanations, sort, limit, and `returned_count` semantics unchanged.
- Use only standard-library `sqlite3`; do not add Alembic, SQLAlchemy, an async database library, a pool, a retry framework, or WAL as a requirement.
- `database.py` owns only connection setup, `CURRENT_SCHEMA_VERSION`, ordered SQL migrations, and the atomic migration runner. Do not add repositories, protocols, engines/sessions, services, generic transaction callbacks, units of work, or dependency-injection infrastructure.
- `catalog_store.py` remains responsible for recipe seeding, recipe integrity/aggregation, and `Recipe` hydration.
- Persist only the singleton marker and the current deduplicated canonical ingredient IDs. Never persist raw strings, aliases, unresolved input, names, timestamps, owners, quantities, positions, versions/history, failed bodies, rankings, or analytics.
- A missing marker means no pantry has been established; a marker with zero item rows means an intentionally saved empty pantry.
- Resolve and validate every write occurrence before opening a database connection. Any unresolved occurrence returns deterministic 422 evidence, makes no store call, and preserves the previous pantry.
- Use short-lived connections and explicit transactions. `BEGIN IMMEDIATE` serializes replacements; reads observe complete committed snapshots; **last successful commit wins**.
- Use SQLite's existing standard timeout behavior in production. Do not add retries, ETags, revisions, compare-and-swap, an application mutex, distributed locking, or a multi-process guarantee.
- Map only known saved-pantry storage/integrity failures to the approved 503 body. Do not catch `Exception` or hide programming defects.
- Keep public saved-pantry ordering ascending by canonical ingredient ID; derive canonical names from `INGREDIENT_REGISTRY` after the complete durable state validates.
- Do not add users, authentication, ownership, multiple pantries, item CRUD, quantities/units, history, retrieval, caching, grocery/waste optimization, or unrelated cleanup.
- Keep existing inline `pantry_items` and `excluded_ingredients` bounds unchanged. Apply the new 0–100 item and 100-character bounds only to saved-pantry replacement.
- Use PowerShell-compatible commands as written; do not use POSIX line continuations.

---

## Final File and Responsibility Map

| File | Action | Single responsibility after Feature 004 |
|---|---|---|
| `src/pantrypilot/database.py` | Create | Concrete SQLite connection setup, schema version 2, ordered migrations 1 and 2, and atomic migration execution. |
| `src/pantrypilot/catalog_store.py` | Modify | Recipe-specific compatibility wrappers plus recipe seed, integrity, aggregation, and hydration. |
| `src/pantrypilot/pantry_store.py` | Create | Atomic singleton pantry replacement and completely validated durable pantry reads. |
| `src/pantrypilot/models.py` | Modify | Saved-pantry write/read models and saved-ranking constraints, while leaving `RankingRequest` unchanged. |
| `src/pantrypilot/app.py` | Modify | Saved-pantry routes, narrow pantry-store error mapping, and convergence of inline/saved ranking on one unchanged domain call. |
| `tests/test_database.py` | Create | Shared connection and migration behavior, including real v1 preservation and rollback evidence. |
| `tests/test_catalog_store.py` | Modify | Recipe-store regression expectations after the mechanical database extraction. |
| `tests/test_pantry_store.py` | Create | Pantry absence/empty/persistence/integrity/atomicity/locking behavior against real SQLite. |
| `tests/test_models.py` | Create | Exact saved-pantry request bounds and saved-ranking request shape. |
| `tests/test_api.py` | Modify | PUT/GET contracts, resolution evidence, storage failures, restart durability, and inline compatibility. |
| `tests/test_saved_pantry_ranking_parity.py` | Create | Complete inline-versus-saved `RankingResponse` equality across canonicalization and ranking edge cases. |
| `README.md` | Modify | Current public API and durable/transient product boundary. |
| `docs/product/vision.md` | Modify | Feature 004 current capability and explicit deferred seams. |
| `docs/learning/004-durable-saved-pantry.md` | Create | Teaching narrative, commands, exercises, failure examples, and guided interview questions. |

No change belongs in `src/pantrypilot/ranking.py`: persistence must not enter the pure ranking domain.

## Interfaces Fixed for All Tasks

```text
src/pantrypilot/database.py
  CURRENT_SCHEMA_VERSION = 2
  SCHEMA_MIGRATIONS: ordered tuple of (integer version, tuple of SQL strings)
  DatabaseError: RuntimeError subclass
  connect_database(database_path: Path) -> sqlite3.Connection
  migrate_database(connection: sqlite3.Connection, database_path: Path) -> None

src/pantrypilot/pantry_store.py
  PantryStoreError: RuntimeError subclass
  replace_saved_pantry(
      database_path: Path,
      ingredient_ids: Iterable[str],
      ingredient_registry: IngredientRegistry,
  ) -> tuple[str, ...]
  load_saved_pantry(
      database_path: Path,
      ingredient_registry: IngredientRegistry,
  ) -> tuple[str, ...] | None
```

`replace_saved_pantry` returns the sorted, deduplicated, registry-validated canonical IDs only after commit. `load_saved_pantry` returns `None` only for an absent marker, `()` for an established empty pantry, and a sorted tuple for a non-empty valid pantry. Every invalid/corrupt/unavailable storage case raises `PantryStoreError` without returning partial state.

```python
# src/pantrypilot/models.py
class SavedPantryWriteRequest(BaseModel):
    pantry_items: Annotated[
        list[Annotated[str, Field(max_length=100)]],
        Field(max_length=100),
    ]


class SavedPantryItem(BaseModel):
    ingredient_id: str
    canonical_name: str


class SavedPantryResponse(BaseModel):
    pantry_items: tuple[SavedPantryItem, ...]


class SavedPantryRankingRequest(BaseModel):
    min_protein_g: Annotated[FiniteFloat, Field(ge=0, strict=True)]
    max_prep_minutes: Annotated[StrictInt, Field(ge=0)]
    excluded_ingredients: list[str]
    limit: Annotated[StrictInt, Field(ge=1, le=50)]
```

All four new models use `ConfigDict(extra="forbid")`; the three response models are frozen. `SavedPantryWriteRequest` rejects strings blank after trimming. `SavedPantryRankingRequest` rejects blank exclusions. Do not introduce a shared ranking-request base class: duplicating four stable constraint declarations is smaller and avoids changing the existing request contract.

The schema is exactly:

```sql
CREATE TABLE saved_pantry (
    id INTEGER PRIMARY KEY NOT NULL
        CHECK (id = 1)
)

CREATE TABLE saved_pantry_items (
    pantry_id INTEGER NOT NULL
        CHECK (typeof(pantry_id) = 'integer' AND pantry_id = 1)
        REFERENCES saved_pantry(id) ON DELETE CASCADE,
    ingredient_id TEXT NOT NULL
        CHECK (length(trim(ingredient_id)) > 0),
    PRIMARY KEY (pantry_id, ingredient_id)
)
```

Migration 2 creates these tables and does not insert a marker or item. Migration 1's recipe DDL remains byte-for-byte equivalent to the current schema.

---

### Task 1: Extract the Shared SQLite Authority and Migrate Schema v1 → v2

**Files:**
- Create: `src/pantrypilot/database.py`
- Create: `tests/test_database.py`
- Modify: `src/pantrypilot/catalog_store.py:1-103,169-205`
- Modify: `tests/test_catalog_store.py:1-20,283-503`
- Modify: `tests/test_api.py:133-143`

**Interfaces:**
- Consumes: current recipe schema SQL and the explicit migration algorithm in `catalog_store.py`.
- Produces: `DatabaseError`, `CURRENT_SCHEMA_VERSION = 2`, `SCHEMA_MIGRATIONS`, `connect_database(Path)`, and `migrate_database(connection, Path)` exactly as declared above.
- Preserves: `CatalogStoreError`, `connect_catalog`, and `migrate_catalog` as thin recipe-store compatibility adapters; all recipe seed/load public signatures remain unchanged.

- [ ] **Step 1: Move migration behavior tests to the shared authority and write the new v2 RED tests**

Create `tests/test_database.py` with imports and helpers that operate only on real SQLite files:

```python
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import pantrypilot.database as database_module
from pantrypilot.database import (
    CURRENT_SCHEMA_VERSION,
    DatabaseError,
    SCHEMA_MIGRATIONS,
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
```

Keep the existing recipe-column/index/constraint assertions when moving the old version-1 schema test; update its final expected table set and schema version to include version 2 rather than deleting that evidence.

- [ ] **Step 2: Run the shared migration tests to prove RED**

Run:

```powershell
uv run pytest tests/test_database.py -v
```

Expected RED: collection fails because `pantrypilot.database` does not exist.

- [ ] **Step 3: Implement the narrow database module and mechanical catalog adapters**

Create `database.py` by moving the two existing recipe `CREATE TABLE` statements without semantic edits, then append the two approved saved-pantry statements as migration 2:

```python
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
```

Do not use `executescript`. Keep one explicit transaction per ordered migration so a migration-2 failure restores the complete version-1 database.

In `catalog_store.py`, import the shared constants/functions. Retain `connect_catalog` and `migrate_catalog` only as behavior-preserving adapters so existing recipe callers do not churn:

```python
from pantrypilot.database import (
    CURRENT_SCHEMA_VERSION,
    DatabaseError,
    connect_database,
    migrate_database,
)


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
```

Delete the duplicated schema constants and migration loop from `catalog_store.py`; do not otherwise restructure `seed_catalog`, `initialize_catalog`, or `load_durable_catalog`.

- [ ] **Step 4: Add the two rollback tests against the real second migration**

Append these tests to `tests/test_database.py`:

```python
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
```

The first test creates a genuine v1 recipe database plus a conflicting second table, proving the first migration-2 DDL rolls back. The second forces SQLite's deferred foreign-key check to fail during commit after `PRAGMA user_version = 2`, proving DDL, data, and version all restore to v1.

- [ ] **Step 5: Update recipe-store regression expectations without weakening them**

In `tests/test_catalog_store.py`:

- import shared migration primitives from `pantrypilot.database` only where a recipe-specific test needs them;
- remove the migration-runner tests now owned by `tests/test_database.py`;
- keep all recipe constraints, seed rollback, hydration, row ordering, quick-check, FK, and error-wrapping tests;
- change current version expectations from 1 to 2;
- change wrong load versions to `0`, `1`, and `3`;
- assert a normal initialization creates all four tables but still seeds only recipe tables.

In `tests/test_api.py::test_incomplete_current_schema_prevents_startup_without_seed_fallback`, set `PRAGMA user_version = 2` so it remains a current-version incomplete-schema test.

- [ ] **Step 6: Run Task 1 GREEN verification and refactor check**

Run:

```powershell
uv run pytest tests/test_database.py tests/test_catalog_store.py tests/test_api.py::test_lifespan_initializes_and_publishes_frozen_catalog tests/test_api.py::test_incomplete_current_schema_prevents_startup_without_seed_fallback -v
uv run ruff format --check src/pantrypilot/database.py src/pantrypilot/catalog_store.py tests/test_database.py tests/test_catalog_store.py tests/test_api.py
uv run ruff check src/pantrypilot/database.py src/pantrypilot/catalog_store.py tests/test_database.py tests/test_catalog_store.py tests/test_api.py
```

Expected GREEN: all selected tests and checks pass. Confirm the diff is a mechanical move plus migration 2; if shared database code contains recipe hydration, a repository abstraction, or a generic transaction helper, remove it.

- [ ] **Step 7: Commit the independently reviewable migration increment**

```powershell
git add src/pantrypilot/database.py src/pantrypilot/catalog_store.py tests/test_database.py tests/test_catalog_store.py tests/test_api.py
git diff --cached --check
git commit -m "feat: add shared schema version two migration"
```

---

### Task 2: Persist and Completely Validate the Singleton Pantry

**Files:**
- Create: `src/pantrypilot/pantry_store.py`
- Create: `tests/test_pantry_store.py`

**Interfaces:**
- Consumes: `connect_database`, `CURRENT_SCHEMA_VERSION`, `DatabaseError`, and `IngredientRegistry`.
- Produces: `PantryStoreError`, `replace_saved_pantry(...) -> tuple[str, ...]`, and `load_saved_pantry(...) -> tuple[str, ...] | None` exactly as fixed above.
- Guarantees: no connection opens until replacement IDs are deduplicated, sorted, nonblank, and present in `ingredient_registry.by_id`; a read returns only after marker, FK, row shape, and every ID validate.

- [ ] **Step 1: Write RED tests for absent, empty, non-empty, persistence, order, and pre-connect validation**

Create `tests/test_pantry_store.py`:

```python
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

import pantrypilot.pantry_store as pantry_store_module
from pantrypilot.catalog import INITIAL_RECIPE_CATALOG
from pantrypilot.catalog_store import initialize_catalog
from pantrypilot.ingredients import INGREDIENT_REGISTRY
from pantrypilot.pantry_store import (
    PantryStoreError,
    load_saved_pantry,
    replace_saved_pantry,
)


def initialized_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "pantrypilot.sqlite3"
    initialize_catalog(database_path, INITIAL_RECIPE_CATALOG, INGREDIENT_REGISTRY)
    return database_path


def test_load_distinguishes_absent_from_deliberately_empty(tmp_path: Path) -> None:
    database_path = initialized_database(tmp_path)

    assert load_saved_pantry(database_path, INGREDIENT_REGISTRY) is None

    assert replace_saved_pantry(database_path, [], INGREDIENT_REGISTRY) == ()
    assert load_saved_pantry(database_path, INGREDIENT_REGISTRY) == ()


def test_replace_deduplicates_sorts_and_persists_across_reopen(tmp_path: Path) -> None:
    database_path = initialized_database(tmp_path)

    saved = replace_saved_pantry(
        database_path,
        ["spinach", "eggs", "spinach"],
        INGREDIENT_REGISTRY,
    )

    assert saved == ("eggs", "spinach")
    assert load_saved_pantry(database_path, INGREDIENT_REGISTRY) == (
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
    def fail_if_connected(_database_path: Path) -> sqlite3.Connection:
        raise AssertionError("invalid IDs must fail before database I/O")

    monkeypatch.setattr(pantry_store_module, "connect_database", fail_if_connected)

    with pytest.raises(PantryStoreError, match="unknown canonical ingredient id"):
        replace_saved_pantry(
            tmp_path / "must-not-exist.sqlite3",
            ["eggs", "not-registered"],
            INGREDIENT_REGISTRY,
        )

    assert not (tmp_path / "must-not-exist.sqlite3").exists()


def test_read_orders_by_canonical_id_not_insertion_order(tmp_path: Path) -> None:
    database_path = initialized_database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("INSERT INTO saved_pantry (id) VALUES (1)")
        connection.executemany(
            "INSERT INTO saved_pantry_items VALUES (1, ?)",
            [("spinach",), ("eggs",), ("black-beans",)],
        )

    assert load_saved_pantry(database_path, INGREDIENT_REGISTRY) == (
        "black-beans",
        "eggs",
        "spinach",
    )
```

- [ ] **Step 2: Run normal-store tests to prove RED**

Run:

```powershell
uv run pytest tests/test_pantry_store.py -v
```

Expected RED: collection fails because `pantrypilot.pantry_store` does not exist.

- [ ] **Step 3: Implement minimal canonical replacement and consistent read transactions**

Create `pantry_store.py` with these exact transaction boundaries:

```python
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
                f"saved pantry contains unknown canonical ingredient id: {ingredient_id}"
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
            _require_current_schema(connection)
            try:
                connection.execute("BEGIN")
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
```

This module contains no ingredient resolution and no response models. Its input is canonical identity, and its output is canonical identity. The explicit read transaction spans integrity checks, marker detection, item query, and complete validation.

- [ ] **Step 4: Add real constraint and complete-hydration corruption tests**

Append to `tests/test_pantry_store.py`:

```python
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
    database_path = initialized_database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute("INSERT OR IGNORE INTO saved_pantry (id) VALUES (1)")
        connection.execute(
            "INSERT OR IGNORE INTO saved_pantry_items VALUES (1, 'eggs')"
        )
        connection.execute(corruption_sql)

    with pytest.raises(PantryStoreError):
        load_saved_pantry(database_path, INGREDIENT_REGISTRY)


def test_orphaned_item_fails_the_complete_read(tmp_path: Path) -> None:
    database_path = initialized_database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("INSERT INTO saved_pantry_items VALUES (1, 'eggs')")

    with pytest.raises(PantryStoreError, match="foreign key integrity"):
        load_saved_pantry(database_path, INGREDIENT_REGISTRY)


def test_missing_runtime_schema_fails_deterministically(tmp_path: Path) -> None:
    database_path = tmp_path / "wrong-schema.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA user_version = 1")

    with pytest.raises(PantryStoreError, match="schema version"):
        load_saved_pantry(database_path, INGREDIENT_REGISTRY)
```

The corruption tests deliberately bypass SQLite checks only to prove hydration rejects damage that can arrive outside supported application writes. Production code must never enable `ignore_check_constraints` or disable foreign keys.

- [ ] **Step 5: Run Task 2 GREEN verification and simplify**

Run:

```powershell
uv run pytest tests/test_pantry_store.py -v
uv run ruff format --check src/pantrypilot/pantry_store.py tests/test_pantry_store.py
uv run ruff check src/pantrypilot/pantry_store.py tests/test_pantry_store.py
```

Expected GREEN: all normal-state, constraint, and corruption tests pass. Refactor only repeated test setup; do not create a store protocol, repository base class, transaction callback, or cache.

- [ ] **Step 6: Commit normal pantry persistence**

```powershell
git add src/pantrypilot/pantry_store.py tests/test_pantry_store.py
git diff --cached --check
git commit -m "feat: persist canonical saved pantry state"
```

---

### Task 3: Prove Replacement Atomicity and SQLite Lock Recovery

**Files:**
- Modify: `tests/test_pantry_store.py`
- Modify only if RED exposes a defect: `src/pantrypilot/pantry_store.py`

**Interfaces:**
- Consumes: Task 2's `replace_saved_pantry` and `load_saved_pantry` functions.
- Produces: executable evidence that a statement failure, commit/transaction failure, or write lock never exposes partial replacement and that a later write is visible after lock release.
- Concurrency contract: `BEGIN IMMEDIATE` serializes writers; **last successful commit wins**. No arrival-order promise, retry, mutex, revision, or multi-process guarantee is added.

- [ ] **Step 1: Write RED tests for statement failure and prior-state preservation**

Append to `tests/test_pantry_store.py`:

```python
def test_failed_replacement_rolls_back_marker_and_items(
    tmp_path: Path,
) -> None:
    database_path = initialized_database(tmp_path)
    replace_saved_pantry(database_path, ["eggs"], INGREDIENT_REGISTRY)
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

    with pytest.raises(PantryStoreError) as exc_info:
        replace_saved_pantry(
            database_path,
            ["black-beans", "spinach"],
            INGREDIENT_REGISTRY,
        )

    assert isinstance(exc_info.value.__cause__, sqlite3.IntegrityError)
    assert load_saved_pantry(database_path, INGREDIENT_REGISTRY) == ("eggs",)
```

This forces failure after the old marker has been deleted and after at least one new item can be inserted; observing `("eggs",)` proves the entire transaction rolled back.

- [ ] **Step 2: Write the deterministic real-SQLite lock test without sleeps**

Add this test-only connection factory and lock test:

```python
def immediate_timeout_connection(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, isolation_level=None, timeout=0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def test_real_write_lock_preserves_state_and_later_replacement_is_visible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = initialized_database(tmp_path)
    replace_saved_pantry(database_path, ["eggs"], INGREDIENT_REGISTRY)
    blocker = sqlite3.connect(database_path, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    monkeypatch.setattr(
        pantry_store_module,
        "connect_database",
        immediate_timeout_connection,
    )

    try:
        with pytest.raises(PantryStoreError) as exc_info:
            replace_saved_pantry(database_path, ["spinach"], INGREDIENT_REGISTRY)
        assert isinstance(exc_info.value.__cause__, sqlite3.OperationalError)
        assert "database is locked" in str(exc_info.value.__cause__)
    finally:
        blocker.rollback()
        blocker.close()

    assert load_saved_pantry(database_path, INGREDIENT_REGISTRY) == ("eggs",)
    assert replace_saved_pantry(
        database_path,
        ["black-beans", "spinach"],
        INGREDIENT_REGISTRY,
    ) == ("black-beans", "spinach")
    assert load_saved_pantry(database_path, INGREDIENT_REGISTRY) == (
        "black-beans",
        "spinach",
    )
```

The monkeypatch changes only the test connection timeout to zero, making the real SQLite lock fail immediately and deterministically. Production `connect_database` retains sqlite3's standard timeout behavior. Do not add sleeps or timing assertions.

- [ ] **Step 3: Run the atomicity/lock tests and verify meaningful RED**

Run:

```powershell
uv run pytest tests/test_pantry_store.py::test_failed_replacement_rolls_back_marker_and_items tests/test_pantry_store.py::test_real_write_lock_preserves_state_and_later_replacement_is_visible -v
```

Expected RED if Task 2 missed a boundary: prior `("eggs",)` is lost, a raw sqlite exception escapes, or a locked connection remains in a transaction. If both tests are already GREEN, retain them as the required evidence and do not change production code merely to manufacture a GREEN step.

- [ ] **Step 4: Make the smallest transaction correction only if the RED test requires it**

The required structure is already explicit; correct only a violated line:

```python
try:
    connection.execute("BEGIN IMMEDIATE")
    connection.execute("DELETE FROM saved_pantry WHERE id = 1")
    connection.execute("INSERT INTO saved_pantry (id) VALUES (1)")
    connection.executemany(
        "INSERT INTO saved_pantry_items (pantry_id, ingredient_id) VALUES (1, ?)",
        ((ingredient_id,) for ingredient_id in canonical_ids),
    )
    connection.commit()
except sqlite3.Error:
    connection.rollback()
    raise
```

Do not retry a lock, configure a production timeout, enable WAL, or add an application lock.

- [ ] **Step 5: Run complete pantry-store GREEN verification**

Run:

```powershell
uv run pytest tests/test_pantry_store.py -v
uv run ruff format --check src/pantrypilot/pantry_store.py tests/test_pantry_store.py
uv run ruff check src/pantrypilot/pantry_store.py tests/test_pantry_store.py
```

Expected GREEN: every pantry-store test passes, including the later replacement after releasing the real lock.

- [ ] **Step 6: Commit the independently reviewable transaction evidence**

```powershell
git add src/pantrypilot/pantry_store.py tests/test_pantry_store.py
git diff --cached --check
git commit -m "test: prove saved pantry transaction safety"
```

---

### Task 4: Add the Saved-Pantry Write/Read HTTP Contract

**Files:**
- Create: `tests/test_models.py`
- Modify: `src/pantrypilot/models.py:1-31`
- Modify: `src/pantrypilot/app.py:1-86`
- Modify: `tests/test_api.py:1-30,145-165,600-end`

**Interfaces:**
- Consumes: Task 2's pantry store, `resolve_ingredients`, and `INGREDIENT_REGISTRY`.
- Produces: `SavedPantryWriteRequest`, `SavedPantryItem`, `SavedPantryResponse`, `PUT /v1/saved-pantry`, and `GET /v1/saved-pantry`.
- Public failures: exact unresolved 422, absent 404, and known-store 503 bodies from the design; an unrelated `RuntimeError` must still use FastAPI's generic 500 path.

- [ ] **Step 1: Write exact model-bound RED tests**

Create `tests/test_models.py`:

```python
import pytest
from pydantic import ValidationError

from pantrypilot.models import SavedPantryWriteRequest


@pytest.mark.parametrize("count", [0, 100])
def test_saved_pantry_write_accepts_zero_and_one_hundred_items(count: int) -> None:
    request = SavedPantryWriteRequest(
        pantry_items=[f"item-{index}" for index in range(count)]
    )
    assert len(request.pantry_items) == count


def test_saved_pantry_write_rejects_one_hundred_one_items() -> None:
    with pytest.raises(ValidationError):
        SavedPantryWriteRequest(pantry_items=[f"item-{index}" for index in range(101)])


def test_saved_pantry_write_accepts_one_hundred_character_nonblank_item() -> None:
    value = "x" * 100
    assert SavedPantryWriteRequest(pantry_items=[value]).pantry_items == [value]


def test_saved_pantry_write_rejects_item_over_one_hundred_characters() -> None:
    with pytest.raises(ValidationError):
        SavedPantryWriteRequest(pantry_items=["x" * 101])


@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_saved_pantry_write_rejects_blank_item(value: str) -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        SavedPantryWriteRequest(pantry_items=[value])


def test_saved_pantry_write_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        SavedPantryWriteRequest(pantry_items=[], owner="future-user")
```

- [ ] **Step 2: Run model tests to prove RED**

Run:

```powershell
uv run pytest tests/test_models.py -v
```

Expected RED: import fails because `SavedPantryWriteRequest` is not defined.

- [ ] **Step 3: Implement only the approved saved-pantry models**

Add to `models.py` without editing `RankingRequest`:

```python
SavedPantryText = Annotated[str, Field(max_length=100)]


class SavedPantryWriteRequest(BaseModel):
    pantry_items: Annotated[list[SavedPantryText], Field(max_length=100)]

    model_config = ConfigDict(extra="forbid")

    @field_validator("pantry_items")
    @classmethod
    def reject_blank_pantry_items(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("pantry items must not be blank")
        return values


class SavedPantryItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ingredient_id: str
    canonical_name: str


class SavedPantryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pantry_items: tuple[SavedPantryItem, ...]
```

Do not trim or normalize the model values; the existing deterministic resolver owns normalization and its evidence must preserve submitted input.

- [ ] **Step 4: Write API RED tests for absent, empty, establish/replace/dedupe, and exact ordering**

Add to `tests/test_api.py`:

```python
def test_get_saved_pantry_returns_exact_absent_404(client: TestClient) -> None:
    response = client.get("/v1/saved-pantry")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "type": "saved_pantry_not_found",
            "message": "No saved pantry has been established.",
        }
    }


def test_put_establishes_empty_saved_pantry(client: TestClient) -> None:
    put_response = client.put("/v1/saved-pantry", json={"pantry_items": []})
    get_response = client.get("/v1/saved-pantry")

    assert put_response.status_code == get_response.status_code == 200
    assert put_response.json() == get_response.json() == {"pantry_items": []}


def test_put_resolves_deduplicates_replaces_and_orders_canonical_items(
    client: TestClient,
) -> None:
    first = client.put(
        "/v1/saved-pantry",
        json={"pantry_items": ["spinach", "egg", "Eggs", "spinach"]},
    )
    second = client.put(
        "/v1/saved-pantry",
        json={"pantry_items": ["black bean", "olive oil"]},
    )

    assert first.status_code == second.status_code == 200
    assert first.json() == {
        "pantry_items": [
            {"ingredient_id": "eggs", "canonical_name": "eggs"},
            {"ingredient_id": "spinach", "canonical_name": "spinach"},
        ]
    }
    assert second.json() == {
        "pantry_items": [
            {"ingredient_id": "black-beans", "canonical_name": "black beans"},
            {"ingredient_id": "olive-oil", "canonical_name": "olive oil"},
        ]
    }
    assert client.get("/v1/saved-pantry").json() == second.json()


def test_equivalent_puts_are_idempotent_by_canonical_id_set(client: TestClient) -> None:
    first = client.put(
        "/v1/saved-pantry",
        json={"pantry_items": ["egg", "spinach", "egg"]},
    )
    second = client.put(
        "/v1/saved-pantry",
        json={"pantry_items": ["spinach", "eggs"]},
    )

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
```

- [ ] **Step 5: Write exact all-or-nothing unresolved evidence and no-store-call tests**

Add:

```python
def test_unresolved_put_returns_all_occurrences_in_order_without_store_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "pantrypilot.sqlite3"
    with TestClient(create_app(database_path)) as client:
        established = client.put(
            "/v1/saved-pantry",
            json={"pantry_items": ["eggs"]},
        )
        assert established.status_code == 200
        calls = 0

        def forbidden_store_call(*_args: object, **_kwargs: object) -> tuple[str, ...]:
            nonlocal calls
            calls += 1
            raise AssertionError("unresolved replacement reached storage")

        monkeypatch.setattr(app_module, "replace_saved_pantry", forbidden_store_call)
        response = client.put(
            "/v1/saved-pantry",
            json={"pantry_items": ["egg", "mystery", "eggs", "unknown"]},
        )

        assert response.status_code == 422
        assert response.json() == {
            "detail": {
                "type": "unresolved_pantry_items",
                "message": "All pantry items must resolve before saving.",
                "ingredient_resolution": {
                    "pantry_items": [
                        {
                            "input": "egg",
                            "normalized": "egg",
                            "ingredient_id": "eggs",
                            "canonical_name": "eggs",
                            "match_type": "alias",
                        },
                        {
                            "input": "mystery",
                            "normalized": "mystery",
                            "ingredient_id": None,
                            "canonical_name": None,
                            "match_type": "unresolved",
                        },
                        {
                            "input": "eggs",
                            "normalized": "eggs",
                            "ingredient_id": "eggs",
                            "canonical_name": "eggs",
                            "match_type": "canonical",
                        },
                        {
                            "input": "unknown",
                            "normalized": "unknown",
                            "ingredient_id": None,
                            "canonical_name": None,
                            "match_type": "unresolved",
                        },
                    ]
                },
            }
        }
        assert calls == 0

    with TestClient(create_app(database_path)) as restarted:
        assert restarted.get("/v1/saved-pantry").json() == {
            "pantry_items": [{"ingredient_id": "eggs", "canonical_name": "eggs"}]
        }
```

This one test proves complete ordered evidence, no store invocation, old-state preservation, and restart durability after rejection.

- [ ] **Step 6: Write narrow 503 and programming-error 500 RED tests**

Import `PantryStoreError`, then add:

```python
def test_known_saved_pantry_failure_returns_safe_exact_503(
    safe_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_read(*_args: object, **_kwargs: object) -> None:
        raise PantryStoreError("C:\\private\\pantry.sqlite3: SQL secret")

    monkeypatch.setattr(app_module, "load_saved_pantry", fail_read)

    response = safe_client.get("/v1/saved-pantry")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "type": "saved_pantry_unavailable",
            "message": "Saved pantry is unavailable.",
        }
    }
    assert "private" not in response.text
    assert "SQL" not in response.text


def test_unexpected_saved_pantry_programming_error_remains_generic_500(
    safe_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def programming_error(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("private programmer defect")

    monkeypatch.setattr(app_module, "load_saved_pantry", programming_error)

    response = safe_client.get("/v1/saved-pantry")

    assert response.status_code == 500
    assert "saved_pantry_unavailable" not in response.text
    assert "private programmer defect" not in response.text
```

- [ ] **Step 7: Run API tests to prove RED**

Run:

```powershell
uv run pytest tests/test_models.py tests/test_api.py -k "saved_pantry or unresolved_put" -v
```

Expected RED: routes return 404/405 or imports fail because saved-pantry models and handlers are not yet wired.

- [ ] **Step 8: Implement PUT/GET orchestration and the narrow exception handler**

In `app.py`, import `resolve_ingredients`, the three saved-pantry models, and pantry-store interfaces. Add two small local helpers inside `create_app`:

```python
def saved_pantry_response(
    ingredient_ids: tuple[str, ...],
) -> SavedPantryResponse:
    return SavedPantryResponse(
        pantry_items=tuple(
            SavedPantryItem(
                ingredient_id=ingredient_id,
                canonical_name=INGREDIENT_REGISTRY.by_id[ingredient_id].canonical_name,
            )
            for ingredient_id in ingredient_ids
        )
    )


def required_saved_pantry() -> tuple[str, ...]:
    ingredient_ids = load_saved_pantry(database_path, INGREDIENT_REGISTRY)
    if ingredient_ids is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": "saved_pantry_not_found",
                "message": "No saved pantry has been established.",
            },
        )
    return ingredient_ids
```

Register only `PantryStoreError`:

```python
@application.exception_handler(PantryStoreError)
def saved_pantry_exception_handler(
    _request: Request,
    _exc: PantryStoreError,
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": {
                "type": "saved_pantry_unavailable",
                "message": "Saved pantry is unavailable.",
            }
        },
    )
```

Add the routes:

```python
@application.put("/v1/saved-pantry", response_model=SavedPantryResponse)
def replace_saved_pantry_route(
    request: SavedPantryWriteRequest,
) -> SavedPantryResponse:
    resolutions = resolve_ingredients(request.pantry_items, INGREDIENT_REGISTRY)
    if any(resolution.ingredient_id is None for resolution in resolutions):
        raise HTTPException(
            status_code=422,
            detail={
                "type": "unresolved_pantry_items",
                "message": "All pantry items must resolve before saving.",
                "ingredient_resolution": {
                    "pantry_items": [
                        resolution.model_dump(mode="json") for resolution in resolutions
                    ]
                },
            },
        )
    canonical_ids = tuple(
        sorted(
            {
                resolution.ingredient_id
                for resolution in resolutions
                if resolution.ingredient_id is not None
            }
        )
    )
    saved_ids = replace_saved_pantry(
        database_path,
        canonical_ids,
        INGREDIENT_REGISTRY,
    )
    return saved_pantry_response(saved_ids)


@application.get("/v1/saved-pantry", response_model=SavedPantryResponse)
def get_saved_pantry() -> SavedPantryResponse:
    return saved_pantry_response(required_saved_pantry())
```

The PUT response uses `saved_ids` returned after commit. It must not call `load_saved_pantry` to render success. The list comprehension intentionally includes every resolution occurrence, not only unresolved ones.

- [ ] **Step 9: Add request-shape and restart tests, then run full Task 4 GREEN**

Add API assertions that `pantry_items` is required, unknown fields are rejected, and a successful non-empty pantry survives a TestClient restart:

```python
@pytest.mark.parametrize(
    "body",
    [{}, {"pantry_items": [], "owner": "future-user"}],
)
def test_put_saved_pantry_rejects_invalid_request_shape(
    client: TestClient,
    body: dict[str, object],
) -> None:
    assert client.put("/v1/saved-pantry", json=body).status_code == 422


def test_saved_pantry_survives_application_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "pantrypilot.sqlite3"
    with TestClient(create_app(database_path)) as first:
        assert (
            first.put(
                "/v1/saved-pantry",
                json={"pantry_items": ["spinach", "egg"]},
            ).status_code
            == 200
        )

    with TestClient(create_app(database_path)) as restarted:
        assert restarted.get("/v1/saved-pantry").json() == {
            "pantry_items": [
                {"ingredient_id": "eggs", "canonical_name": "eggs"},
                {"ingredient_id": "spinach", "canonical_name": "spinach"},
            ]
        }
```

Run:

```powershell
uv run pytest tests/test_models.py tests/test_api.py -v
uv run ruff format --check src/pantrypilot/models.py src/pantrypilot/app.py tests/test_models.py tests/test_api.py
uv run ruff check src/pantrypilot/models.py src/pantrypilot/app.py tests/test_models.py tests/test_api.py
```

Expected GREEN: new contracts and all existing API tests pass. In particular, `test_request_uses_snapshot_without_database_io` still passes for the inline endpoint because only saved-pantry routes perform request-time SQLite work.

- [ ] **Step 10: Commit the saved-pantry HTTP resource**

```powershell
git add src/pantrypilot/models.py src/pantrypilot/app.py tests/test_models.py tests/test_api.py
git diff --cached --check
git commit -m "feat: add saved pantry resource endpoints"
```

---

### Task 5: Rank Through the Saved Pantry With Complete Inline Parity

**Files:**
- Modify: `src/pantrypilot/models.py:15-31`
- Modify: `src/pantrypilot/app.py:34-86`
- Modify: `tests/test_models.py`
- Modify: `tests/test_api.py`
- Create: `tests/test_saved_pantry_ranking_parity.py`

**Interfaces:**
- Consumes: validated canonical IDs from `required_saved_pantry`, current registry names, current immutable `app.state.recipe_catalog`, existing `RankingRequest`, and unchanged `rank_recipes`.
- Produces: `SavedPantryRankingRequest` and `POST /v1/saved-pantry/meal-rankings` returning the existing `RankingResponse`.
- Convergence rule: both HTTP ranking flows call one `rank_or_422(RankingRequest) -> RankingResponse` helper. Saved ranking constructs an ordinary `RankingRequest`; it does not fork resolution, eligibility, scoring, explanations, sorting, limiting, or response construction.

- [ ] **Step 1: Write saved-ranking model RED tests**

Extend `tests/test_models.py`:

```python
from pantrypilot.models import SavedPantryRankingRequest


VALID_SAVED_RANKING = {
    "min_protein_g": 25.0,
    "max_prep_minutes": 30,
    "excluded_ingredients": ["peanuts"],
    "limit": 10,
}


def test_saved_ranking_accepts_exact_existing_constraints_without_pantry_items() -> (
    None
):
    request = SavedPantryRankingRequest(**VALID_SAVED_RANKING)
    assert request.model_dump() == VALID_SAVED_RANKING


@pytest.mark.parametrize(
    "body",
    [
        {**VALID_SAVED_RANKING, "pantry_items": ["eggs"]},
        {**VALID_SAVED_RANKING, "pantry_source": "saved"},
    ],
)
def test_saved_ranking_rejects_mode_and_inline_pantry_fields(
    body: dict[str, object],
) -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        SavedPantryRankingRequest(**body)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("min_protein_g", -0.1),
        ("max_prep_minutes", -1),
        ("max_prep_minutes", 10.5),
        ("limit", 0),
        ("limit", 51),
        ("excluded_ingredients", [" "]),
    ],
)
def test_saved_ranking_reuses_existing_constraint_boundaries(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        SavedPantryRankingRequest(**{**VALID_SAVED_RANKING, field: value})
```

- [ ] **Step 2: Run the saved-ranking model tests to prove RED**

Run:

```powershell
uv run pytest tests/test_models.py -k "saved_ranking" -v
```

Expected RED: import fails because `SavedPantryRankingRequest` is not defined.

- [ ] **Step 3: Implement the saved-ranking request without refactoring the inline model**

Add to `models.py`:

```python
class SavedPantryRankingRequest(BaseModel):
    min_protein_g: Annotated[FiniteFloat, Field(ge=0, strict=True)]
    max_prep_minutes: Annotated[StrictInt, Field(ge=0)]
    excluded_ingredients: list[str]
    limit: Annotated[StrictInt, Field(ge=1, le=50)]

    model_config = ConfigDict(extra="forbid")

    @field_validator("excluded_ingredients")
    @classmethod
    def reject_blank_exclusions(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("ingredient values must not be blank")
        return values
```

Keep `RankingRequest` textually and semantically unchanged. Do not create a base class or source discriminator.

- [ ] **Step 4: Write endpoint RED tests for absence, empty pantry, request shape, and fail-closed exclusions**

Add to `tests/test_api.py`:

```python
SAVED_RANKING_REQUEST = {
    "min_protein_g": 0.0,
    "max_prep_minutes": 30,
    "excluded_ingredients": [],
    "limit": 50,
}


def test_saved_ranking_returns_same_exact_absent_404(client: TestClient) -> None:
    response = client.post(
        "/v1/saved-pantry/meal-rankings",
        json=SAVED_RANKING_REQUEST,
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "type": "saved_pantry_not_found",
            "message": "No saved pantry has been established.",
        }
    }


def test_saved_ranking_accepts_established_empty_pantry(client: TestClient) -> None:
    assert client.put("/v1/saved-pantry", json={"pantry_items": []}).status_code == 200

    response = client.post(
        "/v1/saved-pantry/meal-rankings",
        json=SAVED_RANKING_REQUEST,
    )

    assert response.status_code == 200
    assert response.json()["returned_count"] > 0
    assert all(
        result["score_breakdown"]["pantry_coverage"]["value"] == 0.0
        for result in response.json()["results"]
    )


def test_saved_ranking_rejects_pantry_items_and_inline_omission_stays_invalid(
    client: TestClient,
) -> None:
    assert (
        client.post(
            "/v1/saved-pantry/meal-rankings",
            json={**SAVED_RANKING_REQUEST, "pantry_items": ["eggs"]},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/v1/meal-rankings",
            json=SAVED_RANKING_REQUEST,
        ).status_code
        == 422
    )


def test_saved_ranking_preserves_fail_closed_unresolved_exclusions(
    client: TestClient,
) -> None:
    assert (
        client.put("/v1/saved-pantry", json={"pantry_items": ["eggs"]}).status_code
        == 200
    )

    response = client.post(
        "/v1/saved-pantry/meal-rankings",
        json={**SAVED_RANKING_REQUEST, "excluded_ingredients": ["groundnut"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["type"] == "unresolved_excluded_ingredients"
    assert (
        response.json()["detail"]["ingredient_resolution"]["excluded_ingredients"][0][
            "input"
        ]
        == "groundnut"
    )
```

- [ ] **Step 5: Run endpoint tests to prove RED**

Run:

```powershell
uv run pytest tests/test_api.py -k "saved_ranking or inline_omission" -v
```

Expected RED: the saved-ranking route returns 404/405 because it is not registered.

- [ ] **Step 6: Converge both routes on one existing ranking call**

Inside `create_app`, move the current `try/except UnresolvedExcludedIngredientsError` into one local helper:

```python
def rank_or_422(ranking_request: RankingRequest) -> RankingResponse:
    try:
        return rank_recipes(
            ranking_request,
            application.state.recipe_catalog,
            INGREDIENT_REGISTRY,
        )
    except UnresolvedExcludedIngredientsError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "unresolved_excluded_ingredients",
                "message": "All excluded ingredients must resolve before ranking.",
                "ingredient_resolution": (
                    exc.ingredient_resolution.model_dump(mode="json")
                ),
            },
        ) from exc
```

Keep the existing endpoint path and request model, reducing its body only to:

```python
@application.post("/v1/meal-rankings", response_model=RankingResponse)
def create_meal_ranking(ranking_request: RankingRequest) -> RankingResponse:
    return rank_or_422(ranking_request)
```

Add the separate saved operation:

```python
@application.post(
    "/v1/saved-pantry/meal-rankings",
    response_model=RankingResponse,
)
def create_saved_pantry_meal_ranking(
    request: SavedPantryRankingRequest,
) -> RankingResponse:
    ingredient_ids = required_saved_pantry()
    canonical_names = [
        INGREDIENT_REGISTRY.by_id[ingredient_id].canonical_name
        for ingredient_id in ingredient_ids
    ]
    ranking_request = RankingRequest(
        pantry_items=canonical_names,
        **request.model_dump(),
    )
    return rank_or_422(ranking_request)
```

Do not call SQLite from `rank_or_422` and do not pass a store into `rank_recipes`. The saved route performs one durable read per request; the inline route performs none.

- [ ] **Step 7: Write complete response parity tests for aliases, duplicates, empty state, and exclusions**

Create `tests/test_saved_pantry_ranking_parity.py`:

```python
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pantrypilot.app import create_app
from pantrypilot.catalog_store import initialize_catalog
from pantrypilot.ingredients import INGREDIENT_REGISTRY


CONSTRAINTS = {
    "min_protein_g": 20.0,
    "max_prep_minutes": 30,
    "excluded_ingredients": [],
    "limit": 50,
}


def assert_complete_parity(
    client: TestClient,
    canonical_names: list[str],
    constraints: dict[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    inline = client.post(
        "/v1/meal-rankings",
        json={"pantry_items": canonical_names, **constraints},
    )
    saved = client.post(
        "/v1/saved-pantry/meal-rankings",
        json=constraints,
    )
    assert saved.status_code == inline.status_code
    assert saved.json() == inline.json()
    return saved.json(), inline.json()


def test_aliases_and_duplicates_canonicalize_to_complete_ranking_parity(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(tmp_path / "pantrypilot.sqlite3")) as client:
        saved = client.put(
            "/v1/saved-pantry",
            json={
                "pantry_items": [
                    "black bean",
                    "Black Beans",
                    "egg",
                    "eggs",
                    "olive oil",
                ]
            },
        )
        canonical_names = [
            item["canonical_name"] for item in saved.json()["pantry_items"]
        ]

        body, _ = assert_complete_parity(client, canonical_names, CONSTRAINTS)

    assert saved.json()["pantry_items"] == [
        {"ingredient_id": "black-beans", "canonical_name": "black beans"},
        {"ingredient_id": "eggs", "canonical_name": "eggs"},
        {"ingredient_id": "olive-oil", "canonical_name": "olive oil"},
    ]
    assert body["returned_count"] == len(body["results"])
    assert len(body["results"]) > 1


def test_established_empty_pantry_has_complete_zero_coverage_parity(
    tmp_path: Path,
) -> None:
    with TestClient(create_app(tmp_path / "pantrypilot.sqlite3")) as client:
        assert (
            client.put("/v1/saved-pantry", json={"pantry_items": []}).status_code == 200
        )

        body, _ = assert_complete_parity(client, [], CONSTRAINTS)

    assert all(
        result["score_breakdown"]["pantry_coverage"]["value"] == 0.0
        for result in body["results"]
    )


def test_unresolved_exclusion_has_complete_fail_closed_parity(tmp_path: Path) -> None:
    constraints = {**CONSTRAINTS, "excluded_ingredients": ["groundnut"]}
    with TestClient(create_app(tmp_path / "pantrypilot.sqlite3")) as client:
        assert (
            client.put("/v1/saved-pantry", json={"pantry_items": ["egg"]}).status_code
            == 200
        )

        saved, inline = assert_complete_parity(client, ["eggs"], constraints)

    assert saved == inline
    assert saved["detail"]["type"] == "unresolved_excluded_ingredients"
```

Because equality is over the entire decoded HTTP body, these tests cover results, ingredient evidence, score components, final scores, explanations, ordering, limit, and `returned_count`, rather than checking selected fields only.

- [ ] **Step 8: Add physical row-order and tie/limit parity evidence**

Append:

```python
def test_physical_pantry_row_order_cannot_change_complete_ranking(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "pantrypilot.sqlite3"
    with TestClient(create_app(database_path)) as client:
        assert (
            client.put(
                "/v1/saved-pantry",
                json={"pantry_items": ["black beans", "eggs", "spinach"]},
            ).status_code
            == 200
        )
        with sqlite3.connect(database_path) as connection:
            connection.execute("DELETE FROM saved_pantry_items")
            connection.executemany(
                "INSERT INTO saved_pantry_items VALUES (1, ?)",
                [("spinach",), ("eggs",), ("black-beans",)],
            )

        assert_complete_parity(
            client,
            ["black beans", "eggs", "spinach"],
            CONSTRAINTS,
        )


def test_saved_ranking_preserves_recipe_id_tie_break_limit_and_count(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "ties.sqlite3"
    tied_records = (
        {
            "id": "z-recipe",
            "name": "Z Recipe",
            "required_ingredient_ids": ["eggs"],
            "calories": 200,
            "protein_g": 20.0,
            "prep_minutes": 10,
        },
        {
            "id": "a-recipe",
            "name": "A Recipe",
            "required_ingredient_ids": ["eggs"],
            "calories": 200,
            "protein_g": 20.0,
            "prep_minutes": 10,
        },
    )
    initialize_catalog(database_path, tied_records, INGREDIENT_REGISTRY)
    constraints = {**CONSTRAINTS, "min_protein_g": 20.0, "limit": 1}

    with TestClient(create_app(database_path)) as client:
        assert (
            client.put("/v1/saved-pantry", json={"pantry_items": ["egg"]}).status_code
            == 200
        )

        body, _ = assert_complete_parity(client, ["eggs"], constraints)

    assert [result["id"] for result in body["results"]] == ["a-recipe"]
    assert body["returned_count"] == 1
    result = body["results"][0]
    assert result["final_score"] == round(
        sum(
            component["contribution"]
            for component in result["score_breakdown"].values()
        ),
        4,
    )
    assert result["explanation"]
```

- [ ] **Step 9: Run saved-ranking GREEN and full inline API regression**

Run:

```powershell
uv run pytest tests/test_models.py tests/test_api.py tests/test_saved_pantry_ranking_parity.py tests/test_ranking.py -v
uv run ruff format --check src/pantrypilot/models.py src/pantrypilot/app.py tests/test_models.py tests/test_api.py tests/test_saved_pantry_ranking_parity.py
uv run ruff check src/pantrypilot/models.py src/pantrypilot/app.py tests/test_models.py tests/test_api.py tests/test_saved_pantry_ranking_parity.py
```

Expected GREEN: all tests pass, including old inline endpoint tests and full saved/inline equality. Inspect `git diff -- src/pantrypilot/ranking.py`; it must be empty.

- [ ] **Step 10: Commit saved ranking orchestration and parity**

```powershell
git add src/pantrypilot/models.py src/pantrypilot/app.py tests/test_models.py tests/test_api.py tests/test_saved_pantry_ranking_parity.py
git diff --cached --check
git commit -m "feat: rank meals from durable pantry state"
```

---

### Task 6: Document Feature 004 and Run Final Regression Evidence

**Files:**
- Modify: `README.md`
- Modify: `docs/product/vision.md`
- Create: `docs/learning/004-durable-saved-pantry.md`

**Interfaces:**
- Consumes: the final public API, schema, failure behavior, tests, and unchanged ranking/evaluator behavior from Tasks 1–5.
- Produces: owner-readable current product documentation plus a learning document that makes every approved decision explainable and runnable.
- Does not change: production modules, tests, migrations, lock behavior, or ranking behavior.

- [ ] **Step 1: Update README with the current product boundary and runnable API examples**

Replace the transient-only pantry wording with a concise current-state description:

```markdown
PantryPilot keeps one application-local current pantry in the same SQLite
database as the durable recipe catalog. Saved pantry state contains only
canonical ingredient IDs; canonical names are derived from the code-owned
ingredient registry. Inline ranking remains available and unchanged.
```

Document all four API operations with valid JSON examples:

```markdown
- `PUT /v1/saved-pantry` — replace the complete current pantry.
- `GET /v1/saved-pantry` — inspect the established pantry.
- `POST /v1/saved-pantry/meal-rankings` — rank with saved state.
- `POST /v1/meal-rankings` — rank with required inline `pantry_items`.
```

Include the exact absent 404, unresolved-write 422, and storage 503 response bodies. State that empty is established, unresolved writes are all-or-nothing, ordering is by canonical ID, and SQLite persistence is local/single-process. Do not advertise users, quantities, history, retries, or multi-worker coordination.

- [ ] **Step 2: Update the product vision without broadening the roadmap**

In `docs/product/vision.md`, change the current-boundary section to say recipes and the one current pantry are durable, while recipe ranking remains deterministic and the ingredient registry remains code-owned. Add one explicit seam paragraph:

```markdown
The singleton marker/items schema is intentionally provisional. Future
users/ownership, quantities/units, and grocery or waste optimization require
separate product evidence and migrations; Feature 004 does not model them.
```

Keep retrieval deferred until catalog scale makes full ranking inefficient. Keep request/ranking history deferred because purpose, privacy, and retention semantics remain undefined.

- [ ] **Step 3: Write the Feature 004 learning document with concrete teaching sections**

Create `docs/learning/004-durable-saved-pantry.md` with these sections and exact subjects:

1. **Capability and non-goals** — singleton current pantry, replace/inspect/saved rank, inline compatibility; no users, item CRUD, reset-to-absent operation, quantities, or history.
2. **Why canonical-only durability** — registry authority, alias resolution at write time, deduplication, rejection of any unresolved occurrence, no raw-string re-resolution semantics, and why a future registry display-name edit is visible on the next GET/ranking read.
3. **Absent versus empty** — marker truth table showing no marker → 404, marker/no items → valid empty ranking, marker/items → saved set.
4. **Schema v1 → v2** — both DDL statements, no seed, ordered migration runner, partial-DDL rollback, deferred commit failure, and why registry IDs cannot be a SQLite FK.
5. **Write transaction** — resolution before connection and the exact `BEGIN IMMEDIATE → DELETE → INSERT marker → INSERT sorted IDs → COMMIT` sequence; failure retains prior state.
6. **Read transaction and integrity** — short-lived consistent read, targeted FK check, marker validation, explicit `ORDER BY`, registry validation, complete failure rather than skipped rows.
7. **Concurrency** — standard SQLite timeout, writer serialization, complete read snapshots, **last successful commit wins**, deterministic lock test, no retries/mutex/WAL requirement.
8. **Ranking convergence** — saved IDs → current names → ordinary `RankingRequest` → unchanged `rank_recipes`; formula `0.70 * pantry_coverage + 0.20 * protein_fit + 0.10 * time_fit` and full response parity.
9. **HTTP trust boundary** — exact 404/422/503 bodies, narrow `PantryStoreError` ownership, generic 500 for programmer defects, and no path/SQL leakage.
10. **Privacy and future seams** — only current marker/IDs; quantities, users, optimization, retrieval, and history remain deferred.

Include runnable commands:

```powershell
uv sync
uv run uvicorn pantrypilot.app:app --reload
uv run pytest tests/test_database.py tests/test_pantry_store.py -v
uv run pytest tests/test_api.py tests/test_saved_pantry_ranking_parity.py -v
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
```

Include practical exercises with observable success criteria:

- save aliases/duplicates and verify canonical-ID order;
- save an empty pantry and rank successfully with zero pantry coverage;
- attempt a mixed valid/unresolved replacement and verify the prior GET is unchanged;
- inspect `PRAGMA user_version`, marker rows, and item rows without modifying them;
- hold a real `BEGIN IMMEDIATE` lock, observe safe failure, release it, and verify the later replacement;
- compare complete JSON from inline canonical names and saved ranking.

Include failure examples with the exact safe public bodies for absent state, unresolved replacement, and unavailable storage; explain that raw sqlite details appear only as internal exception causes, never HTTP JSON.

Finish with guided mock-interview questions and concise answer guidance for at least:

- Why whole replacement instead of item CRUD?
- Why reject the entire unresolved write?
- How does the marker distinguish absent from empty?
- Why store IDs but derive names?
- Why can SQLite not FK to the Python registry, and where is that integrity checked?
- How does migration-2 rollback prove atomicity, including commit-time failure?
- Why `BEGIN IMMEDIATE`, and what does **last successful commit wins** mean?
- Why read on each saved-ranking request rather than cache?
- How do both ranking endpoints avoid semantic drift?
- Why is the 503 handler narrow?
- What evidence would justify users, quantities, history, retrieval, or retries later?

- [ ] **Step 4: Verify documentation contains no unsupported claims or placeholders**

Run:

```powershell
rg -n "multi-user|quantity|history|cache|retry" README.md docs/product/vision.md docs/learning/004-durable-saved-pantry.md
Select-String -Path docs/learning/004-durable-saved-pantry.md -Pattern "last successful commit wins"
```

Expected: future-capability terms occur only in explicit deferral/non-goal contexts, the approved concurrency phrase is present, and every current API/path/body matches tests. Read the three changed documents once for unfinished drafting language before continuing.

- [ ] **Step 5: Run the complete Feature 001–004 regression and evaluator**

Run each command separately in PowerShell:

```powershell
uv lock --check
uv run pytest
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected:

- lock check passes;
- the complete pytest suite passes with only the known pre-existing Starlette/httpx `TestClient` warning;
- evaluator reports precision `1.0`, recall `1.0`, false positives `0`, and recall greater than the exact-name baseline;
- Ruff formatting/lint and whitespace checks pass.

If a regression fails, use `superpowers:systematic-debugging`; fix only the root cause within the approved design and rerun the focused test before rerunning the full suite.

- [ ] **Step 6: Review privacy and architecture directly in the final diff**

Run:

```powershell
git diff -- src/pantrypilot tests README.md docs/product/vision.md docs/learning/004-durable-saved-pantry.md
rg -n "raw|alias|timestamp|owner|quantity|history|analytics|cache|retry|Repository|Protocol|UnitOfWork|except Exception" src/pantrypilot
```

Expected review result:

- schema stores only marker/current IDs;
- no ranking or failed request is written;
- `database.py` contains only four approved responsibilities;
- `catalog_store.py` remains recipe-specific;
- pantry routes catch/map only `PantryStoreError`;
- no `except Exception` maps defects to 503;
- no change exists in `ranking.py`;
- no speculative future abstraction appears.

- [ ] **Step 7: Commit documentation and final evidence**

```powershell
git add README.md docs/product/vision.md docs/learning/004-durable-saved-pantry.md
git diff --cached --check
git commit -m "docs: explain durable saved pantry"
```

---

## Commit Boundaries

1. `feat: add shared schema version two migration`
2. `feat: persist canonical saved pantry state`
3. `test: prove saved pantry transaction safety`
4. `feat: add saved pantry resource endpoints`
5. `feat: rank meals from durable pantry state`
6. `docs: explain durable saved pantry`

Each commit must pass its focused commands before proceeding. Do not squash these boundaries during execution unless the owner explicitly changes the workflow.

## Approved Design Coverage Map

| Approved design concern | Implementation task/evidence |
|---|---|
| Singleton current pantry; replacement rather than item CRUD | Tasks 2 and 4; marker model and PUT-only mutation. |
| Canonical-only persistence; aliases/duplicates; all unresolved evidence | Task 4 exact resolver/422/no-store-call test; Task 2 canonical store boundary. |
| Absent versus empty | Task 2 store test; Tasks 4–5 exact HTTP/ranking behavior. |
| Request bounds and forbidden fields | Task 4 `tests/test_models.py` at 0/100/101 and 100/101 characters. |
| Genuine v1 → v2 migration preserving recipes | Task 1 populated-v1 before/after row equality. |
| Fresh v0, v2 no-op, newer rejection | Task 1 shared migration tests. |
| Partial DDL and commit-time rollback | Task 1 real migration-2 conflict and deferred-FK commit failure. |
| Narrow shared migration authority | Task 1 mechanical extraction and review check; no generic transaction layer. |
| Atomic replacement and previous-state preservation | Tasks 2–3 trigger failure and real lock tests. |
| Complete durable validation, ordering, and no registry FK duplication | Task 2 constraints/corruption/FK/unknown-ID/read-order tests. |
| Short connection/read/write transactions and freshness | Tasks 2–3; saved ranking reads on every request; later replacement visible. |
| **Last successful commit wins** concurrency | Task 3 deterministic lock/recovery evidence. |
| PUT/GET exact success and errors | Task 4 API tests and orchestration. |
| Narrow safe 503; programmer defects remain 500 | Task 4 paired error-boundary tests. |
| Separate saved-ranking operation | Task 5 model/path tests; no source flag or omitted-inline behavior. |
| Unchanged ranking semantics and full response parity | Task 5 one helper, unchanged `ranking.py`, whole-body equality across edge cases. |
| Backward-compatible inline endpoint | Tasks 4–5 existing API regression plus explicit omitted-pantry rejection. |
| Restart durability | Task 4 close/reopen API test. |
| Privacy/data minimization | Tasks 1–2 exact schema, Task 6 diff/term audit. |
| README, vision, learning guide, exercises, failure examples, interview | Task 6 exact document outline and commands. |
| Feature 002 evaluator acceptance | Task 6 full evaluator command and required metrics. |

## Plan Self-Review Record

- **Complete design mapping:** Every material section of the approved design maps to a task in the table above, including migration preservation, commit failure, absent/empty semantics, all-or-nothing resolution, bounds, registry validation, atomicity, ordering, lock recovery, error ownership, restart durability, parity, compatibility, privacy, and learning documentation.
- **Placeholder scan:** Passed after replacing every instructional stub with exact SQL, signatures, test bodies, commands, or explicit prose.
- **Type consistency:** Database paths are `Path`; canonical IDs are `tuple[str, ...]`; absence alone is `None`; store input is `Iterable[str]`; responses use `SavedPantryResponse`; both ranking flows end in the existing `RankingResponse`.
- **Mechanical extraction caution:** `database.py` has no recipe hydration, pantry store behavior, repository abstraction, service, protocol, generic transaction callback, DI, or unit of work. Recipe wrappers exist only to preserve established Feature 003 call sites.
- **503 caution:** Only `PantryStoreError` has the 503 handler. `RuntimeError`, assertion failures, Pydantic programming mistakes, and other unexpected defects retain the generic 500 path.
- **Ranking caution:** No task edits `ranking.py`, formula weights, eligibility, resolution meaning, explanations, sorting, limit, or `returned_count`.
- **Scope caution:** No task adds users, quantities, units, history, retrieval, caching, retry behavior, generic storage infrastructure, or multi-process coordination.
- **Platform caution:** All commands are valid PowerShell invocations and avoid POSIX continuation syntax.
- **Reviewable increments:** Every production-bearing task starts with concrete RED evidence, ends with focused GREEN checks, and has a conventional commit; the transaction-evidence task remains independently reviewable even if its tests pass against Task 2 without a production edit.
