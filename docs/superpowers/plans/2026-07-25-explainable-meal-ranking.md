# Explainable Meal Ranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved `POST /v1/meal-rankings` API with a pure,
deterministic, explainable ranking pipeline over a validated in-memory recipe
catalog.

**Architecture:** A thin FastAPI route validates transport data and passes a
`RankingRequest` plus the immutable application catalog to `rank_recipes`.
Small pure functions normalize ingredients, enforce hard filters, calculate
reconstructable score components, render fixed explanations, sort, and limit
results. Pydantic models define both transport and catalog boundaries; the
domain and ranking modules never import FastAPI.

**Tech Stack:** Python 3.12, `src` package layout, FastAPI, Pydantic v2,
Pytest, FastAPI `TestClient`, Ruff, uv, and standard-library collections and
sorting.

## Global Constraints

- The approved design at
  `docs/superpowers/specs/2026-07-25-explainable-meal-ranking-design.md` is the
  product-behavior source of truth.
- Work only on `feat/explainable-meal-ranking` in the existing linked worktree;
  do not create another worktree and do not merge into `main`.
- This plan was approved by the project owner with the Task 1 normalization
  TDD correction incorporated below.
- uv and uv-managed Python 3.12 are authorized for this repository. Verify both
  before implementation and use Python `3.12.*`; do not fall back to another
  interpreter.
- Follow strict red-green-refactor TDD for every production behavior: one
  focused failing test, expected failure inspection, minimum implementation,
  focused pass, broader relevant pass, then refactor only while green.
- Where a step shows several final test functions, add and run one named test
  or one parameterized rule at a time. The combined block shows the intended
  final file, not permission to batch unobserved red states.
- A missing module or symbol may first surface as a pytest collection error,
  but that is not an accepted red state. Temporarily guard the import inside
  the focused test and fail explicitly with the message “expected production
  behavior is not implemented”; rerun until pytest reports a test `FAILED`,
  then implement. Restore ordinary top-level imports during the green refactor.
- Keep the HTTP layer thin. `pantrypilot.ranking`,
  `pantrypilot.normalization`, `pantrypilot.models`, and
  `pantrypilot.catalog` must not import FastAPI.
- Pass `CATALOG` to `rank_recipes`; do not add repositories, services,
  factories, containers, interfaces, or dependency-injection frameworks.
- Use exact normalized string equality only. Do not add synonyms, fuzzy
  matching, embeddings, LLMs, persistence, authentication, a frontend,
  Docker, external recipe APIs, profiles, feedback, or personalization.
- Calculate component values at full precision, round displayed component
  values and weighted contributions to four decimal places, and set
  `final_score` to the four-decimal sum of the returned contributions.
- Sort by exposed four-decimal `final_score` descending, then recipe `id`
  ascending, before applying `limit`.
- Preserve normalized recipe order in `matched_ingredients` and
  `missing_ingredients`.
- Use one writing agent in this worktree. Use subagent-driven development only
  after plan approval, with a fresh implementation worker and independent
  specification/quality review at each task boundary.
- The project owner authorizes the plan commit and each planned task commit
  only after its required tests and independent review pass. Do not push, open
  a pull request, merge, delete the worktree, or create unrelated commits.

---

## Proposed File Structure

```text
.python-version
pyproject.toml
uv.lock
README.md
src/
└── pantrypilot/
    ├── __init__.py
    ├── app.py
    ├── catalog.py
    ├── models.py
    ├── normalization.py
    └── ranking.py
tests/
├── test_api.py
├── test_catalog.py
├── test_normalization.py
└── test_ranking.py
docs/
└── learning/
    └── 001-explainable-meal-ranking.md
```

Responsibilities:

- `.python-version`: select Python `3.12` for uv-aware tooling.
- `pyproject.toml`: declare only runtime/test/lint dependencies and their
  configuration.
- `uv.lock`: record the exact dependency resolution produced by uv.
- `src/pantrypilot/models.py`: own validated request, catalog, score, ranked
  result, and response shapes.
- `src/pantrypilot/normalization.py`: own exact ingredient normalization and
  stable duplicate removal.
- `src/pantrypilot/catalog.py`: define, validate, normalize, and freeze the
  representative in-memory catalog.
- `src/pantrypilot/ranking.py`: own hard filtering, matching, scoring,
  explanation, deterministic sorting, limiting, and the public ranking
  pipeline.
- `src/pantrypilot/app.py`: own the FastAPI application and the single
  versioned route.
- `tests/test_catalog.py`: cover catalog validation and load-time
  normalization.
- `tests/test_normalization.py`: cover normalization independently.
- `tests/test_ranking.py`: cover all domain and pipeline behavior with small
  local recipe fixtures.
- `tests/test_api.py`: cover the HTTP request/response/error contract against
  the application catalog.
- `docs/learning/001-explainable-meal-ranking.md`: explain the feature,
  reasoning, flow, tests, commands, interview guidance, and exercises.
- `README.md`: replace the stale “foundation only” status with a short Feature
  001 quick start and a link to the learning document.

## Exact Interfaces

The tasks below must keep these names and signatures consistent:

```python
# pantrypilot.normalization
def normalize_ingredients(values: Iterable[str]) -> tuple[str, ...]: ...


# pantrypilot.catalog
def load_catalog(
    records: Iterable[Mapping[str, object]],
) -> tuple[Recipe, ...]: ...


CATALOG: tuple[Recipe, ...]


# pantrypilot.ranking
def is_eligible(
    recipe: Recipe,
    excluded_ingredients: Collection[str],
    max_prep_minutes: int,
) -> bool: ...


def match_ingredients(
    recipe: Recipe,
    pantry_items: Collection[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]: ...


def calculate_score(
    recipe: Recipe,
    matched_count: int,
    min_protein_g: float,
    max_prep_minutes: int,
) -> tuple[float, ScoreBreakdown]: ...


def render_explanation(
    recipe: Recipe,
    matched_count: int,
    min_protein_g: float,
    max_prep_minutes: int,
    score_breakdown: ScoreBreakdown,
) -> str: ...


def sort_ranked_recipes(
    recipes: Iterable[RankedRecipe],
) -> list[RankedRecipe]: ...


def limit_ranked_recipes(
    recipes: Sequence[RankedRecipe],
    limit: int,
) -> list[RankedRecipe]: ...


def rank_recipes(
    request: RankingRequest,
    recipes: Sequence[Recipe],
) -> list[RankedRecipe]: ...
```

The Pydantic models must expose these fields:

```python
class RankingRequest(BaseModel):
    pantry_items: list[str]
    min_protein_g: float
    max_prep_minutes: int
    excluded_ingredients: list[str]
    limit: int


class Recipe(BaseModel):
    id: str
    name: str
    required_ingredients: tuple[str, ...]
    calories: int | float
    protein_g: float
    prep_minutes: int


class ScoreComponent(BaseModel):
    value: float
    weight: float
    contribution: float


class ScoreBreakdown(BaseModel):
    pantry_coverage: ScoreComponent
    protein_fit: ScoreComponent
    time_fit: ScoreComponent


class RankedRecipe(Recipe):
    final_score: float
    matched_ingredients: tuple[str, ...]
    missing_ingredients: tuple[str, ...]
    score_breakdown: ScoreBreakdown
    explanation: str


class RankingResponse(BaseModel):
    results: list[RankedRecipe]
    returned_count: int
```

`RankingRequest` rejects extra fields. All response/catalog models are frozen
and reject extra fields. Ingredient-list validators reject values blank after
trimming. `Recipe` also rejects blank `id`/`name`, empty required ingredients,
non-finite or negative numeric values, and negative preparation time.
Use `StrictInt` for preparation time, maximum preparation time, and limit so
booleans and fractional JSON numbers do not satisfy integer fields. Define
calories as a non-negative `int | FiniteFloat`, and define protein values and
targets as non-negative `FiniteFloat` values.

---

### Plan Approval Gate

Status: approved by the project owner. Preserve the reviewed plan as its own
authorized boundary before executing Task 1:

```powershell
git add docs/superpowers/plans/2026-07-25-explainable-meal-ranking.md
git commit -m "docs: plan explainable meal ranking"
```

Then invoke `superpowers:subagent-driven-development` and execute one task at a
time with its specification and quality review gates.

---

### Task 1: Python Project, Ingredient Normalization, and Immutable Catalog

**Files:**

- Create: `.python-version`
- Create: `pyproject.toml`
- Create: `uv.lock` through `uv lock`
- Create: `src/pantrypilot/__init__.py`
- Create: `src/pantrypilot/models.py`
- Create: `src/pantrypilot/normalization.py`
- Create: `src/pantrypilot/catalog.py`
- Create: `tests/test_normalization.py`
- Create: `tests/test_catalog.py`

**Interfaces:**

- Consumes: the approved recipe schema.
- Produces: `Recipe`, `normalize_ingredients(values)`,
  `load_catalog(records)`, and immutable `CATALOG`. Later models remain absent
  until their first behavior tests require them.

- [ ] **Step 1: Verify the authorized toolchain**

Run:

```powershell
uv --version
uv python find 3.12
```

Expected: uv reports its installed version and the second command resolves an
uv-managed Python 3.12 interpreter. Stop if either check fails.

- [ ] **Step 2: Add the minimum project metadata**

Write `.python-version` as:

```text
3.12
```

