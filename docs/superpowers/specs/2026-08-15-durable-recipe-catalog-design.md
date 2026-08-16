# Feature 003: Durable recipe catalog and ranking parity

Status: Proposed for owner review

Design date: 2026-08-15

GitHub issue: #5

## Summary

Feature 003 moves the approved four-recipe catalog from a module-level Python
runtime value into a SQLite database without changing ranking behavior.
Python's standard-library `sqlite3` module owns a small, explicit schema and a
native schema version. Application startup applies known migrations, seeds the
approved records only when the migrated catalog is genuinely empty, closes
that connection, then reopens the database and hydrates validated immutable
`Recipe` objects. The existing pure
`rank_recipes(request, recipes, ingredient_registry)` boundary remains
unchanged.

The canonical ingredient registry remains reviewed, immutable Python data.
The database stores its stable ingredient IDs in ordered recipe relationships;
it does not duplicate canonical names or aliases. Unknown stored ingredient
IDs therefore fail at the hydration boundary before the API serves traffic.

The durable database is the only production recipe source of truth after
initialization. The current Python records remain only as the versioned seed
input and in-memory parity fixture. They are not loaded into a production
`CATALOG`, used as an API fallback, or reapplied to a non-empty store.

This is the smallest coherent durability step in roadmap Phase 3. Pantry
state, ranking requests, request tracing, retrieval, quantities, and all other
later capabilities remain deferred.

## Context and current architecture

The repository at starting commit
`1e231c40b057ccd22335d01115ead5dbf47c4e9b` contains three implementation
commits: the project foundation, Feature 001 ranking, and Feature 002 measured
ingredient resolution. There is no persistence dependency, migration tool,
storage interface, connection lifecycle, or database configuration.

The current production path is:

```text
RAW_INGREDIENTS
    -> load_ingredient_registry(...)
    -> immutable INGREDIENT_REGISTRY

RAW_CATALOG
    -> load_catalog(..., INGREDIENT_REGISTRY)
    -> immutable module-level CATALOG

POST /v1/meal-rankings
    -> rank_recipes(request, CATALOG, INGREDIENT_REGISTRY)
    -> RankingResponse
```

The relevant existing boundaries are already useful:

- `ingredients.py` owns stable kebab-case ingredient IDs, canonical names,
  aliases, immutable indexes, and deterministic resolution.
- `models.py` owns the frozen `Recipe` domain model. Recipes contain an ordered
  non-empty tuple of `required_ingredient_ids` plus validated recipe facts.
- `catalog.py` validates mappings into `Recipe` values, rejects duplicate
  recipe IDs and unknown ingredient IDs, and currently creates `CATALOG` at
  import time from `RAW_CATALOG`.
- `ranking.py` is pure. It receives recipes and the registry, resolves request
  terms once, applies hard filters, scores, explains, sorts by exposed score
  and recipe ID, applies `limit`, and returns resolution evidence.
- `app.py` is a thin synchronous FastAPI adapter. It currently imports the
  module-level catalog and has no startup lifecycle.
- Unit tests construct `Recipe` values and call the pure ranking functions;
  catalog tests exercise `load_catalog`; API tests use FastAPI `TestClient`;
  the Feature 002 evaluation is independent of the recipe catalog.

Feature 002 deliberately made stable ingredient IDs exist before persistence.
Feature 003 can therefore persist relationships to `black-beans` and
`olive-oil` rather than freezing display text such as `black beans` into a
recipe contract.

## Problem statement

The current recipe catalog is reconstructed from Python data whenever the
module is imported. It has strong validation and deterministic behavior but no
durable source of truth, inspectable schema version, migration path, or
restart/reconnection evidence.

Adding a database beside the unchanged module-level `CATALOG` would not solve
the ownership problem. It would create two production recipe sources that can
diverge while ranking continues to use the in-code copy. Feature 003 must
instead make durable records feed the normal API path and preserve the exact
Feature 001/002 ranking contract.

## Goals

- Make one durable store the production source of recipe facts and ordered
  recipe-to-ingredient relationships.
- Reproduce a fresh schema and expose its version without an added dependency.
- Distinguish schema migration, initial data seeding, and runtime catalog use.
- Hydrate all stored data through the existing immutable `Recipe` validation
  boundary before serving requests.
- Reject unavailable, unsupported, partially initialized, relationally
  corrupt, or domain-invalid catalog state deterministically.
- Preserve the existing pure ranking API and all externally meaningful
  ranking behavior.
- Prove durability across closed connections and parity independent of SQLite
  row-return or insertion order.
- Keep local Windows development and isolated tests straightforward.
- Teach durable-state, relational, migration, transaction, hydration, and
  contract-testing fundamentals without hiding them behind a framework.

## Non-goals

Feature 003 does not add:

- pantry-state, ranking-request, history, analytics, or feedback persistence;
- authentication, users, ownership, recipe CRUD, or administration;
- external recipe ingestion or catalog expansion;
- retrieval, search, indexes added only for future retrieval, embeddings, or
  vector databases;
- quantities, units, prices, spoilage, grocery optimization, or multi-meal
  planning;
- ranking formula, feature, weight, explanation, resolution, or API contract
  changes;
- fuzzy matching, ML, personalization, LLMs, agents, or frontend work;
- microservices, distributed storage, caching, asynchronous database drivers,
  generic repository/service/factory interfaces, or a dependency-injection
  framework;
