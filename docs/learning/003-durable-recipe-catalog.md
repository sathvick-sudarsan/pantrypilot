# Feature 003: Durable recipe catalog

## What changed and what did not

Before Feature 003, importing Python code rebuilt the approved recipe catalog
in process memory. That tuple disappeared with the process and could not retain
an out-of-band durable change. Feature 003 makes a local SQLite file the recipe
source of truth. Startup initializes that file, then loads one validated,
immutable `tuple[Recipe, ...]` for the lifetime of the FastAPI application.

Only recipe storage changed. `INGREDIENT_REGISTRY` still owns canonical
ingredient IDs, display names, and aliases in code. `rank_recipes` still
receives recipes and the registry explicitly, and its formula remains:

```text
0.70 * pantry_coverage + 0.20 * protein_fit + 0.10 * time_fit
```

Hard filters, resolution evidence, explanations, four-decimal scoring,
score-descending/recipe-ID-ascending ordering, and post-sort limiting are also
unchanged. `INITIAL_RECIPE_CATALOG` is now only empty-store seed input and a
test parity fixture; it is not a production fallback.

## Stable identifiers are contracts

`spinach-omelet` identifies a recipe even if its display name changes.
Likewise, `olive-oil` identifies an ingredient while `olive oil` is its current
canonical display name. Display text is for people and can be edited; stable
IDs are machine contracts used by relationships, tests, and later migrations.

`recipes.id` is the recipe primary key (PK). Each
`recipe_ingredients.recipe_id` is a foreign key (FK) to it. The relationship
stores a canonical `ingredient_id`, but there is deliberately no ingredient
table: the code-owned registry validates those IDs during seed validation and
hydration. Persisting names or aliases would create a competing registry
source of truth.

## The two-table model

Schema version 1 has exactly these two tables:

```sql
CREATE TABLE recipes (
    id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(id)) > 0),
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    calories NUMERIC NOT NULL
        CHECK (typeof(calories) IN ('integer', 'real') AND calories >= 0),
    protein_g NUMERIC NOT NULL
        CHECK (typeof(protein_g) IN ('integer', 'real') AND protein_g >= 0),
    prep_minutes INTEGER NOT NULL
        CHECK (typeof(prep_minutes) = 'integer' AND prep_minutes >= 0)
);

CREATE TABLE recipe_ingredients (
    recipe_id TEXT NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    position INTEGER NOT NULL
        CHECK (typeof(position) = 'integer' AND position >= 0),
    ingredient_id TEXT NOT NULL CHECK (length(trim(ingredient_id)) > 0),
    PRIMARY KEY (recipe_id, position),
    UNIQUE (recipe_id, ingredient_id)
);
```

The recipe PK rejects duplicate recipe identities. The relationship PK permits
only one row at each recipe position, while `UNIQUE (recipe_id, ingredient_id)`
prevents the same ingredient from appearing twice in one recipe. The FK rejects
an absent parent when foreign-key enforcement is enabled. `ON DELETE CASCADE`
means deleting a recipe also deletes its relationship rows. `NOT NULL` and
`CHECK` constraints reject null, blank, negative, or wrong-storage-class values
covered by the schema.

Order is data, so Spinach Omelet is represented as one recipe plus these rows:

| recipe_id | position | ingredient_id |
|---|---:|---|
| `spinach-omelet` | 0 | `eggs` |
| `spinach-omelet` | 1 | `spinach` |
| `spinach-omelet` | 2 | `olive-oil` |

The zero-based `position` preserves eggs, spinach, then olive oil independently
of physical insertion or row-return order.

## SQLite affinity is not static typing

SQLite column declarations apply type affinity; they do not make columns
statically typed. The schema therefore checks the stored value after affinity
has run:

```sql
SELECT typeof(calories), typeof(protein_g), typeof(prep_minutes)
FROM recipes WHERE id = 'spinach-omelet';
```

For the approved row, the storage classes are `integer`, `integer` or `real`,
and `integer`. Numeric text such as `'410'` may be losslessly coerced by
`NUMERIC` affinity to an integer before `typeof(calories)` is evaluated, so the
check cannot recover the writer's original input type. Text that remains text,
a blob, a negative number, or a non-integral preparation value fails the
corresponding post-affinity check.

