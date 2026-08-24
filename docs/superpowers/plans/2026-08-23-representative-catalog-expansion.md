# Representative Recipe Catalog Expansion and Full-Scan Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Release exactly 24 owner-approved, original PantryPilot recipe records through deterministic official-content reconciliation, preserve out-of-band recipes and saved pantry state, expand exact ingredient-resolution evidence, and record a reproducible exhaustive-ranking baseline without changing ranking semantics or adding retrieval.

**Architecture:** Code owns one validated official recipe manifest and an append-only catalog-content version/digest ledger; SQLite schema version 3 materializes official facts beside durable out-of-band facts and stores the independently managed installed content pair. Startup validates release identity before database access, migrates schema, performs a read-only reserved-ID preflight, reconciles official rows atomically, verifies the resulting digest, then loads the complete durable catalog into the existing immutable request-time snapshot. A standard-library-only benchmark times only `rank_recipes(request, catalog, registry)` against the released manifest and six fixed workloads.

**Tech Stack:** Python 3.12, Pydantic 2, FastAPI, SQLite, Python standard-library `dataclasses`, `hashlib`, `json`, `statistics`, `time`, `platform`, and `subprocess`, Pytest, Ruff, uv, GitHub Actions YAML, Markdown, and CC0 1.0 Universal for the specifically scoped data artifacts.

**Spec:** `docs/superpowers/specs/2026-08-22-representative-catalog-expansion-design.md`

## Global Constraints

- Work only in the linked worktree `C:\Users\sathv\Projects\pantrypilot\.worktrees\representative-catalog-expansion` on branch `feat/representative-catalog-expansion`; commit `8b262507ca5260b0638dc99cbaeeaa2ba1277523` must remain an ancestor.
- Read the approved design, `docs/product/vision.md`, `docs/roadmap.md`, and `AGENTS.md` before changing implementation files. Direct owner instructions in the planning brief supersede the design's stale decision-status text.
- The owner has approved exactly 24 total official recipes including the existing four, an original PantryPilot-authored factual corpus, and a data-scoped CC0 1.0 notice. Do not reopen those decisions merely for convenience.
- The exact 24 recipe facts, new canonical ingredients, new aliases, and confusable negatives are not released until Task 6 receives explicit owner approval. Task 6 is a hard stop.
- The measured benchmark result and retrieval conclusion are not accepted until Task 12 receives explicit owner approval. Task 12 is a second hard stop.
- Preserve the existing IDs and exact facts of `spinach-omelet`, `black-bean-tacos`, `peanut-noodles`, and `lentil-soup` in the Feature 003 legacy snapshot and in the proposed 24-record release unless the owner explicitly changes a fact during Task 6 review.
- Current and cumulative retired official IDs are one permanently reserved namespace. Validate all durable collisions before any recipe ownership or content write; never claim, overwrite, or delete an out-of-band row.
- Keep `PRAGMA user_version` schema-only. Schema migration 3 creates `recipes.is_official` and `catalog_content_state`; catalog content version 1 and its digest are independent application-content identity.
- Use one UTF-8 canonical JSON serializer and SHA-256 implementation for release validation, durable official-subset verification, and benchmark binding. Recipe source order is irrelevant; recipe IDs and retired IDs sort ascending; required ingredient order remains significant.
- The release ledger is append-only, has consecutive positive integer keys through `CURRENT_CATALOG_CONTENT_VERSION`, and binds every released version to one immutable lowercase 64-character digest.
- Migration 3 marks all pre-existing recipe rows out-of-band and inserts exactly `(id=1, version=0, manifest_digest='unmanaged')`. Only exact Feature 003 seed rows may be adopted from that transitional state.
- Reconcile current official rows on every startup, including current-version reruns. Restore modified or missing official rows, but delete retired marked-official rows only while legitimately advancing from an older managed version or adopting an exact legacy row retired by the first release.
- Never write `saved_pantry` or `saved_pantry_items` during catalog-content evolution. Existing canonical ingredient IDs are stable and additive even if a future recipe no longer uses them.
- Add only canonical ingredients used by the approved corpus. Resolution remains normalized exact canonical-name or explicit-alias lookup; unsupported or ambiguous terms abstain. Do not add fuzzy, substring, pluralization, embedding, or similarity behavior.
- Keep `evaluations/ingredient-resolution-v1.json` byte-for-byte unchanged at SHA-256 `523255671bdbc141aca565ab479daffdfa5db0bc07e09454d0a969e22dbba48d`. V2 retains fixture `schema_version: 1`, contains every v1 row unchanged, covers every current canonical term and alias, and preserves zero unsafe false positives.
- Do not change request or response models, route shapes, ranking weights, formula, rounding, explanation template, hard preparation/exclusion semantics, soft protein semantics, sort key, unresolved-exclusion failure, or post-sort limiting.
- Benchmark exactly the released 24-record catalog. Use 100 warmups and 1,000 measurements per workload with `time.perf_counter_ns`; the timed region contains only `rank_recipes(request, catalog, registry)`.
- Hosted CI may validate benchmark semantics but must not assert elapsed time. Feature 006 never implements retrieval, synthetic scale, an index, a cache, a recipe CRUD/import path, an external runtime API, scraping, or a new dependency.
- The scoped CC0 notice applies only to official PantryPilot recipe catalog data and its provenance metadata. It must explicitly exclude PantryPilot source code and every other repository artifact from that dedication.
- Use TDD for behavior changes: create the focused failing assertion, run it and observe the intended failure, add the smallest implementation, then rerun the focused test.
- Keep changes small and use the existing modules unless the responsibility map below names a focused new module. Do not introduce an ORM, generic migration framework, generic content framework, or benchmark framework.
- Planned commit commands are boundaries, not authorization. Commit only when the owner has authorized commits in the implementation thread. Never push, open a PR, merge, or change repository settings from this plan.
- Before Task 1 implementation begins, the execution thread must create the
  documentation-only baseline commit defined below and verify a clean working
  tree. No production file may enter that commit.

---

## Planned File Structure and Responsibilities

### Production files

- Modify `src/pantrypilot/catalog.py`: retain `load_catalog`; preserve an immutable exact Feature 003 four-record legacy snapshot; define the proposed/current 24-record official manifest and cumulative retired official IDs after corpus review.
- Create `src/pantrypilot/catalog_release.py`: own `CatalogRelease`, official-ID/release-ledger validation, canonical manifest serialization, SHA-256 digesting, and the current released version/digest constants. It performs no SQLite access.
- Modify `src/pantrypilot/database.py`: add schema migration 3, `recipes.is_official`, and the singleton `catalog_content_state` table while keeping `PRAGMA user_version` schema-only.
- Modify `src/pantrypilot/catalog_store.py`: replace seed-if-empty behavior with transactional official reconciliation, conservative legacy adoption, reserved-ID preflight, durable pair validation, resulting-digest verification, rollback, and complete catalog hydration.
- Modify `src/pantrypilot/ingredients.py`: append only the canonical ingredients and explicit aliases required by the approved corpus; leave resolver logic unchanged.
- Modify `src/pantrypilot/app.py`: validate/reconcile the current official release during lifespan startup, then publish the complete durable catalog snapshot exactly once.
- Create `src/pantrypilot/benchmark.py`: validate the benchmark fixture/release binding, execute six deterministic workloads, time only `rank_recipes`, calculate fixed statistics, and emit deterministic-key-order JSON.
- Do not modify `src/pantrypilot/ranking.py`, `src/pantrypilot/evaluation.py`, `src/pantrypilot/models.py`, `src/pantrypilot/pantry_store.py`, `pyproject.toml`, or `uv.lock` unless live implementation proves an approved interface impossible; stop and report that discrepancy before changing one of them.

### Test and evaluation files