- a broad logging, observability, or request-tracing rewrite; or
- unrelated cleanup.

The roadmap's broader Phase 3 eventually mentions pantry state, ranking
requests, and request tracing. Issue #5 is a deliberately smaller vertical
slice. Those items are not prerequisites for establishing a durable recipe
contract and would multiply schema, privacy, and lifecycle decisions without
helping ranking parity.

Retrieval remains deferred because four recipes do not create a retrieval or
latency problem. Quantities and units remain deferred because single-recipe
ranking currently models ingredient presence, while those fields belong to
later pantry and waste optimization.

## Recommended approach

Use Python 3.12's standard-library `sqlite3` module with:

- one local SQLite database file;
- two concrete catalog tables;
- `PRAGMA user_version` as the schema-version mechanism;
- an ordered in-code list of explicit SQL migration statements;
- one deliberately controlled atomic transaction per schema migration,
  including its `user_version` update;
- a separate seed-if-empty transaction;
- short-lived connections rather than a shared application connection;
- the existing Pydantic `Recipe` model as the hydration boundary; and
- FastAPI's `lifespan` parameter for startup initialization and loading.

This approach earns its complexity now. SQLite provides atomic commits,
primary/foreign/unique/check constraints, durable reconnect behavior, and a
real relational migration surface while remaining embedded, cross-platform,
and dependency-free. The current catalog needs two tables and no write API, so
an ORM, session layer, connection pool, or migration CLI would add more
concepts and configuration than the feature uses.

The design intentionally uses a concrete catalog-store module rather than a
generic repository interface. There is exactly one store and one operation the
application needs: initialize and load all recipes.

## Alternatives considered

### 1. Standard-library SQLite with explicit migrations — recommended

**Feature fit.** Two tables naturally express recipes plus ordered ingredient
relationships. SQLite supplies durable local state and integrity without a
server.

**Dependencies and ergonomics.** No new package or lockfile change is needed.
Python and SQLite are already present on Windows through the project runtime.
A file path is enough for local use and `tmp_path` is enough for isolated
tests.

**Schema and migration story.** SQL remains visible and small.
`PRAGMA user_version` supplies an inspectable integer version, while ordered
migrations demonstrate transactions and evolution directly.

**Lifecycle and tests.** Short-lived synchronous connections match the current
synchronous endpoint. Real file-backed tests can close/reopen connections and
exercise the same migration runner without mocks.

**Integrity and hydration.** SQLite rejects duplicate identities,
relationships, positions, and basic invalid values. The existing Pydantic
model and ingredient registry enforce richer domain rules after rows are
assembled.

**Future compatibility.** Later pantry tables can be added by a new migration.
Later retrieval can add query-specific indexes when measurements justify them.
Neither requires an abstraction now.

**YAGNI cost.** The project owns a small amount of connection, SQL, and
migration code. With two tables, that code is less machinery than adopting a
framework.

### 2. SQLite with SQLAlchemy Core and Alembic

This middle option would keep SQL-shaped tables rather than introducing
behavior-rich ORM entities. SQLAlchemy Core would construct queries and manage
engines/connections; Alembic would own revision files and upgrade commands.

It offers a mature version history, clearer support for many future
migrations, and familiar production tooling. Tests could still use file-backed
SQLite, and Core rows could be aggregated into the existing Pydantic models.

It is rejected now because it adds SQLAlchemy, Alembic, their transitive
dependencies, engine configuration, migration environment scaffolding, and a
separate operational command for one migration and two tables. FastAPI would
also need an engine lifetime decision even though requests do not query the
database. These costs become reasonable when migration frequency, deployment
coordination, or several persistent aggregates make a revision graph and
dialect abstraction useful.

### 3. SQLite with SQLModel/SQLAlchemy ORM and Alembic

The heavy option would define storage entities and relationships, use ORM
sessions, and let Alembic manage schema revisions. It provides declarative
relationships, identity/session behavior, and a conventional path toward a
larger multi-aggregate application.

It is rejected for the current feature because it adds the Core/Alembic costs
plus ORM session lifetime, relationship-loading choices, and duplicate
storage/domain model questions. Reusing SQLModel objects directly in ranking
would leak persistence and mutability into the pure domain; mapping them back
to `Recipe` would add a second model layer for five stored fields. An ORM
becomes defensible when several write paths need unit-of-work behavior or
relationship navigation, neither of which exists here.

### Comparison across the serious alternatives

