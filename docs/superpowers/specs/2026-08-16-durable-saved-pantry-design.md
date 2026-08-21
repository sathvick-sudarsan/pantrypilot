# Feature 004: Durable saved pantry and ranking integration

Status: Approved

Design date: 2026-08-16

Approved: 2026-08-16

GitHub issue: #7

## Summary

Feature 004 adds one durable, application-local current pantry to PantryPilot.
A caller can atomically establish or replace it, inspect it, and rank meals from
it without resending the pantry. The existing inline
`POST /v1/meal-rankings` contract remains unchanged.

The saved pantry is a singleton resource at `/v1/saved-pantry`. Whole-resource
replacement resolves every submitted string through the existing Feature 002
registry before opening a write transaction. If any term is unresolved, the
complete replacement is rejected with deterministic `422` evidence and the
previous pantry remains unchanged. Successful writes persist only deduplicated
canonical ingredient IDs.

Schema version 2 adds one singleton marker table and one canonical-ID item
table. The marker distinguishes an absent pantry from an intentionally saved
empty pantry. Saved-pantry reads use short-lived SQLite connections and
validate the complete state against the code-owned ingredient registry.
Inspection and saved ranking read the durable pantry on every request; there is
no cache or pantry snapshot to invalidate.

Saved ranking converts the validated canonical IDs to current canonical names,
constructs the existing `RankingRequest`, and calls the unchanged pure
`rank_recipes` function against the immutable startup recipe snapshot. Feature
004 changes durable pantry state and API orchestration, not scoring,
eligibility, resolution, explanation, ordering, limiting, or count semantics.

## Verified context

The design was prepared from branch `feat/durable-saved-pantry` at Feature 003
merge commit `c988a9b83711490d2c28e365d62b562b7b357eaf`, with a clean worktree.
Issue #7 defines the feature boundary but deliberately leaves the detailed API,
schema, lifecycle, and composition choices to this design.

The current implementation establishes these useful boundaries:

- `ingredients.py` owns stable canonical ingredient IDs, names, explicit
  aliases, deterministic resolution, and abstention.
- `ranking.py` owns the pure ranking pipeline and receives a validated
  `RankingRequest`, recipe sequence, and ingredient registry.
- `catalog_store.py` owns the current version-1 connection, migration, recipe
  seed, integrity, and hydration behavior using standard-library `sqlite3`.
- FastAPI lifespan migrates the database and publishes an immutable recipe
  snapshot. Existing ranking requests perform no recipe database work.
- Complete durable/direct parity tests already protect ranking scores,
  explanations, evidence, ordering, limiting, and `returned_count`.

Feature 004 preserves those foundations while accepting that pantry reads and
writes are necessarily request-time storage operations.

## Product boundary

### One application-local current pantry remains the smallest honest boundary

The singleton assumption was challenged during design and remains appropriate.
The current product has one local application process and no user, account,
ownership, authentication, sharing, or multi-pantry concept. The immediate
problem is remembering what is presently available, not managing a pantry
collection.

A singleton solves that present problem with one explicit limitation: every
caller of this local application observes and replaces the same current pantry.
That limitation is documented rather than hidden. Adding owner IDs or multiple
pantry IDs now would create product concepts with no current source or behavior.

### Goals

- Atomically establish or replace one saved pantry.
- Inspect the saved pantry in deterministic order.
- Rank from the saved pantry without resubmitting pantry items.
- Keep the inline ranking request and behavior backward compatible.
- Store only canonical ingredient IDs and validate them against the code-owned
  registry on every durable read.
- Distinguish an absent pantry from an intentionally empty pantry.
- Migrate real version-1 databases to version 2 without changing recipe data.
- Use short-lived synchronous SQLite connections and explicit transactions.
- Define deterministic, privacy-safe request-time failure behavior.
- Prove complete ranking parity through the existing ranking implementation.

### Non-goals

Feature 004 does not add users, authentication, authorization, ownership,
sharing, multiple pantries, item-level CRUD, quantities, units, conversions,
purchase or expiration metadata, prices, grocery lists, substitutions,
multi-meal planning, waste optimization, pantry history, ranking history,
analytics, feedback, recipe CRUD, ingestion, catalog expansion, retrieval,
search indexes, embeddings, fuzzy or learned resolution, ranking changes,
personalization, ML, LLMs, agents, frontend work, microservices, a database
server, caching infrastructure, distributed coordination, multi-process write
coordination, an async SQLite driver, a pool, a retry framework, or a generic
repository/unit-of-work layer.