The SQL checks intentionally cover only cheap storage invariants. For example,
Python's SQLite adapter can store positive infinity as a `real`; `typeof` is
`real` and `infinity >= 0` is true. Hydration then passes the value to
Pydantic's `FiniteFloat`, which rejects it before any catalog is published.
Duplicating the full `Recipe` model in SQL would create two domain contracts
that could drift, so semantic validation stays in `Recipe` and the registry.

## Versioning and atomic migrations

`PRAGMA user_version` is the file's schema version: `0` means no PantryPilot
migration has run, and the only ordered migration currently advances to `1`.
`migrate_catalog` rejects versions newer than the application supports and
applies each missing version in order.

For migration 1 it executes this unit:

```text
BEGIN IMMEDIATE
  -> CREATE recipes
  -> CREATE recipe_ingredients
  -> PRAGMA user_version = 1
  -> COMMIT
```

`BEGIN IMMEDIATE` claims the write transaction before DDL starts. Each DDL
statement is executed individually and the version update is inside that same
transaction. If any statement, version update, or commit fails, explicit
`ROLLBACK` restores both schema and version to their pre-migration state.
`executescript` is excluded because its implicit transaction behavior could
move statements outside this deliberately owned atomic boundary.

## Migration, seeding, loading, and runtime mutation

- **Migration** changes the durable schema contract and `user_version`.
- **Seeding** inserts the approved initial recipes and relationships into a
  migrated store only when both application tables are empty.
- **Loading** reads all durable rows and converts them into domain objects; it
  does not modify the database.
- **Runtime mutation** would be a supported edit after initialization. Feature
  003 provides no recipe write or administration API.

Both tables empty is the Feature 003 uninitialized sentinel. If both contain a
complete catalog, seeding returns without comparing the data with
`INITIAL_RECIPE_CATALOG`. If only one contains data, a recipe has no ingredient
rows, or foreign-key violations exist, startup fails as partially initialized.
A valid non-empty store is never topped up, reconciled, or overwritten from
seed because that would make Python records a second recipe authority.

## Connections and transactions

`connect_catalog` opens every application-owned connection with
`isolation_level=None`. This disables Python's implicit transaction starts so
transaction ownership remains visible. Only migration and seeding issue
`BEGIN IMMEDIATE`, then explicitly `commit()` on complete success or
`rollback()` on failure.

Every connection executes and verifies `PRAGMA foreign_keys = ON`. SQLite
foreign-key enforcement is a per-connection setting, so enabling it on an old
handle does not protect a newly opened one.

Connections have one short purpose:

```text
initialization connection -> migrate -> seed if both tables empty -> close
load connection           -> check version/integrity -> hydrate tuple -> close
request                    -> use tuple; no SQLite connection or transaction
```

Closing and reopening before loading proves initialization committed durable
state rather than relying on an uncommitted transaction or connection-local
object. No shared connection, pool, request-time database I/O, or shutdown
database cleanup is needed.

## Hydration and defense in depth

SQLite owns local relational and basic stored-value rules: PK uniqueness,
parent FKs, one ingredient per position, no repeated ingredient per recipe,
nonblank text, accepted post-affinity storage classes, non-negative values, and
atomic writes.

Hydration owns application semantics. `load_durable_catalog` first requires
schema version 1, `quick_check == "ok"`, and no foreign-key violations. It
builds mappings for every recipe and ordered relationship, then calls the
existing `load_catalog`. Pydantic creates frozen `Recipe` objects, forbids extra
fields, requires nonblank text, finite nutrition, strict integer preparation
minutes, and a non-empty, duplicate-free ingredient tuple. `load_catalog`
checks every ingredient ID against `INGREDIENT_REGISTRY` and recipe IDs again.

This overlap is defense in depth, not competing ownership. If one stored
recipe is invalid, `load_catalog` raises and `load_durable_catalog` exposes no
partial tuple. Rows are never skipped to keep the API running; startup fails
before `app.state.recipe_catalog` is assigned.