- Modify `tests/test_catalog.py`: release identity, serializer/digest sensitivity, stable/reserved IDs, exact 24-record and representative-matrix validation, and pinned released pairs.
- Modify `tests/test_database.py`: schema version 3, ownership/content-state constraints, preservation, and migration rollback.
- Rewrite the ownership-specific portions of `tests/test_catalog_store.py`: fresh/legacy/managed reconciliation, collisions, corrections, removals, digest checks, rollback, idempotence, convergence, out-of-band preservation, and saved-pantry preservation.
- Modify `tests/test_ingredients.py`: pin the expanded registry while proving all original IDs/terms remain unchanged and resolver behavior stays exact.
- Modify `tests/test_evaluation.py`: byte-freeze v1, prove v2 is its strict superset, prove complete current registry/alias coverage and targeted negatives, and run acceptance evidence against v2.
- Modify `tests/test_api.py`: update startup size and old durable-authority expectations to the new official-ownership contract while retaining request/response and snapshot assertions.
- Modify `tests/test_ranking.py`: keep formula tests independent of the expanded corpus and add no production ranking behavior.
- Modify `tests/test_ranking_parity.py`: compare the current code-owned release with the materialized durable official subset without using `initialize_catalog` as an arbitrary-seed helper.
- Modify `tests/test_saved_pantry_ranking_parity.py`: retain complete inline/saved parity over the 24-record startup snapshot; remove redundant arbitrary-seed setup already covered by focused ranking tests.
- Modify `tests/test_pantry_store.py`: update initialization calls and retain saved-pantry behavior under schema 3.
- Create `tests/test_benchmark.py`: fixture binding, six workload categories, synthetic percentile statistics, deterministic output, and result-drift failures without live latency assertions.
- Create `evaluations/ingredient-resolution-v2.json`: schema shape version 1, every v1 row unchanged, all current canonical/alias positives, and reviewed confusable negatives.
- Modify `.github/workflows/ci.yml`: change only the authoritative evaluator fixture path from v1 to v2.

### Data, benchmark, and documentation files

- Create `docs/data/recipe-catalog-v1.md`: candidate then approved exact per-recipe provenance and coverage evidence, authoring/estimate method, aggregate matrix, overlap evidence, ingredient/alias changes, and confusable negatives.
- Create `docs/data/official-recipe-catalog-CC0-1.0.md`: the already-authorized data-scoped CC0 notice, explicitly limited to official catalog facts and the provenance metadata in `docs/data/recipe-catalog-v1.md`.
- Create `benchmarks/full-scan-ranking-v1.json`: release-bound six-workload fixture with exact expected response IDs/digests, eligible counts, and fixed 100/1,000 iteration counts.
- Create `benchmarks/results/full-scan-ranking-v1-reference.json`: raw owner-reviewed Python 3.12 reference-machine output from the dedicated command.
- Create `docs/benchmarks/006-full-scan-baseline.md`: methodology, environment, results, decision rule, evidence limits, and owner-approved retrieval conclusion.
- Create `docs/learning/006-representative-catalog-expansion.md`: learning notes, exercises, and mock-interview questions covering content ownership, independent versions, fail-closed reconciliation, conservative resolution, data licensing, and honest benchmarking.
- Modify `README.md`: Feature 006 current state, 24-recipe ownership/evolution summary, v2 evaluator and benchmark commands, retrieval conclusion, document links, and correction that both pull-request and push-to-main CI paths are proven.
- Modify `docs/product/vision.md`: update only the current boundary from four seed recipes to the versioned official/out-of-band catalog and the measured retrieval decision.
- Modify `docs/roadmap.md`: update only Phase 4 evidence/status wording supported by the approved benchmark conclusion; do not add retrieval implementation.
- Do not modify the approved design unless the owner changes a design decision during execution and explicitly requests the design update.

---

## Pre-Implementation Documentation Baseline

This section runs in the future implementation thread before Task 1. It turns
the owner-approved design and reviewed plan into the durable execution baseline
required by later clean-tree and benchmark-identity checks. It is not
authorization to begin implementation in this planning thread.

- [ ] **Step 1: Verify the two expected planning-stage modifications**

Run in PowerShell:

```powershell
$expectedRoot = 'C:\Users\sathv\Projects\pantrypilot\.worktrees\representative-catalog-expansion'
$expectedBranch = 'feat/representative-catalog-expansion'
$designBase = '8b262507ca5260b0638dc99cbaeeaa2ba1277523'
$specPath = 'docs/superpowers/specs/2026-08-22-representative-catalog-expansion-design.md'
$planPath = 'docs/superpowers/plans/2026-08-23-representative-catalog-expansion.md'
$expectedPaths = @($planPath, $specPath) | Sort-Object

if ((Resolve-Path (git rev-parse --show-toplevel)).Path -ne $expectedRoot) {
    throw 'Wrong Feature 006 worktree'
}
if ((git branch --show-current).Trim() -ne $expectedBranch) {
    throw 'Wrong Feature 006 branch'
}
if ((git rev-parse HEAD).Trim() -ne $designBase) {
    throw 'Planning baseline no longer starts at the approved base commit'
}

$actualPaths = @(
    git status --porcelain | ForEach-Object {
        $_.Substring(3).Replace('\', '/')
    } | Sort-Object -Unique
)
$pathDifference = @(Compare-Object $expectedPaths $actualPaths)
if ($pathDifference.Count) {
    $pathDifference | Out-Host
    throw 'Only the approved spec and implementation plan may be modified'
}

git status --short --branch
git diff --check
```

Expected: root, branch, and HEAD match exactly; status names only the approved
spec and plan; `git diff --check` exits 0. Stop on any other path and do not
discard or absorb it.

- [ ] **Step 2: Commit only the approved documentation once execution is authorized**

Do not run this step until the owner authorizes implementation execution and
local commits. Then run:

```powershell
git add -- $specPath $planPath
$stagedPaths = @(git diff --cached --name-only | Sort-Object)
$stagedDifference = @(Compare-Object $expectedPaths $stagedPaths)
if ($stagedDifference.Count) {
    $stagedDifference | Out-Host
    throw 'Documentation baseline contains an unexpected staged path'
}
git diff --cached --check
git commit -m "docs: approve feature 006 design and plan"
```

Expected: the commit contains exactly the spec and plan and no production,
test, corpus, database, evaluation, benchmark, CI, or generated file. Do not
push it.

- [ ] **Step 3: Verify the durable baseline is clean**

```powershell
$expectedSubject = 'docs: approve feature 006 design and plan'
$expectedCommitPaths = @($planPath, $specPath) | Sort-Object
$actualCommitPaths = @(
    git diff-tree --no-commit-id --name-only -r HEAD | Sort-Object
)
if ((git log -1 --format=%s).Trim() -ne $expectedSubject) {
    throw 'Unexpected execution-baseline commit subject'
}
if ((git rev-parse HEAD^).Trim() -ne $designBase) {
    throw 'Documentation baseline is not directly based on the approved commit'
}
if (@(Compare-Object $expectedCommitPaths $actualCommitPaths).Count) {
    throw 'Documentation baseline commit contains unexpected paths'
}
if (@(git status --porcelain).Count) {
    git status --short --branch
    throw 'Task 1 requires a clean working tree'
}
git status --short --branch
git log -1 --oneline --decorate
```

Expected: the documentation commit is directly based on
`8b262507ca5260b0638dc99cbaeeaa2ba1277523`, contains exactly the spec and plan,
and leaves the working tree clean. Task 1 begins only after this succeeds.

---

### Task 1: Add Canonical Catalog Release Identity Primitives

**Files:**

- Create: `src/pantrypilot/catalog_release.py`
- Modify: `tests/test_catalog.py`
- Inspect only: `src/pantrypilot/catalog.py`, `src/pantrypilot/models.py`, `src/pantrypilot/ingredients.py`

**Interfaces:**

- Consumes: `load_catalog(records, ingredient_registry) -> tuple[Recipe, ...]`, frozen `Recipe`, and `IngredientRegistry`.
- Produces:

```python
@dataclass(frozen=True)
class CatalogRelease:
    version: int
    manifest_digest: str
    recipes: tuple[Recipe, ...]
    retired_recipe_ids: tuple[str, ...]


def canonical_manifest_bytes(
    recipes: Sequence[Recipe],
    retired_recipe_ids: Collection[str],
) -> bytes: ...


def catalog_manifest_digest(
    recipes: Sequence[Recipe],
    retired_recipe_ids: Collection[str],
) -> str: ...


def build_catalog_release(
    recipes: Iterable[Recipe],
    retired_recipe_ids: Iterable[str],
    ingredient_registry: IngredientRegistry,
    current_version: int,
    release_digests: Mapping[int, str],
) -> CatalogRelease: ...
```

- `build_catalog_release` is the only constructor used by production startup. It freezes the iterable as a recipe-ID-sorted tuple and validates every ingredient against the registry, lowercase kebab-case official and retired IDs, duplicate current and retired IDs, disjoint current/retired sets, positive current version, consecutive ledger keys `1..current_version`, lowercase 64-hex ledger digests, and equality of the computed current digest to the ledger's current literal.

- [ ] **Step 1: Reconfirm the committed implementation baseline**

Run in PowerShell:

```powershell
$expectedRoot = 'C:\Users\sathv\Projects\pantrypilot\.worktrees\representative-catalog-expansion'
$expectedBranch = 'feat/representative-catalog-expansion'
$designBase = '8b262507ca5260b0638dc99cbaeeaa2ba1277523'
$expectedSubject = 'docs: approve feature 006 design and plan'

if ((Resolve-Path (git rev-parse --show-toplevel)).Path -ne $expectedRoot) {
    throw 'Wrong Feature 006 worktree'
}
if ((git branch --show-current).Trim() -ne $expectedBranch) {
    throw 'Wrong Feature 006 branch'
}
if ((git rev-parse HEAD^).Trim() -ne $designBase) {
    throw 'Documentation baseline is not based directly on the approved commit'
}
if ((git log -1 --format=%s).Trim() -ne $expectedSubject) {
    throw 'Documentation baseline commit is missing'
}
if (@(git status --porcelain).Count) {
    git status --short --branch
    throw 'Implementation must begin from a clean working tree'
}

git rev-parse --git-dir
git rev-parse --git-common-dir
git status --short --branch
```

Expected: the linked-worktree git directory differs from the common directory;
the branch matches; HEAD is the documentation-only baseline commit directly
above the approved base; and the working tree is clean. Stop on any difference
and do not clean it automatically.

- [ ] **Step 2: Record the pre-change quality baseline**

Run each command separately:

```powershell
uv lock --check
uv run pytest
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: every command exits 0; the evaluator reports improved recall and zero false positives. Do not run the Feature 006 benchmark.

- [ ] **Step 3: Write failing serializer and validation tests**

Add focused tests that construct two valid `Recipe` objects and assert the exact UTF-8 bytes for this fixed shape:

```json
{"recipes":[{"id":"a-recipe","name":"A Recipe","calories":100,"protein_g":10.0,"prep_minutes":15,"required_ingredient_ids":["eggs","spinach"]}],"retired_official_recipe_ids":["retired-recipe"]}
```

Also assert:

- source recipe order does not change bytes or digest;
- relationship order does change bytes and digest;
- changing each of `id`, `name`, `calories`, `protein_g`, and `prep_minutes` changes the digest;
- adding or removing a recipe changes the digest;
- adding or removing a retired ID changes the digest;
- duplicate current IDs, duplicate retired IDs, current/retired overlap, malformed official IDs, unknown ingredient IDs, missing ledger versions, extra ledger versions, invalid digest text, and computed/current-ledger mismatch each fail explicitly.

Run:

```powershell
uv run pytest tests/test_catalog.py -v
```

Expected: collection fails because `pantrypilot.catalog_release` does not exist.

- [ ] **Step 4: Implement the minimal pure release module**

Construct the payload with insertion-ordered dictionaries in the exact field order shown above, sort recipes by `recipe.id`, preserve `required_ingredient_ids`, sort retired IDs, and encode with:

```python
json.dumps(
    payload,
    ensure_ascii=False,
    separators=(",", ":"),
).encode("utf-8")
```

Hash only those bytes with `hashlib.sha256(...).hexdigest()`. Do not use `sort_keys=True`, a second serializer, a JSON library dependency, or SQLite in this module.

- [ ] **Step 5: Run focused and style checks**

```powershell
uv run pytest tests/test_catalog.py -v
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: release identity tests pass; existing four-record catalog tests remain unchanged and pass.

- [ ] **Step 6: Commit the release primitives when authorized**

```powershell
git add src/pantrypilot/catalog_release.py tests/test_catalog.py
git commit -m "feat: add catalog release identity"
```

---

### Task 2: Add Schema Migration 3 and Durable Catalog Content State

**Files:**

- Modify: `src/pantrypilot/database.py`
- Modify: `tests/test_database.py`
- Modify mechanically where positional recipe inserts break: `tests/test_catalog_store.py`, `tests/test_ranking_parity.py`

**Interfaces:**

- Consumes: existing ordered `SCHEMA_MIGRATIONS` and `migrate_database` transaction loop.
- Produces: `CURRENT_SCHEMA_VERSION = 3`; `recipes.is_official`; singleton `catalog_content_state(id, version, manifest_digest)` initialized as `(1, 0, 'unmanaged')`.

- [ ] **Step 1: Write migration 3 failure and preservation tests**

Update the fresh-schema assertion to require:

- exactly five application tables total: the four schema-version-2 tables
  `recipes`, `recipe_ingredients`, `saved_pantry`, and `saved_pantry_items`,
  plus `catalog_content_state`;
- `recipes.is_official` type `INTEGER`, `NOT NULL`, default `0`, constrained to `0` or `1`;
- `catalog_content_state.id` constrained to singleton value `1`;
- `version` constrained to a non-negative SQLite integer;
- `(version=0, manifest_digest='unmanaged')` accepted;
- for `version>0`, exactly 64 lowercase hexadecimal characters required;
- `(0, any digest other than 'unmanaged')` and `(positive version, 'unmanaged')` rejected.

Add a schema-v2 fixture containing one recipe, ordered relationships, one saved-pantry marker, and saved items. Assert migration to 3 preserves every pre-existing row, sets the recipe marker to `0`, inserts exactly one transitional content-state row, and does not modify pantry tables. Inject a DDL conflict during migration 3 and assert all schema/data/user-version changes roll back to schema 2.

Run:

```powershell
uv run pytest tests/test_database.py -v
```

Expected: failures show schema version 2 and missing ownership/content-state structures.

- [ ] **Step 2: Add migration 3 with existing migration mechanics**

Append only these responsibilities to `SCHEMA_MIGRATIONS`:

1. `ALTER TABLE recipes ADD COLUMN is_official INTEGER NOT NULL DEFAULT 0 CHECK (typeof(is_official) = 'integer' AND is_official IN (0, 1))`.
2. Create `catalog_content_state` with primary-key singleton `id=1`, non-negative integer `version`, and the transitional/managed digest check described above.
3. Insert `(1, 0, 'unmanaged')` in the same schema transaction.

Do not place recipe data or catalog version 1 in the schema migration.

- [ ] **Step 3: Replace positional recipe inserts with named columns**

Every existing test helper or reinsertion using `INSERT INTO recipes VALUES (?, ?, ?, ?, ?)` must name the five legacy columns. Tests that intentionally set ownership must name all six columns. This is a schema-compatibility edit only; do not change the tested recipe facts.

- [ ] **Step 4: Run focused migration and existing storage tests**

```powershell
uv run pytest tests/test_database.py tests/test_catalog_store.py tests/test_ranking_parity.py -v
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: schema 3 and rollback tests pass; existing seed-era catalog tests may still pass because `is_official` defaults to 0, but content reconciliation is not integrated yet.

- [ ] **Step 5: Commit schema 3 when authorized**

```powershell
git add src/pantrypilot/database.py tests/test_database.py tests/test_catalog_store.py tests/test_ranking_parity.py
git commit -m "feat: add catalog content state schema"
```

---

### Task 3: Implement Fresh Installation and Conservative Legacy Adoption

**Files:**

- Modify: `src/pantrypilot/catalog.py`
- Modify: `src/pantrypilot/catalog_store.py`
- Modify: `tests/test_catalog_store.py`

**Interfaces:**

- Consumes: `CatalogRelease`, release ledger, `catalog_manifest_digest`, schema-3 connection, and exact Feature 003 records.
- Produces:

```python
FEATURE_003_RECIPE_CATALOG: tuple[Recipe, ...]