Write `pyproject.toml` as:

```toml
[project]
name = "pantrypilot"
version = "0.1.0"
description = "Explainable pantry-based meal ranking"
requires-python = "==3.12.*"
dependencies = [
    "fastapi",
    "pydantic>=2,<3",
    "uvicorn",
]

[dependency-groups]
dev = [
    "httpx",
    "pytest",
    "ruff",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

Then run:

```powershell
uv lock
uv sync --locked --python 3.12
```

Expected: `uv.lock` and `.venv` are created, the lock uses Python 3.12
compatibility, and no unrelated dependency or tool is added.

- [ ] **Step 3: Write the dedicated normalization tests first**

Create `tests/test_normalization.py` before creating
`src/pantrypilot/normalization.py`:

```python
import pytest

from pantrypilot.normalization import normalize_ingredients


def test_normalize_ingredients_trims_lowercases_and_stably_deduplicates():
    assert normalize_ingredients([" Eggs ", "spinach", "EGGS", "Olive  Oil"]) == (
        "eggs",
        "spinach",
        "olive  oil",
    )


def test_normalize_ingredients_rejects_blank_values():
    with pytest.raises(ValueError, match="must not be blank"):
        normalize_ingredients(["eggs", "   "])
```

- [ ] **Step 4: Run normalization tests and verify the red state**

Run:

```powershell
uv run pytest tests/test_normalization.py -v
```

Expected initially: collection reports that `pantrypilot.normalization` does
not exist. Apply the Global Constraints import guard and rerun until the test
reports `FAILED` for the explicit missing-behavior assertion. Confirm that is
the only cause before continuing.

- [ ] **Step 5: Implement only ingredient normalization**

Create `normalization.py` without altering internal whitespace, punctuation,
plurality, or synonyms:

```python
def normalize_ingredients(values: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        ingredient = value.strip().lower()
        if not ingredient:
            raise ValueError("ingredient values must not be blank")
        if ingredient not in seen:
            seen.add(ingredient)
            normalized.append(ingredient)
    return tuple(normalized)
```

- [ ] **Step 6: Run normalization tests and verify green**

Run:

```powershell
uv run pytest tests/test_normalization.py -v
```

Expected: both normalization tests PASS with pristine output.

- [ ] **Step 7: Write the first failing catalog-model tests**

Create `tests/test_catalog.py` with a local valid record and focused tests:

```python
from copy import deepcopy

import pytest
from pydantic import ValidationError

from pantrypilot.catalog import load_catalog

VALID_RECIPE = {
    "id": "test-recipe",
    "name": "Test Recipe",
    "required_ingredients": [" Eggs ", "spinach", "EGGS"],
    "calories": 300,
    "protein_g": 20.0,
    "prep_minutes": 10,
}


def test_load_catalog_normalizes_ingredients_once_and_freezes_collection():
    catalog = load_catalog([VALID_RECIPE])

    assert isinstance(catalog, tuple)
    assert catalog[0].required_ingredients == ("eggs", "spinach")


def test_load_catalog_rejects_duplicate_recipe_ids():
    duplicate = {**VALID_RECIPE, "name": "Duplicate"}

    with pytest.raises(ValueError, match="duplicate recipe id"):
        load_catalog([VALID_RECIPE, duplicate])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "   "),
        ("name", ""),
        ("required_ingredients", []),
        ("required_ingredients", ["valid", "   "]),
        ("calories", -1),
        ("calories", float("inf")),
        ("protein_g", -0.1),
        ("protein_g", float("nan")),
        ("prep_minutes", -1),
    ],
)
def test_load_catalog_rejects_invalid_recipe_records(field, value):
    record = deepcopy(VALID_RECIPE)
    record[field] = value

    with pytest.raises((ValidationError, ValueError)):
        load_catalog([record])


def test_load_catalog_rejects_unknown_recipe_fields():
    record = {**VALID_RECIPE, "future_field": "not approved"}

    with pytest.raises(ValidationError):
        load_catalog([record])
```

- [ ] **Step 8: Run the focused catalog tests and inspect the expected failure**

Run:

```powershell
uv run pytest tests/test_catalog.py -v
```

Expected initially: collection reports that `pantrypilot.catalog` and its
models do not exist. Apply the Global Constraints import guard and rerun until
the focused test reports `FAILED` for missing catalog behavior; do not write
production code while the result is still an import error.

- [ ] **Step 9: Implement only the validated recipe model and loader**

In `models.py`, use Pydantic v2 `ConfigDict`, `Field`, `FiniteFloat`,
`StrictInt`, and `field_validator`. Configure `Recipe` with
`extra="forbid"` and `frozen=True`. Define `calories` as a non-negative
`int | FiniteFloat`, `protein_g` as a non-negative `FiniteFloat`, and
`prep_minutes` as a non-negative `StrictInt`. Reject `id` and `name` when
`not value.strip()` without otherwise changing them. Normalize required
ingredients in an after-validator:

```python
@field_validator("required_ingredients")
@classmethod
def normalize_required_ingredients(cls, values: tuple[str, ...]) -> tuple[str, ...]:
    return normalize_ingredients(values)
```

Have the `Recipe.required_ingredients` field validator call this function.
Implement `load_catalog` by validating every mapping as a `Recipe`, collecting
the results into a tuple, and rejecting the first repeated `id` with
`ValueError("duplicate recipe id: <id>")`.

Define exactly this representative catalog:

| ID | Name | Required ingredients | Calories | Protein | Prep |
|---|---|---|---:|---:|---:|
| `spinach-omelet` | Spinach Omelet | eggs, spinach, olive oil | 410 | 28.0 | 15 |
| `black-bean-tacos` | Black Bean Tacos | black beans, corn tortillas, avocado, lime | 520 | 19.0 | 25 |
| `peanut-noodles` | Peanut Noodles | noodles, peanuts, soy sauce | 560 | 20.0 | 20 |
| `lentil-soup` | Lentil Soup | lentils, carrots, celery, vegetable broth | 360 | 22.0 | 45 |

Create `CATALOG = load_catalog(RAW_CATALOG)` at module import so invalid
application data prevents application import/startup. Do not add a repository
or loader class.

- [ ] **Step 10: Run focused and broader checks**

Run:

```powershell
uv run pytest tests/test_normalization.py -v
uv run pytest tests/test_catalog.py -v
uv run ruff format --check src tests
uv run ruff check src tests
```

Expected: normalization and catalog tests PASS; formatting and lint checks
PASS.

- [ ] **Step 11: Review and commit the independently testable boundary**

Run `superpowers:requesting-code-review` against Task 1's diff. Resolve
correctness, scope, schema, and test findings while keeping the tests green.
After the review is clean, use the authorized task commit:

```powershell
git add .python-version pyproject.toml uv.lock src/pantrypilot tests/test_normalization.py tests/test_catalog.py
git commit -m "feat: add validated recipe catalog"
```

---

### Task 2: Ingredient Matching and Hard Eligibility

**Files:**

- Create: `tests/test_ranking.py`
- Create: `src/pantrypilot/ranking.py`

**Interfaces:**

- Consumes: `Recipe` and `normalize_ingredients`.
- Produces: `is_eligible(recipe, excluded_ingredients, max_prep_minutes)` and
  `match_ingredients(recipe, pantry_items)`.

- [ ] **Step 1: Write failing matching and hard-filter tests**

Create `tests/test_ranking.py` with this local fixture helper:

```python
from pantrypilot.models import Recipe
from pantrypilot.ranking import is_eligible, match_ingredients


def make_recipe(
    *,
    recipe_id: str = "recipe",
    required: tuple[str, ...] = ("eggs", "spinach", "olive oil"),
    protein_g: float = 20.0,
    prep_minutes: int = 10,
) -> Recipe:
    return Recipe(
        id=recipe_id,
        name=recipe_id.replace("-", " ").title(),
        required_ingredients=required,
        calories=300,
        protein_g=protein_g,
        prep_minutes=prep_minutes,
    )


def test_empty_pantry_marks_every_required_ingredient_missing():
    matched, missing = match_ingredients(make_recipe(), set())

    assert matched == ()
    assert missing == ("eggs", "spinach", "olive oil")


def test_matching_is_exact_not_substring_plural_or_synonym_based():
    recipe = make_recipe(required=("tomatoes", "olive oil", "garbanzo beans"))

    matched, missing = match_ingredients(recipe, {"tomato", "oil", "chickpeas"})

    assert matched == ()
    assert missing == recipe.required_ingredients


def test_matching_preserves_normalized_recipe_order():
    matched, missing = match_ingredients(make_recipe(), {"spinach", "eggs"})

    assert matched == ("eggs", "spinach")
    assert missing == ("olive oil",)


def test_excluded_ingredient_makes_recipe_ineligible():
    assert not is_eligible(make_recipe(), {"spinach"}, 30)


def test_exclusion_takes_precedence_over_pantry_presence():
    recipe = make_recipe()
    matched, _ = match_ingredients(recipe, {"spinach"})

    assert matched == ("spinach",)
    assert not is_eligible(recipe, {"spinach"}, 30)


def test_maximum_preparation_time_is_inclusive():
    assert is_eligible(make_recipe(prep_minutes=30), set(), 30)


def test_recipe_over_maximum_preparation_time_is_ineligible():
    assert not is_eligible(make_recipe(prep_minutes=31), set(), 30)