Existing unbounded inline `pantry_items` and `excluded_ingredients` lists remain
unchanged for compatibility. Their broader hardening is not pulled into this
feature.

## Approaches considered

### 1. Normalized singleton tables with request-time reads — recommended

Store one marker row for established state and one row per canonical ingredient
ID. Replace all rows in one `BEGIN IMMEDIATE` transaction. Read and validate the
durable state for each inspection and saved-ranking request.

Advantages:

- clean absent-versus-empty semantics;
- primary-key duplicate protection and foreign-key relationship integrity;
- canonical IDs remain individually inspectable;
- atomic replacement is straightforward to prove with real SQLite;
- each request observes committed durable truth with no invalidation protocol;
- migration 2 is two explicit tables in the existing migration mechanism.

Cost: saved ranking performs one small local SQLite read. With one pantry and
four recipes, that cost is proportionate and simpler than cache correctness.

### 2. One singleton row containing a JSON array

A single row could distinguish absence from empty and make replacement one
`UPDATE`. It would use less relational schema.

It is rejected because duplicate detection, element typing, nonblank values,
ordering, and canonical-ID validation would all become application parsing
rules over an opaque text payload. Corrupt JSON would create another failure
surface, and SQLite could not enforce one row per canonical fact. The schema is
shorter but the durable contract is weaker and less inspectable.

### 3. Normalized tables plus an in-memory pantry snapshot

Startup could load the pantry and successful writes could replace an in-memory
copy used by reads and ranking.

It is rejected because request-time writes create a cache-coherence problem
that Feature 003 does not have. Correctness would require synchronized
write/commit/snapshot publication, explicit behavior after commit succeeds but
memory publication fails, and protection from out-of-band changes. A direct
read is cheaper to own at the approved local scale and makes stale state
impossible within the supported database contract.

| Criterion | Normalized + direct read | JSON singleton | Normalized + memory snapshot |
|---|---|---|---|
| Current complexity | Two small tables and concrete read/write functions | One table plus JSON parsing/validation | Two tables plus synchronization and publication rules |
| Correctness | Database keys plus complete registry hydration | Most element integrity moves into application parsing | Durable integrity plus a second freshness invariant |
| Migration | Two additive DDL statements in migration 2 | One additive table, but an opaque payload contract | Same two tables plus startup snapshot behavior |
| Testability | Real constraints, rollback, reopen, and ordered reads | Corrupt-payload and parser cases dominate | Must prove commit/cache atomicity and stale-state prevention |
| Decision | Recommended | Rejected: weaker durable contract | Rejected: no measured need for caching |

## Public API

### Saved pantry representation

Successful replacement and inspection return the same representation:

```json
{
  "pantry_items": [
    {
      "ingredient_id": "black-beans",
      "canonical_name": "black beans"
    },
    {
      "ingredient_id": "olive-oil",
      "canonical_name": "olive oil"
    }
  ]
}
```

Items are ordered by ascending canonical ingredient ID. The stored ID supplies
identity; `canonical_name` is looked up from the current code-owned registry and
is never stored in the pantry tables. The response has no redundant count,
timestamp, version, raw input, owner, or history field.

### Replace or establish the pantry

```http
PUT /v1/saved-pantry
Content-Type: application/json
```

Request:

```json
{
  "pantry_items": ["black bean", "olive oil", "BLACK BEANS"]
}
```

The request model forbids unknown fields and applies these new-write-only
bounds:

- `pantry_items` may contain zero through 100 strings;
- each string may contain at most 100 characters;
- each string must be nonblank after trimming.

An empty list is valid and establishes an intentionally empty pantry.

The operation resolves every occurrence in input order before any database
mutation. Canonical terms and reviewed aliases resolve through the existing
registry. Multiple terms resolving to one canonical ID are deduplicated. Input
order does not become durable state.

If all terms resolve, the operation atomically replaces the complete pantry and
returns `200` with the saved representation. Creation and replacement use the
same status because callers do not need a mode-dependent contract. Repeating a
request that resolves to the same canonical ID set has the same durable state
and response, so `PUT` is semantically idempotent.

If any term is unresolved, the operation returns `422`, performs no write, and
preserves the prior pantry:

```json
{
  "detail": {
    "type": "unresolved_pantry_items",
    "message": "All pantry items must resolve before saving.",
    "ingredient_resolution": {
      "pantry_items": [
        {
          "input": "groundnut",
          "normalized": "groundnut",
          "ingredient_id": null,
          "canonical_name": null,
          "match_type": "unresolved"
        }
      ]
    }
  }
}
```

The evidence contains one existing `IngredientResolution` record for every
submitted occurrence, including resolved terms and duplicates, in request
order. It is returned to the caller but not persisted or logged by this
feature.

Pydantic shape, type, blank, length, list-size, and unknown-field failures keep
FastAPI's existing deterministic `422` validation transport.

### Inspect the pantry

```http
GET /v1/saved-pantry
```

An established pantry returns `200` with the saved representation. An
established empty pantry returns:

```json
{
  "pantry_items": []
}
```

If no pantry has ever been established, the endpoint returns:

```json
{
  "detail": {
    "type": "saved_pantry_not_found",
    "message": "No saved pantry has been established."
  }
}
```

with status `404`.

### Rank from the saved pantry

```http
POST /v1/saved-pantry/meal-rankings
Content-Type: application/json
```

The request contains the existing ranking constraints except `pantry_items`:

```json
{
  "min_protein_g": 25.0,
  "max_prep_minutes": 30,
  "excluded_ingredients": ["peanuts"],
  "limit": 5
}
```

The numeric, exclusion, unknown-field, and non-finite validation semantics are
the same as the corresponding fields on `RankingRequest`. The existing
`excluded_ingredients` list remains unbounded in this feature. Unsupported
exclusions still fail closed with the existing deterministic
`unresolved_excluded_ingredients` `422` contract.

An established pantry returns the existing `RankingResponse` unchanged. An
empty saved pantry is valid and ranks with zero pantry coverage. An absent
pantry returns the same `404 saved_pantry_not_found` contract as inspection.

### Inline ranking compatibility

`POST /v1/meal-rankings` and its `RankingRequest` are unchanged. In particular,
`pantry_items` remains required, and omission never means "use saved pantry."
No source flag, union request, optional field, or mode-dependent validation is
added.

## Canonical identity and write resolution

Durable pantry state contains canonical ingredient IDs only. It does not store
canonical names, aliases, normalized terms, original strings, unresolved text,
or resolution evidence.

The replacement flow is:

```text
bounded validated pantry strings
    -> existing deterministic resolver for every occurrence
    -> if any unresolved: return complete 422 evidence; stop
    -> canonical ingredient-ID set
    -> sort by canonical ID
    -> validate IDs against INGREDIENT_REGISTRY defensively
    -> one atomic durable replacement
```

Rejecting the complete write is intentionally stricter than inline ranking,
where unresolved pantry terms are visible abstentions. Inline ranking is a
one-shot calculation and can honestly show that an item did not match. A saved
pantry claims to represent current durable state; silently dropping an item
could misrepresent what the user believes was saved. Persisting unresolved raw
text would create a second durable identity form plus future re-resolution and
rename semantics that are outside this feature.

No fuzzy matching, plural rule, substring match, candidate list, confidence,
embedding, or learned behavior is introduced.

## Absent and empty state

The two states are deliberately distinct:

| Durable state | Meaning | GET | Saved ranking |
|---|---|---|---|
| No singleton marker row | Never established | `404` | `404` |
| Marker row, zero item rows | Intentionally empty | `200`, empty list | `200`, zero coverage |
| Marker row and item rows | Established non-empty pantry | `200` | `200` |

Migration from Feature 003 creates the schema but does not insert the marker,
so every upgraded application begins with an absent pantry. A `PUT` always
inserts the marker, including for an empty item list. There is no delete/reset
endpoint in Feature 004; replacement with empty means established empty, not
absent.

## Schema version 2

Feature 004 advances the shared SQLite database from `user_version = 1` to
`user_version = 2`.

Migration 2 adds exactly these tables:

```sql
CREATE TABLE saved_pantry (
    id INTEGER PRIMARY KEY NOT NULL
        CHECK (id = 1)
)
```

```sql
CREATE TABLE saved_pantry_items (
    pantry_id INTEGER NOT NULL
        CHECK (typeof(pantry_id) = 'integer' AND pantry_id = 1)
        REFERENCES saved_pantry(id) ON DELETE CASCADE,
    ingredient_id TEXT NOT NULL
        CHECK (length(trim(ingredient_id)) > 0),
    PRIMARY KEY (pantry_id, ingredient_id)
)
```