def reconcile_catalog(
    connection: sqlite3.Connection,
    database_path: Path,
    release: CatalogRelease,
    release_digests: Mapping[int, str],
    legacy_recipes: Sequence[Recipe],
    ingredient_registry: IngredientRegistry,
) -> None: ...
```

- `FEATURE_003_RECIPE_CATALOG` is an exact immutable-history input for legacy comparison; it is not mutated into a future release and its four IDs/facts are pinned in tests.

- [ ] **Step 1: Replace seed-era ownership tests with failing reconciliation tests**

Keep complete-catalog hydration and SQLite constraint tests. Replace tests asserting “valid non-empty catalogs are never reconciled” with tests that prove:

- a fresh schema-3 database receives every supplied synthetic official recipe with `is_official=1` and the exact release pair;
- version 0 adopts a byte-for-field exact Feature 003 recipe, including relationship order;
- a changed legacy scalar, missing/extra/reordered legacy ingredient, or newly introduced current official ID already present out-of-band fails closed;
- the entire legacy/reserved scan completes before changing an ownership marker or recipe fact;
- a valid non-reserved out-of-band row and its relationship order remain byte-for-row unchanged;
- fresh and schema-2-upgraded databases converge on the same official subset and release pair;
- a successful rerun is idempotent.

Use synthetic one- and two-recipe `CatalogRelease` values whose digests are calculated by the shared serializer. Do not depend on the unapproved 24-record facts.

Run:

```powershell
uv run pytest tests/test_catalog_store.py -v
```

Expected: reconciliation tests fail because `reconcile_catalog` and the exact legacy constant do not exist.

- [ ] **Step 2: Add one connection-level durable catalog loader**

Extract the existing row hydration into an internal helper that can select all recipes or `is_official=1` recipes from an existing connection, always orders recipes by ID and relationships by `(recipe_id, position)`, and still calls `load_catalog` for Pydantic/registry validation. `load_durable_catalog(path, registry)` remains the public complete-catalog loader and continues to reopen the database.

- [ ] **Step 3: Implement version-0 classification before writes**

Inside one `BEGIN IMMEDIATE` transaction:

1. Require exactly one content-state row.
2. Require version 0 to carry literal `unmanaged`.
3. Read every recipe and ordered relationship before writes.
4. For every current or retired reserved ID, mark only an exact Feature 003 record as legacy-adoptable; reject every divergent legacy row and every non-legacy collision.
5. Finish the entire scan before any `UPDATE`, `INSERT`, or `DELETE` against recipe tables.
6. Mark exact legacy rows official, insert missing current official rows, replace complete scalar/relationship facts for owned rows, verify the official digest, update version and digest together, and commit.

Catch `sqlite3.Error`, Pydantic validation errors, release/state errors, and explicit collision errors; roll back and raise `CatalogStoreError` with the database path but no partial success.

- [ ] **Step 4: Prove saved pantry preservation in success and failure**

Create a schema-2 upgraded fixture with `saved_pantry(id=1)` and at least two saved IDs. Capture both pantry tables before reconciliation. Assert row-for-row equality after successful legacy adoption and after a divergent-legacy failure. Also assert the out-of-band rows remain equal in both cases.

- [ ] **Step 5: Run focused reconciliation tests**

```powershell
uv run pytest tests/test_catalog_store.py tests/test_database.py tests/test_pantry_store.py -v
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: fresh/legacy convergence, fail-closed divergence, out-of-band preservation, pantry preservation, rollback, and idempotence pass.

- [ ] **Step 6: Commit legacy reconciliation when authorized**

```powershell
git add src/pantrypilot/catalog.py src/pantrypilot/catalog_store.py tests/test_catalog_store.py
git commit -m "feat: reconcile legacy official recipes"
```

---

### Task 4: Complete Reserved-ID and Managed-Release Evolution Semantics

**Files:**

- Modify: `src/pantrypilot/catalog_store.py`
- Modify: `tests/test_catalog_store.py`

**Interfaces:**

- Extends `reconcile_catalog(...)` from Task 3; no new public abstraction.
- Produces complete current-ID/retired-ID preflight, historical ledger validation, official correction/repair/removal semantics, and atomic current pair storage.

- [ ] **Step 1: Write failing managed-release state tests**

Build synthetic release 1 and release 2 manifests and literal ledgers in the tests. Cover all of these states explicitly:

- managed stored version/digest must match its historical ledger pair;
- unknown historical version, malformed digest, stored mismatch, and database version newer than the application fail before recipe writes;
- current official scalar edits and relationship edits are restored;
- a missing current official recipe is reinserted;
- additions and corrections apply on version advance;
- a marked-official retired row is deleted only when stored version is older than current;
- a retired row on a current-version rerun fails with either marker value;
- a non-official current-ID collision and non-official retired-ID collision fail;
- an official row absent from current manifest but absent from the cumulative retired set fails;
- current and retired collision scans finish before any otherwise-needed correction, insertion, relationship replacement, or deletion;
- resulting official digest mismatch rolls back recipe changes and pair update;
- injected failure after recipe writes but before pair update rolls back everything;
- injected commit failure preserves the old complete release pair and rows;
- successful update stores version and digest atomically;
- rerunning the current version restores edits and yields the same rows/pair.

For every failure test, capture recipes, relationships, content state, saved pantry, and saved items before the call and assert exact equality afterward.

- [ ] **Step 2: Run the managed-release tests to observe failure**

```powershell
uv run pytest tests/test_catalog_store.py -v
```

Expected: the new future-release and retired-ID cases fail against Task 3's version-0-only implementation.

- [ ] **Step 3: Implement the complete preflight state machine**

Use these exact rules before recipe writes:

- version 0 requires `unmanaged`;
- positive stored version must exist in `release_digests` and its stored digest must equal that literal;
- stored version greater than `release.version` fails; no downgrade exists;
- for managed state, every non-official current or retired ID is a collision;
- a marked-official retired ID is deletion-eligible only when stored version is older than current;
- any retired ID on a current-version rerun fails, including `is_official=1`;
- every marked-official ID not current must be cumulative-retired and deletion-eligible, otherwise fail;
- preflight scans all reserved IDs before any recipe mutation.

After preflight, replace each official record completely, including deleting and reinserting its ordered relationships. Verify the official subset with `catalog_manifest_digest(official_rows, release.retired_recipe_ids)`, then update both state columns in one statement and commit.

- [ ] **Step 4: Run storage, pantry, and rollback tests**