```

- [ ] **Step 2: Run the focused ranking tests and inspect the failure**

Run:

```powershell
uv run pytest tests/test_ranking.py -v
```

Expected initially: collection reports that `pantrypilot.ranking` does not
exist. Apply the Global Constraints import guard and rerun until the focused
test reports `FAILED` for missing ranking behavior.

- [ ] **Step 3: Implement matching and hard filtering**

Create `ranking.py` using only standard-library collection types and the
existing models:

```python
def is_eligible(
    recipe: Recipe,
    excluded_ingredients: Collection[str],
    max_prep_minutes: int,
) -> bool:
    return recipe.prep_minutes <= max_prep_minutes and not set(
        recipe.required_ingredients
    ).intersection(excluded_ingredients)


def match_ingredients(
    recipe: Recipe,
    pantry_items: Collection[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    pantry = set(pantry_items)
    matched = tuple(
        ingredient for ingredient in recipe.required_ingredients if ingredient in pantry
    )
    missing = tuple(
        ingredient
        for ingredient in recipe.required_ingredients
        if ingredient not in pantry
    )
    return matched, missing
```

Do not put `min_protein_g` into `is_eligible`; it is a soft scoring target.

- [ ] **Step 4: Run focused and broader checks**

Run:

```powershell
uv run pytest tests/test_normalization.py tests/test_ranking.py -v
uv run pytest tests/test_catalog.py tests/test_normalization.py tests/test_ranking.py -v
uv run ruff format --check src tests
uv run ruff check src tests
```

Expected: all current tests and static checks PASS.

- [ ] **Step 5: Review and commit the boundary**

Run `superpowers:requesting-code-review` for exact matching, exclusion
precedence, inclusive time filtering, and accidental non-goal behavior. After
the review is clean, use the authorized task commit:

```powershell
git add src/pantrypilot/ranking.py tests/test_ranking.py
git commit -m "feat: add ingredient matching and eligibility rules"
```

---

### Task 3: Reconstructable Scoring and Fixed Explanations

**Files:**

- Modify: `src/pantrypilot/models.py`
- Modify: `src/pantrypilot/ranking.py`
- Modify: `tests/test_ranking.py`

**Interfaces:**

- Consumes: `Recipe`.
- Produces: frozen `ScoreComponent` and `ScoreBreakdown` models in `models.py`,
  `calculate_score(...) -> tuple[float, ScoreBreakdown]`, and
  `render_explanation(...) -> str`.

- [ ] **Step 1: Add the complete core scoring tests before scoring production code**

Extend the import block with:

```python
from decimal import Decimal

import pytest

from pantrypilot.ranking import calculate_score
```

Use the Global Constraints import guard so the test module collects while
`calculate_score` is absent. Then append tests that directly call
`calculate_score` for every ordinary scoring boundary, full-precision
contribution rounding, exact reconstruction, and score bounds:

```python
@pytest.mark.parametrize(
    ("matched_count", "expected"),
    [(0, 0.0), (1, 0.3333), (3, 1.0)],
)
def test_pantry_coverage_handles_empty_partial_and_complete_matches(
    matched_count, expected
):
    _, breakdown = calculate_score(
        make_recipe(), matched_count, min_protein_g=20.0, max_prep_minutes=20
    )

    assert breakdown.pantry_coverage.value == expected


@pytest.mark.parametrize(
    ("protein_g", "target", "expected"),
    [
        (10.0, 20.0, 0.5),
        (20.0, 20.0, 1.0),
        (30.0, 20.0, 1.0),
    ],
)
def test_protein_fit_is_capped(protein_g, target, expected):
    _, breakdown = calculate_score(
        make_recipe(protein_g=protein_g),
        matched_count=0,
        min_protein_g=target,
        max_prep_minutes=20,
    )

    assert breakdown.protein_fit.value == expected


@pytest.mark.parametrize(
    ("prep_minutes", "maximum", "expected"),
    [
        (0, 30, 1.0),
        (15, 30, 0.5),
        (30, 30, 0.0),
    ],
)
def test_time_fit_handles_zero_between_and_maximum(prep_minutes, maximum, expected):
    _, breakdown = calculate_score(
        make_recipe(prep_minutes=prep_minutes),
        matched_count=0,
        min_protein_g=20.0,
        max_prep_minutes=maximum,
    )

    assert breakdown.time_fit.value == expected


def test_contributions_use_full_precision_before_four_decimal_rounding():
    recipe = make_recipe(required=tuple(f"item-{i}" for i in range(9)))

    final_score, breakdown = calculate_score(
        recipe,
        matched_count=2,
        min_protein_g=20.0,
        max_prep_minutes=20,
    )

    assert breakdown.pantry_coverage.value == 0.2222
    assert breakdown.pantry_coverage.contribution == 0.1556
    assert final_score == 0.4056


def test_final_score_is_exactly_reconstructable_from_returned_contributions():
    final_score, breakdown = calculate_score(
        make_recipe(protein_g=28.0, prep_minutes=15),
        matched_count=2,
        min_protein_g=25.0,
        max_prep_minutes=30,
    )
    contributions = (
        breakdown.pantry_coverage.contribution,
        breakdown.protein_fit.contribution,
        breakdown.time_fit.contribution,
    )

    assert final_score == 0.7167
    assert Decimal(str(final_score)) == sum(
        (Decimal(str(value)) for value in contributions),
        start=Decimal("0"),
    )
    assert 0.0 <= final_score <= 1.0
```

- [ ] **Step 2: Run the focused tests and inspect the expected failure**

Run:

```powershell
uv run pytest tests/test_ranking.py -k "coverage or protein_fit or time_fit or precision or reconstructable" -v
```

Expected initially: importing `calculate_score` fails. Apply the Global
Constraints import guard and rerun until the focused test reports `FAILED` for
missing score behavior.

- [ ] **Step 3: Implement score models and the ordinary scoring path**

In `models.py`, add the exact frozen, extra-forbidden `ScoreComponent` and
`ScoreBreakdown` Pydantic models declared under **Exact Interfaces**.

In `ranking.py`, import those score models and add constants:

```python
PANTRY_WEIGHT = 0.70
PROTEIN_WEIGHT = 0.20
TIME_WEIGHT = 0.10
SCORE_DECIMALS = 4
```

Calculate pantry coverage from `matched_count /
len(recipe.required_ingredients)`. For the positive protein targets in the
current tests, calculate `min(recipe.protein_g / min_protein_g, 1.0)`. For the
nonzero time maximums in the current tests, calculate
`1 - recipe.prep_minutes / max_prep_minutes`.

Keep all component values at full precision until each contribution is
calculated. Construct each `ScoreComponent` as:

```python
ScoreComponent(
    value=round(full_precision_value, SCORE_DECIMALS),
    weight=weight,
    contribution=round(full_precision_value * weight, SCORE_DECIMALS),
)
```

Then calculate:

```python
final_score = round(
    pantry.contribution + protein.contribution + time.contribution,
    SCORE_DECIMALS,
)
```

Use Python's built-in `round`; do not round component values before calculating
their contributions. Leave only the zero-protein-target and zero-time-maximum
branches for their own later focused failing tests.

- [ ] **Step 4: Run the focused tests**

Run:

```powershell
uv run pytest tests/test_ranking.py -k "coverage or protein_fit or time_fit or precision or reconstructable" -v
```

Expected: PASS.

- [ ] **Step 5: Add the failing zero-protein-target test**

Append:

```python
def test_protein_fit_is_one_when_target_is_zero():
    _, breakdown = calculate_score(
        make_recipe(protein_g=0.0),
        matched_count=0,
        min_protein_g=0.0,
        max_prep_minutes=20,
    )

    assert breakdown.protein_fit.value == 1.0
```

Run:

```powershell
uv run pytest tests/test_ranking.py -k "target_is_zero" -v
```

Expected: FAIL because the ordinary formula divides by zero.

- [ ] **Step 6: Implement and pass the zero-protein-target branch**

Use protein fit `1.0` when `min_protein_g == 0`; otherwise retain the ordinary
capped formula.

Run:

```powershell
uv run pytest tests/test_ranking.py -k "protein_fit or precision or reconstructable" -v
```

Expected: PASS.

- [ ] **Step 7: Add the failing zero-time-maximum test**

Append:

```python
def test_time_fit_is_one_when_maximum_is_zero():
    _, breakdown = calculate_score(
        make_recipe(prep_minutes=0),
        matched_count=0,
        min_protein_g=20.0,
        max_prep_minutes=0,
    )

    assert breakdown.time_fit.value == 1.0
```

Run:

```powershell
uv run pytest tests/test_ranking.py -k "maximum_is_zero" -v
```

Expected: FAIL because the ordinary formula divides by zero.

- [ ] **Step 8: Implement and pass the zero-time-maximum branch**

Use time fit `1.0` when `max_prep_minutes == 0`; otherwise retain
`1 - recipe.prep_minutes / max_prep_minutes`. `calculate_score` is called only
for recipes that already passed the hard time filter; do not add clamping that
changes the approved formula.

Run:

```powershell
uv run pytest tests/test_ranking.py -k "time_fit or precision or reconstructable" -v
```

Expected: PASS.

- [ ] **Step 9: Add failing exact-explanation tests**

Extend the ranking import with `render_explanation`, using the temporary import
guard required by Global Constraints for the red run, then append:

```python
@pytest.mark.parametrize(
    ("protein_g", "target", "phrase"),
    [
        (28.0, 25.0, "meets"),
        (20.0, 25.0, "is below"),
    ],
)
def test_explanation_uses_one_exact_template(protein_g, target, phrase):
    recipe = make_recipe(protein_g=protein_g, prep_minutes=15)
    _, breakdown = calculate_score(
        recipe, matched_count=2, min_protein_g=target, max_prep_minutes=30
    )

    explanation = render_explanation(
        recipe,
        matched_count=2,
        min_protein_g=target,
        max_prep_minutes=30,
        score_breakdown=breakdown,
    )

    assert explanation == (
        "Matched 2 of 3 required ingredients (coverage 0.6667); "
        f"{protein_g:.1f}g protein {phrase} the {target:.1f}g target "
        f"(fit {breakdown.protein_fit.value:.4f}); 15 minutes is within "
        "the 30-minute limit (fit 0.5000)."
    )
```

Run:

```powershell
uv run pytest tests/test_ranking.py -k "explanation" -v
```

Expected: the focused test reports `FAILED` for missing explanation behavior,
not a collection error.

- [ ] **Step 10: Render the fixed template from score data**

Use `"meets"` when `recipe.protein_g >= min_protein_g`; otherwise use
`"is below"`. Format coverage and fit values from `score_breakdown`, not by
recalculating them. Use exactly one template and no generated alternatives.

Run:

```powershell
uv run pytest tests/test_ranking.py -v
uv run pytest tests -v
uv run ruff format --check src tests
uv run ruff check src tests
```

Expected: all tests and checks PASS.

- [ ] **Step 11: Review and commit the boundary**

Run `superpowers:requesting-code-review` with emphasis on full-precision
calculation, four-decimal reconstruction, zero targets, boundary behavior, and
explanation/data agreement. After the review is clean, use the authorized task
commit:

```powershell
git add src/pantrypilot/models.py src/pantrypilot/ranking.py tests/test_ranking.py
git commit -m "feat: add reconstructable recipe scoring"
```

---

### Task 4: Deterministic Ranking Pipeline, Ordering, and Limit

**Files:**

- Modify: `src/pantrypilot/models.py`
- Modify: `src/pantrypilot/ranking.py`
- Modify: `tests/test_ranking.py`

**Interfaces:**

- Consumes: recipe sequences and all pure ranking helpers.
- Produces: the initially unconstrained, all-fields-required `RankingRequest`,
  frozen `RankedRecipe`, `sort_ranked_recipes`, `limit_ranked_recipes`, and the
  public `rank_recipes(request, recipes) -> list[RankedRecipe]`. Transport
  boundary constraints are added only after their failing API tests in Task 5.

- [ ] **Step 1: Add a local request helper and the first failing pipeline test**

Extend the existing model/ranking imports with `RankingRequest` and
`rank_recipes`, then append:

```python
def make_request(
    *,
    pantry_items: list[str] | None = None,
    min_protein_g: float = 20.0,
    max_prep_minutes: int = 30,
    excluded_ingredients: list[str] | None = None,
    limit: int = 5,
) -> RankingRequest:
    return RankingRequest(
        pantry_items=[] if pantry_items is None else pantry_items,
        min_protein_g=min_protein_g,
        max_prep_minutes=max_prep_minutes,
        excluded_ingredients=(
            [] if excluded_ingredients is None else excluded_ingredients
        ),
        limit=limit,
    )


def test_rank_recipes_normalizes_request_and_builds_stable_result_fields():
    recipe = make_recipe()

    result = rank_recipes(
        make_request(
            pantry_items=[" Spinach ", "EGGS", "spinach"],
            excluded_ingredients=[],
        ),
        [recipe],
    )[0]

    assert result.matched_ingredients == ("eggs", "spinach")
    assert result.missing_ingredients == ("olive oil",)
    assert result.required_ingredients == recipe.required_ingredients
    assert result.score_breakdown.pantry_coverage.value == 0.6667
    assert result.explanation.startswith("Matched 2 of 3")
```

Run:

```powershell
uv run pytest tests/test_ranking.py::test_rank_recipes_normalizes_request_and_builds_stable_result_fields -v
```

Expected initially: importing `RankingRequest` or `rank_recipes` fails. Apply
the Global Constraints import guard and rerun until the focused test reports
`FAILED` for missing pipeline behavior.

- [ ] **Step 2: Add all remaining core orchestration tests before production**

While the import guard is still active, append each test below one at a time
and run that named test until it reports `FAILED` for missing pipeline
behavior:

```python
def test_rank_recipes_applies_exclusion_before_scoring():
    recipe = make_recipe()

    assert (
        rank_recipes(
            make_request(
                pantry_items=["spinach"],
                excluded_ingredients=[" SPINACH "],
            ),
            [recipe],
        )
        == []
    )


def test_rank_recipes_applies_time_filter_but_not_protein_as_hard_filter():
    too_slow = make_recipe(recipe_id="slow", protein_g=100.0, prep_minutes=31)
    low_protein = make_recipe(recipe_id="low-protein", protein_g=1.0, prep_minutes=30)

    results = rank_recipes(
        make_request(min_protein_g=50.0, max_prep_minutes=30),
        [too_slow, low_protein],
    )

    assert [result.id for result in results] == ["low-protein"]
    assert results[0].score_breakdown.protein_fit.value == 0.02


def test_rank_recipes_with_empty_pantry_returns_zero_coverage_results():
    result = rank_recipes(make_request(pantry_items=[]), [make_recipe()])[0]

    assert result.matched_ingredients == ()
    assert result.missing_ingredients == ("eggs", "spinach", "olive oil")
    assert result.score_breakdown.pantry_coverage.value == 0.0


def test_repeated_identical_rankings_are_equal():
    request = make_request(pantry_items=["eggs"])
    recipes = [make_recipe(recipe_id="b"), make_recipe(recipe_id="a")]

    assert rank_recipes(request, recipes) == rank_recipes(request, recipes)
```

Use these named commands as the tests are added:

```powershell
uv run pytest tests/test_ranking.py::test_rank_recipes_applies_exclusion_before_scoring -v
uv run pytest tests/test_ranking.py::test_rank_recipes_applies_time_filter_but_not_protein_as_hard_filter -v
uv run pytest tests/test_ranking.py::test_rank_recipes_with_empty_pantry_returns_zero_coverage_results -v
uv run pytest tests/test_ranking.py::test_repeated_identical_rankings_are_equal -v
```

Expected for every command: one test `FAILED`, never a collection error.

- [ ] **Step 3: Implement the minimum request/result models and orchestration**

Add `RankingRequest` with the five exact field names and plain field types from
**Exact Interfaces**, no defaults, and no boundary constraints yet. Add frozen,
extra-forbidden `RankedRecipe` with the exact result fields.

In `rank_recipes`:

1. Normalize request pantry and exclusions once.
2. Convert each to a set for membership checks.
3. Skip ineligible recipes before matching/scoring.
4. Calculate matched and missing ingredients.
5. Calculate the breakdown and final score.
6. Render the explanation from that breakdown.
7. Construct an explicit `RankedRecipe` from recipe and ranking fields.

Do not mutate the request or catalog.

Reuse `is_eligible`; do not duplicate filter rules inside the loop. Do not sort
or limit yet; those behaviors remain for their own later failing tests. Restore
ordinary top-level imports during the green refactor, then run:

```powershell
uv run pytest tests/test_ranking.py -k "rank_recipes_normalizes or rank_recipes_applies or empty_pantry_returns or repeated_identical" -v
```

Expected: PASS.

- [ ] **Step 4: Add failing deterministic ordering and limit tests**

Append and run each test separately so both behaviors have an observed RED:

```python
def test_equal_exposed_scores_tie_break_by_recipe_id():
    recipes = [
        make_recipe(recipe_id="z-recipe", protein_g=10.002),
        make_recipe(recipe_id="a-recipe", protein_g=10.001),
    ]

    results = rank_recipes(
        make_request(min_protein_g=20.0),
        recipes,
    )

    assert results[0].final_score == results[1].final_score
    assert [result.id for result in results] == ["a-recipe", "z-recipe"]


def test_limit_is_applied_after_sorting():
    recipes = [
        make_recipe(recipe_id="low", required=("missing",), protein_g=0.0),
        make_recipe(recipe_id="high", required=("eggs",), protein_g=20.0),
    ]

    results = rank_recipes(
        make_request(pantry_items=["eggs"], limit=1),
        recipes,
    )

    assert [result.id for result in results] == ["high"]
```

Run:

```powershell
uv run pytest tests/test_ranking.py::test_equal_exposed_scores_tie_break_by_recipe_id -v
uv run pytest tests/test_ranking.py::test_limit_is_applied_after_sorting -v
```

Expected: each named test reports `FAILED` until sorting and limiting exist.

- [ ] **Step 5: Implement exposed-score sorting and post-sort slicing**

Implement:

```python
def sort_ranked_recipes(
    recipes: Iterable[RankedRecipe],
) -> list[RankedRecipe]:
    return sorted(recipes, key=lambda recipe: (-recipe.final_score, recipe.id))


def limit_ranked_recipes(
    recipes: Sequence[RankedRecipe],
    limit: int,
) -> list[RankedRecipe]:
    return list(recipes[:limit])
```

Finish `rank_recipes` with:

```python
return limit_ranked_recipes(
    sort_ranked_recipes(ranked_recipes),
    request.limit,
)
```

- [ ] **Step 6: Run the focused and broader verification**

Run:

```powershell
uv run pytest tests/test_ranking.py -k "tie_break or limit_is" -v
uv run pytest tests/test_ranking.py -v
uv run pytest tests -v
uv run ruff format --check src tests
uv run ruff check src tests
```

Expected: all domain, catalog, and normalization tests PASS.

- [ ] **Step 7: Review and commit the boundary**

Run `superpowers:requesting-code-review` with emphasis on pure orchestration,
input immutability, filters-before-score, exposed-score tie behavior, stable
ingredient order, and post-sort limiting. After the review is clean, use the
authorized task commit:

```powershell
git add src/pantrypilot/models.py src/pantrypilot/ranking.py tests/test_ranking.py
git commit -m "feat: add deterministic meal ranking pipeline"
```

---

### Task 5: Versioned FastAPI Contract and Validation Errors

**Files:**

- Modify: `src/pantrypilot/models.py`
- Create: `src/pantrypilot/app.py`
- Create: `tests/test_api.py`

**Interfaces:**

- Consumes: `RankingRequest`, `RankedRecipe`, `CATALOG`, and `rank_recipes`.
- Produces: the constrained request boundary, frozen `RankingResponse`, FastAPI
  application object `app`, and `POST /v1/meal-rankings`.

- [ ] **Step 1: Write the failing valid-response contract test**

Create `tests/test_api.py`:

```python
import json

import pytest
from fastapi.testclient import TestClient

import pantrypilot.app as app_module

client = TestClient(app_module.app)

VALID_REQUEST = {
    "pantry_items": [" Eggs ", "spinach", "EGGS"],
    "min_protein_g": 25.0,
    "max_prep_minutes": 30,
    "excluded_ingredients": ["peanuts"],
    "limit": 1,
}


def test_meal_rankings_returns_known_catalog_result():
    response = client.post("/v1/meal-rankings", json=VALID_REQUEST)

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "id": "spinach-omelet",
                "name": "Spinach Omelet",
                "required_ingredients": [
                    "eggs",
                    "spinach",
                    "olive oil",
                ],
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
                        "contribution": 0.4667,
                    },
                    "protein_fit": {
                        "value": 1.0,
                        "weight": 0.2,
                        "contribution": 0.2,
                    },
                    "time_fit": {
                        "value": 0.5,
                        "weight": 0.1,
                        "contribution": 0.05,
                    },
                },
                "explanation": (
                    "Matched 2 of 3 required ingredients "
                    "(coverage 0.6667); 28.0g protein meets the "
                    "25.0g target (fit 1.0000); 15 minutes is within "
                    "the 30-minute limit (fit 0.5000)."
                ),
            }
        ],
        "returned_count": 1,
    }