| Criterion | Standard-library `sqlite3` | SQLAlchemy Core + Alembic | SQLModel/ORM + Alembic |
|---|---|---|---|
| Current feature fit | Direct fit for two tables and one read-all path | Capable but broader than the current path | Solves session/entity problems the feature does not have |
| New dependencies | None | SQLAlchemy, Alembic, and transitives | SQLModel/ORM stack, Alembic, and transitives |
| Schema clarity | Explicit reviewed SQL | Declarative Core metadata plus generated/reviewed revisions | Declarative entities plus generated/reviewed revisions |
| Versioning/migrations | Linear integer versions and explicit transactions | Revision graph and upgrade tooling | Same Alembic graph, coupled to ORM metadata |
| Transactions/connections | A few visible `sqlite3` contexts | Engine and connection conventions | Engine, sessions, flush/commit/rollback conventions |
| FastAPI lifecycle | Initialize/load/close; no live resource | Engine lifecycle must be chosen even if startup-only | Engine and session lifecycle must be chosen |
| Windows/local use | One standard-library database file | Package install plus migration environment/command | Largest install and configuration surface |
| Test isolation | `tmp_path` file passed directly | Temporary URL/engine and Alembic configuration | Temporary engine/session and Alembic configuration |
| Reconnect durability | Close and reopen `sqlite3` directly | Dispose/recreate engine or connection | Dispose engine and create a new session |
| Integrity constraints | Explicit SQL constraints | Equivalent Core/Alembic constraints | Equivalent ORM/Alembic constraints |
| Pydantic hydration | Aggregate rows and call existing loader | Aggregate Core rows and call existing loader | Map ORM entities into separate immutable recipes |
| Ingredient ordering | Explicit `position` and `ORDER BY` | Same relational design via Core | Ordered relationship configuration plus storage position |
| Deterministic failures | Small explicit mapping from SQLite/schema/data errors | Framework exception layers and migration errors | Framework plus session/loading failure layers |
| Operational complexity | Startup migration for one local process | Migration command/configuration and engine management | Migration command, engine, and session management |
| Educational value now | Exposes SQL, constraints, transactions, and hydration directly | Teaches common tooling but hides some fundamentals | Teaches ORM concepts not yet needed by the product |
| Later pantry persistence | Add tables and migration versions | Stronger once revisions and environments multiply | Stronger once many writable related entities exist |
| Later retrieval | Add measured indexes/queries without changing ranking | Core query composition may help with many queries | ORM relationships do not remove retrieval measurement needs |
| YAGNI cost | Small owned migration/connection code | Framework and configuration before scale requires them | Highest abstraction and dependency cost |

A versioned JSON file was also tested against the Ponytail/YAGNI threshold. It
would be shorter for four read-only recipes, but it was not a serious finalist:
duplicate identities, relationship integrity, multi-record atomicity, and
future pantry transactions would all become custom application rules. SQLite
provides those present-tense Feature 003 guarantees without a server or added
package.

The framework options are not ruled out forever. They should be reconsidered
only when hand-written migrations or connection code become a measured
maintenance problem, not merely because later phases may persist more data.

## Source-of-truth ownership

After Feature 003 initialization succeeds:

- The SQLite `recipes` and `recipe_ingredients` rows are the production source
  of recipe truth.
- `INGREDIENT_REGISTRY` remains the production source of canonical ingredient
  IDs, display names, and aliases.
- The hydrated immutable recipe tuple is a startup snapshot derived from the
  database, not an independent source.
- The current raw recipe records are renamed to make their restricted role
  explicit, for example `INITIAL_RECIPE_CATALOG`. They are seed input for an
  empty migrated store and a parity fixture for tests.
- There is no module-level production `CATALOG` created from the Python seed.
- There is no request-time or startup fallback from a failed database load to
  the seed records.
- A non-empty durable store is never reconciled, overwritten, or topped up
  from the Python seed.

This asymmetry is intentional. Recipe facts become durable in Feature 003;
ingredient vocabulary does not. Persisting a second copy of canonical names
and aliases would create two registry sources or force unrelated registry
administration and migration decisions into this feature.

## Durable schema

Schema version 1 contains two tables.

### `recipes`

| Column | SQLite declaration | Meaning |
|---|---|---|
| `id` | `TEXT PRIMARY KEY` | Stable recipe identity |
| `name` | `TEXT NOT NULL` | Display name |
| `calories` | `NUMERIC NOT NULL` plus stored-type/non-negative `CHECK` | Basic stored numeric value |
| `protein_g` | `NUMERIC NOT NULL` plus stored-type/non-negative `CHECK` | Basic stored numeric value |
| `prep_minutes` | `INTEGER NOT NULL` plus stored-type/non-negative `CHECK` | Basic stored whole-minute value |

SQLite declarations establish type affinity, not static typing. `NUMERIC` or
`INTEGER` alone therefore does not reject arbitrary values. Schema version 1
adds explicit checks over the value after SQLite has applied affinity:

```sql
CHECK(typeof(calories) IN ('integer', 'real') AND calories >= 0)
CHECK(typeof(protein_g) IN ('integer', 'real') AND protein_g >= 0)
CHECK(typeof(prep_minutes) = 'integer' AND prep_minutes >= 0)
```

Together with `NOT NULL`, these checks reject nulls, values that remain stored
as text or blobs, negative numeric values, and a preparation time that remains
stored with a non-integer storage class. They do not recover the type originally
presented by a writer: for example, affinity may losslessly convert numeric
text or an integral real value to an integer before the check runs. They also
do not express the complete `Recipe` contract. A non-negative value with SQLite
storage class `real` can still be non-finite, so Pydantic hydration remains
responsible for finite nutrition and all other numeric/domain semantics.

No arbitrary numeric ceiling is added merely to approximate finiteness in SQL.
The recipe ID remains a stable opaque string; Feature 003 does not introduce a
new format rule that the current domain does not have.

### `recipe_ingredients`

| Column | SQLite declaration | Meaning |
|---|---|---|
| `recipe_id` | `TEXT NOT NULL` | Parent recipe ID |
| `position` | `INTEGER NOT NULL` | Zero-based ingredient order |
| `ingredient_id` | `TEXT NOT NULL` | Feature 002 canonical ingredient ID |

The table has:

- primary key `(recipe_id, position)` so one ordered slot exists once;
- unique constraint `(recipe_id, ingredient_id)` so a recipe cannot repeat a
  canonical ingredient;
- foreign key `recipe_id -> recipes.id` with `ON DELETE CASCADE`;
- a check that `position` is a non-negative integer; and
- a check that `ingredient_id` is nonblank.

Every connection enables `PRAGMA foreign_keys = ON` before a transaction.
Connection setup verifies that the pragma took effect.

There is deliberately no persisted ingredient or alias table. Consequently a
database foreign key cannot validate `ingredient_id` against the code-owned
registry. Seed validation and domain hydration perform that check using the
authoritative `INGREDIENT_REGISTRY`. An unknown reference prevents startup.

There is no retrieval index on `ingredient_id`. The application reads all four
recipes, and ranking already performs full-catalog scoring. A later retrieval
feature can add an index in the migration that introduces measured queries.

### Why ordering is explicit

SQLite does not promise row-return order without `ORDER BY`. Ingredient order
affects `required_ingredients`, `matched_ingredients`, and
`missing_ingredients`, so it is stored as data in `position` and read with
`ORDER BY recipe_id, position`.

Recipe row order has no ranking meaning. Catalog reads use an explicit recipe
ID order only to make hydration and failure reporting repeatable. The ranking
pipeline still establishes result semantics by sorting four-decimal
`final_score` descending and recipe ID ascending before applying `limit`.

## Schema versioning and migrations

SQLite's native `PRAGMA user_version` is the sole schema-version record.
Version `0` means no PantryPilot migration has been applied; the first approved
schema is version `1`. A constant records the application-supported current
version, and an ordered migration collection maps each next integer to its
explicit SQL statements.

The migration runner:

1. Opens a concrete SQLite connection and enables foreign keys.
2. Reads `PRAGMA user_version`.
3. Rejects a version greater than the application supports; it never
   downgrades or guesses.
4. Applies each missing known version in order.
5. Starts one deliberately controlled write transaction for that version,
   executes every schema statement individually, updates `PRAGMA user_version`
   inside the same transaction, and commits only after all of those operations
   succeed.
6. Explicitly rolls back on any statement, version-update, or commit failure.
   Both the schema and `user_version` then remain exactly as they were before
   that migration version began.
7. May be called again safely when the database is already current.

The runner uses explicit transaction control, such as `BEGIN IMMEDIATE`,
individual `execute` calls, `COMMIT`, and `ROLLBACK`. It must not use
`executescript` or another helper whose implicit commit or transaction behavior
could move schema statements outside that controlled atomic boundary. Migration
DDL does not use `IF NOT EXISTS` to conceal a partially present application
schema; a conflict is an error and the whole version rolls back.

Migration 1 creates schema only. It does not insert the four recipes. Keeping
schema evolution separate from seed data makes three responsibilities clear:

- **Migration** changes the durable contract and schema version.
- **Seeding** creates the approved initial catalog only in a migrated empty
  store.
- **Runtime loading** reads whatever valid records the durable source now
  contains and never mutates them.

Migration statements live in the concrete catalog-store code because version
1 has two small tables. A migration directory, templating system, revision
graph, and CLI would be scaffolding without a present need. If migration count
or operational coordination later makes this collection hard to review, that
is the point to reconsider a migration framework.

### Schema-state behavior

- A missing database file or existing empty SQLite file starts at version 0,
  migrates to version 1, and is then eligible for seeding.
- A supported older version runs the known forward migrations.
- A current version loads without schema mutation.
- A newer version fails startup with the found and supported versions; the
  application never attempts a downgrade.
- Version 0 with conflicting partial application tables makes the real
  migration fail and roll back rather than adopting them.
- A database claiming the current version but missing a required table or
  column fails the real catalog read. Version metadata is not trusted as a
  substitute for usable schema.

## Initialization and seeding

Application initialization deliberately composes, but does not conflate,
migration and seeding:

```text
configured database path
    -> migrate schema to supported version
    -> inspect application table emptiness
    -> seed approved recipes only when both tables are empty
    -> close initialization connection
```

Before insertion, the seed records pass through the existing
`load_catalog(..., INGREDIENT_REGISTRY)` validation. The seed transaction then
inserts each recipe followed by its ingredient IDs with enumerated positions.
All four recipes and all relationships commit atomically.

Seeding has three states:

- Both tables empty: insert the complete validated version-1 seed in one
  transaction.
- Both tables contain data: do nothing; the durable data owns the catalog.
- Only one table is empty, an orphan relationship exists, or any recipe lacks
  required relationships: treat the state as partial/corrupt and fail rather
  than guessing, deleting, or topping up.

For Feature 003, both application tables being empty is reserved as the
uninitialized sentinel, not a supported runtime catalog state. The feature has
no delete-all or catalog-mutation capability, and the approved initial product
catalog is non-empty. If a future CRUD feature needs an intentionally empty
catalog, it must add explicit initialization state rather than overloading
emptiness.

An interrupted seed transaction rolls back to the empty state, so the next
startup can retry safely. The application does not need a separate seed marker
or history table for this single atomic seed. A valid non-empty catalog is not
compared with the Python seed, because doing so would make the seed a competing
runtime authority.

This feature adds no runtime recipe mutation API. Tests may modify an isolated
database directly to prove that a non-empty durable record survives restart
without being overwritten; that test seam is not a supported product write
path.