`saved_pantry.id = 1` makes the singleton constraint explicit. The child
primary key prevents duplicate canonical facts. The foreign key prevents item
rows without established state and cascades the old item set when replacement
deletes the marker. The nonblank check protects the basic stored-text boundary.

There is deliberately no item position: inspection orders by canonical ID and
request order has no approved product meaning. There is no ingredient table or
foreign key to one, because `INGREDIENT_REGISTRY` remains the canonical
vocabulary authority. There are no timestamps, owner IDs, quantities, history,
or future-only indexes.

### Forward migration behavior

The existing ordered `PRAGMA user_version` mechanism remains authoritative.
For a version-1 database, migration 2 executes:

```text
BEGIN IMMEDIATE
  -> CREATE saved_pantry
  -> CREATE saved_pantry_items
  -> PRAGMA user_version = 2
  -> COMMIT
```

Statements execute individually. `executescript` remains prohibited. Any DDL,
version-update, or commit failure triggers explicit rollback and leaves the
database at version 1 with its pre-migration schema and recipe rows.

Migration behavior is:

- fresh version 0: apply migration 1, then migration 2, then perform the
  existing recipe seed logic;
- real version 1: add only the pantry tables and preserve every recipe and
  relationship row row-for-row and value-for-value;
- current version 2: no-op;
- newer version: fail deterministically without downgrade or mutation;
- conflicting or partial version-1 schema: fail and roll back version 2;
- a database claiming version 2 without usable required tables: fail startup
  or request validation rather than repairing or adopting it.

No pantry seed runs. Absence after migration is valid product state.

### Migration evidence

Real file-backed tests must prove:

- a fresh file reaches version 2 with all four exact tables;
- a real version-1 database containing non-default recipe values migrates and
  retains the complete recipe and relationship rows row-for-row and
  value-for-value;
- migration 2 reruns as a current-version no-op;
- a newer version remains unchanged and fails deterministically;
- a real migration-2 second-DDL conflict rolls back the first new table and
  leaves `user_version = 1`;
- a synthetic deferred commit failure after the traced
  `PRAGMA user_version = 2` rolls back the synthetic schema/data and restores
  `user_version = 1`.

The last two tests separately prove partial-DDL rollback and the stronger claim
that an already executed version update shares the migration transaction.

## Integrity and validation boundaries

### Pydantic and HTTP

- enforce the new write list and item bounds;
- reject blank strings and unknown request fields;
- retain the existing strict numeric and non-finite ranking validation;
- serialize deterministic safe public error bodies.

### Ingredient resolution

- normalize with the existing trim/lower rule;
- resolve only canonical names and reviewed aliases;
- preserve per-occurrence input evidence for a rejected write;
- reject the complete write if any occurrence is unresolved;
- deduplicate equivalent resolved IDs before persistence.

### SQLite

- permit at most the singleton marker identity;
- reject orphan pantry items through the foreign key;
- reject duplicate `(pantry_id, ingredient_id)` rows;
- reject null or blank stored IDs;
- make replacement and migration atomic;
- expose committed old or new state, never an intermediate replacement.

### Durable read validation

Every saved-pantry read:

- requires schema version 2;
- checks pantry foreign-key integrity;
- distinguishes no marker from a marker with zero items;
- reads all item IDs in explicit ascending ID order;
- rejects any stored ID absent from `INGREDIENT_REGISTRY`;
- maps all IDs to current canonical names only after the complete set validates;
- never skips a malformed row or returns a partially valid pantry.

An out-of-band syntactically valid but unknown ID cannot be prevented by a
normal SQLite foreign key. Complete registry-backed hydration is therefore the
authoritative semantic check. Duplicating registry rows into SQLite solely for
an FK remains rejected.

## Storage responsibilities

Feature 004 creates a real second use of the database connection and migration
mechanism. One small extraction is now justified:

- a concrete database module owns the single connection setup,
  `CURRENT_SCHEMA_VERSION`, ordered migrations, and migration transaction;
- recipe-specific seeding, catalog integrity, aggregation, and `Recipe`
  hydration remain in the catalog store;
- pantry-specific replacement and validated read behavior live in a pantry
  store;
- FastAPI owns raw-request resolution and HTTP error mapping;
- `rank_recipes` remains unaware of every storage module.

