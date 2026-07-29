# Feature 001: Explainable pantry-based meal ranking

Status: Approved

Design date: 2026-07-25

Approved: 2026-07-26

Amended: 2026-07-27

Amendment reason: Validation-transport and score-rounding clarification.

## Summary

Feature 001 provides PantryPilot's first end-to-end product capability: a user
submits pantry ingredients and constraints to a versioned API and receives up to
`limit` eligible recipes ordered by an explainable deterministic score.

This vertical slice establishes a measurable recommendation baseline without
introducing persistence, probabilistic matching, learned models, or LLM calls.

## Goals

- Deliver useful pantry-based recipe ranking through a production-shaped API.
- Separate HTTP validation from pure ranking behavior.
- Make every score and explanation reproducible.
- Establish fixtures and failure cases for later entity resolution and learned
  ranking.
- Keep the implementation small enough to understand and review file by file.
- Include tests, learning documentation, and mock-interview questions.

## Non-goals

- Ingredient synonyms or canonical entities
- Fuzzy matching
- Embeddings or learned ranking
- LLM calls or generated explanations
- A database or other persistence
- Authentication
- A frontend
- Docker
- External recipe APIs
- User profiles, feedback, or personalization
- Repository, service, factory, or dependency-injection abstractions created
  only for possible future use

## Architecture

The feature uses a thin HTTP layer over a pure ranking pipeline:

```text
HTTP request
    -> request validation
    -> rank_recipes(request, catalog)
        -> normalize
        -> hard filter
        -> score
        -> explain
        -> deterministically sort
        -> limit
    -> response validation
    -> JSON response
```

The recipe catalog is a small immutable collection loaded and validated with the
application. The ranking pipeline accepts that collection as an argument; a
storage abstraction is unnecessary until persistence exists.

## Components

### API application

Owns FastAPI application creation and the `POST /v1/meal-rankings` route. It
validates transport data, calls the ranking pipeline, and serializes the
validated response. It contains no scoring rules.

### Models

Define the request, recipe, score breakdown, ranked recipe, and response shapes.
They reject unknown request fields and invalid catalog records.

### Catalog

Contains a small representative recipe set. Recipe IDs are unique, ingredient
lists are non-empty after normalization, and numeric nutrition and time values
are non-negative. Invalid catalog data fails application startup.

### Ranking pipeline

Provides pure functions for normalization, filtering, scoring, explanation,
sorting, and limiting. Its public entry point is conceptually:

```python
rank_recipes(request, recipes) -> list[RankedRecipe]
```

### Tests

Exercise ranking rules directly and cover the HTTP contract with a small number
of endpoint tests.

### Learning documentation

Explains the baseline, pure-function boundary, validation, hard versus soft
constraints, score construction, deterministic ordering, tests, and future
replacement points. It includes commands, exercises, and mock-interview
questions with concise answer guidance.

## API contract

### Endpoint

```http
POST /v1/meal-rankings
Content-Type: application/json
```

All request fields are required.

### Request

```json
{
  "pantry_items": [" Eggs ", "spinach", "EGGS"],
  "min_protein_g": 25.0,
  "max_prep_minutes": 30,
  "excluded_ingredients": ["peanuts"],
  "limit": 5
}
```

| Field | Type | Validation |
|---|---|---|
| `pantry_items` | `list[str]` | Each value is non-empty after trimming; the list may be empty |
| `min_protein_g` | `float` | Finite and greater than or equal to `0` |
| `max_prep_minutes` | `int` | Greater than or equal to `0` |
| `excluded_ingredients` | `list[str]` | Each value is non-empty after trimming; the list may be empty |
| `limit` | `int` | From `1` through `50` |

Unknown request fields are rejected.

### Recipe data

Each catalog recipe has:

- `id`: unique non-empty string
- `name`: non-empty string
- `required_ingredients`: non-empty list of non-empty strings
- `calories`: non-negative number
- `protein_g`: non-negative number
- `prep_minutes`: non-negative integer

### Response