## Domain hydration and validation

After initialization closes its connection, startup opens a fresh connection
and validates/loads the durable catalog. Reopening is intentional: it proves
the application does not rely on uncommitted state or a connection-local
object created during seeding.

Loading performs these checks:

1. Require the supported `user_version` without running migrations.
2. Run SQLite's quick consistency check and foreign-key check.
3. Select every recipe in explicit recipe-ID order.
4. Select every relationship in `(recipe_id, position)` order.
5. Group ordered ingredient IDs into raw recipe mappings, retaining recipes
   with zero relationships so they fail rather than disappear in an inner
   join.
6. Pass the mappings through the existing catalog loader and frozen Pydantic
   `Recipe` model with the authoritative ingredient registry.
7. Return one immutable tuple only if the complete catalog validates.

No SQLite row, ORM model, or mutable dictionary reaches ranking.

### Storage constraints versus domain validation

SQLite enforces invariants that are local and naturally relational:

- unique recipe IDs;
- valid parent recipe references;
- one ingredient per ordered position;
- no repeated ingredient ID within one recipe;
- non-null and basic nonblank values;
- numeric columns whose post-affinity SQLite storage classes are integer/real
  as specified, including an integer storage class for preparation time;
- basic non-negative numeric values; and
- atomic schema and seed writes.

Domain hydration enforces semantic application contracts:

- frozen `Recipe` objects and forbidden model fields;
- nonblank recipe text according to existing validation;
- finite nutrition values and current strict numeric behavior;
- a non-empty required-ingredient tuple;
- canonical ingredient membership in `INGREDIENT_REGISTRY`;
- duplicate required IDs as a defense in depth; and
- all current Pydantic recipe expectations.

Some rules intentionally exist at both boundaries. Cheap storage constraints
prevent bad durable state; domain validation prevents persistence from
bypassing the model used by every other caller. SQLite affinity and the basic
checks are not treated as proof of the full `Recipe` numeric contract. Any
malformed value that can legally remain in SQLite must fail complete-catalog
hydration deterministically; it is never skipped and never reaches ranking.

### Deterministic invalid-data behavior

- A duplicate recipe ID is rejected by the recipe primary key on write and by
  the catalog loader if duplicate raw records are ever supplied.
- A duplicate ingredient relationship is rejected by the relationship unique
  constraint and again by the `Recipe` validator.
- An unknown canonical ingredient ID can exist only through an out-of-band
  write; hydration reports the recipe ID and unknown ingredient ID and aborts
  startup.
- A recipe with no relationships remains visible to hydration and fails the
  non-empty domain rule.
- Invalid names, non-finite nutrition, preparation time, or any other
  unsupported stored value not already rejected by SQLite fails Pydantic
  hydration before the catalog snapshot is published.
- Foreign-key violations, failed quick checks, missing schema objects, and
  SQLite read errors abort startup.

The loader validates the whole catalog before assigning it to application
state. There is no partially published snapshot and no behavior that silently
skips a malformed recipe.

## Application and FastAPI integration

Feature 003 introduces one concrete application-construction seam so tests can
supply an isolated database path. The production module still exports
`app`, built with a documented database path configuration. A relative default
such as `pantrypilot.sqlite3` keeps the current quick start working from the
project directory; `PANTRYPILOT_DB_PATH` permits an explicit absolute path.
Relative paths resolve from the process working directory and this limitation
is documented.

The app uses FastAPI's non-deprecated `lifespan` parameter with a standard-
library async context manager:

```text
app import
    -> create FastAPI object; do not open or create a database

lifespan startup
    -> initialize/migrate/seed through one short-lived connection
    -> close it
    -> reopen through another short-lived connection
    -> hydrate and validate immutable recipes
    -> close it
    -> publish recipes to app.state

request
    -> rank_recipes(request, app.state recipe snapshot,
                    INGREDIENT_REGISTRY)

lifespan shutdown
    -> no database connection to close
```

Using lifespan is required because catalog availability is a startup
precondition and import-time file creation would make tests, tooling, and
module inspection mutate local state. Deprecated startup/shutdown event
decorators are not used.

The synchronous route and pure ranking function remain synchronous. No async
driver or thread-sharing option is necessary because requests do not hold a
database connection. The route keeps its existing unresolved-exclusion `422`
mapping and otherwise returns the unchanged `RankingResponse`.

The immutable startup snapshot is not a second source of truth; it is the
validated in-process representation of the durable source for an application
lifetime. Because Feature 003 has no recipe writes, refreshing it per request
would add I/O and failure modes without changing observable data. A future
runtime recipe-write feature must define snapshot invalidation or request-time
reads as part of that feature.

## Connection and transaction lifetimes

Every store operation creates a connection for one bounded purpose and closes
it explicitly. A connection context manager controls commit/rollback, while an
explicit closing context controls resource lifetime; the design does not rely
on Python's connection context manager to close the handle.

- Migration connection: open for migration and seed orchestration, then close.
- Migration transaction: one explicit controlled transaction per schema
  version, containing every DDL statement and its `user_version` update.
- Seed transaction: one transaction for all approved recipes and
  relationships.
- Hydration connection: a new read connection, closed after the immutable
  tuple is constructed.
- Request: no connection and no transaction.

SQLite's default journal mode and locking are sufficient for startup-only
writes and a read-only runtime catalog. WAL, pooling, retries, busy-loop logic,
and global locks are not justified.