```powershell
uv run pytest tests/test_catalog_store.py tests/test_database.py tests/test_pantry_store.py -v
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: all named managed-release, collision-order, digest, atomicity, rollback, convergence, out-of-band, and saved-pantry assertions pass.

- [ ] **Step 5: Commit managed evolution when authorized**

```powershell
git add src/pantrypilot/catalog_store.py tests/test_catalog_store.py
git commit -m "feat: protect reserved official recipe ids"
```

---

### Task 5: Prepare and Mechanically Validate the Exact Candidate Corpus

**Files:**

- Modify: `src/pantrypilot/catalog.py`
- Modify: `src/pantrypilot/ingredients.py`
- Modify: `tests/test_catalog.py`
- Modify: `tests/test_ingredients.py`
- Create as candidate: `docs/data/recipe-catalog-v1.md`

**Interfaces:**

- Produces `OFFICIAL_RECIPE_CATALOG: tuple[Recipe, ...]` with exactly 24 proposed frozen records and `RETIRED_OFFICIAL_RECIPE_IDS: tuple[str, ...]` (empty for release 1 unless owner review explicitly establishes otherwise).
- Keeps `FEATURE_003_RECIPE_CATALOG` as the exact four-record legacy snapshot.
- Review tags remain evidence, not `Recipe` model fields.

- [ ] **Step 1: Author exactly 20 additional factual records and only needed registry entries**

Create short generic PantryPilot-authored dish names and explicit lowercase kebab-case IDs. Each record contains only `id`, `name`, ordered `required_ingredient_ids`, `calories`, `protein_g`, and `prep_minutes`. Preserve the four existing records exactly. Do not add instructions, descriptions, quantities, units, images, external identifiers, medical claims, or third-party prose.

Append only canonical ingredients used by at least one candidate recipe. Preserve all 14 existing registry records exactly and in stable identity. Add an alias only when the candidate review package states the positive reason and at least one exact confusable input that must remain unresolved.

- [ ] **Step 2: Write the candidate matrix tests before accepting the facts**

Add tests that derive bands from the actual `Recipe` fields and use an explicit test-owned review-tag mapping keyed by all 24 IDs. Require:

- exactly 24 unique current IDs and the exact four stable legacy IDs;
- no current/retired overlap and no duplicate retired IDs;
- every relationship ID exists in the registry;
- every new registry ID is used by at least one candidate recipe;
- all original registry IDs and terms remain byte-for-value unchanged;
- at least four breakfast and four soup/stew/salad tags, with lunch/light-meal and dinner represented;
- at least eight culinary traditions, every represented tradition having at least two recipes and no tradition more than six;
- at least 12 meat/fish-free recipes, including at least six vegan, and at least six containing poultry, fish, or meat;
- at least four recipes in each preparation band `<=15`, `16-30`, `31-45`, and `46-60`, and no recipe beyond 60;
- all four calorie bands `<=350`, `351-500`, `501-650`, and `>650` represented;
- at least four recipes in each protein band `<15`, `15-24.9`, `25-34.9`, and `>=35`;
- required ingredient counts only from 3 through 8, with at least four recipes in each `3-4`, `5-6`, and `7-8` band;
- every recipe shares at least one ingredient with another recipe;
- at least six unordered recipe pairs share two or more required IDs;
- at least ten canonical IDs appear in at least four but fewer than 24 recipes;
- every proposed confusable negative resolves as `unresolved`.

Run:

```powershell
uv run pytest tests/test_catalog.py tests/test_ingredients.py -v
```

Expected: tests expose any matrix, registry, alias, overlap, or stability failure until the exact candidate facts satisfy every gate. Do not weaken a gate to make a candidate pass.

- [ ] **Step 3: Write the compact candidate review package**

Mark `docs/data/recipe-catalog-v1.md` as `Candidate — not released` and include, for every one of the 24 records:

- recipe ID and display name;
- ordered required ingredient IDs;
- calories, `protein_g`, and `prep_minutes`;
- meal/category review tags;
- culinary-tradition review tag;
- dietary review tag;
- derived preparation, calorie, protein, and ingredient-count bands.

Then include exact aggregate counts for every coverage gate, the qualifying unordered pairs with two-or-more overlap, each recipe's at-least-one-overlap witness, every ingredient used by four-or-more recipes with its count, the complete new canonical-ID list, complete proposed alias mapping, complete targeted confusable-negative list, author/owner, creation date, estimate method, and statements that values are representative estimates and review tags are not allergy or medical guarantees.

- [ ] **Step 4: Cross-check source, registry, and review evidence**

Run:

```powershell
uv run pytest tests/test_catalog.py tests/test_ingredients.py -v
uv run python -c "from pantrypilot.catalog import OFFICIAL_RECIPE_CATALOG; print(len(OFFICIAL_RECIPE_CATALOG)); print(*(recipe.id for recipe in OFFICIAL_RECIPE_CATALOG), sep='\n')"
git diff -- src/pantrypilot/catalog.py src/pantrypilot/ingredients.py tests/test_catalog.py tests/test_ingredients.py docs/data/recipe-catalog-v1.md
git diff --check
```

Expected: tests pass; the command prints `24` followed by 24 unique IDs; the diff contains no runtime release version, digest ledger entry, CC0 claim, app integration, benchmark result, or ranking change.

- [ ] **Step 5: Leave the candidate uncommitted for owner review**

Do not commit the exact candidate facts before Task 6. Preserve the reviewable working-tree diff so requested factual changes can be made without rewriting a released ledger entry.

---

### Task 6: OWNER CHECKPOINT — Exact Corpus, Ingredient, Alias, and Negative Facts

**Files:**

- Review: `docs/data/recipe-catalog-v1.md`
- Review diff: `src/pantrypilot/catalog.py`, `src/pantrypilot/ingredients.py`, `tests/test_catalog.py`, `tests/test_ingredients.py`
- Modify: none unless the owner requests factual changes

- [ ] **Step 1: Stop execution and present the exact candidate**

Present the owner with the candidate document and a concise summary containing:

- total recipe count;
- all 24 IDs/names/ordered ingredient lists/nutrition/time values;
- exact coverage-matrix counts;
- overlap witnesses and all pairs sharing at least two ingredients;
- ingredients appearing in at least four recipes;
- new canonical ingredient IDs;
- proposed aliases;
- targeted confusable negatives;
- focused validation commands and results;
- the exact uncommitted file list.

- [ ] **Step 2: Do not continue without explicit factual approval**

Execution stops here. Approval of the design strategy and CC0 scope does not approve these exact facts. If the owner requests a change, return to Task 5, update the candidate facts/evidence, rerun every Task 5 check, and present the entire exact package again. Do not compute/pin catalog content version 1, create the CC0 artifact, create v2, integrate startup, or commit candidate facts until the owner explicitly approves the full package.

---

### Task 7: Finalize the Approved Release Ledger, Provenance, and Scoped CC0 Notice

**Files:**

- Modify: `src/pantrypilot/catalog_release.py`
- Modify: `tests/test_catalog.py`
- Finalize: `docs/data/recipe-catalog-v1.md`
- Create: `docs/data/official-recipe-catalog-CC0-1.0.md`
- Include approved candidate changes: `src/pantrypilot/catalog.py`, `src/pantrypilot/ingredients.py`, `tests/test_ingredients.py`

**Interfaces:**

- Produces `CURRENT_CATALOG_CONTENT_VERSION = 1`, immutable `CATALOG_RELEASE_DIGESTS`, and:

```python
def current_catalog_release(
    ingredient_registry: IngredientRegistry,
) -> CatalogRelease: ...
```

- [ ] **Step 1: Compute the digest only from approved facts**

Run:

```powershell
$digestCommand = "from pantrypilot.catalog import OFFICIAL_RECIPE_CATALOG, RETIRED_OFFICIAL_RECIPE_IDS; from pantrypilot.catalog_release import catalog_manifest_digest; print(catalog_manifest_digest(OFFICIAL_RECIPE_CATALOG, RETIRED_OFFICIAL_RECIPE_IDS))"
$firstDigest = (uv run python -c $digestCommand).Trim()
$secondDigest = (uv run python -c $digestCommand).Trim()
if ($firstDigest -notmatch '^[0-9a-f]{64}$') { throw 'Invalid release digest' }
if ($secondDigest -ne $firstDigest) { throw 'Release digest is not deterministic' }
$firstDigest
```

Task 5's passing catalog tests already prove registry validity; this command establishes only the canonical identity to pin. Do not hand-edit recipe order or ingredient order to obtain a preferred digest. The digest records the approved facts; it does not choose them.

- [ ] **Step 2: Write failing production-ledger tests**

Add independent literal assertions for release version 1 and its exact computed digest. Assert ledger keys are consecutive and immutable, `current_catalog_release` returns exactly 24 frozen recipes, and changing any scalar, ingredient order, recipe addition/removal, or retired set while holding the literal ledger fixed fails.

Run:

```powershell
uv run pytest tests/test_catalog.py -v
```

Expected: tests fail until version 1, its literal digest, and the production wrapper are defined.

- [ ] **Step 3: Add the immutable version-1 ledger entry**

Set `CURRENT_CATALOG_CONTENT_VERSION = 1`, create a read-only mapping containing only key `1` and the exact 64-character output from Step 1, and make `current_catalog_release` call `build_catalog_release` with the approved manifest and cumulative retired IDs. Never calculate the ledger value dynamically at import time.

- [ ] **Step 4: Finalize provenance and the data-only dedication**

Change the provenance status from candidate to owner-approved release, record the review date, version 1, and exact digest. Create `docs/data/official-recipe-catalog-CC0-1.0.md` stating that the owner applies CC0 1.0 Universal only to:

- the official recipe facts in `OFFICIAL_RECIPE_CATALOG`; and
- the factual provenance and coverage metadata in `docs/data/recipe-catalog-v1.md`.

State explicitly that PantryPilot source code, tests, documentation outside that provenance metadata, trademarks, and third-party material are not licensed or dedicated by this notice. Link the CC0 1.0 legal code. Do not add a repository-root `LICENSE` or imply repository-wide CC0.

- [ ] **Step 5: Verify and commit the approved release when authorized**

```powershell
uv run pytest tests/test_catalog.py tests/test_ingredients.py -v
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
git diff --stat
git status --short --branch
git add src/pantrypilot/catalog.py src/pantrypilot/catalog_release.py src/pantrypilot/ingredients.py tests/test_catalog.py tests/test_ingredients.py docs/data/recipe-catalog-v1.md docs/data/official-recipe-catalog-CC0-1.0.md
git commit -m "data: release representative recipe catalog"
```

Expected: the committed release contains only owner-approved facts, their pinned identity, focused validation, provenance, and the scoped notice.

---

### Task 8: Add Ingredient Resolution V2 and Move the Authoritative CI Evidence

**Files:**

- Create: `evaluations/ingredient-resolution-v2.json`
- Modify: `tests/test_evaluation.py`
- Modify: `.github/workflows/ci.yml`
- Modify only evaluator command paths: `README.md`
- Do not modify: `evaluations/ingredient-resolution-v1.json`, `src/pantrypilot/evaluation.py`, resolver logic in `src/pantrypilot/ingredients.py`

- [ ] **Step 1: Split historical-v1 and current-v2 test responsibilities**

Replace the test that requires v1 to cover the current expanded registry with exact historical evidence:

- v1 SHA-256 is `523255671bdbc141aca565ab479daffdfa5db0bc07e09454d0a969e22dbba48d`;
- v1 retains schema version 1, 28 cases, 14 canonical, 7 alias, and 7 unresolved rows;
- v2 schema version remains 1;
- the first 28 v2 cases equal v1 in value and order;
- v2 has no duplicate normalized input;
- v2 has exactly one canonical positive per current registry entry and one alias positive per current explicit alias;
- every new alias's reviewed confusable negative is present and unresolved;
- the exact-name baseline remains strictly lower recall than the canonical/alias resolver;
- v2 canonical/alias resolver has zero false positives and no false negatives.

- [ ] **Step 2: Run the new tests before creating v2**

```powershell
uv run pytest tests/test_evaluation.py -v
```

Expected: v2-path tests fail because the fixture does not exist; historical v1 assertions pass.

- [ ] **Step 3: Create the strict-superset fixture**

Copy all 28 v1 case objects unchanged and in order, append one canonical row for every new registry entry, append one alias row for every new alias, then append the exact owner-reviewed unresolved/confusable negatives. Do not change the JSON schema or evaluator implementation.

- [ ] **Step 4: Update the two authoritative command surfaces**

Change only the fixture argument in `.github/workflows/ci.yml`, README Quick start, and README local verification contract from `ingredient-resolution-v1.json` to `ingredient-resolution-v2.json`. Preserve every other Feature 005 workflow line.

- [ ] **Step 5: Run focused and command-level evidence**

```powershell
uv run pytest tests/test_ingredients.py tests/test_evaluation.py -v
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v2.json
git diff -- evaluations/ingredient-resolution-v1.json
git diff --check
```

Expected: tests and evaluator exit 0 with improved recall and zero false positives; the v1 diff is empty.

- [ ] **Step 6: Commit v2 evidence when authorized**

```powershell
git add evaluations/ingredient-resolution-v2.json tests/test_evaluation.py .github/workflows/ci.yml README.md
git commit -m "test: expand ingredient resolution evidence"
```

---

### Task 9: Integrate Release Reconciliation into Startup and Preserve Ranking Semantics

**Files:**

- Modify: `src/pantrypilot/catalog_store.py`
- Modify: `src/pantrypilot/app.py`
- Modify: `tests/test_catalog_store.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_ranking.py`
- Modify: `tests/test_ranking_parity.py`
- Modify: `tests/test_saved_pantry_ranking_parity.py`
- Modify: `tests/test_pantry_store.py`
- Do not modify: `src/pantrypilot/ranking.py`, `src/pantrypilot/models.py`, `src/pantrypilot/pantry_store.py`

**Interfaces:**

- Replace the seed-oriented public initializer with:

```python
def initialize_catalog(
    database_path: Path,
    ingredient_registry: IngredientRegistry,
) -> None: ...
```

- The function calls `current_catalog_release(ingredient_registry)` before `connect_catalog`, migrates, calls `reconcile_catalog`, closes, and leaves `load_durable_catalog` as the separate reopen/validate/load step used by app lifespan.

- [ ] **Step 1: Write failing startup-preflight and 24-record integration tests**

Add a parameterized test that mutates each release dimension—owned scalar, ingredient order, addition, removal, and retired set—while holding version 1's ledger digest fixed. Monkeypatch `connect_catalog` to fail if called. Assert `initialize_catalog` raises `CatalogStoreError`, the connection spy is untouched, and the database path does not exist.

Update integration assertions to require:

- fresh lifespan publishes exactly 24 frozen recipes;
- a direct official scalar edit is restored on restart;
- a missing official recipe is repaired on restart;
- a valid out-of-band recipe survives restart and appears in the complete snapshot;
- current/retired out-of-band collisions prevent startup without changing recipe or pantry rows;
- request-time ranking still performs no recipe-database I/O;
- schema/content startup failure prevents serving and never falls back to code data.

- [ ] **Step 2: Make ranking regression tests corpus-independent**

Keep formula, soft protein target, hard prep/exclusion, unresolved exclusion, deterministic tie, and post-sort limit tests on explicit small `Recipe` tuples or the exact Feature 003 legacy tuple. Do not pin a full 24-record order in formula tests. API tests may assert structural compatibility and intended data-driven result IDs, but formula values remain pinned at the function level.

Delete redundant arbitrary-seed tie tests in parity files when `tests/test_ranking.py` already proves the same sort/limit rule. Retain one direct-versus-durable full response parity matrix and complete inline-versus-saved parity over the real 24-record startup catalog.

- [ ] **Step 3: Run integration tests to observe the seed-era failures**

```powershell
uv run pytest tests/test_catalog_store.py tests/test_api.py tests/test_ranking.py tests/test_ranking_parity.py tests/test_saved_pantry_ranking_parity.py tests/test_pantry_store.py -v
```

Expected: old initializer signatures, four-record size, and durable-edit-survival assertions fail until startup uses release reconciliation and tests adopt the new ownership contract.

- [ ] **Step 4: Integrate the validated release before database access**

In `initialize_catalog`, call `current_catalog_release` first and wrap its validation failures as `CatalogStoreError`; only then connect, migrate, and reconcile. In `app.py`, remove `INITIAL_RECIPE_CATALOG` and call the new initializer with the path and registry. Keep the subsequent reopen through `load_durable_catalog` and immutable application-state tuple exactly as the current flow.

- [ ] **Step 5: Prove public ranking behavior and pantry parity**

Run:

```powershell
uv run pytest tests/test_ranking.py tests/test_ranking_parity.py tests/test_saved_pantry_ranking_parity.py tests/test_api.py -v
uv run pytest tests/test_catalog.py tests/test_database.py tests/test_catalog_store.py tests/test_pantry_store.py -v
uv run ruff format --check src tests
uv run ruff check src tests
git diff -- src/pantrypilot/ranking.py src/pantrypilot/models.py src/pantrypilot/pantry_store.py
git diff --check
```

Expected: all tests pass; the three prohibited production files have empty diffs; inline/saved responses match exactly; official edits restore; out-of-band and saved-pantry rows persist.

- [ ] **Step 6: Commit startup integration when authorized**

```powershell
git add src/pantrypilot/catalog_store.py src/pantrypilot/app.py tests/test_catalog_store.py tests/test_api.py tests/test_ranking.py tests/test_ranking_parity.py tests/test_saved_pantry_ranking_parity.py tests/test_pantry_store.py
git commit -m "feat: reconcile official catalog at startup"
```

---

### Task 10: Add the Release-Bound Full-Scan Benchmark Harness and Fixture

**Files:**

- Create: `src/pantrypilot/benchmark.py`
- Create: `tests/test_benchmark.py`
- Create: `benchmarks/full-scan-ranking-v1.json`

**Interfaces:**

- Consumes: `current_catalog_release`, `RankingRequest`, `INGREDIENT_REGISTRY`, `rank_recipes`, and `is_eligible`.
- Produces:

```python
def nearest_rank_percentile(samples_ns: Sequence[int], percentile: float) -> int: ...


