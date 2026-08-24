# Feature 006: Representative recipe catalog expansion and full-scan baseline

Status: Owner-approved for implementation

Design date: 2026-08-22

Owner approval date: 2026-08-23

The owner approved exactly 24 total official recipes including the existing
four, an original PantryPilot-authored factual corpus, and a data-scoped CC0
1.0 notice for the official catalog data and its provenance metadata. The only
remaining owner checkpoints are review of the exact candidate facts before
release and review of the measured benchmark evidence and retrieval conclusion.

GitHub issue: [#11](https://github.com/sathvick-sudarsan/pantrypilot/issues/11)

## 1. Context and verified current state

This design was prepared from linked worktree
`representative-catalog-expansion`, branch
`feat/representative-catalog-expansion`, at commit
`8b262507ca5260b0638dc99cbaeeaa2ba1277523`. The worktree was clean before
this document was created.

The live repository confirms the following baseline:

- `catalog.py` defines four seed records: `spinach-omelet`,
  `black-bean-tacos`, `peanut-noodles`, and `lentil-soup`.
- `load_catalog` validates frozen `Recipe` models, rejects unknown canonical
  ingredient IDs and duplicate recipe IDs, and returns a tuple.
- `catalog_store.py` migrates, then seeds only when both catalog tables are
  empty. A valid non-empty catalog is neither compared with nor topped up from
  the Python seed.
- SQLite schema version 2 has exactly four application tables: `recipes`,
  ordered `recipe_ingredients`, `saved_pantry`, and `saved_pantry_items`.
  `PRAGMA user_version` describes schema only; no catalog-content version
  exists.
- The code-owned ingredient registry has 14 stable IDs. Resolution is a
  normalized exact canonical-name or explicit-alias lookup and otherwise
  abstains. There is no fuzzy matching.
- Startup initializes the store, reloads the complete durable catalog through
  model and registry validation, and publishes one immutable snapshot in
  application state.
- Both ranking endpoints call the same exhaustive `rank_recipes` function over
  that snapshot. Maximum preparation time and exclusions are hard constraints;
  minimum protein is a scoring target. Unresolved exclusions fail closed,
  unresolved pantry terms do not match, results sort by descending exposed
  score then recipe ID, and `limit` is applied last.
- `ingredient-resolution-v1.json` has schema version 1, all 14 canonical terms,
  all seven aliases, and seven negative cases. The required command accepts the
  fixture path explicitly.
- CI covers pull requests and pushes to `main`. GitHub Actions shows the
  successful push run for commit `8b26250`, so the README's “unproven until
  merge” wording is stale.

The approved Feature 003 design deliberately made durable recipe rows
authoritative after initial seeding. Its tests prove that a changed official
seed row and an arbitrary valid durable-only row survive restart. Feature 006
must replace that contract explicitly, not accidentally.

## 2. Problem statement

Four recipes are too few to give useful pantry-dependent variety and too few
to provide credible evidence about exhaustive ranking. Editing only
`INITIAL_RECIPE_CATALOG` would also split installations: fresh databases would
receive new recipes while every valid existing database remained unchanged.

Feature 006 needs a reviewable and redistributable official corpus, a precise
boundary between application-owned and out-of-band recipe facts, deterministic
content evolution independent of schema evolution, and a reproducible timing
baseline. It must preserve saved pantry state and every public ranking
semantic. It does not add retrieval.

## 3. Product capability being added

Users receive materially more realistic meal choices for the same pantry and
constraints. Maintainers receive:

- an approved official catalog with stable IDs and source/license evidence;
- convergent behavior for fresh and upgraded databases;
- explicit handling of official, modified, removed, and out-of-band rows;
- ingredient-resolution evidence that grows with the registry; and
- a measured full-scan baseline used to decide whether retrieval remains
  deferred.

The API surface and ranking formula do not change.

## 4. Representative-catalog definition

“Representative” means coverage of PantryPilot decisions, not statistical
representation of all recipes or users. The approved 24-record set must satisfy
one documented coverage matrix. Categories are review metadata only; no new
runtime cuisine, meal-type, or dietary fields are justified because ranking
does not consume them.

The matrix must show:

- breakfast, lunch/light-meal, dinner, and soup/stew/salad choices, including
  at least four breakfast and four soup/stew/salad records;
- at least eight culinary traditions, at least two records per tradition, and
  no tradition accounting for more than six records;
- at least 12 meat/fish-free choices, including at least six vegan choices,
  and at least six choices containing poultry, fish, or meat;
- preparation-time coverage across `<=15`, `16-30`, `31-45`, and `46-60`
  minute bands, with at least four records in every band;
- calorie values spanning at least `<=350`, `351-500`, `501-650`, and `>650`;
- protein values with at least four records in each of `<15`, `15-24.9`,
  `25-34.9`, and `>=35` grams;
- required-ingredient counts spanning three through eight, with at least four
  recipes in each of the `3-4`, `5-6`, and `7-8` bands;
- every recipe sharing at least one required ingredient with another recipe,
  at least six recipe pairs sharing two or more, and at least ten canonical
  ingredients each used by four or more recipes; and
- common ingredients that appear in several but not all recipes so pantry
  coverage and exclusions alter both eligibility and ordering.

The eventual provenance document must publish the completed matrix and exact
counts. Meal and dietary labels are descriptive catalog-review aids, not allergy
or medical guarantees.

## 5. Catalog-size rationale

The target is **24 total official recipes**, including the existing four, so
implementation would add 20. The number follows a bounded product hypothesis:

- fewer than roughly 20 can touch the named dimensions but commonly leaves
  only one candidate in a cuisine, time, or diet intersection;
- 24 permits at least four examples in each preparation band, sixfold growth
  from the current catalog, and meaningful ingredient overlap while remaining
  small enough to review every identity, ordered ingredient list, nutrition
  estimate, and provenance entry by hand; and
- 24 stays below the API's maximum limit of 50, allowing benchmark workloads
  to observe all eligible results without inventing bulk records.

This is not claimed as internet-scale or as evidence that 24 is universally
representative. Selection stops at the first 24 honest recipes satisfying the
matrix; filler recipes and synthetic replication are prohibited. If the final
candidate set cannot satisfy the matrix at 24, the owner must revise either the
matrix or target before data is added rather than quietly relaxing a gate.

## 6. Dataset/source alternatives

### A. Original PantryPilot factual corpus

The project owner authors generic recipe identities and names, ordered
canonical ingredient requirements, and representative per-serving calorie,
protein, and preparation-time estimates. No source text is copied. This is
small, tailored to ranking overlap, and fully reviewable.

### B. Structured external recipe dataset

Serious candidates were Open Recipes, RecipeNLG, and the UCSD Food.com Recipe
and Review dataset. Each offers useful title/ingredient/nutrition-like fields,
but none provides a sufficiently clear end-to-end rights chain for the fields
PantryPilot would redistribute. They are rejected in section 7.

### C. Combination

Wikibooks Cookbook could provide clearly licensed recipe text, or USDA FoodData
Central could support nutrient calculations for original recipes. Wikibooks is
not a clean structured corpus and requires per-page attribution/share-alike
care. FoodData Central is clearly reusable but deriving recipe totals requires
quantities, serving assumptions, and a transformation ledger that this feature
otherwise does not model. A combination adds provenance and transformation
work without improving the 24-record product baseline enough to justify it.

## 7. Licensing/provenance analysis

This is an architecture review, not legal advice. No external data was copied.

### Original PantryPilot facts — owner-approved approach

- **Publisher/owner:** the PantryPilot project owner.
- **Exact approved data license:**
  [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/legalcode.en),
  scoped explicitly to the official catalog data and its provenance metadata.
- **Redistribution and derivatives:** the owner authorized this scoped CC0
  approach on 2026-08-23. The implementation applies the notice after the exact
  corpus facts pass their separate owner checkpoint; attribution is not
  required by CC0, though the repository preserves authorship and provenance
  for auditability.
- **Fields used:** all existing `Recipe` fields only.
- **Fields excluded:** instructions, descriptive prose, quantities, units,
  images, source-site IDs, reviews, and user content.
- **Copyright risk:** the records are independently authored factual summaries.
  The U.S. Copyright Office distinguishes uncopyrightable ingredient/process
  facts from potentially protectable expressive explanation and images in
  [Circular 33](https://www.copyright.gov/circs/circ33.pdf). PantryPilot still
  avoids copying even unprotectable-looking fields because provenance clarity
  is better than reliance on a legal exception.
- **Reproducibility:** a committed catalog provenance document records author,
  creation/review date, factual-estimate method, and coverage tags per recipe.

The repository currently has no license file. The owner authorized the
data-scoped CC0 notice on 2026-08-23, but the exact corpus must not be described
as a released CC0 catalog until its factual checkpoint passes and that scoped
notice is committed. This authorization does not license the source code or
other repository content.

### Open Recipes — license stated, rights chain ambiguous; reject

- **Publisher:** Fictive Kin LLC; archived
  [source repository](https://github.com/fictive-kin/openrecipes).
- **License:** the README says the database is CC BY 3.0 Unported; the repository
  `LICENSE` applies Apache 2.0 to software. Database redistribution would require
  attribution and applicable change notices.
- **Potential fields:** name, ingredient strings, time, yield, nutrition, and
  source URL; instructions are intentionally absent.
- **Excluded fields:** source prose, images, and any publisher-owned content.
- **Reason rejected:** the publisher states that recipes were scraped from
  various publishers. The database license does not establish that Fictive Kin
  could license every underlying publisher-supplied field. An archived 2013
  scrape is also a poor reproducibility and maintenance base. PantryPilot will
  not rely on that ambiguity or reproduce the scraping.

### RecipeNLG — no clear dataset license; reject

- **Publisher:** the Poznan University research team; official
  [repository](https://github.com/glorf/recipenlg).
- **Exact license:** no dataset license is stated in the repository material
  reviewed. A citation request is not a redistribution license.
- **Potential fields:** title, ingredients, directions, source, and named-entity
  annotations.
- **Excluded fields:** all directions/prose and scraped source content.
- **Reason rejected:** the project states that the dataset combines gathered
  recipes and other datasets and includes scraping scripts. Without an explicit
  dataset license and upstream rights chain, transformed structured records
  cannot safely be committed. Reproduction also depends on unavailable or
  changing web sources.

### UCSD Food.com Recipe and Review data — download/citation is not a license; reject

- **Publisher:** UCSD McAuley Lab; official
  [dataset page](https://cseweb.ucsd.edu/~jmcauley/datasets.html).
- **Exact license:** none is stated for the Food.com recipe dataset on the
  publisher page reviewed.
- **Potential fields:** recipe name, ingredients, tags, time, nutrition, and
  directions.
- **Excluded fields:** directions, descriptions, reviews, contributor data,
  and images.
- **Reason rejected:** the page identifies the content as scraped from
  Food.com and supplies download/citation instructions, not redistribution
  permission. PantryPilot rejects ambiguous licenses and unauthorized scraping.

### Wikibooks Cookbook — legally reusable but operationally inferior; reject

- **Publisher/owners:** Wikibooks contributors under the official
  [Wikibooks copyright policy](https://en.wikibooks.org/wiki/Wikibooks:Copyrights).
- **License:** most text is CC BY-SA 4.0 and GFDL, with page-specific exceptions.
- **Redistribution:** permitted with contributor/page attribution, license
  notice, change indication, and share-alike treatment of adaptations.
- **Potential fields:** page title and ingredient facts. Prose and images would
  be excluded.
- **Reason rejected:** it is not a stable structured recipe dataset; each page
  requires history and exception review. For 24 small factual records, original
  curation is clearer and avoids accidental prose reuse or license mixing.

### USDA FoodData Central combination — clear license, wrong feature boundary

- **Publisher:** U.S. Department of Agriculture, Agricultural Research Service.
- **License:** official [FoodData Central](https://fdc.nal.usda.gov/) material
  states the data is public domain and published under CC0 1.0; USDA requests a
  source citation.
- **Potential fields:** calories and protein for food components.
- **Excluded fields:** the database itself, branded product content, and every
  nutrient not used by `Recipe`.
- **Reason rejected:** FoodData Central does not provide the target recipes.
  Reproducible totals require quantities, units, yields, and serving-size rules,
  all explicit Feature 006 non-goals. A credentialed API is also forbidden at
  runtime. This source can be reconsidered only with a later nutrition-data
  feature.

## 8. Approved corpus approach

Use the owner-approved original PantryPilot factual corpus only. Keep one
reviewed, code-owned official manifest containing exactly the existing `Recipe`
fields. Pair it with one data provenance document and the owner-authorized
data-scoped CC0 notice.
Do not build an ingestion pipeline: 24 hand-reviewed records are safer and less
code than importing and transforming a much larger source.

Nutrition and time values must be labeled representative estimates, not precise
medical claims. The provenance record states the method and reviewer rather
than inventing third-party authority. Recipe names remain short generic dish
names; no instructions, expressive descriptions, or images enter the repo.

## 9. Stable recipe-ID strategy

- Keep the four existing IDs unchanged.
- Assign each new recipe one reviewed lowercase kebab-case ID based on the dish
  concept. The ID is stored explicitly, never generated at runtime.
- A display-name correction or rename does not change the ID.
- Current official IDs and the cumulative retired-official-ID set are one
  reserved namespace. An official ID is never reused after removal, and no
  out-of-band row may use an ID in either class.
- Validation rejects duplicate current IDs and overlap between current and
  retired official IDs. Startup checks durable rows for both classes before
  reconciliation mutates recipe content; a non-official collision is fatal and
  is never claimed, overwritten, or deleted.
- The canonical current manifest and cumulative retired-ID set produce the
  release digest described in section 14. Stable ID, scalar, ingredient-order,
  addition, removal, or retired-set changes therefore require a new catalog
  content version.

## 10. Ingredient-registry implications

Choose the 24 recipes for overlap first, then add only canonical ingredients
actually required by their records. There is no registry-size quota.

Registry behavior remains unchanged: stable kebab-case ID, normalized explicit
canonical name, reviewed explicit aliases, dictionary lookup, and otherwise
unresolved. No fuzzy threshold, embeddings, substring rules, broad plural
guessing, or speculative synonym expansion is allowed.

Existing ingredient IDs cannot be renamed or removed because saved pantry rows
may reference them. An ingredient no longer used by any current recipe remains
in the registry. A new alias needs positive evidence and confusable negative
evidence; uncertainty means omit the alias and abstain.

Recipe-record validation remains separate from free-text evaluation. The
catalog proves only that every relationship uses a registered ID. It does not
prove that arbitrary user text should resolve to that ID.

## 11. Evaluation-versioning strategy

Freeze `ingredient-resolution-v1.json` byte-for-byte as historical Feature 002
evidence. Add `ingredient-resolution-v2.json` as a strict superset for the
expanded registry.

The JSON `schema_version` remains `1` because the file shape and metric contract
do not change; `v2` in the filename versions the labeled case set. This avoids a
meaningless evaluator schema migration. V2 must contain:

- exactly one canonical positive for every current registry entry;
- exactly one alias positive for every current explicit alias;
- every v1 row unchanged;
- at least one targeted unresolved/confusable negative for every materially new
  alias, plus negatives for new canonical terms where a plausible unsafe rule
  needs evidence; and
- no duplicate normalized inputs.

CI and README move the authoritative command to the v2 path. Unit tests keep v1
loadable, prove v1 is an unchanged subset of v2, prove v2 covers the complete
registry, and retain strict recall improvement over exact-name matching and zero
false positives. The evaluator algorithm does not change.

## 12. Existing catalog ownership contract

Feature 003 says SQLite rows are authoritative after seed, the Python catalog
is seed-only, and valid non-empty data is never reconciled. It intentionally
permits direct test mutations to remain durable, although there is no supported
recipe write API.

Feature 006 revises that contract only because “official PantryPilot catalog”
now needs corrections and releases across existing installations. It preserves
the useful part: SQLite remains the complete validated runtime catalog and may
contain out-of-band rows. It narrows authorship: official facts have one
code-owned authority; out-of-band facts have one durable authority.

## 13. Content-evolution alternatives considered

### One-time schema/data migration

It could add 20 rows during schema version 3. Fresh and upgraded databases
would initially converge, transactions would protect pantry state, and reruns
could be no-ops. However every later factual correction/removal would need a
schema bump or ad hoc SQL. It cannot safely distinguish official from
out-of-band rows without ownership metadata, and modified rows would either be
silently overwritten or block SQL unpredictably. It conflates storage shape
with content release and makes application rollback semantics unclear. Reject.

### Independent catalog-content version metadata alone

A singleton version cleanly separates schema and content releases, rejects a
database newer than the running app, and supports deterministic reruns. Alone,
it cannot say which rows the application owns, how collisions behave, or which
rows removal may delete. Keep it only as part of the recommendation.

A code-owned expected SHA-256 beside the version improves this option: a test
and startup check can detect a manifest edit when the expected digest is left
unchanged. It is insufficient by itself because changing both code values under
the same version leaves no durable memory of the identity previously installed.
An existing database could then be reconciled to different facts while still
reporting the same version. Reject code-only binding.

### Deterministic reconciliation with explicit ownership — recommended

Mark recipe rows as official or out-of-band, keep the approved current official
manifest in code, and reconcile only official rows in one startup transaction.
Fresh and upgraded databases converge on official content; out-of-band rows and
saved pantry rows remain untouched. Additions insert, corrections replace,
removals delete only marked official rows, and reruns restore the same state.
The content-state row persists the version and its exact manifest digest. The
trade-off is one ownership column, one additional digest value in the existing
singleton, and an explicit legacy-adoption check. This is the smallest approach
that answers every ownership and release-identity case without guessing.

### Fresh-database-only expansion

It preserves Feature 003 exactly and is trivial, but existing valid databases
remain at four recipes indefinitely. Fresh and upgraded installations diverge,
corrections/removals have no path, and the benchmark would not describe existing
users. Saved pantry safety is irrelevant if the feature never reaches them.
Reject as failing Issue #11.

### Administrative/import interface

CRUD/import could make all rows operator-owned and support manual conflict
resolution, but it adds authentication, validation UX, snapshot invalidation,
write concurrency, provenance policy, and a second content-authoring path.
Rollback and convergence would become operator procedures. PantryPilot has no
recipe-management product requirement. Reject.

## 14. Recommended content-evolution architecture

Schema migration 3 makes only the storage changes required for ownership:

- add `recipes.is_official INTEGER NOT NULL DEFAULT 0` constrained to `0` or
  `1`; and
- create a singleton `catalog_content_state` table containing a non-negative
  integer `version` and non-null `manifest_digest`, initialized to version `0`
  with the literal transitional sentinel `unmanaged` in the schema transaction.

`PRAGMA user_version = 3` continues to mean only that these structures exist.
`CURRENT_CATALOG_CONTENT_VERSION = 1` means the Feature 006 official corpus has
been reconciled. Version 0 plus `unmanaged` means the pre-Feature-006 ownership
transition has not completed; it is not a released official-manifest identity.
Every managed version greater than zero stores a 64-character lowercase
SHA-256 digest.

### Canonical manifest identity

One shared pure function constructs the release identity after `Recipe` and
registry validation. It serializes UTF-8 JSON with fixed separators and no
insignificant whitespace from:

- current official recipes sorted by recipe ID;
- for each recipe, exactly `id`, `name`, `calories`, `protein_g`,
  `prep_minutes`, and `required_ingredient_ids` in fixed field order;
- ingredient IDs in their approved relationship order, without sorting; and
- the cumulative retired-official-ID set in ascending ID order.

Source-record order is intentionally irrelevant; relationship order and every
owned scalar are significant. SHA-256 of those bytes is the canonical manifest
digest. The same serializer is used by release validation, durable verification,
and the benchmark; no second digest definition is allowed.

An append-only code-owned release ledger associates each managed integer
version with one literal expected digest. It starts with the eventual approved
pair for version 1; the exact digest cannot be established until the owner
approves the recipe facts. Ledger keys must be consecutive through
`CURRENT_CATALOG_CONTENT_VERSION`, existing pairs are immutable, and a new
manifest requires appending a new version/digest pair. A regression test pins
each released pair independently from the mutable current manifest test.

Before opening or mutating the database, startup computes the current canonical
digest and requires it to equal the ledger digest for
`CURRENT_CATALOG_CONTENT_VERSION`. Thus an accidental unversioned addition,
correction, removal, ingredient-order change, or retired-set change fails before
schema or content mutation. Changing the manifest and expected digest without a
version bump also fails existing-database and pinned-release regression tests;
it cannot silently replace a released pair.

Before database mutation, load and validate the complete current official
manifest and its retired-ID set against `INGREDIENT_REGISTRY`. Startup then:

1. validates the current version/digest pair as above;
2. applies normal schema migrations;
3. opens one `BEGIN IMMEDIATE` catalog-content transaction;
4. requires exactly one supported content-state row, rejects a newer version,
   requires version 0 to carry `unmanaged`, and for every managed stored version
   requires its digest to equal that version's release-ledger digest;
5. completes the read-only reserved-ID collision preflight in section 15;
6. performs the version-0 legacy adoption rules when needed;
7. reconciles every current official recipe and ordered relationship;
8. requires every marked-official ID absent from the current manifest to be in
   the cumulative retired set, then deletes only eligible marked-official rows
   whose IDs are retired;
9. reads the resulting official rows inside the transaction, canonicalizes them
   with the current retired set, and requires the digest to equal the current
   release-ledger digest;
10. updates both durable version and digest in the same transaction and commits;
    and
11. closes, reopens, validates, and loads the complete durable catalog exactly
    as today.

Reconciliation runs even when the version is current so unsupported direct
edits or deletion of official rows cannot persist. Current and retired IDs are
both reserved. A collision is detected before any recipe reconciliation write
and is a fatal conflict rather than an overwrite or deletion.

## 15. Official vs out-of-band ownership semantics

An official recipe is recognized by `recipes.is_official = 1`, not merely by a
name or by being present in the current manifest.

For an official row, PantryPilot owns the stable ID, display name, calories,
protein, preparation time, complete ordered ingredient relationships, and the
official marker. Direct modification is not a supported product concept; no
CRUD API exists. A changed or missing official row is restored from the approved
manifest on next startup.

For an out-of-band row (`is_official = 0`), PantryPilot owns only schema and
domain validity requirements. Its recipe facts and relationships remain durable
and are ranked, but are never corrected or removed by official reconciliation.
Invalid out-of-band data still fails complete-catalog hydration as it does now.

Legacy transition is deliberately conservative. Migration 3 initially marks
all existing rows out-of-band. During content version 0 only, startup first
classifies, without writing, each exact Feature 003 seed row as eligible for
legacy adoption. This narrow exception applies whether that legacy ID remains
current or has been retired by the first managed release. A divergent legacy
row, a row using a newly introduced current official ID, or any other row using
a retired official ID is a fatal collision. The complete scan finishes before
an ownership marker or recipe fact changes.

For a managed database, every `is_official = 0` row whose ID is current or
retired is a fatal collision. On current-version startup, any durable row at a
retired ID is fatal, including one inserted directly with an incorrect official
marker; a legitimate prior release could not leave it behind. During an upgrade
from an older managed version, a retired-ID row marked official is eligible for
the release's deletion, while a non-official row at that ID remains a fatal
collision. This distinction lets future releases remove application-owned rows
without ever deleting an out-of-band row.

The operator may later resolve a conflict outside this feature by backing up and
renaming/removing the colliding row or restoring the legacy value. No repair API
is added.

## 16. Add/update/remove behavior

- **Addition:** insert a missing manifest record as official. If the ID already
  belongs to an official row, reconcile it. If it belongs to an out-of-band
  row, fail and roll back.
- **Correction:** replace every application-owned scalar and the complete
  ordered relationship set for the official ID. Partial merging is forbidden.
- **Manual official change:** restore the approved record on startup. If the
  marker was changed to out-of-band, treat it as an ID collision and fail.
- **Manual official deletion:** reinsert it while it remains current.
- **Removal:** only while advancing from an older managed version, delete a
  marked official row now present in the cumulative retired set;
  `ON DELETE CASCADE` removes its relationships. On a current-version rerun, a
  retired-ID row is corruption/collision and fails rather than being silently
  deleted. Never remove the ID from the retired set or reuse it.
- **Direct retired-ID insertion:** the normal default marker makes the row
  out-of-band, so the next startup fails during preflight before recipe writes.
  Even an inserted `is_official = 1` row fails at current version because no
  retired official row should exist after that release.
- **Unknown/out-of-band row:** preserve every recipe fact and ordered
  relationship unchanged and continue ranking it if complete catalog validation
  succeeds. Schema migration 3 adds only the explicit `is_official = 0` marker.

Any official manifest or retired-set change, including corrections and
removals, changes the canonical digest, requires a new independent content
version/digest pair, and requires provenance/review updates.

## 17. Fresh vs upgraded database behavior

A fresh database migrates through schema version 3, starts with content version
0 and digest sentinel `unmanaged`, receives all 24 official recipes atomically,
advances to the exact released version 1/digest pair, and loads the result.

An ordinary upgraded schema-v2 database adopts exact copies of the four legacy
seed rows, preserves other valid rows as out-of-band, installs missing official
records, and reaches the same version 1/digest pair. Its official subset equals
a fresh database's official subset. Its complete catalog may intentionally
differ because out-of-band facts remain durable.

A modified legacy row, current-ID collision, or retired-ID collision prevents
startup and leaves recipe and pantry content unchanged apart from an already
committed schema migration. A managed stored digest that does not match its
version's ledger entry and a newer content version are rejected without
reconciliation or downgrade.

For later releases, an older managed database must first match the ledger digest
for its stored version; it then advances directly and atomically to the current
official manifest and pair. A current managed database must match the current
ledger pair, passes reserved-ID preflight, reconciles supported official edits,
re-verifies the resulting digest, and persists the same pair. A newer version,
an unknown historical version, a malformed digest, or any version/digest mismatch
fails before recipe mutation. These checks make fresh, legacy, older-managed,
and current-managed paths explicit rather than inferring state from recipe
counts.

## 18. Transaction/rollback/rerun semantics

Manifest and current release-ledger validation happen before a database write.
Schema migration 3 remains an existing-style atomic schema transaction. Content
evolution is a separate atomic `BEGIN IMMEDIATE` transaction containing
collision preflight, legacy adoption, all recipe and relationship
writes/deletes, resulting official-manifest digest verification, and the atomic
version/digest update.

Any SQLite, validation, collision, or commit failure explicitly rolls back the
content transaction. Because collision scanning precedes recipe writes, a
collision cannot claim, overwrite, or delete the conflicting row. An
interruption exposes either the old complete version/digest pair or the new
complete pair, never a prefix. A committed schema version 3 with version 0 and
`unmanaged` is a safe retry state. Repeated successful startup is deterministic
and idempotent.

There is no automatic downgrade. Older schema code already rejects schema 3;
future older content code must reject a newer content version. Operational
rollback requires a pre-upgrade database backup or the application version that
supports the stored versions.

## 19. Saved-pantry preservation

The content transaction never writes `saved_pantry` or `saved_pantry_items`.
Tests compare both tables row-for-row before and after success and injected
failure. Recipe deletion cannot cascade into pantry tables because they have no
recipe foreign key.

Canonical ingredient IDs are additive and stable. Even if an official recipe is
removed, every ingredient ID previously valid for saved pantry remains in the
code-owned registry. A saved pantry therefore hydrates unchanged after catalog
evolution.

## 20. Runtime loading behavior

Startup order becomes: validate the canonical official manifest against the
current release-ledger digest, migrate schema, validate durable version/digest
and reserved-ID collisions, reconcile official content, verify the resulting
official digest, atomically persist the pair, close, reopen, validate/load the
complete durable catalog, and publish one immutable snapshot. Requests still
perform no recipe-database I/O.

The code manifest is the sole authority for official facts. SQLite is their
materialized startup result and the sole authority for out-of-band facts. The
runtime tuple is derived from SQLite. Because each row has exactly one owner and
reconciliation completes before loading, this is not two competing recipe
sources of truth.

## 21. API/ranking compatibility

No request or response model, route, status mapping, score weight, formula,
rounding rule, explanation template, hard constraint, resolution rule, sort
key, or limit rule changes. Both inline and saved-pantry routes continue to call
the same `rank_recipes` function over the same application-state tuple.

More recipes may change returned recipe IDs, counts, and rankings for the same
request; that is intended data evolution, not an API or algorithm change.
Regression tests pin formula semantics independently of catalog membership and
retain complete inline/saved parity.

## 22. Benchmark design

Add a standard-library-only dedicated command, conceptually:

```powershell
uv run python -m pantrypilot.benchmark benchmarks/full-scan-ranking-v1.json
```

The versioned fixture records schema version, the exact catalog content
version/digest pair from the release ledger, expected catalog size 24, warm-up
count, measurement count, and fixed `RankingRequest` payloads. The benchmark
uses the same canonical serializer as startup and fails unless its pair, the
computed manifest digest, and the code-owned release pair all agree. The runtime
official manifest remains the production authority; the fixture cannot invent
or redefine release identity. Historical reproduction also records the git
commit.

The timed region contains only `rank_recipes(request, catalog, registry)`.
Fixture I/O, validation, digest construction, JSON serialization, and environment
inspection are outside it. Run 100 warm-ups per workload, then 1,000 measured
iterations using `time.perf_counter_ns`. After each timed call, compare the full
response with the first validated response so nondeterminism fails the command
without contaminating measured duration.

For each workload report scanned catalog size, hard-constraint-eligible
candidate count before limit, returned count, ordered output IDs and response
digest, median, nearest-rank p95, minimum, and maximum latency in milliseconds.
Record Python implementation/version, OS/platform/machine/processor strings,
fixture and catalog digests, iteration counts, UTC run time, and git commit.

The command emits deterministic-key-order JSON. One raw reference result is
committed under `benchmarks/results/`; the benchmark documentation records the
reference hardware, methodology, result summary, and interpretation. Timing
values are evidence, not golden test values. Unit tests use fixed synthetic
duration samples to check statistics and fixture/output validation. CI runs
semantic tests but no wall-clock pass threshold.

## 23. Representative benchmark workloads

The v1 request fixture contains at least these successful workloads, all using
real catalog ingredients and fixed expected result digests:

1. **Broad/high coverage:** a common pantry, permissive 60-minute limit, no
   exclusions; exercises maximum scoring work and many matches.
2. **Broad/low coverage:** a sparse pantry including one intentionally
   unresolved pantry term, permissive time, no exclusions; exercises abstention
   and many missing ingredients.
3. **Strict preparation limit:** a realistic pantry with a 20-minute maximum;
   produces a smaller eligible candidate set.
4. **Common hard exclusion:** excludes a resolvable ingredient shared by several
   recipes but not all; proves exclusion eligibility work.
5. **High protein target:** uses a target above many recipes with permissive
   time; verifies protein changes scores but does not filter candidates.
6. **Typical limited response:** mixed pantry, 30-minute maximum, one resolvable
   exclusion, and limit 5; exercises post-sort limiting.

An unresolved-exclusion request belongs in semantic tests rather than latency
aggregation because its correct result is a fail-closed exception. Saved-pantry
route I/O is also excluded: once canonical names are constructed, both routes
use the identical ranking function being baselined.

## 24. Benchmark reporting and retrieval-decision criteria

The decision rule is declared before results:

- **A — defer retrieval:** the worst successful workload's p95 full-scan ranking
  latency is below 50 ms on the documented Python 3.12 reference machine, all
  output digests are stable, and no correctness or memory concern appears.
- **B — propose retrieval later:** the worst p95 is 50 ms or more on two clean
  runs and profiling confirms exhaustive ranking—not fixture, HTTP, or database
  work—is material. That result authorizes a later retrieval design proposal,
  not retrieval in Feature 006.

Fifty milliseconds is a project engineering budget for the complete in-process
ranking stage, leaving most of a 100 ms local compute budget for adapters and
other work. It is not a hosted-CI assertion and is not presented as a universal
UX boundary. The second-run requirement reduces one-off machine noise. No
larger synthetic catalog is introduced to force outcome B.

The expected outcome at 24 records is A, but this design does not claim it until
the implemented benchmark produces evidence.

## 25. Test strategy

- `tests/test_catalog.py`: validate the approved manifest, exact stable unique
  IDs, disjoint current/cumulative-retired sets, reserved-ID uniqueness,
  malformed records, duplicate IDs/relationships, unknown registry IDs,
  immutability, deterministic ingredient order, canonical serialization, and
  digest sensitivity to every owned scalar, ingredient order, additions,
  removals, and retired-set changes. Pin every released version/digest pair so
  an existing ledger entry cannot drift silently. A parameterized startup
  preflight test changes each of those five manifest dimensions while holding
  version and expected digest fixed and proves failure occurs before any
  database connection or mutation.
- `tests/test_database.py`: prove schema version 3, ownership defaults, singleton
  content version 0 with `unmanaged`, version/digest storage constraints,
  preservation of existing recipe and saved-pantry rows, and full rollback of
  migration failures.
- `tests/test_catalog_store.py`: prove fresh 24-record initialization; exact
  legacy adoption; additions, corrections, removals, missing-official repair,
  current-version reruns, modified-legacy conflict, current-ID and retired-ID
  collision failure before mutation, direct retired-ID insertion with either
  marker, out-of-band preservation, official-edit restoration, stored-digest
  mismatch failure, newer-version failure, resulting-digest verification,
  atomic pair update, complete transaction rollback, and fresh/upgraded
  official-subset and version/digest convergence. Upgrade tests hard-code each
  prior released pair, so changing a ledger digest without a new version breaks
  the suite.
- Pantry-store and integration tests compare saved pantry marker/items
  row-for-row across successful and failed content evolution.
- `tests/test_ingredients.py` and `tests/test_evaluation.py`: preserve exact
  lookup/abstention, stable IDs, term-collision validation, frozen v1 evidence,
  complete v2 canonical/alias coverage, targeted negatives, recall improvement,
  and zero false positives.
- `tests/test_ranking.py`: remain the formula and hard-constraint authority,
  including soft protein target, fail-closed exclusions, unresolved pantry
  behavior, score reconstruction, deterministic ties, and post-sort limit.
- `tests/test_ranking_parity.py`,
  `tests/test_saved_pantry_ranking_parity.py`, and `tests/test_api.py`: retain
  durable/domain parity, complete inline/saved response parity, startup snapshot
  behavior, compatible response shapes, and deterministic results with the
  larger catalog. Tests should avoid treating intended catalog additions as an
  algorithm change.
- A focused benchmark test validates fixture/release pair equality, workload
  outputs, nearest-rank p95 calculation from fixed samples, deterministic JSON
  fields, and failure on manifest or output drift. It does not assert live time.
- Final implementation verification retains the full pytest, v2 evaluation,
  formatting, lint, lockfile, and whitespace contracts. CI changes only the
  evaluation fixture path when v2 becomes authoritative.

## 26. Documentation plan

The eventual implementation updates:

- `README.md`: Feature 006 status, 24-recipe catalog, ownership/evolution
  summary, benchmark/evaluation commands, retrieval conclusion, and correction
  that both pull-request and push-to-`main` CI paths are proven;
- this design only if the owner later changes an approved decision;
- one `docs/data/recipe-catalog-v1.md` provenance/coverage record plus the
  owner-authorized data-scoped CC0 notice;
- one `docs/benchmarks/006-full-scan-baseline.md` methodology/results record;
- `docs/product/vision.md` and `docs/roadmap.md` only where current-state or
  retrieval-decision wording changes; and
- `docs/learning/006-representative-catalog-expansion.md` with learning notes
  and mock-interview questions about content ownership, migrations versus
  content versions, conservative resolution, licensing, and benchmarking.

The README summarizes and links; provenance, benchmark detail, and learning
material each have one owner document rather than duplicated prose.

## 27. Risks and mitigations

- **Representativeness is subjective:** publish quantitative gates and the full
  matrix; describe 24 as a product baseline, not population coverage.
- **Nutrition/time estimates may be imprecise:** label them representative,
  record the authoring method, avoid health claims, and do not imply ingredient
  quantities that the model lacks.
- **License scope may be unclear:** release no catalog facts until the exact
  corpus checkpoint passes and the authorized data-scoped CC0 notice is
  committed; copy no third-party prose.
- **Legacy edits have ambiguous ownership:** compare exact legacy snapshots and
  fail closed instead of overwriting.
- **Future official ID collision:** explicit ownership makes the conflict fatal
  and preserves the out-of-band row; preflight covers both current and
  cumulative retired IDs before recipe mutation, and IDs are never reused.
- **Unversioned official-content drift:** canonical serialization plus SHA-256,
  an append-only release ledger, the durable version/digest pair, and pinned
  release/upgrade tests make additions, corrections, removals, ingredient-order
  changes, and retired-set changes fail under an unchanged version.
- **Digest adds another invariant:** a malformed or unexpected stored digest now
  blocks startup even if recipe rows look valid. This fail-closed behavior is
  intentional; the pair is application-owned release evidence and changes
  atomically with reconciliation.
- **Canonical encoding becomes a release contract:** changing JSON field order,
  numeric representation, UTF-8 handling, or separators would change the digest
  even when a reviewer considers the facts equivalent. Preserve the serializer
  for released versions; an intentional encoding change requires a new content
  version and documented digest rather than rewriting an existing pair.
- **Reconciliation bug could delete data:** delete only rows already marked
  official during a genuine version advance, reject current-version retired
  rows, transact all changes, verify the resulting official digest, inject
  rollback failures in tests, and compare pantry/out-of-band rows before and
  after.
- **Registry growth could over-resolve:** add explicit terms only and require v2
  positive/negative evidence with zero false positives.
- **Benchmark noise:** warm up, repeat, report environment and raw results, use a
  second clean run for outcome B, and keep timing out of CI gates.
- **Runtime divergence after out-of-band writes:** recipe CRUD is unsupported and
  the application snapshot remains startup-scoped, matching current behavior.

## 28. Security/legal considerations

No scraper, external runtime API, credential, token, network dependency, or
untrusted import parser is added. Official data is reviewed source code and
passes existing Pydantic and registry validation before any database mutation.
Out-of-band durable rows remain untrusted and must pass complete hydration.

The catalog contains no instructions, images, reviews, personal data, or source
account identifiers. Generic recipe facts do not make the API safe for medical,
allergy, or dietary-compliance decisions: a required-ingredient set is not an
exhaustive allergen declaration. Documentation must not claim otherwise.

Only the rights holder can apply CC0 to original catalog material. External
dataset incorporation remains prohibited without a new owner-authorized design
decision and complete license evidence.

## 29. Explicit non-goals

Feature 006 excludes retrieval, embeddings, vector/ANN/full-text indexes,
synthetic scale, runtime external APIs, scraping, images, instructions, recipe
CRUD/admin UI, user accounts, multiple pantries, quantities, units, a nutrition
database, spoilage, multi-meal optimization, personalization, learned or LLM
ranking, formula changes, history, analytics, telemetry, correlation IDs,
deployment, repository governance, a generic migration framework, unrelated
dependencies, and unrelated cleanup.

## 30. Acceptance criteria

Implementation is acceptable only when:

1. the owner-approved 24-record original-corpus strategy and data-scoped CC0
   notice are implemented without implying a repository-wide license;
2. the completed corpus meets and documents every section 4 gate without copied
   prose or unlicensed content;
3. all current and cumulative retired recipe IDs are stable, unique, disjoint,
   permanently reserved, and protected from out-of-band reuse before mutation;
4. every required ingredient ID exists in the conservative registry;
5. canonical serialization covers every owned scalar, ordered ingredient list,
   current recipe ID, and retired ID; every released content version has one
   pinned SHA-256; an unversioned change fails before database mutation;
6. fresh databases receive all 24 official recipes and persist the exact
   released version/digest pair;
7. upgraded databases adopt exact legacy rows, receive official additions and
   corrections/removals, preserve valid out-of-band rows, and fail without
   overwrite or deletion on ambiguous legacy, current-ID, or retired-ID
   collisions;
8. official direct edits restore according to the new ownership contract;
9. schema and content versions remain independent; stored digest mismatch and
   newer versions fail safely; resulting official rows are digest-verified; and
   evolution and pair updates are atomic, rerunnable, and deterministic;
10. saved pantry rows and stable ingredient identities survive success and
   injected failure unchanged;
11. malformed records, duplicate IDs, duplicate relationships, unknown
    ingredient IDs, and corrupt durable data fail before serving;
12. relationship, ranking, and tie ordering remain deterministic;
13. APIs remain structurally compatible, ranking formula/hard constraints stay
    unchanged, and inline/saved parity passes;
14. v1 resolution evidence remains frozen, v2 covers every current term, recall
    still improves, and false positives remain zero;
15. the versioned benchmark uses the same release digest, validates deterministic
    output, records median/p95 and environment evidence, and produces outcome A
    or B using section 24;
16. no hosted-CI wall-clock threshold or retrieval implementation is added;
17. README, provenance, benchmark, roadmap/vision as needed, and Feature 006
    learning/interview documentation are current; and
18. the complete existing verification contract passes with only the justified
    v2 evaluation path update.

## 31. Alternatives rejected and why

- A larger imported corpus: unclear rights, excessive transformation, and fake
  scale for the current product.
- Open Recipes, RecipeNLG, and Food.com data: ambiguous upstream or dataset
  redistribution rights.
- Wikibooks: clear reuse terms but high attribution/share-alike and extraction
  overhead for a small factual corpus.
- USDA nutrition combination: clear license but requires out-of-scope quantity,
  yield, and nutrient-calculation semantics.
- Schema version as content version: couples unrelated evolution and still does
  not define ownership.
- Code-only version/digest binding: detects a manifest-only edit but has no
  durable memory of the previously installed identity if both code values are
  changed under one version.
- Content version without an ownership marker: cannot protect out-of-band rows
  or resolve future ID collisions safely.
- Recipe IDs alone as ownership: a newly official ID could silently claim an
  existing out-of-band row.
- Always overwrite known IDs during legacy transition: violates the prior
  durable-authority contract without detecting modified facts.
- Preserve all modified official rows forever: prevents official corrections
  and fresh/upgraded convergence.
- Fresh-only expansion: fails existing installations.
- Admin/import API: creates an unrequested content-management product.
- Benchmarking through HTTP or SQLite: measures adapters rather than the
  exhaustive ranking algorithm at issue.
- Synthetic catalog multiplication or CI timing gate: benchmark theater and
  unstable evidence.

## 32. Design self-review

The design was challenged against the requested failure modes and revised as
follows:

- **Is the corpus truly representative?** It is representative only of the
  documented PantryPilot decision matrix, not global food culture. Quantitative
  minimums, overlap gates, a no-dominant-tradition cap, and a published matrix
  make that limitation reviewable.
- **Is 24 justified?** It is a sixfold, hand-reviewable product baseline that
  supports multiple candidates across bands. The document forbids filler and
  requires owner revision if 24 cannot meet the gates.
- **Are redistribution rights clear?** External candidates are rejected. The
  owner authorized the data-scoped CC0 approach on 2026-08-23. The exact corpus
  is not called a released CC0 catalog until its factual checkpoint passes and
  the scoped notice is committed; the authorization does not license the
  source code or other repository content.
- **Are there two recipe sources of truth?** No fact has two owners: code owns
  official facts, SQLite owns out-of-band facts, and SQLite materializes both for
  runtime. The startup snapshot is derived only.
- **Could evolution overwrite unowned state?** Legacy mismatches and
  out-of-band collisions on current or retired IDs fail before recipe writes.
  Only rows already marked official are updated, and removal happens only while
  advancing from an older release.
- **Are out-of-band rows consistent?** Valid rows remain ranked and untouched;
  invalid rows retain fail-fast hydration. No unsupported CRUD promise is added.
- **Could removals invalidate pantry state?** No recipe-to-pantry relationship
  exists, and canonical ingredient IDs are retained even when unused.
- **Are schema and content versions conflated?** Schema 3 creates the mechanism;
  independent content version 1 plus its canonical digest identifies the exact
  factual release.
- **Can a manifest fact change without a content-version change?** A canonical
  digest covers IDs, every scalar, ordered relationships, and retired IDs.
  Startup checks it against the pinned release ledger before database mutation;
  durable state and upgrade fixtures remember prior pairs. An unchanged version
  cannot silently accept a different manifest.
- **Could an unversioned removal delete an official recipe?** No. Removing a
  current record or changing the retired set changes the digest, so preflight
  fails against the unchanged release pair before reconciliation can delete.
- **Does each released version identify exactly one manifest?** Yes. Release
  ledger entries are append-only and pinned in regression/upgrade fixtures; the
  durable singleton stores the installed pair and the transaction verifies the
  resulting official digest before advancing it.
- **Are current and retired IDs both protected?** Yes. Both are reserved.
  Non-official collisions always fail; current-version retired rows also fail;
  only a marked official row from an older managed version is eligible for
  retirement deletion.
- **Can collision handling alter an out-of-band row?** No. The complete
  collision scan is read-only and finishes before adoption, update, insertion,
  or deletion. Failure rolls back without recipe or pantry mutation.
- **Does registry growth weaken resolution?** No algorithms change. Additive
  explicit terms require collision checks and v2 evidence; uncertain terms
  abstain.
- **Does evaluation scale with the registry?** V2 includes every canonical term
  and alias, retains v1, and adds targeted negatives. Recipe validation remains
  separate.
- **Are workloads realistic?** They cover broad/high and low pantry overlap,
  time and exclusion constraints, soft protein targeting, and normal limiting
  over the real 24-record catalog.
- **Are timings reproducible?** Catalog/request digests, environment metadata,
  fixed warm-ups/repetitions, raw JSON, and a recorded commit bound the claim;
  no claim of cross-machine identical latency is made.
- **Is retrieval favored?** The criterion is declared before measurement,
  requires confirmation for outcome B, and forbids synthetic scale. The expected
  result remains explicitly unclaimed.
- **Are fresh and upgraded semantics deterministic?** Both validate the same
  code release pair and finish with the same official subset and durable pair;
  only preserved out-of-band rows may differ.
- **Does saved pantry remain untouched?** Yes. Digest and collision checks read
  catalog state only, and the content transaction never writes either pantry
  table or removes registry IDs.
- **Is any mechanism unnecessary?** No importer, ORM, general content-migration
  framework, admin path, retrieval layer, or runtime dependency is proposed.
  One pure canonical serializer, SHA-256 from the standard library, one
  append-only constants ledger, the existing ownership column, and one extra
  singleton value are the minimum needed to bind release identity durably.

The only remaining owner checkpoints are review and approval of the eventual
exact recipe IDs, names, ordered ingredients, nutrition/time estimates,
coverage metadata, new canonical ingredients, aliases, and negative cases; and
review and approval of the measured benchmark evidence and retrieval
conclusion. External dataset incorporation remains prohibited without a new
owner-authorized design decision.
