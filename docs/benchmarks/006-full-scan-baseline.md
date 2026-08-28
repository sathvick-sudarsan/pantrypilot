# Feature 006 full-scan ranking baseline

> **Owner-approved 2026-08-27.** This evidence supports Outcome A at the
> representative 24-recipe catalog scale only; it does not establish behavior
> at substantially larger future catalog sizes.

## Evidence identity

- Raw result: [full-scan-ranking-v1-reference.json](../../benchmarks/results/full-scan-ranking-v1-reference.json)
- Fixed fixture: [full-scan-ranking-v1.json](../../benchmarks/full-scan-ranking-v1.json)
- Measurement commit: `9974237c938c68c39564ee3ba585d99938300b61`
- Catalog content version: `1`
- Catalog manifest digest: `f811853765a0732ae34521e47c2f7e3c691f5cb00bfec4e138f9ce08a01c9f2c`
- Fixture SHA-256: `ffdb5ecd42aa251dca2680b0c6cc085d41d1bcf8a266fb7b4297c5aa755e3839`
- Fixture schema version: `1`
- Catalog size: `24`
- Warmups per workload: `100`
- Measurements per workload: `1000`
- Run time: `2026-08-26T16:16:58.116747Z`

The measurement worktree was clean on branch
`feat/representative-catalog-expansion`, the committed identity matched the
measurement commit above, `uv run python --version` reported Python 3.12.13,
and the focused semantic gate reported `60 passed in 0.40s` before the result
was produced.

## Reference environment

- Python implementation/version: `CPython 3.12.13`
- Operating system: `Windows`
- Platform: `Windows-11-10.0.26200-SP0`
- Machine: `AMD64`
- Processor: `Intel64 Family 6 Model 197 Stepping 2, GenuineIntel`

## Methodology

The reference command was run exactly once:

```powershell
uv run python -m pantrypilot.benchmark benchmarks/full-scan-ranking-v1.json
```

The committed fixture pins the released catalog identity, catalog size, six
requests, expected eligible counts, ordered response IDs, and response digests.
Each workload received 100 untimed warmups followed by 1,000 measurements with
`time.perf_counter_ns`. Only
`rank_recipes(request, catalog, registry)` was inside the timed region. Fixture
I/O and validation, release validation, environment inspection, eligible-count
calculation, and response digest construction were outside it. Each measured
response was compared with the first validated response after the end
timestamp. Median uses the standard-library median; p95 uses nearest rank.

## Raw workload results

All latency values are milliseconds.

### `broad-high-coverage`

- Counts: catalog `24`; eligible `24`; returned `24`
- Timing: median `0.25505`; p95 `0.4779`; min `0.2325`; max `0.9799`
- Response digest: `c4caf4c6260ea59b76ce7a115d3473b6544ef18c1dda471900f16a4377582cd5`
- Ordered response IDs: `spinach-omelet`, `black-bean-quinoa-salad`, `black-bean-rice-bowl`, `avocado-egg-toast`, `tuna-avocado-salad`, `chicken-tacos`, `black-bean-tacos`, `coconut-lentil-curry`, `tomato-lentil-stew`, `chicken-pasta-bowl`, `coconut-chicken-stew`, `chickpea-rice-bowl`, `chickpea-cucumber-salad`, `pasta-tomato-soup`, `lentil-cucumber-salad`, `salmon-quinoa-salad`, `beef-rice-bowl`, `potato-chickpea-curry`, `tofu-rice-bowl`, `tofu-vegetable-soup`, `lentil-soup`, `peanut-noodles`, `yogurt-oat-bowl`, `overnight-oats`

### `broad-low-coverage`

- Counts: catalog `24`; eligible `24`; returned `24`
- Timing: median `0.2338`; p95 `0.4423`; min `0.2148`; max `0.9837`
- Response digest: `5fb98708a6d0ae29e33c070e23553b39f4eb5306f13e85e05311cf84b76b5533`
- Ordered response IDs: `lentil-soup`, `lentil-cucumber-salad`, `coconut-lentil-curry`, `tomato-lentil-stew`, `spinach-omelet`, `tuna-avocado-salad`, `peanut-noodles`, `avocado-egg-toast`, `chicken-tacos`, `chickpea-rice-bowl`, `salmon-quinoa-salad`, `black-bean-tacos`, `beef-rice-bowl`, `black-bean-quinoa-salad`, `black-bean-rice-bowl`, `tofu-rice-bowl`, `tofu-vegetable-soup`, `yogurt-oat-bowl`, `chicken-pasta-bowl`, `overnight-oats`, `coconut-chicken-stew`, `chickpea-cucumber-salad`, `potato-chickpea-curry`, `pasta-tomato-soup`

### `strict-preparation-limit`

