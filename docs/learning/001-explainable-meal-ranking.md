# Feature 001: Explainable meal ranking

## What was built

`POST /v1/meal-rankings` accepts pantry ingredients and constraints, validates
them, and returns up to the requested limit of eligible recipes. A validated,
immutable in-memory catalog feeds a pure deterministic ranking pipeline. Each
result includes its ingredient evidence, score breakdown, reconstructable final
score, and one fixed explanation template.

## Why the deterministic baseline comes first

The same request and catalog always produce the same response. That gives the
project stable test fixtures, concrete exact-match failures, shared product
vocabulary, and a comparison point before adding entity resolution, learned
ranking, or grounded LLM orchestration.

## Complete request-to-response flow

FastAPI validates the JSON request, including required fields and boundaries.
`rank_recipes` normalizes pantry and exclusion strings, removes recipes with an
excluded ingredient or excessive preparation time, and partitions each eligible
recipe's ingredients into matched and missing values. It calculates score
components at full precision, rounds returned values and contributions to four
decimals, and sums the returned contributions for the final score. It renders
the fixed explanation, sorts by exposed score then ID, applies `limit`, and
returns a `RankingResponse` that FastAPI validates and serializes as JSON.

## File responsibilities

- `src/pantrypilot/__init__.py` marks the package.
- `src/pantrypilot/normalization.py` trims, lowercases, and stably
  deduplicates ingredient strings.
- `src/pantrypilot/models.py` defines validated request, recipe, score, ranked
  recipe, and response shapes.
- `src/pantrypilot/catalog.py` validates and freezes the four-recipe catalog
  when the application imports it.
- `src/pantrypilot/ranking.py` contains the pure filters, matching, scoring,
  explanation, sorting, limiting, and `rank_recipes` pipeline.
- `src/pantrypilot/app.py` owns the FastAPI app and the one versioned route.
- `tests/test_normalization.py` tests normalization alone;
  `tests/test_catalog.py` tests catalog validation and immutability;
  `tests/test_ranking.py` tests the domain pipeline with local fixtures; and
  `tests/test_api.py` tests the HTTP contract against the application catalog.
- `pyproject.toml` declares the runtime, test, and lint dependencies and their
  configuration; `uv.lock` fixes their resolved versions.

## Hard filters and soft constraints

An excluded required ingredient makes a recipe ineligible, even when that
ingredient is in the pantry. A recipe is also ineligible only when
`prep_minutes > max_prep_minutes`; equality remains eligible. The minimum
protein target is soft: it changes `protein_fit` but never removes a recipe.

## Normalization and exact matching

Normalization trims leading and trailing whitespace, lowercases text, and
removes repeated exact normalized strings while keeping the first occurrence.
It preserves internal whitespace, punctuation, and plurality: `"Olive  Oil"`
becomes `"olive  oil"`, while `"tomato"` still differs from `"tomatoes"`.
Matching is normalized string equality, so synonyms are deliberately deferred
until this baseline supplies measured failure cases.

## Scoring and rounding

For every eligible recipe:

```text
pantry_coverage = matched_required_ingredients / total_required_ingredients
protein_fit = 1.0 when min_protein_g == 0; otherwise min(protein_g / min_protein_g, 1)
time_fit = 1.0 when max_prep_minutes == 0; otherwise 1 - prep_minutes / max_prep_minutes
final_score = 0.70 * pantry_coverage + 0.20 * protein_fit + 0.10 * time_fit
```

The code calculates component values at full precision. It exposes each value
to four decimals, rounds each full-precision weighted contribution to four
decimals, then sets `final_score` to the four-decimal sum of those returned
contributions. A zero-minute maximum admits only zero-minute recipes through
the hard filter, making its `time_fit = 1.0` branch well-defined.

For Spinach Omelet with pantry `eggs` and `spinach`, a 25.0g protein target,
and a 30-minute maximum: coverage is `2 / 3 = 0.6667` and contributes
`round((2 / 3) * 0.70, 4) = 0.4667`; protein fit is `min(28 / 25, 1) = 1.0000`
and contributes `0.2000`; time fit is `1 - 15 / 30 = 0.5000` and contributes
`0.0500`. The returned final score is exactly reconstructable as
`0.4667 + 0.2000 + 0.0500 = 0.7167`.

## Deterministic ordering

Results sort by descending exposed four-decimal `final_score`, then ascending
recipe ID for ties. `limit` slices that ordered list, not the catalog order.
Those rules make repeated identical requests reproducible and prevent hidden
floating-point precision from choosing a displayed-score tie.

## Test strategy

Direct tests exercise normalization, catalog validation, matching, eligibility,
score branches, rounding, explanations, ordering, and limiting without an HTTP
server. Small local recipe fixtures in `test_ranking.py` isolate those rules
from the application catalog. HTTP tests separately prove the endpoint's
valid response, empty result, validation `422` responses, and generic `500`
behavior.

## Run and verify

```powershell
uv sync --locked --python 3.12
uv run pytest tests/test_catalog.py -v
uv run pytest tests/test_normalization.py -v
uv run pytest tests/test_ranking.py -v
uv run pytest tests/test_api.py -v
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run uvicorn pantrypilot.app:app --app-dir src
```

## Mock-interview questions

- **Why separate hard and soft constraints?** Exclusions and time limits define
  safe eligibility; protein expresses a trade-off among eligible recipes.
- **Why does the domain not import FastAPI?** Pure functions can be tested and
  reused without HTTP setup, while the route remains only a transport adapter.
- **Why use exact matching first?** It is deterministic and measurable, so
  later resolution can prove it improves known misses rather than add guesswork.
- **Why make rounding reconstructable?** Users and tests can reproduce the
  displayed score from its returned evidence without hidden precision.
- **Why tie-break by ID?** A stable secondary key makes equal displayed scores
  repeatable.
- **Why validate the catalog at startup?** Bad application data fails early
  instead of producing unreliable recommendations at request time.
- **Why no repository abstraction?** The only data source is the in-memory
  tuple; an abstraction would add indirection without behavior.
- **What would justify entity resolution or learned ranking?** Labeled
  exact-match failures, retrieval or resolution metrics, and repeatable
  baseline comparisons that show a measurable improvement.

## Exercises

1. Add a local `test_ranking.py` case showing that `"olive oil"` does not
   match a recipe ingredient normalized from `"Olive  Oil"`.
2. Calculate a three-recipe ranking by hand, then add local fixtures asserting
   the same recipe order and each returned score breakdown.

## Concepts to understand before merging

- Pydantic request and response validation
- Pure functions and thin HTTP adapters
- Hard filters versus soft score targets
- Ingredient normalization and exact matching
- Full-precision calculations versus displayed four-decimal values
- Deterministic sorting and post-sort limiting
- TDD red-green-refactor
- FastAPI `422` validation responses and generic `500` failures
- uv lockfiles and locked dependency synchronization