This is not a repository framework. There is one SQLite database, one concrete
connection function, one linear migration authority, and concrete recipe and
pantry functions. No protocol, alternate implementation, engine, session,
factory, service layer, generic transaction callback, or unit-of-work object is
introduced.

Keeping two separate migration runners or two `user_version` constants would
be unsafe duplication because both aggregates share one file. Conversely,
moving recipe seed/hydration into generic helpers would erase useful domain
boundaries without a second implementation.

The expected concrete ownership is:

| Path | Responsibility |
|---|---|
| `src/pantrypilot/database.py` | Shared SQLite connection setup, schema version 2, ordered migrations, and atomic migration runner |
| `src/pantrypilot/catalog_store.py` | Existing recipe seed, catalog integrity, ordered aggregation, and validated `Recipe` hydration |
| `src/pantrypilot/pantry_store.py` | Atomic singleton replacement and complete validated pantry reads |
| `src/pantrypilot/models.py` | Bounded saved-pantry write model, saved-pantry representation, and saved-ranking constraint model |
| `src/pantrypilot/app.py` | Lifespan migration/catalog publication, raw write resolution, endpoint orchestration, and safe HTTP error mapping |

The extraction is mechanical for existing catalog callers: catalog behavior
and its persistence tests retain the same contracts while importing the one
shared connection and migration authority.

## Request-time connection and transaction lifecycle

All application-owned connections retain Feature 003's explicit
`isolation_level=None`, `sqlite3.Row`, verified `PRAGMA foreign_keys = ON`, and
caller-owned closure.

### Replacement

Resolution and canonical-ID validation finish before a connection is opened.
A valid replacement then uses one short-lived connection and one explicit write
transaction:

```text
open
  -> require schema version 2
  -> BEGIN IMMEDIATE
  -> DELETE saved_pantry id 1 (cascade old items)
  -> INSERT saved_pantry id 1
  -> INSERT sorted canonical item IDs
  -> COMMIT
close
```

Any statement or commit failure triggers rollback before close. Because the old
state is deleted inside the transaction, a failed replacement restores the
complete previous marker and item set. Validation failure opens no connection
and cannot mutate state.

The success response is constructed from the already validated canonical set
after commit. It does not perform a second read whose failure could make a
successfully committed write appear to have failed.

### Inspection and saved ranking

Each operation opens one short-lived read connection. An explicit read
transaction covers the schema-version check, targeted foreign-key check, marker
read, ordered item read, and registry validation, providing one consistent
snapshot. It then commits the read transaction and closes the connection.

There is no application-wide connection, pool, cache, or shutdown database
resource. Recipe ranking still uses the immutable startup recipe tuple; only
the saved pantry is read at request time.

### Freshness

A successful write is visible to later GET and saved-ranking requests because
they open new connections and read committed durable state. A read overlapping
a write observes either the complete previously committed pantry or the
complete newly committed pantry according to SQLite's transaction snapshot; it
never observes the delete/insert intermediate state.

## Concurrency contract

The supported scope remains one local application process. SQLite's native
locking and the standard `sqlite3.connect` five-second timeout are sufficient;
no new timeout configuration is introduced.

- `BEGIN IMMEDIATE` serializes overlapping writers before mutation starts.
- Every successful replacement is atomic.
- If multiple replacements succeed, the last successfully committed
  replacement is current: last-write-wins.
- Arrival order is not promised; commit order is the only durable order.
- A writer that cannot obtain or complete its transaction within the SQLite
  timeout fails safely and does not partially replace the pantry.
- Reads see a complete committed snapshot.

No ETag, revision number, compare-and-swap field, optimistic conflict response,
application mutex, retry loop, WAL requirement, distributed lock, or
multi-process guarantee is added. Those mechanisms need an actual concurrent
editing product requirement.

Real SQLite tests should hold a write lock from one connection, prove a second
write fails safely without changing the committed pantry, release the lock,
and prove a later replacement succeeds and becomes visible.

## Ranking integration

The pure ranking domain remains unchanged. The saved route performs only
orchestration:

```text
validated saved-ranking constraints
    + validated durable canonical pantry IDs
    -> current canonical names in canonical-ID order
    -> existing RankingRequest(pantry_items=canonical names, constraints=...)
    -> rank_recipes(request, app.state.recipe_catalog, INGREDIENT_REGISTRY)
    -> existing RankingResponse
```

