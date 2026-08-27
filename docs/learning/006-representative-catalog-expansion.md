# Feature 006: Representative catalog expansion and full-scan baseline

## What changed and what did not

Feature 006 releases 24 owner-approved official recipes, reconciles them with
the local durable catalog, expands the exact ingredient-resolution evidence,
and records a full-scan benchmark. The official factual corpus and its
provenance are documented in [recipe-catalog-v1.md](../data/recipe-catalog-v1.md).
The [CC0 notice](../data/official-recipe-catalog-CC0-1.0.md) applies only to
that official data and provenance metadata, not to source code or the rest of
the repository.

The approved benchmark conclusion is narrow: retrieval remains deferred at the
representative 24-recipe catalog scale. Feature 006 does not implement
retrieval, indexing, embeddings, or candidate generation.

## Schema state is not catalog state

SQLite's `PRAGMA user_version` describes the database schema: tables, columns,
and constraints. Catalog content version `1` identifies one released set of
official recipes and its digest. A catalog correction can require a content
version without a schema migration; a schema migration can require no recipe
change. Keeping those identities separate makes both changes reviewable.

The release ledger is append-only and immutable. A canonical serializer includes
every owned recipe field, ingredient order, and retired-ID state, then records a
SHA-256 digest. Source-order changes cannot silently redefine a release, while
meaningful data changes cannot masquerade as the same version.

## Ownership and safe catalog evolution

An ownership marker distinguishes a PantryPilot-managed official row from a
valid out-of-band row. Without it, startup could overwrite or delete facts a
user or external process added outside the official release. Before mutation,
reconciliation scans the reserved current and retired official ID namespace for
collisions. A collision fails before writes rather than claiming someone else's
record.

Feature 003 stores are adopted conservatively: only the exact historical seed
catalog qualifies as legacy official content. A divergent durable row remains
out-of-band rather than being guessed into ownership. Official additions,
corrections, removals, restoration, and retirement occur in one transaction;
failure rolls back the catalog-content transition. Saved-pantry rows are not
part of that mutation and remain preserved. Their canonical ingredient IDs stay
stable even if a display name changes, so saved input retains its meaning.

## Exact resolution is evidence, not a guess

Ingredient resolution remains normalized exact canonical-name or explicit-alias
lookup. It abstains for unknown terms. This protects hard exclusions: a false
positive could make a user believe an unsafe ingredient was excluded or could
incorrectly match pantry coverage.

`ingredient-resolution-v1.json` is frozen historical evidence; it remains
byte-identical rather than being reinterpreted under the expanded registry.
`ingredient-resolution-v2.json` is the current strict-superset evidence for
the 24-recipe catalog. Run the evaluator with:

```powershell
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v2.json
```

The approved v2 result has exact-name recall `0.75`, resolver recall `1.0`,
precision `1.0`, and zero false positives or false negatives.

## Provenance and limited dedication

The released records are original PantryPilot-authored factual summaries: short
generic identities, ordered canonical ingredients, and representative nutrition
and preparation estimates. No external recipe material, instructions,
descriptive prose, images, quantities, units, or source-site data was copied.
The catalog document records the factual-estimate limits and review metadata.

CC0 is deliberately narrow. It covers official recipe facts in
`OFFICIAL_RECIPE_CATALOG` and factual provenance/coverage metadata only. It
does not dedicate the implementation, tests, unrelated documentation,
trademarks, third-party material, or the repository as a whole.

## Benchmark discipline and conclusion

The fixed benchmark fixture binds the release identity and six real-catalog
workloads. Each workload receives 100 untimed warmups and 1,000 measurements.
Only `rank_recipes(request, catalog, registry)` is timed with
`time.perf_counter_ns`; fixture I/O, validation, release checks, environment
inspection, response-digest construction, HTTP, and database work are outside
the timed region. Responses are compared after timing, so speed never excuses
a semantic drift.

