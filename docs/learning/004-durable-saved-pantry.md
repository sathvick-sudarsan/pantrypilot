# Feature 004: Durable saved pantry

## Capability and non-goals

Feature 004 adds one application-local current pantry. A caller can replace the
whole pantry, inspect it, and rank from it without resending pantry items:

- `PUT /v1/saved-pantry` replaces or establishes the current pantry.
- `GET /v1/saved-pantry` reads it.
- `POST /v1/saved-pantry/meal-rankings` ranks from it.
- `POST /v1/meal-rankings` remains the compatible inline endpoint and still
  requires `pantry_items`.

There are no users, ownership, multiple pantries, item-level CRUD,
reset-to-absent operation, quantities, units, or request/ranking history. An
empty replacement establishes an empty pantry; no endpoint returns it to the
absent state.

## Why durability stores canonical IDs only

`INGREDIENT_REGISTRY` is the vocabulary authority. At `PUT` time the API uses
the existing deterministic resolver for every submitted occurrence, including
canonical terms and reviewed aliases. It rejects the entire replacement if any
occurrence is unresolved, then deduplicates the resolved canonical IDs and
stores the sorted set.

That rule avoids silently losing food the caller thought was saved. It also
avoids storing raw text, aliases, normalized strings, or resolution evidence,
which would create a second identity contract and force future
re-resolution rules. A future edit to a registry display name is visible on the
next `GET` or saved-ranking read because those names are derived from the
registry, not stored in SQLite.

## Absent and empty are different states

The singleton marker records whether a pantry was ever established.

| Durable rows | Meaning | `GET` | Saved ranking |
|---|---|---|---|
| No marker | Absent | `404` | `404` |
| Marker, no items | Established empty | `200` with `[]` | `200`, zero pantry coverage |
| Marker and items | Established set | `200` in canonical-ID order | `200` |

Migration creates tables but no marker, so an upgraded v1 database begins
absent. Whole replacement with `[]` inserts the marker and is valid.

## Schema v1 to v2

Schema version 2 adds exactly these tables; it does not seed pantry rows.

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

The ordered migration runner advances v1 to v2 as one explicit transaction:

```text
BEGIN IMMEDIATE
  -> CREATE saved_pantry
  -> CREATE saved_pantry_items
  -> PRAGMA user_version = 2
  -> COMMIT
```

Statements run individually. A second-DDL conflict rolls back the first new
table and leaves a populated v1 recipe catalog unchanged. A separate deferred
foreign-key failure proves the stronger case: even after `PRAGMA user_version =
2` executes, a failed `COMMIT` rolls back the new schema, data, and version.

SQLite cannot make `ingredient_id` a foreign key to the Python registry because
the registry is not a SQLite table. SQLite protects the marker/item relation;
every durable read validates every ID against `INGREDIENT_REGISTRY` before it
returns any state.

## Write transaction

Resolution and input validation happen before opening a database connection.
For an all-resolved replacement, the store uses one short transaction:

```text
BEGIN IMMEDIATE -> DELETE -> INSERT marker -> INSERT sorted IDs -> COMMIT
```

Deleting the marker cascades old items. If any statement or the commit fails,
rollback retains the complete prior marker and item set. This is why a mixed
valid/unresolved request changes nothing: it never reaches the store.

## Read transaction and integrity

Each inspection and saved-ranking request opens a short-lived connection and a
consistent read transaction. It requires schema v2, runs the targeted
`PRAGMA foreign_key_check(saved_pantry_items)`, validates marker rows, reads
items with explicit `ORDER BY ingredient_id`, and validates the complete ID set
against the registry. It commits and closes only after all checks pass.

Malformed, orphaned, duplicate, or unknown rows make the complete read fail;
the code never skips a bad row and returns a partial pantry. Each later request
opens a fresh connection, so it observes committed durable state.

## Concurrency

SQLite's standard connection timeout is used. `BEGIN IMMEDIATE` serializes
writers before they delete or insert. Reads see complete committed snapshots,
never the delete/insert middle. If competing writes succeed, **last successful
commit wins**: commit order, not arrival order, decides the current pantry.

The deterministic lock test holds a real `BEGIN IMMEDIATE` transaction, proves
the overlapping replacement fails safely with the old pantry intact, releases
the lock, then proves a later replacement succeeds. There is no retry loop,
application mutex, WAL requirement, or multi-process coordination guarantee.

## Ranking convergence and parity

Saved ranking follows one adapter path:

```text
saved canonical IDs -> current canonical names -> RankingRequest -> rank_recipes
```

`rank_recipes` is unchanged and still computes:

```text
0.70 * pantry_coverage + 0.20 * protein_fit + 0.10 * time_fit
```

Tests compare complete JSON bodies from saved ranking and inline ranking using
the same canonical names. That proves parity for results, evidence, score
breakdowns, explanations, ordering, limits, and `returned_count`, including
aliases, duplicates, empty pantries, fail-closed exclusions, physical row
order, and tie behavior.