Using canonical names deliberately routes saved state through the same
resolution, exclusion, matching, scoring, explanation, sorting, limiting, and
response construction as inline requests. Persistence does not enter
`is_eligible`, `match_ingredients`, `calculate_score`, `render_explanation`,
`sort_ranked_recipes`, or `limit_ranked_recipes`.

The saved response's pantry resolution evidence is deterministic canonical
evidence generated from current canonical names in canonical-ID order. Original
write aliases, duplicates, casing, and whitespace are not available because
they are intentionally not durable state. This is the only provenance
difference.

### Full parity definition

For a saved pantry and an inline request whose `pantry_items` are the saved
pantry's canonical names in canonical-ID order, with identical constraints,
the complete `RankingResponse` values must be equal. This protects:

- eligibility and hard preparation-time filtering;
- hard canonical/alias exclusions and unresolved-exclusion fail-closed errors;
- pantry coverage, protein fit, and time fit;
- weights `0.70`, `0.20`, and `0.10`;
- full-precision calculation and four-decimal contributions;
- reconstructable final scores;
- fixed explanations;
- required, matched, and missing ingredient evidence and order;
- ingredient-resolution evidence;
- result ordering by `(-final_score, recipe.id)`;
- post-sort `limit`; and
- `returned_count`.

An additional alias/duplicate replacement test proves that the stored pantry
canonicalizes to the expected set and that ranked result objects equal the
canonical inline request. It does not pretend that discarded raw write
provenance survives in the later ranking response.

## Deterministic ordering

Three order rules remain separate:

1. Saved pantry inspection and saved ranking input use ascending canonical
   ingredient ID.
2. Recipe ingredient evidence uses durable recipe `position` from Feature 003.
3. Ranking results use final score descending and recipe ID ascending, then
   apply `limit`.

SQLite insertion and unspecified row-return order control none of them. No
pantry position is persisted because submitted order has no approved user
value.

## HTTP failure contract

| Failure | Public status and detail | Durable effect |
|---|---|---|
| Invalid write shape, blank, type, item length, or list size | Existing validation `422` | No write |
| Any unresolved pantry write item | `422 unresolved_pantry_items` with complete deterministic evidence | Prior state unchanged |
| Pantry never established | `404 saved_pantry_not_found` | None |
| Unresolved saved-ranking exclusion | Existing `422 unresolved_excluded_ingredients` | None |
| Connection unavailable, persistent lock, failed read/write transaction, corrupt pantry state, unknown stored ID, missing pantry schema, or runtime schema mismatch | `503 saved_pantry_unavailable` with fixed message `Saved pantry is unavailable.` | Failed writes roll back; reads return no partial state |
| Unexpected non-storage application failure | Existing generic `500` | Depends on owning operation; no internals exposed |

Request-time storage failures intentionally share one public `503` contract.
Clients can act on availability but do not need SQLite-specific distinctions.
The exact response is:

```json
{
  "detail": {
    "type": "saved_pantry_unavailable",
    "message": "Saved pantry is unavailable."
  }
}
```

The server-side exception may retain operation context and a chained cause for
diagnosis, but the response never includes a database path, SQL, SQLite text,
row payload, stack trace, or internal exception class.

Schema migration and recipe hydration still occur during lifespan. Failure
there prevents startup as Feature 003 already requires; there is no HTTP
response because the application never begins serving.

## Privacy and data minimization

The database stores only:

- one marker saying the current pantry has been established; and
- the current set of canonical ingredient IDs.

Replacement deletes the previous current set in the same transaction and does
not retain it elsewhere. The feature does not store raw request strings,
unresolved inputs, aliases, failed bodies, timestamps, request/ranking history,
previous pantry snapshots, analytics, traces containing pantry contents, or
user activity. Error responses echo submitted terms only to the requesting
caller as explicitly approved resolution evidence.

## Testing and evidence strategy

All storage and migration tests use isolated real files below `tmp_path`.
SQLite-owned behavior is not mocked.

### Resolution and request-model tests

- zero and 100 items are accepted; 101 is rejected;
- 100-character nonblank items are accepted; longer and blank items are
  rejected;
- unknown fields and invalid types retain deterministic `422` behavior;
- canonical terms, aliases, and duplicates resolve to one sorted ID set;
- any unresolved term produces complete ordered evidence and no store call.

### Migration tests