```

- [ ] **Step 2: Observe the first RED, then add framework-backed tests before the route**

Run:

```powershell
uv run pytest tests/test_api.py::test_meal_rankings_returns_known_catalog_result -v
```

Expected initially: collection reports that `pantrypilot.app` does not exist.
Apply the Global Constraints import guard and rerun until the focused test
reports `FAILED` for missing endpoint behavior.

While that guard is active, append each framework-backed or route acceptance
rule below one at a time. Run its named test immediately and confirm an
explicit `FAILED` result before creating `app.py`:

```python
def test_meal_rankings_returns_successful_empty_result():
    request = {
        **VALID_REQUEST,
        "pantry_items": [],
        "max_prep_minutes": 0,
        "excluded_ingredients": [],
        "limit": 5,
    }

    response = client.post("/v1/meal-rankings", json=request)

    assert response.status_code == 200
    assert response.json() == {"results": [], "returned_count": 0}


@pytest.mark.parametrize(
    "missing_field",
    [
        "pantry_items",
        "min_protein_g",
        "max_prep_minutes",
        "excluded_ingredients",
        "limit",
    ],
)
def test_meal_rankings_requires_every_request_field(missing_field):
    request = {**VALID_REQUEST}
    request.pop(missing_field)

    response = client.post("/v1/meal-rankings", json=request)

    assert response.status_code == 422
    assert missing_field in response.text