def run_benchmark(
    fixture_path: Path,
    *,
    clock: Callable[[], int] = time.perf_counter_ns,
) -> dict[str, object]: ...


def main(argv: Sequence[str] | None = None) -> int: ...
```

- CLI: `uv run python -m pantrypilot.benchmark benchmarks/full-scan-ranking-v1.json` prints indented JSON with sorted keys and returns nonzero with one JSON error object on invalid fixture, release drift, response drift, or nondeterministic output.

- [ ] **Step 1: Write failing fixture/statistics/output tests**

Test all of these without asserting live latency:

- fixture validation requires schema version 1, a release version/digest, positive catalog size, non-negative warmups, positive measurements, at least one unique workload ID, and exact allowed request fields;
- the committed fixture specifically pins release version 1, its exact digest, catalog size 24, warmups 100, measurements 1,000, and exactly the workload IDs `broad-high-coverage`, `broad-low-coverage`, `strict-preparation-limit`, `common-hard-exclusion`, `high-protein-target`, and `typical-limited-response`;
- each workload stores exact expected eligible count, ordered response IDs, and response digest;
- fixture/release version, digest, or size drift fails before timing;
- nearest-rank p95 returns sorted sample index `ceil(0.95 * n) - 1`, including fixed even/odd samples;
- `statistics.median` supplies the median and min/max use the same integer nanosecond samples;
- a fake clock and reduced in-memory fixture produce deterministic output fields and key ordering;
- every measured response is compared after the end timestamp with the first validated response;
- changing one response between iterations fails;
- output includes catalog size, eligible count, returned count, response IDs/digest, median/p95/min/max milliseconds, Python implementation/version, platform/OS/machine/processor, fixture SHA-256, catalog version/digest, warmups, measurements, UTC run time, and git commit.

Run:

```powershell
uv run pytest tests/test_benchmark.py -v
```

Expected: import fails because the benchmark module does not exist.

- [ ] **Step 2: Implement exact fixture validation and response identity**

Use `json.loads`, exact key-set checks, existing `RankingRequest.model_validate`, and `hashlib.sha256`. Define the response digest as SHA-256 over `json.dumps(response.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")`. Reject unresolved exclusions in the benchmark fixture. Compute eligible counts outside the timed region using the same resolved exclusion IDs and `is_eligible` hard-constraint function.

The fixture is evidence only: it must equal the production release pair and expected catalog size and cannot define a different catalog.

- [ ] **Step 3: Implement the timed loop and statistics**

For each workload:

1. Build and validate the request outside timing.
2. Call `rank_recipes` once outside timing; validate expected IDs, response digest, eligible count, and returned count.
3. Perform exactly 100 untimed warmups and require every response to equal the validated response.
4. For exactly 1,000 iterations, read `start = perf_counter_ns()`, call only `rank_recipes(request, release.recipes, INGREDIENT_REGISTRY)`, read `end = perf_counter_ns()`, append `end - start`, then compare the response outside the timed interval.
5. Calculate median with `statistics.median`, nearest-rank p95, minimum, and maximum; convert to milliseconds only for output.

Do not time fixture I/O, validation, release hashing, environment inspection, eligible counting, JSON serialization, or result comparison.

- [ ] **Step 4: Author the six fixed real-catalog workloads**

Use owner-approved canonical names and exact aliases from the release:

- broad/high coverage: common pantry, max 60, no exclusions, limit 50;
- broad/low coverage: sparse pantry plus one intentionally unresolved pantry term, max 60, no exclusions, limit 50;
- strict preparation: realistic pantry, max 20;
- common hard exclusion: a resolvable ingredient shared by several but not all recipes;
- high protein: target above many recipes, max 60, no protein filtering;
- typical limited: mixed pantry, max 30, one resolvable exclusion, limit 5.

Run each request once outside the benchmark, calculate and paste its exact expected eligible count, ordered response IDs, and canonical response digest into the fixture. The fixture iteration counts remain 100 and 1,000.

- [ ] **Step 5: Verify benchmark semantics without using elapsed time as a gate**

```powershell
uv run pytest tests/test_benchmark.py -v
uv run pytest tests/test_ranking.py tests/test_ranking_parity.py tests/test_saved_pantry_ranking_parity.py -v
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: fixture/release/output drift tests pass; no test contains a live millisecond threshold.

- [ ] **Step 6: Commit the benchmark machinery when authorized**

```powershell
git add src/pantrypilot/benchmark.py tests/test_benchmark.py benchmarks/full-scan-ranking-v1.json
git commit -m "feat: add full-scan ranking benchmark"
```

---

### Task 11: Execute and Record the Python 3.12 Reference Benchmark

**Files:**

- Create from exact command output: `benchmarks/results/full-scan-ranking-v1-reference.json`
- Draft: `docs/benchmarks/006-full-scan-baseline.md`
- Modify production code: none

- [ ] **Step 1: Require a clean, committed benchmark identity**

Run:

```powershell
git status --short --branch
git rev-parse HEAD
uv run python --version
uv run pytest tests/test_benchmark.py tests/test_ranking.py -q
```

Expected: working tree is clean, HEAD identifies the committed harness/fixture, Python is 3.12.*, and semantic tests pass. Stop if uncommitted code/data would make the recorded git commit inaccurate.

- [ ] **Step 2: Run the approved command once on the documented reference machine**

```powershell
uv run python -m pantrypilot.benchmark benchmarks/full-scan-ranking-v1.json
```

Expected: exit 0; six workloads; catalog size 24; 100 warmups and 1,000 measurements each; stable exact response IDs/digests; complete environment and git metadata. Do not alter the fixture after seeing latency unless a correctness mismatch proves the fixture wrong and the owner reviews that change.

- [ ] **Step 3: Preserve the raw output exactly**

Use the implementation agent's patch-edit mechanism to create `benchmarks/results/full-scan-ranking-v1-reference.json` from the complete stdout, without reformatting values or deleting metadata. Validate it with `python -m json.tool` and compare its release pair, fixture digest, commit, response IDs, and response digests with the fixture and current release.

- [ ] **Step 4: Apply the approved decision rule**

- If the worst successful workload p95 is below 50 ms, outputs are stable, and code/test inspection exposes no correctness or retained-memory concern, draft conclusion A: retrieval remains deferred.
- If the worst p95 is at least 50 ms, run a second clean benchmark. Only when both clean runs are at least 50 ms, profile the exhaustive `rank_recipes` call with standard-library `cProfile`, confirm ranking rather than fixture/HTTP/database work is material, and draft conclusion B: retrieval may be proposed as a later feature.
- If two clean runs straddle 50 ms or profiling does not show exhaustive ranking is material, report mixed evidence at Task 12 and make neither stronger claim. Do not add retrieval or change the predeclared threshold.

- [ ] **Step 5: Draft the evidence document without committing it**

In `docs/benchmarks/006-full-scan-baseline.md`, record the fixed methodology, exact reference environment, raw-result link, all workload catalog/eligible/returned counts, median/p95/min/max, response identities, worst workload, decision-rule application, limitations, and draft A/B conclusion. State that hosted CI does not enforce wall time and that 24 records do not model internet scale.

Do not commit the raw result or conclusion before Task 12.

---

### Task 12: OWNER CHECKPOINT — Benchmark Evidence and Retrieval Conclusion

**Files:**

- Review: `benchmarks/results/full-scan-ranking-v1-reference.json`
- Review: `docs/benchmarks/006-full-scan-baseline.md`
- Review: `benchmarks/full-scan-ranking-v1.json`
- Modify: none unless the owner requests evidence corrections

- [ ] **Step 1: Stop execution and present the exact evidence**

Present the git commit, Python/platform metadata, fixture/release digests, all six workload counts and timing statistics, stable response IDs/digests, worst p95, any required second run/profile evidence, correctness/memory assessment, and the exact draft retrieval conclusion.

- [ ] **Step 2: Do not continue without explicit result/conclusion approval**

Execution stops here. Do not mark the benchmark conclusion accepted, update README/vision/roadmap current-state language, or commit the raw result until the owner explicitly approves the evidence and conclusion. Requested reruns must use the unchanged committed harness and fixture and remain separately identifiable.

---

### Task 13: Complete Feature Documentation After Benchmark Approval

**Files:**

- Finalize: `docs/benchmarks/006-full-scan-baseline.md`
- Include approved result: `benchmarks/results/full-scan-ranking-v1-reference.json`
- Create: `docs/learning/006-representative-catalog-expansion.md`
- Modify: `README.md`
- Modify only supported current-state text: `docs/product/vision.md`, `docs/roadmap.md`
- Verify links: `docs/data/recipe-catalog-v1.md`, `docs/data/official-recipe-catalog-CC0-1.0.md`

- [ ] **Step 1: Finalize benchmark documentation from approved evidence**

Record the approved A/B conclusion verbatim in substance, retain exact methodology and evidence limits, link the raw result and fixture, and state that Feature 006 does not implement retrieval. Do not copy the complete raw JSON into Markdown.

- [ ] **Step 2: Write the Feature 006 learning guide**

Cover:

- why schema version and catalog content version are independent;
- canonical serialization and immutable release ledgers;
- why ownership markers protect out-of-band facts;
- conservative legacy adoption and collision-first transactions;
- official correction/removal and rollback semantics;
- saved-pantry preservation and stable ingredient identities;
- exact resolution, v1/v2 evidence versioning, and unsafe false positives;
- original factual corpus provenance and narrowly scoped CC0;
- benchmark timed-region discipline, percentile calculation, reproducibility, and evidence limits;
- practical exercises;
- mock-interview questions with answer guidance for every subject above.

- [ ] **Step 3: Update README without duplicating owner documents**

Set current status to Feature 006, summarize the 24-recipe official/out-of-band ownership model, show the v2 evaluator and benchmark commands, state the approved retrieval conclusion, link the Feature 006 design/plan/provenance/license/benchmark/learning artifacts, and correct both stale CI passages: pull-request and push-to-main execution are proven, while branch protection remains separate.

- [ ] **Step 4: Update product current state only where evidence changed**

In `docs/product/vision.md`, replace the four-seed/seed-only current boundary with the versioned 24-official-recipe plus preserved out-of-band model and the approved retrieval conclusion. In `docs/roadmap.md`, update Phase 4 evidence wording to acknowledge the representative full-scan baseline and approved decision; do not mark retrieval implemented or add new phases.

- [ ] **Step 5: Verify documentation consistency and commit when authorized**

```powershell
rg -n "four recipes|seed.*only|ingredient-resolution-v1|push-to-main.*unproven|retrieval" README.md docs/product/vision.md docs/roadmap.md docs/data docs/benchmarks docs/learning/006-representative-catalog-expansion.md
git diff --check
git status --short --branch
```

Expected: historical descriptions are either clearly historical or removed from current-state prose; v1 remains documented as frozen history; retrieval wording matches the owner-approved conclusion and never claims implementation; CC0 scope remains data-only.

```powershell
git add README.md docs/product/vision.md docs/roadmap.md docs/benchmarks/006-full-scan-baseline.md benchmarks/results/full-scan-ranking-v1-reference.json docs/learning/006-representative-catalog-expansion.md
git commit -m "docs: record representative catalog baseline"
```

---

### Task 14: Complete Focused and Full Verification

**Files:**

- Verify: every file in the responsibility map
- Modify: only files directly responsible for a discovered failure, followed by the same focused TDD cycle

- [ ] **Step 1: Run focused catalog identity and evolution verification**

```powershell
uv run pytest tests/test_catalog.py tests/test_database.py tests/test_catalog_store.py tests/test_pantry_store.py -v
```

Expected: canonical serialization, all digest sensitivities, ledger pinning, schema 3, legacy adoption, all current/retired collisions, additions/corrections/removals, official restoration/repair, digest verification, atomicity, rollback, idempotence, convergence, out-of-band preservation, and saved-pantry preservation pass.

- [ ] **Step 2: Run focused registry/evaluation verification**

```powershell
uv run pytest tests/test_ingredients.py tests/test_evaluation.py -v
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v2.json
```

Expected: v1 hash/frozen-history, v2 strict superset and complete term coverage, targeted negatives, recall improvement, and zero false positives pass.

- [ ] **Step 3: Run focused ranking/API/benchmark semantic verification**

```powershell
uv run pytest tests/test_ranking.py tests/test_ranking_parity.py tests/test_saved_pantry_ranking_parity.py tests/test_api.py tests/test_benchmark.py -v
```

Expected: formula, soft protein, hard prep/exclusions, fail-closed unresolved exclusions, deterministic order, post-sort limit, durable parity, inline/saved parity, startup snapshot, fixture binding, statistics, deterministic output, and drift failure pass. No live-time threshold is asserted.

- [ ] **Step 4: Run the complete repository contract**

Run each command separately:

```powershell
uv lock --check
uv run pytest
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v2.json
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: every command exits 0. Do not use a bare evaluator command and do not add a benchmark latency command to CI.

- [ ] **Step 5: Inspect final scope and immutable artifacts**

```powershell
(Get-FileHash -Algorithm SHA256 evaluations/ingredient-resolution-v1.json).Hash.ToLowerInvariant()
git diff 8b262507ca5260b0638dc99cbaeeaa2ba1277523 -- src/pantrypilot/ranking.py src/pantrypilot/evaluation.py src/pantrypilot/models.py src/pantrypilot/pantry_store.py pyproject.toml uv.lock
git diff 8b262507ca5260b0638dc99cbaeeaa2ba1277523 -- .github/workflows/ci.yml
git status --short --branch
git log --oneline --decorate 8b262507ca5260b0638dc99cbaeeaa2ba1277523..HEAD
```

Expected:

- v1 hash is exactly `523255671bdbc141aca565ab479daffdfa5db0bc07e09454d0a969e22dbba48d`;
- prohibited production/dependency files have empty diffs;
- CI changes only the evaluator path from v1 to v2;
- no database, cache, credential, environment, benchmark scratch, or unrelated file exists;
- commits match the approved boundaries and nothing was pushed.

- [ ] **Step 6: Perform the final requirement audit**

Confirm every item in the coverage map and self-review below against the actual diff and test names. If any assertion is unsupported, fix the responsible task and rerun its focused command plus the complete contract. Stop after reporting the verified implementation; do not push or open a PR.

---

## Intended Commit Boundaries

1. `docs: approve feature 006 design and plan` — the pre-implementation
   documentation baseline containing exactly the approved spec and this plan;
   committed locally only after execution and commit authorization, before any
   production implementation.
2. `feat: add catalog release identity` — Task 1 pure serializer, digest, ledger validation, and tests.
3. `feat: add catalog content state schema` — Task 2 migration 3 and schema tests.
4. `feat: reconcile legacy official recipes` — Task 3 fresh/version-0 adoption and preservation behavior.
5. `feat: protect reserved official recipe ids` — Task 4 managed evolution, collisions, digest verification, and rollback.
6. No candidate commit before Task 6. After exact factual approval, `data: release representative recipe catalog` contains Tasks 5 and 7 approved facts, registry additions, release pair, provenance, and scoped CC0 notice.
7. `test: expand ingredient resolution evidence` — Task 8 v2 fixture, tests, authoritative evaluator paths, and only the justified CI path edit.
8. `feat: reconcile official catalog at startup` — Task 9 app/store integration and ranking/API/pantry regressions.
9. `feat: add full-scan ranking benchmark` — Task 10 harness, semantic tests, and fixed fixture; committed before measurement so the recorded git commit is meaningful.
10. No result commit before Task 12. After benchmark owner approval, `docs: record representative catalog baseline` contains the raw result, benchmark conclusion, learning guide, README, vision, and roadmap updates.

No commit is pushed by this plan.

---

## Approved Design Coverage Map

- Exactly 24 original factual records, four stable IDs, matrix gates, estimates, and no copied prose: Tasks 5–7.
- Exact corpus/ingredient/alias owner review before release identity: Task 6 hard stop.
- Stable current and cumulative retired namespace: Tasks 1, 4, 7, and 14.
- Additive exact ingredient registry with no fuzzy behavior: Tasks 5, 8, 9, and 14.
- Frozen v1, schema-shape-1 strict-superset v2, full registry/alias coverage, targeted negatives, zero false positives, and CI path: Task 8.
- Schema 3 ownership column and independent singleton content state: Task 2.
- One canonical serializer, every owned field/order/retired set, SHA-256, and source-order independence: Task 1.
- Append-only immutable version/digest ledger and pre-database drift failure: Tasks 1, 7, and 9.
- Fresh, legacy, managed-current, and managed-upgrade reconciliation: Tasks 3, 4, and 9.
- Conservative exact Feature 003 adoption and divergent legacy failure: Task 3.
- Collision scan before writes for current and retired IDs: Tasks 3 and 4.
- Official addition/correction/restoration/deletion/retirement rules: Task 4.
- Resulting official digest, atomic pair update, rollback, rerun, and convergence: Tasks 3 and 4.
- Durable out-of-band authority and complete-catalog runtime hydration: Tasks 3, 4, and 9.
- Saved-pantry preservation on successful and failed evolution: Tasks 3, 4, 9, and 14.
- Unchanged full-scan ranking/API semantics and inline/saved parity: Task 9.
- Fixed six-workload, 100/1,000, `perf_counter_ns`, deterministic standard-library benchmark: Task 10.
- Reference result, decision A/B rule, no CI timing gate, no retrieval: Tasks 11–14.
- Data-scoped CC0 only: Task 7.
- README, provenance, benchmark, learning/interview, vision, and roadmap documentation: Tasks 5, 7, 11–13.
- Complete Feature 005 verification contract with v2 evaluator path: Tasks 8 and 14.
- Approved spec/plan committed as the clean execution baseline before Task 1:
  Pre-Implementation Documentation Baseline.

---

## Plan Self-Review Record

1. Every approved design requirement maps to the coverage map and at least one executable test or evidence step.
2. Task 6 and Task 12 are explicit unconditional owner stops.
3. Candidate facts remain uncommitted, unversioned, unlicensed as a released corpus, and unintegrated until Task 6 approval.
4. `src/pantrypilot/ranking.py` is explicitly unchanged; focused tests pin every ranking semantic.
5. Task 2 uses `PRAGMA user_version = 3` only for schema and version 1 only in `catalog_content_state`/release code.
6. Tasks 3 and 4 complete a read-only reserved-ID scan before writes and never mutate an out-of-band row.
7. Current and cumulative retired IDs are validated as one disjoint reserved namespace and both collision classes are tested.
8. Canonical digest, append-only literals, durable historical pair validation, pinned tests, and pre-connection drift failure prevent silent release-pair changes.
9. Both pantry tables are compared row-for-row across successful reconciliation and injected failure.
10. V1 is protected by the exact SHA-256 and v2 completeness no longer reinterprets historical v1.
11. Benchmark tests are semantic/synthetic; hosted CI receives no wall-clock assertion.
12. Retrieval, indexing, embeddings, synthetic scale, and candidate generation remain outside every file/task.
13. The CC0 filename and text scope only the official data/provenance pair and explicitly exclude the codebase.
14. `CatalogRelease`, serializer, digest, ledger, initializer, reconciliation, fixture, and benchmark names/signatures are consistent across tasks.
15. No task depends on an unspecified implementation action; unknown future factual values and timings are created by exact commands and then reviewed at the required gates.
16. Task order follows identity → schema → reconciliation → collision safety → candidate → approval → release → evaluation → startup → benchmark → measurement → approval → docs → verification.
17. The pre-implementation section commits only the approved spec and plan,
    verifies that commit directly follows the approved base, and requires a
    clean working tree before Task 1.
18. Task 1 re-establishes the committed repository context, every task names
    inputs, outputs, files, commands, expected results, and commit boundary for
    a fresh worker with no conversation history, and Task 11 can require a
    genuinely clean committed benchmark identity.