## HTTP trust boundary

Absent state returns `404`:

```json
{
  "detail": {
    "type": "saved_pantry_not_found",
    "message": "No saved pantry has been established."
  }
}
```

An unresolved replacement returns `422` and preserves the prior state:

```json
{
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
          "match_type": "alias"
        },
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

A known pantry-store failure returns `503`:

```json
{
  "detail": {
    "type": "saved_pantry_unavailable",
    "message": "Saved pantry is unavailable."
  }
}
```

Only `PantryStoreError` owns that `503` mapping. Programmer defects keep the
generic `500` path. Raw SQLite details are exception causes for diagnostics,
never HTTP JSON, so paths and SQL do not leak.

## Privacy and future seams

The database stores only the current singleton marker and canonical IDs. It
does not retain aliases, raw submitted text, unresolved input, timestamps,
owners, quantities, previous snapshots, analytics, or history. Users,
quantities/units, grocery or waste optimization, retrieval, and history need
separate product evidence and migrations. Retrieval remains deferred until the
catalog is large enough that full ranking is inefficient.

## Run and inspect

```powershell
uv sync
uv run uvicorn pantrypilot.app:app --reload
uv run pytest tests/test_database.py tests/test_pantry_store.py -v
uv run pytest tests/test_api.py tests/test_saved_pantry_ranking_parity.py -v
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
```

In a second PowerShell window, use the API examples in the README. For a
read-only SQLite inspection after the app has initialized the default database:

```powershell
uv run python -c "import sqlite3; c=sqlite3.connect('pantrypilot.sqlite3'); print(c.execute('PRAGMA user_version').fetchone()[0]); print(c.execute('SELECT id FROM saved_pantry').fetchall()); print(c.execute('SELECT pantry_id, ingredient_id FROM saved_pantry_items ORDER BY ingredient_id').fetchall()); c.close()"
```

## Practical exercises

1. Save `black bean`, `BLACK BEANS`, and `egg`. Success: `GET` returns only
   `black-beans` then `eggs`, in ascending ID order.
2. Save `[]`, then call saved ranking. Success: it returns `200` and every
   result has pantry-coverage value `0.0`.
3. Save `eggs`, attempt to replace with `egg` and `groundnut`, then `GET`.
   Success: the PUT is the exact unresolved `422` body above and GET still
   returns `eggs`.
4. Run the read-only command above. Success: `user_version` is `2`; the marker
   and item rows match the established state; no command modifies them.
5. In one SQLite connection, hold `BEGIN IMMEDIATE`; attempt a PUT from another
   connection, observe its safe `503`, release the lock, and repeat the PUT.
   Success: the failed attempt preserves the old pantry and the later attempt
   is visible. The real test is `tests/test_pantry_store.py`.
6. Save aliases and duplicates, copy the returned canonical names into the
   inline request, and compare the complete JSON of both ranking endpoints.
   Success: the decoded bodies are identical.

## Guided mock interview

1. **Why whole replacement instead of item CRUD?** One current local set has
   no approved item identity, ownership, or merge behavior; PUT is atomic and
   idempotent for the resulting canonical set.
2. **Why reject the entire unresolved write?** A durable pantry claims to be
   complete. Silently dropping one submitted food would misrepresent it.
3. **How does the marker distinguish absent from empty?** No marker means no
   established resource; marker plus zero item rows is an intentional empty set.
4. **Why store IDs but derive names?** IDs are stable registry identities;
   derived names stay current after a registry display-name edit.
5. **Why can SQLite not FK to the Python registry, and where is integrity
   checked?** The registry is not a SQLite relation. Store reads validate the
   complete ID set against it after SQLite validates its own foreign key.
6. **How does migration-2 rollback prove atomicity, including commit-time
   failure?** A real DDL conflict removes earlier new DDL; a deferred-FK commit
   failure after the version update removes schema/data and restores v1.
7. **Why `BEGIN IMMEDIATE`, and what does last successful commit wins mean?**
   It acquires writer serialization before mutation. Of successful writes, the
   one that commits last supplies the current set; arrival order is not promised.
8. **Why read on each saved-ranking request rather than cache?** One small
   local read exposes committed truth without invalidation or stale-state rules.
9. **How do both ranking endpoints avoid semantic drift?** Saved IDs become
   canonical names in an ordinary `RankingRequest`, then both call unchanged
   `rank_recipes`; full-body parity tests enforce it.
10. **Why is the `503` handler narrow?** Known storage failures are safely
    unavailable; catching arbitrary defects would hide programming errors.
11. **What evidence would justify users, quantities, history, retrieval, or
    retries later?** A defined user/ownership workflow, measurement semantics,
    privacy and retention rules, catalog-scale latency/recall evidence, or
    demonstrated lock contention with a conflict policy.