```json
{
  "results": [
    {
      "id": "spinach-omelet",
      "name": "Spinach Omelet",
      "required_ingredients": ["eggs", "spinach", "olive oil"],
      "calories": 410,
      "protein_g": 28.0,
      "prep_minutes": 15,
      "final_score": 0.7167,
      "matched_ingredients": ["eggs", "spinach"],
      "missing_ingredients": ["olive oil"],
      "score_breakdown": {
        "pantry_coverage": {
          "value": 0.6667,
          "weight": 0.7,
          "contribution": 0.4667
        },
        "protein_fit": {
          "value": 1.0,
          "weight": 0.2,
          "contribution": 0.2
        },
        "time_fit": {
          "value": 0.5,
          "weight": 0.1,
          "contribution": 0.05
        }
      },
      "explanation": "Matched 2 of 3 required ingredients (coverage 0.6667); 28.0g protein meets the 25.0g target (fit 1.0000); 15 minutes is within the 30-minute limit (fit 0.5000)."
    }
  ],
  "returned_count": 1
}
```

A valid request with no eligible recipes returns status `200` with an empty
`results` list and `returned_count` of `0`.

Malformed JSON and schema violations return FastAPI's standard `422` response.
Unexpected errors return `500` without internal implementation details.

Python HTTP test clients can serialize non-finite floats as the non-standard
numeric tokens `Infinity`, `-Infinity`, and `NaN`. Pydantic correctly rejects
those values, but Starlette's default validation response cannot serialize the
original non-finite input with strict JSON. The FastAPI layer therefore uses a
narrow `RequestValidationError` handler that preserves the standard
`{"detail": [...]}` shape and each Pydantic error's type, location, message,
input, and useful metadata while rendering only non-finite floats as the
deterministic strings `"Infinity"`, `"-Infinity"`, and `"NaN"`. The handler
does not mutate request input before validation.

## Normalization and matching

An ingredient is normalized by:

1. Trimming leading and trailing whitespace.
2. Converting text to lowercase.
3. Removing exact duplicates while preserving first occurrence.

Matching uses exact equality between normalized strings. Internal whitespace,
punctuation, plurality, and synonyms are not changed. For example, `" Eggs "`
matches `"eggs"`, while `"tomato"` does not match `"tomatoes"` and `"oil"` does
not match `"olive oil"`.

Recipe ingredients are normalized once when the catalog is loaded. Matched and
missing ingredients preserve the normalized recipe ingredient order.

Blank ingredient values are rejected rather than silently discarded. If a
normalized ingredient occurs in both the pantry and exclusions, exclusion
takes precedence.

## Eligibility

A recipe is excluded when either condition is true:

1. Its normalized required ingredients intersect with normalized
   `excluded_ingredients`.
2. Its `prep_minutes` is greater than `max_prep_minutes`.

A recipe whose preparation time equals the maximum remains eligible.

`min_protein_g` is a soft target used in scoring, not a hard eligibility rule.

## Scoring

For each eligible recipe:

```text
pantry_coverage =
    matched_required_ingredients / total_required_ingredients
```

```text
protein_fit =
    1.0                                      when min_protein_g == 0
    min(recipe.protein_g / min_protein_g, 1) otherwise
```

```text
time_fit =
    1.0                                        when max_prep_minutes == 0
    1 - prep_minutes / max_prep_minutes        otherwise
```

When `max_prep_minutes` is zero, the hard filter permits only zero-minute
recipes, so the special time score is well-defined.

The final score is:

```text
0.70 * pantry_coverage + 0.20 * protein_fit + 0.10 * time_fit
```

Component values are calculated at full precision. Each weighted contribution
is then rounded to four decimal places, and the final score is the four-decimal
sum of those returned contributions. Component values are also exposed to four
decimal places. The returned `final_score` is exactly reconstructable by
summing the returned weighted contributions. Because a contribution is
calculated from the full-precision component value before both are
independently rounded, multiplying a displayed component value by its displayed
weight may differ from the displayed contribution by `0.0001`. Final scores
fall within `[0, 1]`.

## Ordering and limiting

Eligible recipes are ordered by:

1. Four-decimal final score descending.
2. Recipe ID ascending.

Using the exposed score for ordering prevents hidden floating-point precision
from deciding between recipes that display the same score. The ordered
collection is sliced to the requested `limit`.

## Explanation

Each result uses one fixed template:

```text
Matched {matched} of {required} required ingredients
(coverage {pantry_coverage:.4f}); {protein_g:.1f}g protein
{meets_or_is_below} the {min_protein_g:.1f}g target
(fit {protein_fit:.4f}); {prep_minutes} minutes is within the
{max_prep_minutes}-minute limit (fit {time_fit:.4f}).
```

The wording and values come from the same structured data used by scoring. The
implementation does not generate alternative prose.

## Data flow

1. FastAPI parses and validates the request.
2. Pantry and exclusion ingredients are normalized.
3. The immutable catalog is supplied to the ranking pipeline.
4. Recipes violating hard constraints are removed.
5. Matched and missing ingredients are calculated.
6. Score components and weighted contributions are calculated.
7. The deterministic explanation is rendered.
8. Results are sorted and limited.
9. The response model validates and serializes the result.

## Error handling

- Request errors are reported as `422` responses with field-level details.
- Empty eligible result sets are successful, not errors.
- Invalid catalog data stops application startup.
- Unexpected failures return a generic `500` response and do not expose
  internals.
- The first feature does not add custom exception hierarchies because it has no
  recoverable domain errors beyond validation.
- The FastAPI layer has one narrow request-validation response handler for
  safely rendering non-finite values in otherwise standard `422` details.

## Testing strategy

### Ranking tests

- Lowercasing, trimming, and stable duplicate removal
- Empty pantry behavior
- Exact matching without substring, plural, or synonym behavior
- Excluded-ingredient filtering
- Exclusion precedence over pantry presence
- Inclusive maximum preparation time
- Partial and complete pantry coverage
- Protein fit below, at, and above the target
- Zero protein target
- Time fit at zero, between boundaries, and at the maximum
- Zero-minute maximum
- Four-decimal contribution and final-score rounding
- Deterministic recipe-ID tie-breaking
- Limit application after sorting
- Stable matched and missing ingredient order
- Exact deterministic explanation text

### API tests

- A valid request against the known catalog
- A valid request with no eligible recipes
- Missing required fields
- Negative constraint values
- Real non-finite numeric input with preserved Pydantic error details
- Blank ingredient strings
- Invalid limits
- Unknown request fields
- Non-finite values nested inside rejected unknown fields

Tests should assert product behavior without copying framework implementation
details into every test.

## Technology choices

- Python 3.12
- `src` package layout
- FastAPI
- Pydantic v2
- Pytest and FastAPI's test client
- Ruff for formatting and linting
- Standard-library collections and sorting for ranking
- An in-memory catalog stored with the application

Dependency metadata is added during Feature 001 implementation, not during the
project-foundation commit.

## Acceptance criteria

- `POST /v1/meal-rankings` accepts all specified request fields.
- Invalid boundary data receives a useful validation response.
- Ingredient normalization lowercases, trims, and removes exact duplicates.
- Excluded ingredients and maximum preparation time act as hard filters.
- Minimum protein acts as the documented soft scoring target.
- Each eligible recipe receives the documented three-component score.
- The returned contributions sum exactly to the returned final score.
- Matched and missing ingredients are correct and stably ordered.
- Explanations are deterministic and agree with the score inputs.
- Repeated identical requests produce identical ordered responses.
- Ties use ascending recipe ID, and `limit` is applied after sorting.
- Ranking behavior is testable without starting an HTTP server.
- Ranking and endpoint tests pass.
- Formatting and lint checks pass.
- Learning documentation and mock-interview questions are present.
- No non-goal technology or feature is introduced.

## Implementation workflow

The project-foundation documents are committed on `main` only after user
approval. All Feature 001 application work then occurs on a focused branch in
an isolated worktree. Codex implements; Claude Code independently reviews
without editing unless explicitly authorized. The project owner reviews code,
tests, learning notes, and commands before integration.