def test_meal_rankings_rejects_fractional_integer():
    response = client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, "max_prep_minutes": 30.5},
    )

    assert response.status_code == 422
    assert "max_prep_minutes" in response.text


def test_meal_rankings_rejects_malformed_json():
    response = client.post(
        "/v1/meal-rankings",
        content="{",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422


def test_unexpected_error_returns_500_without_internal_details(monkeypatch):
    def fail_ranking(*_args, **_kwargs):
        raise RuntimeError("private implementation detail")

    monkeypatch.setattr(app_module, "rank_recipes", fail_ranking)
    safe_client = TestClient(
        app_module.app,
        raise_server_exceptions=False,
    )

    response = safe_client.post(
        "/v1/meal-rankings",
        json=VALID_REQUEST,
    )

    assert response.status_code == 500
    assert "private implementation detail" not in response.text


def test_identical_http_requests_return_identical_ordered_responses():
    first = client.post("/v1/meal-rankings", json=VALID_REQUEST)
    second = client.post("/v1/meal-rankings", json=VALID_REQUEST)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
```

Run each new rule separately:

```powershell
uv run pytest tests/test_api.py::test_meal_rankings_returns_successful_empty_result -v
uv run pytest tests/test_api.py::test_meal_rankings_requires_every_request_field -v
uv run pytest tests/test_api.py::test_meal_rankings_rejects_fractional_integer -v
uv run pytest tests/test_api.py::test_meal_rankings_rejects_malformed_json -v
uv run pytest tests/test_api.py::test_unexpected_error_returns_500_without_internal_details -v
uv run pytest tests/test_api.py::test_identical_http_requests_return_identical_ordered_responses -v
```

Expected for every command: the test or parameterized rule reports `FAILED`
for the missing endpoint, never a collection error.

- [ ] **Step 3: Implement the thin route**

Add frozen, extra-forbidden `RankingResponse` with `results:
list[RankedRecipe]` and non-negative `returned_count`. Create `app.py`:

```python
from fastapi import FastAPI

from pantrypilot.catalog import CATALOG
from pantrypilot.models import RankingRequest, RankingResponse
from pantrypilot.ranking import rank_recipes

app = FastAPI(title="PantryPilot")


@app.post("/v1/meal-rankings", response_model=RankingResponse)
def create_meal_ranking(request: RankingRequest) -> RankingResponse:
    results = rank_recipes(request, CATALOG)
    return RankingResponse(
        results=results,
        returned_count=len(results),
    )
```

Do not catch Pydantic/FastAPI validation errors and do not duplicate ranking
rules in the route.

Restore ordinary top-level imports during the green refactor, then run:

```powershell
uv run pytest tests/test_api.py -k "known_catalog or successful_empty or requires_every or fractional_integer or malformed_json or unexpected_error or identical_http" -v
```

Expected: all framework-backed and route acceptance tests PASS.

- [ ] **Step 4: Add only genuinely missing validation constraints as failing tests**

Create a non-raising client for invalid inputs that currently reach domain
exceptions:

```python
safe_client = TestClient(app_module.app, raise_server_exceptions=False)
```

Append each parameterized rule or named test below one at a time and run it
before adding any request constraint:

```python
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("min_protein_g", -0.1),
        ("max_prep_minutes", -1),
        ("limit", 0),
        ("limit", 51),
    ],
)
def test_meal_rankings_rejects_invalid_numeric_boundaries(field, value):
    response = client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, field: value},
    )

    assert response.status_code == 422
    assert field in response.text


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("min_protein_g", "25.0"),
        ("max_prep_minutes", True),
        ("limit", 5.0),
        ("limit", True),
    ],
)
def test_meal_rankings_rejects_wrong_numeric_types(field, value):
    response = client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, field: value},
    )

    assert response.status_code == 422
    assert field in response.text


# Post-review correction: Task 8 adds and executes this real-float regression
# from the 04ae8ab baseline. It replaces the original Task 5 string cases.
@pytest.mark.parametrize(
    ("value", "rendered_input"),
    [
        (float("inf"), "Infinity"),
        (float("-inf"), "-Infinity"),
        (float("nan"), "NaN"),
    ],
)
def test_meal_rankings_preserves_non_finite_validation_details(value, rendered_input):
    response = safe_client.post(
        "/v1/meal-rankings",
        content=json.dumps({**VALID_REQUEST, "min_protein_g": value}),
        headers={"content-type": "application/json"},
    )

    error = response.json()["detail"][0]
    assert response.status_code == 422
    assert error["type"] == "finite_number"
    assert error["loc"] == ["body", "min_protein_g"]
    assert error["msg"] == "Input should be a finite number"
    assert error["input"] == rendered_input
    assert "url" in error


def test_meal_rankings_keeps_null_distinct_from_non_finite_values():
    response = safe_client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, "min_protein_g": None},
    )

    error = response.json()["detail"][0]
    assert response.status_code == 422
    assert error["type"] == "float_type"
    assert error["loc"] == ["body", "min_protein_g"]
    assert error["msg"] == "Input should be a valid number"
    assert error["input"] is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pantry_items", ["eggs", "   "]),
        ("excluded_ingredients", [""]),
    ],
)
def test_meal_rankings_rejects_blank_ingredient_values(field, value):
    response = safe_client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, field: value},
    )

    assert response.status_code == 422
    assert field in response.text