- Counts: catalog `24`; eligible `8`; returned `8`
- Timing: median `0.0903`; p95 `0.1684`; min `0.0823`; max `0.4961`
- Response digest: `8afe1680cc7946f00e2d1c196dd542bc88a4401a0a0c2d5eff0b85b0c0c7c30e`
- Ordered response IDs: `avocado-egg-toast`, `spinach-omelet`, `yogurt-oat-bowl`, `overnight-oats`, `peanut-noodles`, `tuna-avocado-salad`, `chickpea-cucumber-salad`, `lentil-cucumber-salad`

### `common-hard-exclusion`

- Counts: catalog `24`; eligible `16`; returned `16`
- Timing: median `0.1715`; p95 `0.3048`; min `0.1577`; max `0.8882`
- Response digest: `f2b97f109348315a964a6c394e48571e4ce3f10e841cdf20263398e59565763f`
- Ordered response IDs: `spinach-omelet`, `chickpea-rice-bowl`, `chickpea-cucumber-salad`, `tuna-avocado-salad`, `black-bean-rice-bowl`, `lentil-cucumber-salad`, `chicken-tacos`, `salmon-quinoa-salad`, `black-bean-quinoa-salad`, `avocado-egg-toast`, `tofu-vegetable-soup`, `lentil-soup`, `peanut-noodles`, `black-bean-tacos`, `yogurt-oat-bowl`, `overnight-oats`

### `high-protein-target`

- Counts: catalog `24`; eligible `24`; returned `24`
- Timing: median `0.2481`; p95 `0.4841`; min `0.2279`; max `1.1656`
- Response digest: `b825203f321e8e2f5fda7a4567bef168b2630544af12589308f43569f150d662`
- Ordered response IDs: `spinach-omelet`, `chicken-pasta-bowl`, `salmon-quinoa-salad`, `avocado-egg-toast`, `tuna-avocado-salad`, `coconut-lentil-curry`, `tomato-lentil-stew`, `pasta-tomato-soup`, `potato-chickpea-curry`, `chickpea-cucumber-salad`, `chickpea-rice-bowl`, `chicken-tacos`, `black-bean-rice-bowl`, `beef-rice-bowl`, `lentil-cucumber-salad`, `coconut-chicken-stew`, `tofu-rice-bowl`, `black-bean-quinoa-salad`, `tofu-vegetable-soup`, `yogurt-oat-bowl`, `peanut-noodles`, `overnight-oats`, `black-bean-tacos`, `lentil-soup`

### `typical-limited-response`

- Counts: catalog `24`; eligible `11`; returned `5`
- Timing: median `0.1184`; p95 `0.1508`; min `0.1088`; max `0.5973`
- Response digest: `d4f51d15a55ed3fe286364dde510b0c472cf514b584b788b41e83b479dec3647`
- Ordered response IDs: `spinach-omelet`, `chickpea-cucumber-salad`, `chickpea-rice-bowl`, `tuna-avocado-salad`, `lentil-cucumber-salad`

## Correctness and retained-memory assessment

The command completed successfully, and all warmup and measured responses
equaled the first validated response. Independent result validation confirmed
the release pair, fixture SHA-256, measurement commit, iteration counts, and
all six workload IDs, catalog/eligible/returned counts, ordered response IDs,
and response digests against the committed fixture and current release. The
focused benchmark and ranking tests passed before measurement. Inspection found
no correctness concern in the benchmark path.

Inspection also found no retained-memory concern. Each iteration replaces its
local response after comparison; it does not append responses to a persistent
collection. The harness retains a bounded list of 1,000 integer durations for
the current workload and one small summary per workload. `rank_recipes` builds
only per-call local collections and does not store results globally. This is a
code-inspection assessment, not a heap profile.

## Decision-rule application

The worst successful workload was `high-protein-target`, with p95 `0.4841 ms`.
The predeclared threshold is `50 ms`. Because the worst p95 was below the
threshold, all outputs were stable, and inspection exposed no correctness or
retained-memory concern, the evidence follows **outcome A**.

A second clean run was not performed, and `cProfile` was not run. Those steps
apply only when the first clean run's worst p95 is at least `50 ms`.

**Approved conclusion A:** retrieval remains deferred at the representative
24-recipe catalog scale. Feature 006 does not implement retrieval, indexing,
embeddings, or candidate generation.

## Limitations and scope

- This is one run on the exact local environment recorded above; wall time can
  vary with machine load, hardware, operating system, and Python build.
- Hosted CI enforces benchmark semantics but has no wall-time gate.
- The 24-record representative catalog is not internet scale and cannot
  establish performance at substantially larger catalog sizes.
- The timed region excludes fixture work, HTTP handling, and database work, so
  this result characterizes only in-process full-scan ranking.
- The retained-memory assessment is by bounded-allocation code inspection; the
  outcome-A rule did not call for memory profiling.
- Feature 006 implements no retrieval, indexing, embeddings, or candidate
  generation.