- fresh version 0 reaches exact version-2 schema;
- genuine populated version 1 migrates with recipe rows unchanged;
- current version rerun is a no-op;
- newer version fails without mutation;
- actual migration-2 DDL conflict rolls back partial schema;
- deferred commit failure after `user_version = 2` restores schema and version
  1.

### Pantry-store tests

- absent reads return the explicit absent value;
- empty replacement creates the marker with zero items;
- valid replacement persists canonical IDs and survives connection close;
- reverse insertion order still reads by canonical ID;
- duplicate, blank, orphan, unknown-registry, and malformed durable states fail
  the complete read;
- a failed replacement preserves the previous valid pantry;
- a held write lock fails the overlapping write safely;
- later successful writes and reads demonstrate last-commit-wins visibility.

### API and restart tests

- PUT establishes, replaces, deduplicates, and returns canonical state;
- GET distinguishes absent and empty;
- unresolved replacement returns the exact `422` and preserves prior state;
- the write bounds are public contract tests;
- saved ranking distinguishes absent and empty;
- saved state survives application restart;
- safe `503` bodies contain no path, SQL, SQLite error, or stack trace;
- existing inline API tests remain unchanged and green.

### Ranking parity tests

- equivalent canonical inline and saved requests compare complete successful
  `RankingResponse` objects;
- alias/duplicate writes produce the same ranked result objects as their
  canonical inline state;
- unresolved exclusions compare the complete fail-closed evidence;
- empty pantry responses have zero coverage in both flows;
- reversed durable pantry row insertion cannot change pantry evidence or
  ranking output;
- multiple results, ties, explanations, score breakdowns, limits, and
  `returned_count` remain protected.

### Regression and final evidence

The complete Feature 001-003 suite remains required. The Feature 002 evaluator
must still report precision `1.0`, recall `1.0`, zero false positives, and
strict recall improvement over the exact-name baseline. Final implementation
verification must include lock, full pytest, evaluation, Ruff format/lint, and
diff checks plus focused migration, pantry-store, API, parity, and concurrency
tests.

## Documentation and learning expectations

Implementation later updates README and the product current boundary, and adds
`docs/learning/004-durable-saved-pantry.md`. The learning guide must explain:

- transient request input versus durable current state;
- singleton limitations;
- canonical-only persistence and write-time resolution;
- absent versus empty state;
- whole replacement and idempotency;
- schema version 1 to 2 migration evidence;
- atomic replacement and rollback;
- request-time read/write connections and SQLite locking;
- last-commit-wins behavior;
- validation ownership across API, resolver, SQLite, and hydration;
- direct reads versus caching;
- inline/saved ranking convergence and parity;
- public storage errors and privacy;
- rejected alternatives and future seams.

It includes runnable commands, practical exercises, failure examples, and
guided mock-interview questions. These are implementation deliverables, not
changes in this design-only session.

## Future seams without future implementation

### Quantities and units

The canonical item ID is the correct stable key for later quantity facts. A
future design can migrate `saved_pantry_items` or introduce a related facts
table once unit, conversion, and waste semantics are approved. Feature 004 does
not add nullable placeholder columns.

### Users and ownership

The explicit singleton key makes the current limitation visible. A future
multi-user feature will need authentication, owner identity, authorization,
and a migration from the singleton to owner-keyed state. Feature 004 does not
guess those contracts or claim the singleton schema is the final user model.

### Grocery and waste optimization

Stable ingredient IDs and durable current presence are reusable inputs, but
optimization also needs quantities, units, time, price, and planning semantics.
Those capabilities receive their own schema and evidence when the roadmap
reaches them.

## Risks and deliberate trade-offs

### Request-time SQLite reads

Saved ranking now depends on one small local durable read. A storage failure can
make saved ranking unavailable while inline ranking still works from caller
input and the recipe snapshot. This is honest source-of-truth behavior. Caching
would hide some failures and introduce stale-state risk without a measured
latency problem.

### Code-owned registry cannot be an SQLite FK target

Out-of-band writes can insert a nonblank unknown ID. Every durable read must
therefore validate the complete set against `INGREDIENT_REGISTRY` and fail
closed. A duplicate ingredient registry in SQLite remains a worse ownership
problem than this explicit hydration boundary.

### Last-write-wins can overwrite another caller

That is acceptable for one application-local current pantry with no user or
collaborative editing model. Versions or conditional writes should be added
only with evidence of conflicting editors.

### Canonical-name changes affect reads