Median uses the standard-library median. P95 uses nearest rank: sort `n`
durations and select rank `ceil(0.95 * n)`, so 1,000 samples select the 950th
one-based value. The [fixed fixture](../../benchmarks/full-scan-ranking-v1.json)
and [raw result](../../benchmarks/results/full-scan-ranking-v1-reference.json)
make the run reproducible on its recorded identity; the
[baseline document](../benchmarks/006-full-scan-baseline.md) records all
workload evidence.

The approved one-run reference used CPython 3.12.13 on the recorded Windows
machine. Its worst workload, `high-protein-target`, had p95 `0.4841 ms`, below
the unchanged `50 ms` threshold, with stable responses and no correctness or
retained-memory concern under the documented bounded-allocation inspection.
Outcome A therefore keeps retrieval deferred at the 24-recipe representative
scale. This is not internet-scale evidence, is not a CI wall-time gate, does
not include HTTP or database time, and does not generalize to substantially
larger future catalogs.

Run the same fixed harness when future catalog evidence justifies a new
decision; do not compare an unrecorded machine result as though it were the
reference run:

```powershell
uv run python -m pantrypilot.benchmark benchmarks/full-scan-ranking-v1.json
```

## Practical exercises

1. Change one ordered ingredient in a copy of the release input and explain
   why the canonical digest must change even if the recipe ID does not.
2. Sketch a database containing one exact legacy recipe and one divergent row.
   Decide which is adopted, which remains out-of-band, and why an ID collision
   must fail before any write.
3. Add a hypothetical alias and a confusable negative. Explain why passing the
   positive case alone is insufficient for a hard-exclusion resolver.
4. Given 1,000 sorted durations, identify the nearest-rank p95 element and
   list which benchmark work belongs outside `rank_recipes` timing.

## Mock-interview questions and answer guidance

1. **Why separate schema and catalog content versions?** Schema versions track
   storage shape; content versions track a released fact set. Either can change
   independently, avoiding false migrations or silent data drift.
2. **What does canonical serialization protect?** It defines one byte-level
   release representation, including ingredient order and retired IDs, so a
   digest detects meaningful release drift without depending on source order.
3. **Why is the release ledger immutable and append-only?** Historical release
   identities remain auditable; a correction creates a new version instead of
   rewriting evidence for an old one.
4. **Why add ownership markers to recipe rows?** They prevent startup
   reconciliation from treating valid out-of-band facts as official data and
   preserve a clear authority boundary.
5. **Why is legacy adoption conservative and collision-first?** Exact matching
   avoids accidental ownership claims, and scanning before writes prevents a
   transaction from overwriting a colliding non-official record.
6. **How do official correction, removal, and rollback work?** A versioned
   official transition updates current rows, retires removed IDs, and commits
   atomically; any failure restores the prior catalog state.
7. **Why preserve saved pantries as canonical IDs?** Stable IDs retain intent
   across display-name changes and catalog reconciliation, while names can be
   resolved at read time.
8. **Why keep v1 frozen after adding v2?** V1 remains truthful historical
   evidence. V2 expands current coverage without revising the baseline or
   hiding the resolver's earlier limits.
9. **Why are false positives unsafe for this resolver?** An incorrect alias or
   fuzzy match can defeat a hard exclusion or claim pantry coverage that does
   not exist; abstention is safer than a guess.
10. **What is the provenance and CC0 boundary?** The corpus is original
    factual content with documented estimates; CC0 covers only official data
    and provenance metadata, never code or the whole repository.
11. **How do you make benchmark percentiles meaningful?** Fix workloads and
    iterations, time only the target function, validate output outside the
    clock, record the environment, and define percentile calculation before
    observing latency.
12. **What does Outcome A prove and not prove?** It supports deferring
    retrieval for this 24-recipe reference run; it does not prove performance
    for larger catalogs, other machines, HTTP/database paths, or hosted CI.