Two queries preserve this fail-closed behavior. The first selects every recipe,
including a recipe with no relationships. The second selects all relationships
and attaches them. An inner join would make a zero-ingredient recipe disappear,
hiding invalid durable state instead of sending its empty tuple through domain
validation.

## FastAPI lifespan and snapshot flow

The implemented startup and request path is:

```text
construct app
  -> enter lifespan
  -> migrate
  -> seed if empty
  -> close initialization connection
  -> reopen load connection
  -> validate immutable Recipe tuple
  -> assign app.state.recipe_catalog
  -> request
  -> rank_recipes(request, app.state.recipe_catalog, INGREDIENT_REGISTRY)
```

Constructing or importing the app does not create a database. FastAPI's
`lifespan` context makes a valid catalog a startup precondition. The tuple is a
derived, immutable snapshot rather than a second source of truth: the file owns
durable recipe facts, while the tuple is the validated representation used by
one running process. Feature 003 has no runtime writes, so per-request reloads
would add I/O without exposing newer supported state.

## Row order is not ranking order

Three different order concepts must not be confused:

1. Relationship `position` is stored application meaning. Hydration uses
   `ORDER BY recipe_id, position` so ingredient evidence follows that value.
2. Recipe hydration uses `ORDER BY id` only for repeatable loading and failure
   reporting. It is not recommendation order.
3. `rank_recipes` establishes result order after scoring: exposed
   `final_score` descending, then recipe ID ascending for a tie. `limit` is
   applied afterward.

Reversing physical recipe and relationship insertion order therefore changes
neither required/matched/missing ingredient evidence nor ranking result order.

## Testing layers

- Domain/unit tests cover `Recipe`, `load_catalog`, ingredient resolution, and
  pure ranking without SQLite or HTTP.
- Real persistence tests use isolated files below `tmp_path` to exercise the
  actual schema, constraints, affinity, hydration, seeding, and invalid rows.
- One real migration test creates a conflicting second table so the first DDL
  succeeds and the next fails. It proves partial DDL rollback; the
  `user_version` update is never reached.
- A separate synthetic migration inserts a deferred foreign-key violation. Its
  trace proves `PRAGMA user_version = 1` executes before `COMMIT`; the
  commit-time failure then proves the new schema, data, and version all roll
  back together.
- Integration/lifespan tests enter `TestClient` as a context manager, proving
  startup creates and publishes the snapshot and storage failure prevents the
  API from starting.
- Reconnection tests close initialization and load from a new connection,
  proving committed file durability and non-empty-store authority.
- Parity tests reverse physical insertion order and compare complete
  `RankingResponse` objects, fail-closed evidence, and tie ordering with the
  direct seed fixture.
- The full suite preserves Feature 001 and Feature 002 behavior as regression
  coverage.
- The registry evaluation remains independent of the recipe database and
  measures the exact-name baseline against canonical/alias resolution.

## Why `sqlite3` is sufficient now

Python's standard-library `sqlite3` adds zero dependencies and directly exposes
the SQL, affinity, constraints, connections, transactions, and hydration this
feature is meant to teach. One local file, one application process, startup-only
writes, two tables, and one read-all path do not need an engine, session,
repository abstraction, connection pool, or migration CLI.

An ORM and Alembic could earn their cost when the product has multiple writers,
a server database, a large migration graph, many related write paths, or
complex cross-database deployment coordination. Those are measured future
needs, not current scaffolding requirements.

## Explicit deferrals

Feature 003 does not add pantry or ranking/history persistence, recipe CRUD,
retrieval or indexing, quantities or units, food-waste or multi-meal
optimization, authentication or users, analytics or request tracing, external
recipe ingestion, ML or LLM behavior, a frontend, or microservices. The
ingredient registry also remains code-owned. Each deferred capability needs
its own contract and evidence when the roadmap reaches the problem it solves.

## Run and inspect

Start the API once before the inspection command if the default development
database does not yet exist.