def test_meal_rankings_rejects_unknown_request_fields():
    response = client.post(
        "/v1/meal-rankings",
        json={**VALID_REQUEST, "ranking_model": "future"},
    )

    assert response.status_code == 422
    assert "ranking_model" in response.text
```

Run each new rule immediately after adding it:

```powershell
uv run pytest tests/test_api.py::test_meal_rankings_rejects_invalid_numeric_boundaries -v
uv run pytest tests/test_api.py::test_meal_rankings_rejects_wrong_numeric_types -v
uv run pytest tests/test_api.py::test_meal_rankings_rejects_blank_ingredient_values -v
uv run pytest tests/test_api.py::test_meal_rankings_rejects_unknown_request_fields -v
```

Expected before final model constraints: every parameterized rule or named
test executed in this historical task reports `FAILED` with a `200` or safe
generic `500`, never an uncaught exception or collection error. Task 8 owns the
later RED/GREEN cycle for the corrected real-float regression.

- [ ] **Step 5: Implement and pass the exact request constraints**

Tighten only the Pydantic fields/validators needed to match the approved
boundaries:

```python
min_protein_g: Annotated[FiniteFloat, Field(ge=0, strict=True)]
max_prep_minutes: Annotated[StrictInt, Field(ge=0)]
limit: Annotated[StrictInt, Field(ge=1, le=50)]
model_config = ConfigDict(extra="forbid")
```

Add the ingredient-list validator only now:

```python
@field_validator("pantry_items", "excluded_ingredients")
@classmethod
def reject_blank_ingredients(cls, values: list[str]) -> list[str]:
    if any(not value.strip() for value in values):
        raise ValueError("ingredient values must not be blank")
    return values
```

Run the focused validation group:

```powershell
uv run pytest tests/test_api.py `
  -k "rejects_invalid or rejects_wrong or rejects_blank or rejects_unknown" -v
```

Expected: the original request-constraint tests PASS with FastAPI's field-level
`422` responses. Do not add a custom exception hierarchy or validation handler
in this historical task. Task 8 installs the narrow app-layer
`RequestValidationError` handler after first adding and observing the corrected
real-float regression failures at the current `04ae8ab` baseline.

- [ ] **Step 6: Run API, full-suite, and static checks**

Run:

```powershell
uv run pytest tests/test_api.py -v
uv run pytest tests -v
uv run ruff format --check src tests
uv run ruff check src tests
```

Expected: all tests and checks PASS.

- [ ] **Step 7: Review and commit the boundary**

Run `superpowers:requesting-code-review` with emphasis on the exact path,
required/unknown fields, finite-number validation, no-result semantics,
response reconstruction, thin routing, and generic unexpected errors. After
the review is clean, use the authorized task commit:

```powershell
git add src/pantrypilot/app.py src/pantrypilot/models.py tests/test_api.py
git commit -m "feat: expose explainable meal ranking API"
```

---

### Task 6: Learning Document, README, Final Verification, and Final Review

**Files:**

- Modify: `docs/superpowers/plans/2026-07-25-explainable-meal-ranking.md`
- Create: `docs/learning/001-explainable-meal-ranking.md`
- Modify: `README.md`

**Interfaces:**

- Consumes: the implemented request-to-response flow, exact commands, and
  final file responsibilities.
- Produces: the required learning material, mock-interview guidance, exercises,
  merge-readiness concepts, and accurate repository quick start.

- [ ] **Step 1: Write the learning document with every required section**

Create the document with these exact top-level sections and content:

```markdown
# Feature 001: Explainable meal ranking

## What was built
Describe the versioned endpoint, validated in-memory catalog, pure deterministic
ranking pipeline, structured score evidence, and fixed explanations.

## Why the deterministic baseline comes first
Explain how a reproducible baseline creates test fixtures, failure cases,
product vocabulary, and a comparison point for later entity resolution,
learned ranking, and grounded LLM orchestration.

## Complete request-to-response flow
Trace validation → normalization → exclusion/time filters → ingredient
partition → full-precision score calculation → four-decimal contributions →
reconstructable final score → fixed explanation → exposed-score/ID sorting →
limit → response validation.

## File responsibilities
Explain each file in `src/pantrypilot`, each test file, dependency metadata,
and the immutable catalog without inventing future layers.

## Hard filters and soft constraints
Explain why exclusions and maximum prep time determine eligibility while
minimum protein changes score only, including exclusion precedence and the
inclusive time boundary.

## Normalization and exact matching
Explain trimming, lowercasing, stable exact deduplication, preserved internal
whitespace/punctuation/plurality, and why synonyms are deferred.

## Scoring and rounding
Show all three formulas, weights, zero-target branches, full-precision
calculation, four-decimal values/contributions, and exact final-score
reconstruction with a worked Spinach Omelet example.

## Deterministic ordering
Explain descending exposed score, ascending recipe ID tie-break, post-sort
limit, and repeated-request reproducibility.

## Test strategy
Map direct pure-function tests to HTTP contract tests and explain why small
local recipe fixtures isolate ranking behavior from the application catalog.

## Run and verify
List `uv sync --locked --python 3.12`, the focused pytest commands,
`uv run pytest`, `uv run ruff format --check .`, `uv run ruff check .`,
and `uv run uvicorn pantrypilot.app:app --app-dir src`.

## Mock-interview questions
Include concise answer guidance for: hard versus soft constraints; why the
domain does not import FastAPI; exact matching as a measurable baseline;
reconstructable rounding; deterministic tie-breaking; catalog startup
validation; why no repository abstraction exists; and what evidence would
justify entity resolution or learned ranking.

## Exercises
1. Add a local ranking test that proves internal whitespace is preserved.
2. Calculate a three-recipe ranking by hand, then add a fixture that asserts
   the same ordering and score breakdown.

## Concepts to understand before merging
List Pydantic request/response validation, pure functions, hard filters,
normalization, full-precision versus displayed values, deterministic sorting,
TDD red-green-refactor, FastAPI `422`/`500` behavior, and uv lockfiles.
```

Replace each imperative description with concise project-specific prose and
the actual formulas/commands. Do not leave the instructional text in the final
document.

- [ ] **Step 2: Update the README without duplicating the learning document**

Change “foundation stage” to “Feature 001 implemented,” add the endpoint path,
and add a compact quick start:

```powershell
uv sync --locked --python 3.12
uv run pytest
uv run uvicorn pantrypilot.app:app --app-dir src
```

Add a relative link to
`docs/learning/001-explainable-meal-ranking.md`. Keep architectural and scoring
detail in the learning document.

- [ ] **Step 3: Verify documentation completeness**

Run:

```powershell
rg -n "What was built|deterministic baseline|request-to-response|Hard filters|Normalization|Scoring|Deterministic ordering|Test strategy|Mock-interview|Exercises|before merging" docs/learning/001-explainable-meal-ranking.md
rg -n "POST /v1/meal-rankings|uv run pytest|001-explainable-meal-ranking" README.md
rg -n "T[B]D|T[O]DO|implement la[t]er|fill i[n]|simila[r] to" docs/learning README.md
```

Expected: every required learning topic and README command/link is found; the
placeholder scan has no matches.

- [ ] **Step 4: Run verification-before-completion from a clean invocation**

Invoke `superpowers:verification-before-completion`, then run:

```powershell
uv --version
uv python find 3.12
uv lock --check
uv sync --locked --python 3.12
uv run python --version
uv run pytest tests/test_catalog.py -v
uv run pytest tests/test_normalization.py -v
uv run pytest tests/test_ranking.py -v
uv run pytest tests/test_api.py -v
uv run pytest -v
uv run ruff format --check .
uv run ruff check .
git diff --check
git status --short
```

Expected:

- uv is available.
- `uv run python --version` reports Python 3.12.x.
- the lock is current and sync succeeds without changing it.
- every focused group and the full suite pass with zero failures.
- Ruff formatting and lint checks pass.
- `git diff --check` reports no whitespace errors.
- `git status --short` lists only the intended Feature 001 files before their
  authorized commits, or is empty after them.

- [ ] **Step 5: Audit scope against the approved non-goals**

Run:

```powershell
uv tree
rg -n "sqlalchemy|database|repository|embedding|openai|anthropic|fuzzy|synonym|auth|docker" src tests pyproject.toml
git diff --stat ba0cff53f1ad1bfb471178bd95ad777fcbf9c62c
```

Expected: the dependency tree contains only the direct dependencies required by
FastAPI, its test client, uvicorn, Pytest, and Ruff plus their transitives; the
source scan finds no introduced non-goal technology; the diff remains limited
to Feature 001 code, tests, dependency metadata, README, plan, and learning
documentation.

- [ ] **Step 6: Review and commit the documentation boundary**

Run `superpowers:requesting-code-review` on the learning document and README
for correctness, explainability, command accuracy, interview usefulness, and
agreement with the implemented code. After the review is clean, use the
authorized task commit:

```powershell
git add README.md docs/learning/001-explainable-meal-ranking.md docs/superpowers/plans/2026-07-25-explainable-meal-ranking.md
git commit -m "docs: explain deterministic meal ranking"
```

- [ ] **Step 7: Request final independent branch review**