## Data flow

```text
INITIAL_RECIPE_CATALOG (seed-only)
    -> existing Recipe + registry validation
    -> only if migrated durable tables are empty
    -> atomic insert into SQLite

SQLite recipes + ordered recipe_ingredients (production truth)
    -> close initialization connection
    -> reopen and run schema/integrity checks
    -> ordered row aggregation
    -> existing load_catalog / Recipe validation
    -> immutable startup snapshot
    -> rank_recipes(request, recipes, INGREDIENT_REGISTRY)
    -> unchanged RankingResponse
```

The seed arrow stops after initialization. There is no arrow from seed data to
the route.

## Ranking-parity contract

Persistence changes only how the `Sequence[Recipe]` argument is produced.
`rank_recipes` and its scoring helpers remain unaware of SQLite.

For equivalent recipe data, Feature 003 preserves:

- preparation-time hard filtering and inclusive maximum behavior;
- ingredient-exclusion hard filtering;
- fail-closed unresolved exclusions;
- canonical and explicit-alias resolution;
- unresolved pantry abstention;
- pantry coverage, protein fit, and time fit;
- weights `0.70`, `0.20`, and `0.10`;
- full-precision component calculation and four-decimal contribution
  rounding;
- reconstructable four-decimal final score;
- fixed explanation text;
- required, matched, and missing canonical-name evidence;
- recipe ingredient order in all evidence;
- ingredient-resolution evidence and request-term order;
- final score-descending, recipe-ID-ascending result order;
- limit application after sorting; and
- `returned_count == len(results)`.

Neither SQLite insertion order nor unspecified row order is accepted as
semantic input. Relationship order is explicit data; result order remains an
explicit ranking rule.

## Failure behavior and minimal diagnostics

Startup is fail-fast. The API does not serve an empty catalog or fall back to
Python seed data when storage cannot be trusted.

- **Unavailable path, permission, lock, or I/O failure:** initialization or
  hydration raises a catalog-store startup error, chains the original SQLite
  exception, and prevents lifespan startup from completing.
- **Missing database:** treated as a fresh store and initialized.
- **Unsupported newer schema:** rejected with found and supported version
  numbers; no downgrade is attempted.
- **Known older schema:** migrated forward transactionally.
- **Missing/partial schema or failed migration:** the failing migration rolls
  back and startup stops.
- **Partial seed:** atomic insertion prevents a crash from committing a
  prefix. Mismatched non-empty table state fails rather than being repaired.
- **Invalid/corrupt durable records:** SQLite consistency/foreign-key checks or
  domain hydration fail the complete load and startup stops.
- **Unexpected ranking failure:** existing FastAPI behavior remains a generic
  `500` without internal details.

Minimal server-side error context is the operation (`migrate`, `seed`, or
`load`), configured database path, and schema version when relevant. SQL text,
row payloads, request contents, and secrets are not added to public responses.
No request ID is added because all new persistence failures occur before
requests and there is no cross-service trace to correlate.

After successful startup, removal or unavailability of the database file does
not invalidate the already validated immutable snapshot. Existing requests
continue until restart; the next startup fails. This is an explicit consequence
of the read-only runtime design, not a claim of live database monitoring.

## Testing and evidence strategy

Implementation must retain the existing Feature 001/002 tests and add focused
evidence at the boundary that owns each rule. All durable tests use a unique
file below pytest's `tmp_path`; no test reads or mutates the developer's
default database.

### Domain and unit tests

Existing `Recipe`, catalog-loader, ranking, and ingredient-resolution tests
remain the domain baseline. Focused additions cover aggregation of ordered
relationship rows into raw recipe mappings and ensure no recipe with zero
relationships disappears.

These tests do not mock SQLite for behavior that SQLite owns.

### Persistence and hydration tests

Real isolated SQLite files prove:

- valid rows hydrate to the expected frozen `Recipe` tuple;
- recipe ingredients follow stored `position`, not insertion or fetch order;
- duplicate recipe IDs and duplicate ingredient relationships are rejected by
  real constraints;
- unknown ingredient IDs fail registry validation;
- out-of-band text/blob numeric values and non-integer preparation values that
  remain those SQLite storage classes fail the real `typeof` constraints;
- a malformed numeric value SQLite can legally store under the basic checks,
  such as non-negative non-finite nutrition, fails complete Pydantic hydration;
- empty ingredient sets and any other invalid durable values fail complete
  hydration;
- foreign-key violations and missing schema objects fail deterministically;
  and
- a bad recipe is not skipped while valid siblings are returned.

### Schema and migration tests

Tests call the real migration runner against file-backed SQLite databases and
assert:

- a fresh version-0 file reaches the current `user_version` and exact required
  tables/constraints;
- rerunning migration at the current version is a no-op;
- a database with a newer version is rejected;
- a real file-backed version-0 database is prepared with a conflicting second
  migration-owned table so migration 1 successfully creates its first table
  and then fails partway through; after failure, the newly created first table
  is absent, the pre-migration schema is otherwise unchanged, and
  `user_version` remains `0`;
- a database claiming current version with a missing table fails the real
  loader.

Mocks or assertions against a copied SQL string are insufficient migration
evidence.

### Initialization and durability tests

File-backed tests prove:

- a fresh migrated empty store receives exactly the four approved recipes and
  ordered relationships;