```powershell
uv run python -c "import sqlite3; c=sqlite3.connect('pantrypilot.sqlite3'); print(c.execute('PRAGMA user_version').fetchone()[0]); print(c.execute('SELECT id, name FROM recipes ORDER BY id').fetchall()); c.close()"
uv run pytest tests/test_catalog_store.py -v
uv run pytest tests/test_ranking_parity.py -v
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
```

## Exercises with answers

### Exercise 1

The migration rollback test pre-creates a `recipe_ingredients(sentinel TEXT)`
table. Predict what remains after migration 1 creates `recipes` and then fails
while trying to create the already-named relationship table. Why is
`user_version` still zero? How does the separate deferred-foreign-key test
prove the stronger version-atomicity claim?

**Answer:** The pre-existing empty sentinel table remains exactly as it was;
the newly created `recipes` table and any rows from the failed transaction do
not remain. `PRAGMA user_version = 1` is never reached, and rollback restores
the partial migration transaction, so the version stays `0`. In the separate
test, every synthetic migration statement succeeds, trace evidence records
`PRAGMA user_version = 1` before `COMMIT`, and a deferred foreign-key violation
fails only at commit. Rollback then removes the synthetic schema/data and
restores `user_version` to `0`, proving they share the transaction.

### Exercise 2

Predict whether inserting recipes in descending ID order and relationships in
descending position order changes ingredient evidence or ranking order. Name
the two semantic ordering rules.

**Answer:** Neither changes. Ingredient evidence follows stored `position`,
read by `ORDER BY recipe_id, position`. Ranking results follow
`final_score DESC` and then recipe ID ascending, independent of catalog row
order.

### Exercise 3

Classify these changes: a new schema column, first-run initial rows, an admin
edit, a Pydantic validation failure while reading, and an alias addition.

**Answer:** A new column is a migration; first-run initial rows are a seed; an
admin edit is runtime mutation (not implemented in Feature 003); a Pydantic
read failure is a hydration failure; and an alias addition is a code-owned
registry change.

## Guided mock interview

1. **Why is the SQLite file the source of truth if requests use an in-memory
   tuple?** The tuple is recreated from the file at startup and cannot update
   the file. It is one process's validated read snapshot, while durable recipe
   facts survive restart only in SQLite.
2. **Why is seeding not a migration?** A migration changes schema/version for
   every older store. Seeding supplies initial rows only to the both-empty
   sentinel and never reconciles a non-empty store.
3. **How does migration 1 keep DDL and `user_version` atomic?** It runs
   `BEGIN IMMEDIATE`, executes both DDL statements individually, sets
   `user_version` in the same transaction, and commits only after all succeed;
   any SQLite error triggers rollback.
4. **What does `PRAGMA foreign_keys = ON` guarantee, and why is it set for every
   connection?** It enforces declared parent references and cascade behavior
   for that handle. SQLite scopes the setting per connection, so every new
   handle must enable and verify it.
5. **Which invariants belong to SQLite and which remain in `Recipe` hydration?**
   SQLite owns keys, relationships, uniqueness, basic nonblank/type/non-negative
   checks, and atomicity. Hydration owns frozen domain objects, finite numeric
   semantics, strict model fields/types, non-empty ingredient tuples, and
   registry membership.
6. **Why can positive infinity pass the approved SQL check but still be
   rejected safely?** SQLite stores it as non-negative `real`, which satisfies
   the basic check. Pydantic's `FiniteFloat` rejects it during complete-catalog
   hydration before the snapshot is published.
7. **Why are two queries used instead of an inner join during hydration?** The
   recipe query retains parents with zero relationships so domain validation
   can reject them; an inner join would silently hide them.
8. **How is recipe ingredient order preserved independently of row order?**
   Each relationship stores a zero-based `position`, and hydration explicitly
   orders by recipe ID and position before building the tuple.
9. **How do parity tests prove ranking meaning did not change?** They load
   equivalent direct and durable catalogs, deliberately reverse durable
   insertion order, run the unchanged `rank_recipes`, and compare complete
   responses plus fail-closed and tie behavior.
10. **When would an ORM and Alembic earn their added complexity?** When multiple
    writers, server-database deployment, many related write paths, a large
    migration graph, or cross-database release coordination makes the explicit
    `sqlite3` code a measured maintenance problem.