Request an independent read-only review of the approved design, all branch
changes, tests, and learning documentation. Require findings in severity order
with file and line references and coverage of correctness, security, scope,
test quality, understandable design, and specification consistency. Fix
confirmed findings using focused failing tests and separately authorized
conventional commits, then rerun Step 4. Do not push, open a pull request, or
merge into `main` without separate user direction.

---

### Task 7: Record the Approved Validation-Transport Clarification

**Files:**

- Modify:
  `docs/superpowers/specs/2026-07-25-explainable-meal-ranking-design.md`
- Modify:
  `docs/superpowers/plans/2026-07-25-explainable-meal-ranking.md`

**Interfaces:**

- Preserves Pydantic request validation as the source of validation errors.
- Authorizes one narrow FastAPI `RequestValidationError` handler to render
  non-finite values safely in the standard `{"detail": [...]}` response shape.
- Does not authorize a custom exception hierarchy, request-input mutation, or
  handling outside the HTTP transport boundary.
- Tasks 8–10 are the project-owner-authorized follow-up implementation,
  coverage, and documentation scope for this clarification.

- [ ] **Step 1: Correct Task 5 and the approved design**

Replace the Task 5 string cases with real `float("inf")`, `float("-inf")`,
and `float("nan")` JSON request bodies. Require the tests to inspect
Pydantic's `finite_number` type, `["body", "min_protein_g"]` location,
finite-number message, truthful rendered input, and useful metadata. Add a
separate real `null` assertion so it remains distinguishable.

Record in the design that Python HTTP clients can emit non-standard
non-finite numeric tokens, Pydantic rejects them correctly, and only the
rendered validation payload needs sanitization.

- [ ] **Step 2: Self-review and commit the clarification**

Check the amendment for design coverage, missing requirements, vague steps,
interface/type inconsistencies, scope creep, and contradictions with Tasks
1–6. Then run:

```powershell
uv run ruff format --check `
  docs/superpowers/specs/2026-07-25-explainable-meal-ranking-design.md `
  docs/superpowers/plans/2026-07-25-explainable-meal-ranking.md
uv run ruff check `
  docs/superpowers/specs/2026-07-25-explainable-meal-ranking-design.md `
  docs/superpowers/plans/2026-07-25-explainable-meal-ranking.md
git diff --check
```

After independent review is clean:

```powershell
git add `
  docs/superpowers/specs/2026-07-25-explainable-meal-ranking-design.md `
  docs/superpowers/plans/2026-07-25-explainable-meal-ranking.md
git commit -m "docs: clarify validation error transport handling"
```

---

### Task 8: Preserve Non-Finite Pydantic Validation Details

**Files:**

- Modify: `tests/test_api.py`
- Modify: `src/pantrypilot/models.py`
- Modify: `src/pantrypilot/app.py`

**Interfaces:**

- `RankingRequest` receives the original parsed input and remains responsible
  only for schema validation.
- The FastAPI application handles `RequestValidationError` and returns status
  `422` with `{"detail": [...]}`.
- Only non-finite floats in the rendered error payload become the strings
  `"Infinity"`, `"-Infinity"`, or `"NaN"`.

- [ ] **Step 1: Write focused regression tests before production changes**

Strengthen `test_meal_rankings_preserves_non_finite_validation_details` to
send real non-finite floats through a raw JSON body and assert:

- status `422`;
- `loc == ["body", "min_protein_g"]`;
- `type == "finite_number"`;
- `msg == "Input should be a finite number"`;
- input is the correct canonical string rather than `null`; and
- useful Pydantic metadata remains present.

Add:

- `test_meal_rankings_keeps_null_distinct_from_non_finite_values`, asserting
  actual `null` retains Pydantic's `float_type`, valid-number message, and
  `input is None`; and
- `test_unknown_field_with_nested_non_finite_values_returns_serializable_422`,
  asserting `extra_forbidden`, location, message, and a nested input containing
  canonical `"Infinity"`, `"-Infinity"`, and `"NaN"` values.

Run:

```powershell
uv run pytest tests/test_api.py `
  -k "preserves_non_finite or keeps_null_distinct or nested_non_finite" -v
```

Expected RED at `04ae8ab`: the recursive request-model sanitizer changes
non-finite input to `null`, so the tests observe inaccurate types and inputs.

- [ ] **Step 2: Implement the smallest transport-boundary fix**

Remove `replace_non_finite_values` and its imports from `RankingRequest`.

In `app.py`, register a `RequestValidationError` handler. Encode
`exc.errors()` with FastAPI's existing `jsonable_encoder`, recursively replace
only non-finite float values in that rendered copy with the three canonical
strings, and return `JSONResponse(status_code=422, content={"detail": ...})`.
Do not mutate model input, catch errors inside the route, introduce a custom
exception class, or change ranking behavior.

- [ ] **Step 3: Prove GREEN and broaden the API check**

Run:

```powershell
uv run pytest tests/test_api.py `
  -k "preserves_non_finite or keeps_null_distinct or nested_non_finite" -v
uv run pytest tests/test_api.py -v
git diff --check
```

Expected: every focused regression and all API tests PASS.

- [ ] **Step 4: Review and commit the fix**

Request independent specification and quality review of the task diff, with
special attention to accurate Pydantic detail preservation, JSON safety,
input immutability, standard response compatibility, and transport-only scope.
After review is clean:

```powershell
git add src/pantrypilot/app.py src/pantrypilot/models.py tests/test_api.py
git commit -m "fix: preserve non-finite validation details"
```

---

### Task 9: Strengthen API and Catalog Contracts

**Files:**

- Modify: `tests/test_api.py`
- Modify: `tests/test_catalog.py`
- Modify: `src/pantrypilot/ranking.py`

**Interfaces:**

- Existing request and catalog schemas do not change.
- The API's returned count and deterministic ordering receive broader
  committed coverage.
- `calculate_score` and `render_explanation` document their existing
  eligible-recipe precondition.

- [ ] **Step 1: Strengthen structured validation assertions**

Update blank-ingredient and unknown-field tests to inspect `loc`, `type`,
`msg`, and `input` where relevant rather than merely searching response text.
Remove the redundant local `safe_client` rebinding from the generic `500`
test.

- [ ] **Step 2: Add multi-result API coverage**

Add a request with no exclusions, a 45-minute maximum, and limit `50`. Assert
the complete ordered ID list:

```python
[
    "spinach-omelet",
    "peanut-noodles",
    "black-bean-tacos",
    "lentil-soup",
]
```

Also assert `returned_count > 1` and
`returned_count == len(response_body["results"])`.

- [ ] **Step 3: Add strict catalog integer coverage**

Extend the invalid recipe cases with `prep_minutes` values `True`, `10.5`,
and `"10"`. These are contract-regression tests for the existing `StrictInt`
schema and should pass without production validation changes.

- [ ] **Step 4: Document scoring/explanation preconditions**

Add concise docstrings stating that `calculate_score` and
`render_explanation` require an eligible recipe whose preparation time is
within `max_prep_minutes`. Do not add defensive domain checks or alter
behavior.

- [ ] **Step 5: Verify, review, and commit the coverage boundary**

Run:

```powershell
uv run pytest tests/test_api.py -v
uv run pytest tests/test_catalog.py -v
uv run pytest tests/test_ranking.py -v
git diff --check
```

After independent specification and quality review is clean:

```powershell
git add src/pantrypilot/ranking.py tests/test_api.py tests/test_catalog.py
git commit -m "test: strengthen ranking contracts"
```

---

### Task 10: Explain the Transport and Reverify the Branch

**Files:**

- Modify: `docs/learning/001-explainable-meal-ranking.md`

**Interfaces:**

- Documents the implemented transport behavior and existing rounding
  semantics without adding product behavior.

- [ ] **Step 1: Update the learning guide**

Explain:

- Python clients may send non-finite float tokens that Pydantic rejects but
  Starlette's strict JSON validation-response serialization cannot render;
- serialization safety belongs at the HTTP boundary because the request model
  must validate the original input and the domain has no transport concerns;
- the handler preserves Pydantic type, location, message, input, and useful
  metadata while canonicalizing only non-finite rendered values; and
- displayed component `value × weight` can differ from displayed
  `contribution` by one four-decimal unit because contributions use the
  full-precision value, while `final_score` remains exactly reconstructable
  from returned contributions.

- [ ] **Step 2: Run complete verification**

Invoke `superpowers:verification-before-completion`, then run:

```powershell
uv --version
uv python find 3.12
uv lock --check
uv sync --locked --python 3.12
uv run python --version
uv run pytest tests/test_catalog.py -v
uv run pytest tests/test_normalization.py -v
uv run pytest tests/test_ranking.py -v
uv run pytest tests/test_api.py -v
uv run pytest -v
uv run ruff format .
uv run ruff format --check .
uv run ruff check .
git diff --check
```

Expected: Python 3.12, a current lockfile, all tests passing, no Ruff or
whitespace errors, and no generated files.

- [ ] **Step 3: Review and commit the learning update**

Request independent review for technical accuracy and consistency with the
design and implementation. After review is clean:

```powershell
git add docs/learning/001-explainable-meal-ranking.md
git commit -m "docs: explain validation error transport"
```

- [ ] **Step 4: Request fresh whole-branch reviews**

Request separate read-only specification-compliance and code-quality reviews
of the full branch diff. Address confirmed load-bearing findings with focused
tests and separately reviewed conventional commits. Do not push, open a pull
request, merge, or delete the worktree.