- running initialization again does not duplicate or overwrite data;
- mismatched partial table state fails;
- after all connections close, a new connection loads the same validated
  recipes; and
- an isolated durable change to a non-empty record survives reinitialization
  and reconnection, proving the Python seed is not a competing runtime source.

The last test is storage evidence only, not a public recipe mutation feature.

### Ranking parity and contract tests

Parity tests build two catalogs from equivalent data:

1. the seed records passed directly through the existing catalog loader; and
2. the same records inserted into an isolated database in deliberately
   different recipe and relationship insertion order, then reloaded through
   the durable path.

For representative requests, tests compare the complete externally meaningful
`RankingResponse` values rather than only recipe IDs or scores. Cases cover:

- canonical pantry input;
- supported aliases;
- unresolved pantry terms;
- supported canonical and alias exclusions;
- a fail-closed unresolved exclusion and its complete evidence;
- multiple eligible recipes;
- equal-score recipes inserted in reverse ID order;
- ingredient evidence order;
- complete score breakdowns and explanations;
- post-sort limits; and
- `returned_count`.

The tie case uses a focused local recipe fixture if the approved four recipes
do not naturally tie. Expected and durable paths both call the same unchanged
`rank_recipes` function; the test is a storage/domain contract, not a second
copy of ranking arithmetic.

### API tests

API tests construct an app with a unique `tmp_path` database and use
`TestClient` as a context manager so the real lifespan runs. They retain the
existing exact success, validation, fail-closed, determinism, and generic-500
assertions. New tests prove:

- the normal endpoint response came from the initialized durable catalog;
- startup creates and loads a fresh store;
- unavailable storage prevents startup instead of serving a fallback; and
- a persisted non-empty catalog value is reflected after app restart.

### Regression and evaluation evidence

The complete existing suite remains Feature 001/002 regression coverage. The
committed Feature 002 command remains mandatory:

```text
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
```

It must continue to report strictly improved recall and zero false positives.
The evaluation uses only the code-owned ingredient registry and therefore
should not acquire a database dependency.

Final implementation verification must include Issue #5's lock, full test,
evaluation, Ruff, and diff checks plus any focused migration command documented
by implementation. This design stage does not run or prescribe a task-by-task
implementation sequence.

## Dependency implications

No runtime or development dependency is added. `pyproject.toml` and `uv.lock`
should remain unchanged. The design uses only Python 3.12 standard-library
modules, existing Pydantic validation, and FastAPI's installed lifespan
mechanism.

If implementation appears to require SQLAlchemy, SQLModel, Alembic, an async
SQLite driver, a settings package, or a migration CLI, work must stop and show
the present requirement that the standard-library design cannot meet.

## Operational and local-development behavior

- The application database is a single file and must be ignored by Git.
- A documented `PANTRYPILOT_DB_PATH` overrides the local relative default.
- Tests always pass explicit temporary absolute paths.
- Importing `pantrypilot.app` does not create a file; entering lifespan does.
- Starting the app against a fresh path performs migration and initial seed
  automatically, then serves the durable snapshot.
- Starting against an invalid, unavailable, or unsupported store fails before
  accepting requests.
- There is no separate database server, daemon, container, migration service,
  or manual seed command for version 1.
- Backups and concurrent writers are outside Feature 003 because the product
  has no recipe write path. The database file itself is the durable artifact.

Automatic startup migration is proportionate for this local single-process
portfolio application. If later deployment has multiple concurrent instances
or independently managed releases, migration execution should move to an
explicit deployment step before those instances start.

## Learning goals

The Feature 003 learning document and guided mock interview should enable the
owner to explain:

- how process-memory state differs from file-backed durable state;
- why stable recipe and ingredient IDs are data contracts rather than display
  text;
- primary keys, foreign keys, unique constraints, checks, and relationship
  tables;
- why relationship order must be modeled explicitly;
- schema versioning and forward migrations;
- the difference among migration, seeding, and runtime mutation;
- why durable source-of-truth ownership forbids a silent Python fallback;
- transaction atomicity and connection lifetime;
- why SQLite foreign keys are enabled per connection;
- which guarantees belong in storage, domain validation, or both;
- how rows hydrate into validated immutable domain objects;
- why ranking consumes domain recipes instead of storage rows;
- why database row order is not application or ranking semantics;
- migration, integration, restart, API, and parity test distinctions;
- why standard-library SQLite fits now and what would justify an ORM or
  migration framework later;
- why pantry and request persistence remain separate future features;
- why retrieval waits for catalog scale; and
- why quantities and units wait for optimization and waste-management work.

The later learning document must include concrete commands, worked schema and
transaction examples, limitations, exercises, and guided mock-interview
questions. It is an implementation deliverable, not part of this design-only
stage.

## Future compatibility and explicit deferrals

The design preserves only seams that current code already needs or that the
chosen durable contract naturally provides:

- Stable recipe IDs permit later references from pantry, plan, or feedback
  records.
- Stable ingredient IDs permit later registry persistence or foreign keys
  without changing recipe meaning.
- Ordered schema migrations permit new tables and columns.
- The relationship table can support later retrieval after a measured query
  and index are designed.
- The pure `rank_recipes` boundary permits future retrieval to supply a
  candidate `Sequence[Recipe]` without coupling scoring to SQL.
- The application-construction seam permits isolated stores in tests.