Inspection and saved ranking use the current code-owned name for a stable ID.
That is intentional: names are display data, not durable pantry identity. An ID
removed from the registry is a breaking registry change and causes validated
pantry reads to fail until a deliberate migration or registry correction is
made.

### No reset-to-absent operation

Feature 004 needs save/replace, inspect, and rank. Replacing with empty is a
valid established state. A delete endpoint adds little product value and would
make clients choose between two kinds of emptiness, so it is deferred.

## Acceptance mapping

| Requirement | Design decision and evidence |
|---|---|
| One durable current pantry | Singleton marker plus canonical item rows |
| Replace/save | Idempotent whole-resource `PUT` in one `BEGIN IMMEDIATE` transaction |
| Inspect | `GET` returns registry names in canonical-ID order |
| Rank without resending pantry | Separate saved-ranking endpoint reads durable state then calls `rank_recipes` |
| Inline compatibility | Existing endpoint and request model unchanged |
| Canonical-only state | Write resolution completes before persistence; only IDs stored |
| Unsupported writes | Complete `422` evidence; no write; prior state retained |
| Duplicate equivalents | Deduplicated canonical ID set and database primary key |
| Absent versus empty | No marker versus marker with zero items |
| Input bounds | New PUT only: 100 items, 100 characters each |
| Deterministic pantry order | Ascending canonical ID; no stored position |
| Real v1 migration | Atomic migration 2 with populated-recipe preservation test |
| Fresh/current/newer versions | Ordered v1/v2, current no-op, newer deterministic failure |
| Migration atomicity | Real partial-DDL and post-version commit-failure rollback evidence |
| Replacement atomicity | Delete/marker/insert in one transaction; failure preserves prior state |
| Durable integrity | PK/FK/check constraints plus complete registry-backed read validation |
| Request-time lifecycle | One short connection per read/write; explicit transactions; always close |
| Concurrency | SQLite serialization, last successful commit wins, lock failure is safe |
| Freshness | Every GET and saved ranking reads committed durable state; no cache |
| Ranking meaning | Existing `rank_recipes` and all helpers unchanged |
| Complete parity | Canonical inline and saved requests compare complete responses |
| Failure privacy | Fixed 404/422/503 details; no paths, SQL, or raw SQLite errors |
| Data minimization | Current marker and IDs only; no raw inputs or history |
| Existing store abstractions | Share only connection/migration authority; keep aggregate logic concrete |
| Future seams | Stable IDs and ordered migrations, without placeholder future fields |

## Design self-review

- **Placeholder scan:** No TODO, TBD, undecided endpoint, schema field, status,
  error, ordering rule, or lifecycle choice remains.
- **Internal consistency:** The API, marker schema, replacement transaction,
  read behavior, and absent/empty contract agree.
- **Source-of-truth review:** SQLite owns current saved pantry facts;
  `INGREDIENT_REGISTRY` owns vocabulary; the recipe database owns recipes; the
  in-memory recipe tuple is derived. No competing pantry cache or raw-text
  store exists.
- **Compatibility review:** Inline ranking remains required-field compatible.
  Saved ranking is additive and calls the same domain function.
- **Failure review:** Invalid, unresolved, absent, unavailable, locked,
  transaction-failed, malformed, unknown-ID, schema-mismatched, and startup
  failures each have an explicit outcome.
- **Migration review:** Fresh, real v1, current, newer, partial-DDL, and
  post-version commit failure evidence are all required; recipe preservation is
  explicit.
- **Parity review:** Complete canonical response equality and intentional raw
  write-provenance loss are both explicit.
- **Ordering review:** Pantry, recipe ingredient, and ranking order are separate
  explicit rules; SQLite row order is never semantic.
- **Scope review:** No users, quantities, item CRUD, history, caching, retries,
  async database work, framework migration, ranking change, or unrelated
  cleanup entered the design.
- **Abstraction review:** Only the now-shared connection/migration authority is
  extracted. Recipe and pantry operations stay concrete.
- **Privacy review:** Only current canonical state is durable; failed inputs and
  prior snapshots are not retained.

## Scope conclusion

Feature 004 is one coherent durability slice: one explicit singleton pantry,
canonical-only atomic replacement, deterministic inspection, direct validated
request-time reads, a real schema-version-1-to-2 migration, and a separate
saved-ranking route that converges on the unchanged pure ranking pipeline. It
solves the current recipes-durable/pantry-transient asymmetry and stops before
users, quantities, history, caching, or ranking changes.