---

## Planned Commit Boundaries

| Boundary | Deliverable | Conventional commit |
|---|---|---|
| 0 | Approved implementation plan | `docs: plan explainable meal ranking` |
| 1 | Python metadata, tested normalization, validated models, immutable catalog | `feat: add validated recipe catalog` |
| 2 | Exact normalization/matching and hard eligibility rules | `feat: add ingredient matching and eligibility rules` |
| 3 | Full-precision components, reconstructable score, fixed explanation | `feat: add reconstructable recipe scoring` |
| 4 | Pure end-to-end ranking, deterministic ordering, post-sort limit | `feat: add deterministic meal ranking pipeline` |
| 5 | Versioned FastAPI route and complete HTTP validation/error contract | `feat: expose explainable meal ranking API` |
| 6 | Learning guide, mock-interview guidance, exercises, README quick start | `docs: explain deterministic meal ranking` |
| 7 | Approved non-finite validation transport clarification | `docs: clarify validation error transport handling` |
| 8 | Accurate, JSON-safe non-finite Pydantic validation details | `fix: preserve non-finite validation details` |
| 9 | Structured validation, multi-result ordering, and strict catalog coverage | `test: strengthen ranking contracts` |
| 10 | Transport/rounding learning update and final verification | `docs: explain validation error transport` |

Review findings that require code changes stay inside the uncommitted task
diff, receive focused tests and scoped re-review, and are included in the
single authorized task-boundary commit. The authorization is limited to the
plan and task boundaries listed above.

## Testing-Requirement Coverage Map

| Approved requirement | Explicit planned tests |
|---|---|
| Lowercase, trim, stable duplicate removal | `test_normalize_ingredients_trims_lowercases_and_stably_deduplicates`; catalog normalization test |
| Empty pantry | matching unit test and `test_rank_recipes_with_empty_pantry_returns_zero_coverage_results` |
| Exact matching; no substring/plural/synonym | `test_matching_is_exact_not_substring_plural_or_synonym_based` |
| Excluded ingredient filter | direct eligibility test and integrated pipeline test |
| Exclusion precedence | `test_exclusion_takes_precedence_over_pantry_presence` and normalized integrated filter test |
| Inclusive maximum preparation time | boundary eligibility tests |
| Partial and complete coverage | parameterized pantry-coverage test |
| Protein fit below, at, above | parameterized protein-fit test |
| Zero protein target | dedicated zero-target protein-fit test |
| Time fit at zero, between, maximum | parameterized time-fit test |
| Zero-minute maximum | dedicated zero-maximum time-fit test |
| Four-decimal contributions/final score | full-precision `2/9` test and exact reconstruction test |
| Deterministic ID tie-break | `test_equal_exposed_scores_tie_break_by_recipe_id` |
| Limit after sorting | `test_limit_is_applied_after_sorting` |
| Stable matched/missing order | matching and integrated result tests |
| Exact deterministic explanation | parameterized exact-template test |
| Valid known-catalog request | exact JSON API test |
| Valid request with no eligible recipe | exact empty JSON API test |
| Missing required fields | parameterized API test for all five fields |
| Negative constraints | parameterized API boundary test |
| Numeric schema types | parameterized API test for strings, fractional integers, and booleans |
| Non-finite number | real-float API tests for NaN and both infinities with exact `loc`, `type`, `msg`, and canonical rendered `input` |
| Non-finite versus null | API test preserving Pydantic's distinct `float_type` and `input: null` |
| Nested non-finite unknown input | API `extra_forbidden` test with a serializable, truthfully rendered nested input |
| Blank ingredients | parameterized API test for pantry and exclusions with structured detail assertions |
| Limits outside 1–50 | API tests for 0 and 51 |
| Unknown request fields | API extra-field tests with structured detail assertions |
| Malformed JSON | API malformed-body test |
| Generic unexpected 500 | monkeypatched API test with secret non-disclosure assertion |
| Invalid catalog stops startup/import | loader validation tests plus module-level `CATALOG = load_catalog(...)` |
| Strict catalog preparation time | loader tests reject boolean, fractional-float, and numeric-string values |
| Repeated identical request behavior | direct ranking equality test and repeated-request HTTP equality test |
| Complete multi-result HTTP order/count | known-catalog API test asserts all four ordered IDs and count consistency |
| Final scores remain in `[0, 1]` | reconstructability test assertion |
| Ranking works without an HTTP server | all `test_ranking.py` calls target pure functions directly |

## Self-Review Checklist

- [x] Every architecture, API, schema, validation, normalization, eligibility,
  scoring, rounding, ordering, explanation, error, testing, documentation, and
  acceptance requirement in the approved design maps to a task and test.
- [x] The plan contains no unfinished markers, deferred implementation
  language, unspecified error handling, or unnamed tests.
- [x] All cross-task interfaces use the exact names and types declared under
  **Exact Interfaces**.
- [x] `min_protein_g` appears only as validation and a soft score target, never
  as an eligibility condition.
- [x] Contributions use full-precision component values; sorting uses exposed
  final scores; limiting follows sorting.
- [x] Domain modules do not import FastAPI and the route contains no ranking
  rule.
- [x] The plan introduces no approved non-goal, Mypy configuration, GitHub
  Actions workflow, custom cache, repository, service layer, exception
  hierarchy, or extra dependency. Its one validation handler is confined to
  the explicitly approved HTTP serialization problem.
- [x] Every production task has focused red/green commands, a broader test run,
  independent review, and a planned conventional-commit boundary.
- [x] Dedicated normalization tests are created and observed failing in Task 1
  before `normalize_ingredients` is implemented; Task 2 adds no after-the-fact
  normalization tests.
- [x] Task 3 declares `models.py` as the owner of score response shapes, and
  ordinary scoring, full-precision contribution, reconstruction, and score
  bound tests all fail before `calculate_score` is implemented.
- [x] Zero protein-target and zero time-maximum branches each follow their own
  later red/green cycle rather than being implemented ahead of a failing test.
- [x] Task 4 includes `models.py` in both its file list and commit boundary so
  `RankingRequest` and `RankedRecipe` remain owned by the model layer.
- [x] Task 4 writes and observes failures for pipeline normalization, hard
  filters, empty pantry behavior, and repeatability before `rank_recipes`;
  ordering and limiting retain separate later red/green cycles.
- [x] Task 5 includes `models.py`, puts route/framework-default acceptance
  tests before `app.py`, and reserves the later validation RED/GREEN cycle for
  constraints that the plain Task 4 request model does not already enforce.
- [x] Task 5 uses a non-raising client only for RED validation cases that would
  otherwise escape as domain exceptions, preserving explicit test failures.
- [x] Task 5 now sends real non-finite numeric values rather than numeric
  strings and inspects structured Pydantic details.
- [x] Task 6 includes the implementation plan in scope so Ruff can format its
  Python fenced blocks and the exact repository-wide format check can pass.
- [x] Tasks 7–10 remove the inaccurate request-model sanitizer, preserve the
  original validation input, constrain sanitization to rendered HTTP error
  details, and cover null distinction plus nested unknown inputs.
- [x] The post-review work adds only requested regression coverage,
  precondition docstrings, and learning material; it does not trim catalog
  text or impose speculative list-length limits.
- [x] Every missing-module or missing-symbol red step is converted from a
  collection error into an explicit test failure before production code.
- [x] The final verification is evidence-based and runs on Python 3.12 through
  uv before any completion, push, or pull-request claim.

## Approved Decisions and Remaining Ambiguity

- No conflict was found among `AGENTS.md`, `CLAUDE.md`, the vision, roadmap,
  approved design, and the requested planning workflow.
- uv and uv-managed Python 3.12 are installed and authorized for this
  repository; Task 1 verifies them before dependency resolution.
- The four-record representative catalog is approved. Domain tests still use
  local fixtures so catalog choices do not define scoring behavior.
- Python's built-in `round` is approved for every four-decimal rounding step.
- The Task 3 correction is approved: score models live in `models.py`, and
  precision/reconstruction tests are written and observed failing before
  scoring production behavior.
- The Task 4 correction is approved: `models.py` is included in the task file
  list and commit boundary for `RankingRequest` and `RankedRecipe`.
- The additional Task 4 TDD correction is approved: core orchestration and
  repeatability tests move before pipeline production code, while sorting and
  limiting remain later focused failing tests.
- The Task 5 correction is approved: `models.py` is explicit task scope,
  framework-backed acceptance tests precede route production, and genuinely
  missing validation constraints retain their own later failing tests.
- The Task 6 correction is approved: the implementation plan is included in
  the documentation boundary for mechanical Ruff formatting of Python fences.
- The post-review clarification is approved: the previous prohibition on a
  custom validation handler is superseded only for safely serializing
  non-finite values in FastAPI `RequestValidationError` details. The request
  model must receive the original input, and no custom exception hierarchy is
  authorized.
- Trimming recipe IDs or names is not approved; the existing non-blank
  validation remains unchanged.
- Arbitrary maximum lengths for pantry and exclusion lists are not approved.
- `calories` is specified as a non-negative number rather than specifically an
  integer or float. The model preserves either JSON numeric form with
  `int | float`; scoring does not depend on calories.
- Omitting Mypy and GitHub Actions for Feature 001 is approved.