Feature 003 does not create interfaces for alternate databases, storage
plugins, repository implementations, unit-of-work objects, catalog mutation,
cache invalidation, multi-process coordination, or retrieval. Those seams
should be designed with the feature that first needs them.

## Risks and trade-offs

### Code-owned ingredients cannot have a database foreign key

The database cannot independently reject an unknown canonical ingredient ID.
Hydration must consult the registry and fail startup. This is acceptable
because Feature 003 intentionally persists recipes only and every production
read hydrates through that boundary. Persisting ingredient rows merely to gain
a foreign key would duplicate registry ownership.

### Startup snapshot does not observe live out-of-band edits

The API reads the catalog once per application lifespan. Direct database edits
become visible after restart, not during the running process. There is no
approved write path, so request-time reloads or invalidation are unnecessary.

### Automatic migrations couple startup to write access

A fresh or old supported store requires startup write permission. This is
simple for current local deployment and is tested fail-fast. A later managed
deployment may need a separate migration phase.

### Hand-written migrations require discipline

The project owns version ordering, transactions, and SQL review. With one
schema and two tables this is transparent educational value. If migration
volume or concurrent deployment makes it error-prone, Alembic becomes
justified.

### Relative default paths depend on the working directory

The simple default can create different files when the process starts from
different directories. Documentation must state this clearly and recommend an
absolute `PANTRYPILOT_DB_PATH` outside quick-start development. Adding a
platform-specific settings dependency is not justified for this feature.

### Valid out-of-band deletions are durable truth

Initialization deliberately does not compare a non-empty catalog with the seed.
A manually altered but still domain-valid smaller catalog is accepted because
the database owns recipe truth. Deleting every recipe is the one exception:
empty tables are Feature 003's explicit uninitialized sentinel and will be
seeded on restart. Detecting unauthorized edits or supporting an intentionally
empty catalog would require explicit catalog administration/state outside this
scope.

## Acceptance mapping to Issue #5

| Issue #5 requirement | Design decision and later evidence |
|---|---|
| Normal ranking path uses durable recipes | FastAPI lifespan hydrates only from SQLite and publishes that snapshot; no production `CATALOG` or fallback remains. |
| Restart/reconnection durability | Initialization closes, hydration reopens, and file-backed tests close/reopen again. |
| Reproducible schema and explicit version | Ordered real migrations plus `PRAGMA user_version`; migration tests inspect the real file. |
| Stable recipe and ingredient identities | Recipe primary key stores stable recipe ID; relationship rows store Feature 002 IDs. |
| Ingredient ordering | Explicit non-negative `position`, unique per recipe, read with `ORDER BY`. |
| Duplicate recipe/reference rejection | Primary and unique constraints plus existing domain validation. |
| Unknown ingredient rejection | Seed and hydration validate every ID against code-owned `INGREDIENT_REGISTRY`; startup aborts. |
| Invalid durable data rejection | SQLite checks/integrity checks plus complete Pydantic hydration before app state publication. |
| Unavailable/unmigrated/corrupt behavior | Missing fresh stores initialize; unsupported/partial/unavailable/corrupt stores fail lifespan with no fallback. |
| Isolated real storage tests | Every test gets a file under `tmp_path`; migrations and reopen behavior are not mocked. |
| Ranking parity independent of row order | Equivalent direct/durable catalogs compare complete responses after reversed insertion; ranking still sorts score then ID. |
| Existing score/filter/evidence contract | `rank_recipes` signature and implementation semantics stay unchanged; full responses and exceptions are parity-tested. |
| Post-sort limit and returned count | Complete parity assertions plus existing ranking/API regressions. |
| Feature 002 evaluation | Existing versioned evaluation remains database-independent and mandatory in final verification. |
| One recipe source of truth | Seed applies only to an empty store; non-empty durable data is never reconciled or replaced. |
| Documentation and learning | Later implementation updates README/current product boundary and adds Feature 003 learning, exercises, and mock interview questions. |
| No scope expansion | Recipe-only SQLite schema; no pantry, request history, retrieval, quantities, CRUD, ORM, or tracing work. |

## Design self-review

- The database, ingredient registry, seed, and in-memory snapshot each have one
  explicit and non-competing ownership role.
- Migration, seeding, loading, and request behavior are distinct.
- SQLite storage guarantees are limited to explicit post-affinity
  storage-class/basic checks; complete finite numeric semantics remain a
  whole-catalog Pydantic hydration responsibility.
- Every migration version places all DDL and its `user_version` update in one
  explicit atomic transaction, with a real partial-failure rollback test.
- Every required failure class has a deterministic outcome; none falls back to
  an empty or in-code production catalog.
- Storage row order has no implicit semantic role.
- Ranking behavior and the public request/response contract do not change.
- The design adds one concrete store boundary and one necessary app-construction
  seam, not speculative storage infrastructure.
- The schema contains only current recipe facts and ordered ingredient IDs.
- Pantry persistence, request history, retrieval, quantities, and tracing are
  explicitly deferred.
- There are no unresolved placeholders or implementation decisions hidden
  behind generic phrases.

## Scope conclusion

Feature 003 is one coherent durability slice: a dependency-free two-table
SQLite catalog, one explicit schema version and migration runner, atomic
seed-only initialization, validated reconnect hydration, FastAPI lifespan
integration, parity/durability evidence, and the required learning material.
It changes where recipes live and nothing about what ranking means.
