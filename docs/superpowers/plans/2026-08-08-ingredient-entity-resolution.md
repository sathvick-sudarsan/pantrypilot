# Measured Ingredient Entity Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add stable canonical ingredient identities, deterministic explicit
alias resolution, shared pantry/exclusion matching, structured resolution
evidence, and a measured comparison with Feature 001's exact-name baseline.

**Architecture:** A validated immutable in-code registry maps normalized
canonical names and explicit aliases to stable IDs. The catalog stores those
IDs, while the pure ranking pipeline resolves request terms once, compares ID
sets, and maps IDs back to canonical names for the unchanged result objects.
A versioned JSON fixture and pure evaluator compare exact-name and alias-aware
resolution with inspectable precision/recall errors.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, Pytest, Ruff, uv, and Python
standard-library dataclasses, immutable mapping proxies, JSON, argparse, and
path handling. No dependency is added.

## Global Constraints

- The approved design at
  `docs/superpowers/specs/2026-08-08-ingredient-entity-resolution-design.md`
  is the behavior source of truth.
- Work only in the existing linked worktree on
  `feat/ingredient-entity-resolution`; do not create or switch worktrees.
- Never work on or modify `main`.
- Use one writing agent in this worktree. Implementation subagents run one at
  a time; independent reviewers are read-only.
- Do not begin these tasks until the project owner explicitly approves this
  plan and authorizes the implementation phase and planned local commits.
- Follow strict red-green-refactor TDD for every production behavior: add one
  focused test or one parameterized rule, run it, inspect the expected failure,
  add minimum production code, rerun the focused test, run relevant broader
  tests, and refactor only while green.
- A missing module or symbol may initially cause collection failure, but that
  is not an accepted RED. Each affected step below contains the exact temporary
  test-side guard and explicit failure assertion required for its RED run.
  Remove that guard and restore the stated ordinary top-level production import
  as soon as the GREEN implementation exists. Do not carry guards forward to a
  task commit.
- Mechanical fixture/schema migrations may make several existing assertions
  fail together. Run the changed focused file before production changes and
  confirm every failure is caused by the approved canonical-ID contract, then
  restore the entire relevant test file to green before proceeding.
- Keep `pantrypilot.normalization`, `pantrypilot.ingredients`,
  `pantrypilot.models`, `pantrypilot.catalog`,
  `pantrypilot.ranking`, and `pantrypilot.evaluation` free of FastAPI imports.
- Pass the immutable ingredient registry and recipe catalog explicitly to pure
  domain functions. Do not add repositories, services, factories, interfaces,
  containers, or dependency-injection frameworks.
- Resolution is normalized exact lookup of canonical names and explicit
  aliases only. Do not add fuzzy matching, stemming, lemmatization, edit
  distance, embeddings, learned models, LLMs, persistence, retrieval,
  quantities, units, or any other approved non-goal.
- Preserve the request schema and all existing ranked-result fields.
  `ingredient_resolution` is the only successful-response addition.
- Reject any unresolved exclusion with the approved fail-closed `422`; unknown
  pantry terms remain unresolved and do not match.
- Keep ranking weights exactly `0.70`, `0.20`, and `0.10`; preserve existing
  full-precision calculation, four-decimal contribution rounding,
  reconstructable final scores, hard time filtering, fixed explanations,
  exposed-score/ID ordering, and post-sort limiting.
- Preserve recipe order when returning required, matched, and missing canonical
  names. Resolve duplicate request terms individually for evidence but dedupe
  canonical IDs for matching.
- The approved evaluation fixture contains exactly 14 canonical cases, seven
  alias cases, and seven unresolved confusable cases. Both systems evaluate the
  same parsed cases.
- Feature 002 must report TP/FP/FN/TN, precision, recall, and inspectable FP/FN
  cases; it must beat baseline recall and have zero false positives.
- For every Task 1-7 boundary, the controlling agent records `TASK_BASE` as the
  current `HEAD` before dispatching or beginning the task by running
  `git rev-parse HEAD` and writing the literal returned SHA into the
  subagent-driven-development task ledger. The implementer then follows strict
  RED/GREEN/refactor, runs the task's focused and broader verification,
  inspects the exact intended diff, stages only the named files, and makes the
  planned small conventional task commit.
- Only after that task commit exists, record `TASK_HEAD` and run independent
  specification-compliance and code-quality review against the immutable
  `TASK_BASE..TASK_HEAD` range. A task is not complete merely because its first
  commit exists.
- If either reviewer reports a Critical or Important finding, record
  `FIX_BASE` at the current `HEAD`, make the minimum correction using focused
  RED/GREEN/refactor when behavior changes, rerun scoped verification, inspect
  and stage only the correction diff, and make a focused task-specific review-
  fix commit. Run scoped re-review against `FIX_BASE..HEAD`. Repeat this
  fix-commit/re-review loop until no Critical or Important findings remain;
  only then mark the task complete and continue.
- Preserve the initial task commit and every review-fix commit. Do not amend,
  squash, reset, or otherwise rewrite them. Do not push, open a pull request,
  merge, rebase, force-push, delete the worktree, or remove the branch.

---

## File Structure and Responsibilities

```text
README.md                                      # implemented status and links
docs/
├── learning/
│   └── 002-ingredient-entity-resolution.md    # learning and interview guide
├── product/
│   └── vision.md                              # approved sequence correction
├── roadmap.md                                 # approved phase ordering
└── superpowers/
    ├── plans/
    │   └── 2026-08-08-ingredient-entity-resolution.md
    └── specs/
        └── 2026-08-08-ingredient-entity-resolution-design.md
evaluations/
└── ingredient-resolution-v1.json              # 28 labeled cases
src/pantrypilot/
├── app.py                                      # HTTP adapter and 422 mapping
├── catalog.py                                  # ID-based validated recipes
├── evaluation.py                               # fixture, metrics, comparison CLI
├── ingredients.py                              # registry and resolver
├── models.py                                   # request, recipe, ranking response
├── normalization.py                            # text-only normalization
└── ranking.py                                  # ID-based pure ranking pipeline
tests/
├── test_api.py                                 # external contract
├── test_catalog.py                             # catalog/registry integrity
├── test_evaluation.py                          # fixture and metrics
├── test_ingredients.py                         # registry and resolver
├── test_normalization.py                       # text normalization
└── test_ranking.py                             # domain ranking behavior
```

`pyproject.toml` and `uv.lock` remain unchanged. If either changes during
implementation, stop and identify the unapproved dependency or metadata change
before proceeding.

## Final Interfaces

The implementation tasks must converge on these names and signatures:

```python
# pantrypilot.normalization
def normalize_ingredient(value: str) -> str: ...


def normalize_ingredients(values: Iterable[str]) -> tuple[str, ...]: ...


# pantrypilot.ingredients
IngredientMatchType = Literal["canonical", "alias", "unresolved"]


class CanonicalIngredient(BaseModel):
    id: str
    canonical_name: str
    aliases: tuple[str, ...]


class IngredientResolution(BaseModel):
    input: str
    normalized: str
    ingredient_id: str | None
    canonical_name: str | None
    match_type: IngredientMatchType


class IngredientResolutionEvidence(BaseModel):
    pantry_items: tuple[IngredientResolution, ...]
    excluded_ingredients: tuple[IngredientResolution, ...]


@dataclass(frozen=True)
class IngredientRegistry:
    by_id: Mapping[str, CanonicalIngredient]
    by_term: Mapping[str, str]


def load_ingredient_registry(
    records: Iterable[Mapping[str, object]],
) -> IngredientRegistry: ...


def resolve_ingredient(
    value: str,
    registry: IngredientRegistry,
) -> IngredientResolution: ...


def resolve_ingredients(
    values: Iterable[str],
    registry: IngredientRegistry,
) -> tuple[IngredientResolution, ...]: ...


INGREDIENT_REGISTRY: IngredientRegistry


# pantrypilot.catalog
def load_catalog(
    records: Iterable[Mapping[str, object]],
    ingredient_registry: IngredientRegistry,
) -> tuple[Recipe, ...]: ...


CATALOG: tuple[Recipe, ...]


# pantrypilot.ranking
class UnresolvedExcludedIngredientsError(ValueError):
    ingredient_resolution: IngredientResolutionEvidence


def is_eligible(
    recipe: Recipe,
    excluded_ingredient_ids: Collection[str],
    max_prep_minutes: int,
) -> bool: ...


def match_ingredients(
    recipe: Recipe,
    pantry_ingredient_ids: Collection[str],
    ingredient_registry: IngredientRegistry,
) -> tuple[tuple[str, ...], tuple[str, ...]]: ...


def rank_recipes(
    request: RankingRequest,
    recipes: Sequence[Recipe],
    ingredient_registry: IngredientRegistry,
) -> RankingResponse: ...


# pantrypilot.evaluation
def load_evaluation_fixture(
    path: Path,
    ingredient_registry: IngredientRegistry,
) -> EvaluationFixture: ...


def resolve_exact_name(
    value: str,
    ingredient_registry: IngredientRegistry,
) -> str | None: ...


def evaluate_resolver(
    cases: Sequence[EvaluationCase],
    resolver: Callable[[str], str | None],
) -> ResolutionMetrics: ...


def compare_resolvers(
    fixture: EvaluationFixture,
    ingredient_registry: IngredientRegistry,
) -> ResolverComparison: ...


def main(argv: Sequence[str] | None = None) -> int: ...
```

All new Pydantic models use `ConfigDict(extra="forbid", frozen=True)`.
`Recipe.required_ingredient_ids` is an immutable, non-empty tuple. The final
`RankedRecipe` is an explicit response model, not a `Recipe` subclass.

---

## Approval and Documentation Commit Gate

The design is approved, but neither design nor plan is committed yet. After
the owner approves this plan and explicitly authorizes implementation commits,
preserve the review artifacts in two focused commits before Task 1:

```powershell
git add docs/superpowers/specs/2026-08-08-ingredient-entity-resolution-design.md
git commit -m "docs: design measured ingredient resolution"

git add docs/superpowers/plans/2026-08-08-ingredient-entity-resolution.md
git commit -m "docs: plan measured ingredient resolution"
```

Verify after each commit that the other artifact remains the only expected
uncommitted file. Do not execute these commands during plan review.

---

### Task 1: Single-Term Normalization and Validated Canonical Registry

**Files:**

- Modify: `src/pantrypilot/normalization.py`
- Create: `src/pantrypilot/ingredients.py`
- Modify: `tests/test_normalization.py`
- Create: `tests/test_ingredients.py`

**Interfaces:**

- Consumes: existing Feature 001 trim/lower normalization rules and Pydantic.
- Produces: `normalize_ingredient`, `CanonicalIngredient`,
  `IngredientRegistry`, and `load_ingredient_registry`.
- Does not yet create the application registry or resolution functions; Task 2
  owns those behaviors.

- [ ] **Step 1: Add the focused single-term normalization test**

Add this exact temporary missing-symbol guard below the existing `import
pytest`, then add the test. The guard converts only the expected absent-symbol
import into an executable pytest failure and re-raises any unrelated import
error:

```python
try:
    from pantrypilot.normalization import normalize_ingredient
except ImportError as exc:
    if "cannot import name 'normalize_ingredient'" not in str(exc):
        raise
    normalize_ingredient = None


def test_normalize_ingredient_trims_and_lowercases_without_other_changes():
    if normalize_ingredient is None:
        pytest.fail("expected production behavior is not implemented")

    assert normalize_ingredient(" Olive  Oil ") == "olive  oil"
```

- [ ] **Step 2: Observe the expected normalization RED**

Run:

```powershell
uv run pytest tests/test_normalization.py::test_normalize_ingredient_trims_and_lowercases_without_other_changes -v
```

Expected: one explicit `FAILED` because `normalize_ingredient` is absent, not
a collection error.

- [ ] **Step 3: Implement the single-value primitive and reuse it**

Refactor `src/pantrypilot/normalization.py` to this behavior:

```python
from collections.abc import Iterable


def normalize_ingredient(value: str) -> str:
    ingredient = value.strip().lower()
    if not ingredient:
        raise ValueError("ingredient values must not be blank")
    return ingredient


def normalize_ingredients(values: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        ingredient = normalize_ingredient(value)
        if ingredient not in seen:
            seen.add(ingredient)
            normalized.append(ingredient)
    return tuple(normalized)
```

Immediately after the production symbol exists, remove the temporary
`try`/`except` and in-test `None` check and restore this ordinary top-level
import before the GREEN run:

```python
from pantrypilot.normalization import normalize_ingredient
```

- [ ] **Step 4: Prove normalization GREEN and preserve Feature 001 behavior**

Run:

```powershell
uv run pytest tests/test_normalization.py -v
```

Expected: the new test and both existing normalization tests pass. The existing
test continues to prove stable exact deduplication and preserved internal
whitespace.

- [ ] **Step 5: Add the first registry construction test**

Create `tests/test_ingredients.py` with this exact missing-module guard for the
RED run. It converts only the expected absent module into an executable pytest
failure and re-raises an unexpected missing dependency:

```python
import pytest
from pydantic import ValidationError

try:
    from pantrypilot.ingredients import (
        CanonicalIngredient,
        load_ingredient_registry,
    )
except ModuleNotFoundError as exc:
    if exc.name != "pantrypilot.ingredients":
        raise
    CanonicalIngredient = None
    load_ingredient_registry = None


VALID_INGREDIENTS = (
    {
        "id": "black-beans",
        "canonical_name": " Black Beans ",
        "aliases": ["Black Bean"],
    },
    {
        "id": "vegetable-broth",
        "canonical_name": "vegetable broth",
        "aliases": ["vegetable stock"],
    },
)


def test_load_ingredient_registry_normalizes_terms_and_builds_read_only_indexes():
    if CanonicalIngredient is None or load_ingredient_registry is None:
        pytest.fail("expected production behavior is not implemented")

    registry = load_ingredient_registry(VALID_INGREDIENTS)

    assert tuple(registry.by_id) == ("black-beans", "vegetable-broth")
    assert registry.by_id["black-beans"] == CanonicalIngredient(
        id="black-beans",
        canonical_name="black beans",
        aliases=("black bean",),
    )
    assert dict(registry.by_term) == {
        "black beans": "black-beans",
        "black bean": "black-beans",
        "vegetable broth": "vegetable-broth",
        "vegetable stock": "vegetable-broth",
    }
    with pytest.raises(TypeError):
        registry.by_id["other"] = registry.by_id["black-beans"]
    with pytest.raises(TypeError):
        registry.by_term["beans"] = "black-beans"
```

- [ ] **Step 6: Observe the registry-construction RED**

Run:

```powershell
uv run pytest tests/test_ingredients.py::test_load_ingredient_registry_normalizes_terms_and_builds_read_only_indexes -v
```

Expected: one explicit failure because the registry module/behavior is absent.

- [ ] **Step 7: Implement only the validated record and immutable indexes**

Create `src/pantrypilot/ingredients.py` with only the behavior needed by the
basic construction test:

```python
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from pydantic import BaseModel, field_validator

from pantrypilot.normalization import normalize_ingredient


class CanonicalIngredient(BaseModel):
    id: str
    canonical_name: str
    aliases: tuple[str, ...]

    @field_validator("canonical_name")
    @classmethod
    def normalize_canonical_name(cls, value: str) -> str:
        return normalize_ingredient(value)

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(normalize_ingredient(value) for value in values)


@dataclass(frozen=True)
class IngredientRegistry:
    by_id: Mapping[str, CanonicalIngredient]
    by_term: Mapping[str, str]


def load_ingredient_registry(
    records: Iterable[Mapping[str, object]],
) -> IngredientRegistry:
    by_id: dict[str, CanonicalIngredient] = {}
    by_term: dict[str, str] = {}
    for record in records:
        ingredient = CanonicalIngredient.model_validate(record)
        for term in (ingredient.canonical_name, *ingredient.aliases):
            by_term[term] = ingredient.id
        by_id[ingredient.id] = ingredient
    return IngredientRegistry(
        by_id=MappingProxyType(by_id),
        by_term=MappingProxyType(by_term),
    )
```

Immediately after the production module exists, remove the temporary
`try`/`except`, both `None` assignments, and the in-test guard, and restore
these ordinary top-level imports before the GREEN run:

```python
from pantrypilot.ingredients import (
    CanonicalIngredient,
    load_ingredient_registry,
)
```

- [ ] **Step 8: Prove basic registry GREEN**

Run:

```powershell
uv run pytest tests/test_ingredients.py::test_load_ingredient_registry_normalizes_terms_and_builds_read_only_indexes -v
```

Expected: PASS.

- [ ] **Step 9: Add and observe each invalid-record rule separately**

Append these tests. Add one named test or one parameterized rule, run its named
command, and observe the expected RED before adding only the validation needed
for that rule. The blank-term rule is the one expected immediate PASS: it is an
integration regression for `normalize_ingredient`, whose blank rejection was
already test-driven in Steps 1–4.

```python
@pytest.mark.parametrize("ingredient_id", ["", "Black-Beans", "black beans", "-beans"])
def test_registry_rejects_invalid_machine_ids(ingredient_id):
    record = {**VALID_INGREDIENTS[0], "id": ingredient_id}

    with pytest.raises(ValidationError):
        load_ingredient_registry([record])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("canonical_name", "   "),
        ("aliases", ["black bean", "  "]),
    ],
)
def test_registry_rejects_blank_terms(field, value):
    record = {**VALID_INGREDIENTS[0], field: value}

    with pytest.raises(ValidationError, match="must not be blank"):
        load_ingredient_registry([record])


def test_registry_rejects_unknown_record_fields():
    record = {**VALID_INGREDIENTS[0], "ontology_code": "future"}

    with pytest.raises(ValidationError):
        load_ingredient_registry([record])


def test_canonical_ingredient_records_are_frozen():
    ingredient = load_ingredient_registry([VALID_INGREDIENTS[0]]).by_id[
        "black-beans"
    ]

    with pytest.raises(ValidationError):
        ingredient.canonical_name = "beans"


def test_registry_rejects_duplicate_ids():
    duplicate = {**VALID_INGREDIENTS[0], "canonical_name": "beans"}

    with pytest.raises(ValueError, match="duplicate ingredient id: black-beans"):
        load_ingredient_registry([VALID_INGREDIENTS[0], duplicate])


def test_registry_rejects_duplicate_aliases_after_normalization():
    record = {
        **VALID_INGREDIENTS[0],
        "aliases": ["black bean", " BLACK BEAN "],
    }

    with pytest.raises(ValidationError, match="duplicate ingredient alias"):
        load_ingredient_registry([record])


def test_registry_rejects_alias_equal_to_its_canonical_name():
    record = {**VALID_INGREDIENTS[0], "aliases": [" BLACK BEANS "]}

    with pytest.raises(
        ValidationError, match="ingredient alias duplicates canonical name"
    ):
        load_ingredient_registry([record])


@pytest.mark.parametrize(
    "second_record",
    [
        {
            "id": "other",
            "canonical_name": "BLACK BEANS",
            "aliases": [],
        },
        {
            "id": "other",
            "canonical_name": "beans",
            "aliases": ["black beans"],
        },
        {
            "id": "other",
            "canonical_name": "beans",
            "aliases": ["black bean"],
        },
    ],
)
def test_registry_rejects_every_cross_identity_term_collision(second_record):
    with pytest.raises(ValueError, match="ingredient term"):
        load_ingredient_registry([VALID_INGREDIENTS[0], second_record])
```

Run each rule after adding it:

```powershell
uv run pytest tests/test_ingredients.py::test_registry_rejects_invalid_machine_ids -v
uv run pytest tests/test_ingredients.py::test_registry_rejects_blank_terms -v
uv run pytest tests/test_ingredients.py::test_registry_rejects_unknown_record_fields -v
uv run pytest tests/test_ingredients.py::test_canonical_ingredient_records_are_frozen -v
uv run pytest tests/test_ingredients.py::test_registry_rejects_duplicate_ids -v
uv run pytest tests/test_ingredients.py::test_registry_rejects_duplicate_aliases_after_normalization -v
uv run pytest tests/test_ingredients.py::test_registry_rejects_alias_equal_to_its_canonical_name -v
uv run pytest tests/test_ingredients.py::test_registry_rejects_every_cross_identity_term_collision -v
```

Apply these minimum increments only after their corresponding RED:

1. Invalid IDs: import `Field`, define
   `INGREDIENT_ID_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"`, and change the ID
   field to `id: str = Field(pattern=INGREDIENT_ID_PATTERN)`.
2. Unknown fields: import `ConfigDict` and set
   `model_config = ConfigDict(extra="forbid")`.
3. Frozen records: change that config to
   `ConfigDict(extra="forbid", frozen=True)`.
4. Duplicate IDs: before adding an entity to either index, add:

   ```python
   if ingredient.id in by_id:
       raise ValueError(f"duplicate ingredient id: {ingredient.id}")
   ```

5. Duplicate aliases: replace the alias validator body with:

   ```python
   normalized: list[str] = []
   seen: set[str] = set()
   for value in values:
       alias = normalize_ingredient(value)
       if alias in seen:
           raise ValueError(f"duplicate ingredient alias: {alias}")
       seen.add(alias)
       normalized.append(alias)
   return tuple(normalized)
   ```

6. Canonical-name aliases: import `model_validator` and add:

   ```python
   @model_validator(mode="after")
   def reject_canonical_name_alias(self) -> "CanonicalIngredient":
       if self.canonical_name in self.aliases:
           raise ValueError(
               "ingredient alias duplicates canonical name: "
               f"{self.canonical_name}"
           )
       return self
   ```

7. Cross-identity collisions: replace unconditional `by_term` assignment with:

   ```python
   existing_id = by_term.get(term)
   if existing_id is not None:
       raise ValueError(
           f"ingredient term '{term}' maps to both "
           f"'{existing_id}' and '{ingredient.id}'"
       )
   by_term[term] = ingredient.id
   ```

Expected after each increment: the named rule and all earlier registry rules
pass. Run the blank-term rule after the basic implementation and confirm its
expected immediate PASS from the already-tested normalization primitive.

- [ ] **Step 10: Run the Task 1 focused and broader checks**

Run:

```powershell
uv run pytest tests/test_normalization.py tests/test_ingredients.py -v
uv run pytest tests/test_catalog.py tests/test_normalization.py tests/test_ingredients.py -v
uv run pytest -v
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: all current tests and checks pass. `tests/test_ranking.py` and
`tests/test_api.py` remain unchanged and continue to pass when the full suite
is run before review.

- [ ] **Step 11: Commit Task 1, then independently review its commit range**

Use the `TASK_BASE` recorded before Step 1. After Step 10 is green, inspect the
exact intended diff:

```powershell
git diff -- src/pantrypilot/normalization.py src/pantrypilot/ingredients.py tests/test_normalization.py tests/test_ingredients.py
```

Then stage only those files and make the planned task commit:

```powershell
git add src/pantrypilot/normalization.py src/pantrypilot/ingredients.py tests/test_normalization.py tests/test_ingredients.py
git commit -m "feat: add validated ingredient registry"
git rev-parse HEAD
```

Record that final command's output as `TASK_HEAD`. Using the
`superpowers:subagent-driven-development` review-package workflow, require
independent reviews of `TASK_BASE..TASK_HEAD`:

1. specification compliance for approved ID format, normalization, both
   immutable indexes, and every collision rule;
2. code quality for simple data flow, precise errors, test isolation, and no
   speculative abstraction.

For any Critical or Important finding, follow the Global Constraints fix loop,
using focused TDD for behavior changes and
`fix: address ingredient registry review findings` for each focused correction
commit. Run scoped re-review against each recorded `FIX_BASE..HEAD` range until
the reviewers clear all Critical and Important findings. Do not amend or
squash the task or fix commits. Only then mark Task 1 complete.

---

### Task 2: Deterministic Resolution Evidence and Application Registry

**Files:**

- Modify: `src/pantrypilot/ingredients.py`
- Modify: `tests/test_ingredients.py`

**Interfaces:**

- Consumes: `IngredientRegistry`, `CanonicalIngredient`, and
  `normalize_ingredient` from Task 1.
- Produces: `IngredientResolution`, `resolve_ingredient`,
  `resolve_ingredients`, the exact 14-record `RAW_INGREDIENTS`, and immutable
  `INGREDIENT_REGISTRY`. Task 3 adds the grouped request-evidence model when its
  first ranking response test requires it.

- [ ] **Step 1: Add the canonical-resolution test and observe RED**

Add this exact temporary missing-symbol guard beside the existing ingredient
imports:

```python
try:
    from pantrypilot.ingredients import resolve_ingredient
except ImportError as exc:
    if "cannot import name 'resolve_ingredient'" not in str(exc):
        raise
    resolve_ingredient = None
```

Then add:

```python
def test_resolve_ingredient_returns_canonical_evidence_after_normalization():
    if resolve_ingredient is None:
        pytest.fail("expected production behavior is not implemented")

    registry = load_ingredient_registry(VALID_INGREDIENTS)

    resolution = resolve_ingredient(" BLACK BEANS ", registry)

    assert resolution.model_dump() == {
        "input": " BLACK BEANS ",
        "normalized": "black beans",
        "ingredient_id": "black-beans",
        "canonical_name": "black beans",
        "match_type": "canonical",
    }
```

Run:

```powershell
uv run pytest tests/test_ingredients.py::test_resolve_ingredient_returns_canonical_evidence_after_normalization -v
```

Expected: explicit `FAILED` because resolution behavior is absent.

- [ ] **Step 2: Add the evidence models and canonical lookup only**

Add the frozen per-term model and only the canonical path to `ingredients.py`:

```python
from typing import Literal

IngredientMatchType = Literal["canonical", "alias", "unresolved"]


class IngredientResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input: str
    normalized: str
    ingredient_id: str | None
    canonical_name: str | None
    match_type: IngredientMatchType


def resolve_ingredient(
    value: str,
    registry: IngredientRegistry,
) -> IngredientResolution:
    normalized = normalize_ingredient(value)
    ingredient_id = registry.by_term.get(normalized)
    if ingredient_id is None:
        raise NotImplementedError("unresolved terms are not implemented")
    ingredient = registry.by_id[ingredient_id]
    if normalized != ingredient.canonical_name:
        raise NotImplementedError("alias terms are not implemented")
    return IngredientResolution(
        input=value,
        normalized=normalized,
        ingredient_id=ingredient.id,
        canonical_name=ingredient.canonical_name,
        match_type="canonical",
)
```

Immediately after the production symbol exists, remove the temporary guard and
the in-test `None` check and restore this ordinary top-level import before the
GREEN run:

```python
from pantrypilot.ingredients import resolve_ingredient
```

- [ ] **Step 3: Prove canonical-resolution GREEN**

Run:

```powershell
uv run pytest tests/test_ingredients.py::test_resolve_ingredient_returns_canonical_evidence_after_normalization -v
```

Expected: PASS.

- [ ] **Step 4: Add alias resolution, observe RED, and implement it**

Add:

```python
def test_resolve_ingredient_returns_explicit_alias_evidence():
    registry = load_ingredient_registry(VALID_INGREDIENTS)

    resolution = resolve_ingredient("Black Bean", registry)

    assert resolution.model_dump() == {
        "input": "Black Bean",
        "normalized": "black bean",
        "ingredient_id": "black-beans",
        "canonical_name": "black beans",
        "match_type": "alias",
    }
```

Run before implementation:

```powershell
uv run pytest tests/test_ingredients.py::test_resolve_ingredient_returns_explicit_alias_evidence -v
```

Expected RED: alias input is not yet returned with `match_type="alias"`.
Replace the alias `NotImplementedError` with:

```python
return IngredientResolution(
    input=value,
    normalized=normalized,
    ingredient_id=ingredient.id,
    canonical_name=ingredient.canonical_name,
    match_type="alias",
)
```

Rerun the named test, then run both resolution tests. Expected: PASS.

- [ ] **Step 5: Add abstention, observe RED, and implement it**

Add:

```python
def test_resolve_ingredient_abstains_on_unsupported_text():
    registry = load_ingredient_registry(VALID_INGREDIENTS)

    resolution = resolve_ingredient("black bean sauce", registry)

    assert resolution.model_dump() == {
        "input": "black bean sauce",
        "normalized": "black bean sauce",
        "ingredient_id": None,
        "canonical_name": None,
        "match_type": "unresolved",
    }
```

Run before implementation:

```powershell
uv run pytest tests/test_ingredients.py::test_resolve_ingredient_abstains_on_unsupported_text -v
```

Expected RED: unsupported terms do not yet return valid unresolved evidence.
Replace the unresolved `NotImplementedError` with:

```python
return IngredientResolution(
    input=value,
    normalized=normalized,
    ingredient_id=None,
    canonical_name=None,
    match_type="unresolved",
)
```

Rerun and expect PASS.

- [ ] **Step 6: Prove the evidence model rejects contradictory states**

Add this parameterized rule before completing the model validator:

```python
@pytest.mark.parametrize(
    "fields",
    [
        {
            "ingredient_id": "black-beans",
            "canonical_name": "black beans",
            "match_type": "unresolved",
        },
        {
            "ingredient_id": None,
            "canonical_name": None,
            "match_type": "alias",
        },
    ],
)
def test_ingredient_resolution_rejects_contradictory_states(fields):
    with pytest.raises(ValidationError):
        IngredientResolution(
            input="black bean",
            normalized="black bean",
            **fields,
        )
```

Run:

```powershell
uv run pytest tests/test_ingredients.py::test_ingredient_resolution_rejects_contradictory_states -v
```

Expected RED before the `model_validator`: contradictory evidence is accepted.
Add only this validator, rerun, and expect PASS:

```python
@model_validator(mode="after")
def validate_resolution_state(self) -> "IngredientResolution":
    has_identity = self.ingredient_id is not None and self.canonical_name is not None
    if self.match_type == "unresolved" and (
        self.ingredient_id is not None or self.canonical_name is not None
    ):
        raise ValueError("unresolved ingredients must not contain identity fields")
    if self.match_type != "unresolved" and not has_identity:
        raise ValueError("resolved ingredients require both identity fields")
    return self
```

- [ ] **Step 7: Add batch order and duplicate-evidence behavior**

Add this exact temporary missing-symbol guard:

```python
try:
    from pantrypilot.ingredients import resolve_ingredients
except ImportError as exc:
    if "cannot import name 'resolve_ingredients'" not in str(exc):
        raise
    resolve_ingredients = None
```

Then add the test:

```python
def test_resolve_ingredients_preserves_every_input_in_order():
    if resolve_ingredients is None:
        pytest.fail("expected production behavior is not implemented")

    registry = load_ingredient_registry(VALID_INGREDIENTS)

    resolutions = resolve_ingredients(
        ["black beans", "black bean", "BLACK BEANS", "unknown"],
        registry,
    )

    assert [resolution.input for resolution in resolutions] == [
        "black beans",
        "black bean",
        "BLACK BEANS",
        "unknown",
    ]
    assert [resolution.ingredient_id for resolution in resolutions] == [
        "black-beans",
        "black-beans",
        "black-beans",
        None,
    ]
```

Run and observe explicit missing-behavior RED:

```powershell
uv run pytest tests/test_ingredients.py::test_resolve_ingredients_preserves_every_input_in_order -v
```

Then implement:

```python
def resolve_ingredients(
    values: Iterable[str],
    registry: IngredientRegistry,
) -> tuple[IngredientResolution, ...]:
    return tuple(resolve_ingredient(value, registry) for value in values)
```

Remove the temporary guard and in-test `None` check and restore this ordinary
top-level import before rerunning GREEN:

```python
from pantrypilot.ingredients import resolve_ingredients
```

Rerun and expect PASS.

- [ ] **Step 8: Add the exact application registry records**

Before defining application data, add this exact temporary missing-symbol
guard:

```python
try:
    from pantrypilot.ingredients import INGREDIENT_REGISTRY
except ImportError as exc:
    if "cannot import name 'INGREDIENT_REGISTRY'" not in str(exc):
        raise
    INGREDIENT_REGISTRY = None
```

Then add the test:

```python
def test_application_registry_is_the_approved_canonical_identity_set():
    if INGREDIENT_REGISTRY is None:
        pytest.fail("expected production behavior is not implemented")

    assert {
        ingredient.id: (ingredient.canonical_name, ingredient.aliases)
        for ingredient in INGREDIENT_REGISTRY.by_id.values()
    } == {
        "eggs": ("eggs", ("egg",)),
        "spinach": ("spinach", ()),
        "olive-oil": ("olive oil", ()),
        "black-beans": ("black beans", ("black bean",)),
        "corn-tortillas": ("corn tortillas", ("corn tortilla",)),
        "avocado": ("avocado", ()),
        "lime": ("lime", ()),
        "noodles": ("noodles", ()),
        "peanuts": ("peanuts", ("peanut",)),
        "soy-sauce": ("soy sauce", ()),
        "lentils": ("lentils", ("lentil",)),
        "carrots": ("carrots", ("carrot",)),
        "celery": ("celery", ()),
        "vegetable-broth": ("vegetable broth", ("vegetable stock",)),
    }
```

Run:

```powershell
uv run pytest tests/test_ingredients.py::test_application_registry_is_the_approved_canonical_identity_set -v
```

Expected RED: application registry constant is absent.

Add `RAW_INGREDIENTS` as a tuple of exactly these records and load it at import:

```python
RAW_INGREDIENTS = (
    {"id": "eggs", "canonical_name": "eggs", "aliases": ["egg"]},
    {"id": "spinach", "canonical_name": "spinach", "aliases": []},
    {"id": "olive-oil", "canonical_name": "olive oil", "aliases": []},
    {
        "id": "black-beans",
        "canonical_name": "black beans",
        "aliases": ["black bean"],
    },
    {
        "id": "corn-tortillas",
        "canonical_name": "corn tortillas",
        "aliases": ["corn tortilla"],
    },
    {"id": "avocado", "canonical_name": "avocado", "aliases": []},
    {"id": "lime", "canonical_name": "lime", "aliases": []},
    {"id": "noodles", "canonical_name": "noodles", "aliases": []},
    {"id": "peanuts", "canonical_name": "peanuts", "aliases": ["peanut"]},
    {"id": "soy-sauce", "canonical_name": "soy sauce", "aliases": []},
    {"id": "lentils", "canonical_name": "lentils", "aliases": ["lentil"]},
    {"id": "carrots", "canonical_name": "carrots", "aliases": ["carrot"]},
    {"id": "celery", "canonical_name": "celery", "aliases": []},
    {
        "id": "vegetable-broth",
        "canonical_name": "vegetable broth",
        "aliases": ["vegetable stock"],
    },
)

INGREDIENT_REGISTRY = load_ingredient_registry(RAW_INGREDIENTS)
```

Remove the temporary guard and in-test `None` check and restore this ordinary
top-level import before rerunning GREEN:

```python
from pantrypilot.ingredients import INGREDIENT_REGISTRY
```

Rerun and expect PASS.

- [ ] **Step 9: Prove deterministic repeated resolution**

Add:

```python
def test_identical_input_and_registry_produce_identical_resolution():
    first = resolve_ingredients([" Black Bean ", "unknown"], INGREDIENT_REGISTRY)
    second = resolve_ingredients([" Black Bean ", "unknown"], INGREDIENT_REGISTRY)

    assert first == second
```

Run:

```powershell
uv run pytest tests/test_ingredients.py::test_identical_input_and_registry_produce_identical_resolution -v
```

Expected: PASS without production changes because the already-tested pure
lookup is deterministic. This is an explicit regression assertion, not a new
behavior implementation.

- [ ] **Step 10: Run Task 2 focused and broader checks**

Run:

```powershell
uv run pytest tests/test_ingredients.py -v
uv run pytest tests/test_normalization.py tests/test_ingredients.py -v
uv run pytest -v
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: all tests and checks pass; no current Feature 001 response changes
exist yet.

- [ ] **Step 11: Commit Task 2, then independently review its commit range**

Use the `TASK_BASE` recorded before Step 1. After Step 10 is green, inspect the
exact intended diff:

```powershell
git diff -- src/pantrypilot/ingredients.py tests/test_ingredients.py
```

Then stage only those files and make the planned task commit:

```powershell
git add src/pantrypilot/ingredients.py tests/test_ingredients.py
git commit -m "feat: add deterministic ingredient resolver"
git rev-parse HEAD
```

Record that final command's output as `TASK_HEAD`. Using the
`superpowers:subagent-driven-development` review-package workflow, require
independent specification-compliance and code-quality reviews of
`TASK_BASE..TASK_HEAD` covering canonical-versus-alias classification,
abstention, evidence invariants, order preservation, approved registry
contents, determinism, and absence of heuristic behavior.

For any Critical or Important finding, follow the Global Constraints fix loop,
using focused TDD for behavior changes and
`fix: address ingredient resolver review findings` for each focused correction
commit. Run scoped re-review against each recorded `FIX_BASE..HEAD` range until
the reviewers clear all Critical and Important findings. Do not amend or
squash the task or fix commits. Only then mark Task 2 complete.

---

### Task 3: Canonical-ID Catalog, Ranking Integration, and API Evidence

**Files:**

- Modify: `src/pantrypilot/ingredients.py`
- Modify: `src/pantrypilot/models.py`
- Modify: `src/pantrypilot/catalog.py`
- Modify: `src/pantrypilot/ranking.py`
- Modify: `src/pantrypilot/app.py`
- Modify: `tests/test_catalog.py`
- Modify: `tests/test_ranking.py`
- Modify: `tests/test_api.py`

**Interfaces:**

- Consumes: `INGREDIENT_REGISTRY`, `IngredientResolution`, and
  `resolve_ingredients` from Task 2.
- Produces: grouped `IngredientResolutionEvidence`, ID-based `Recipe`, explicit
  `RankedRecipe`, registry-validating `load_catalog`, ID-based
  matching/filtering, full `RankingResponse`,
  `UnresolvedExcludedIngredientsError`, successful HTTP evidence, and the
  fail-closed unresolved-exclusion `422`.
- This is one vertical migration boundary because committing only the model or
  catalog half would leave the existing ranking/API suite broken.

- [ ] **Step 1: Add the failing catalog-ID migration rule**

Change only the local `VALID_RECIPE` in `tests/test_catalog.py` to use:

```python
VALID_RECIPE = {
    "id": "test-recipe",
    "name": "Test Recipe",
    "required_ingredient_ids": ["eggs", "spinach"],
    "calories": 300,
    "protein_g": 20.0,
    "prep_minutes": 10,
}
```

Import `INGREDIENT_REGISTRY`, pass it to `load_catalog`, and change the first
test to:

```python
def test_load_catalog_stores_valid_canonical_ids_and_freezes_collection():
    catalog = load_catalog([VALID_RECIPE], INGREDIENT_REGISTRY)

    assert isinstance(catalog, tuple)
    assert catalog[0].required_ingredient_ids == ("eggs", "spinach")
```

Run only that named test before changing production:

```powershell
uv run pytest tests/test_catalog.py::test_load_catalog_stores_valid_canonical_ids_and_freezes_collection -v
```

Expected RED: the current `Recipe` and `load_catalog` do not accept the new
field/signature.

- [ ] **Step 2: Migrate the internal recipe and catalog contract minimally**

In `models.py`, replace `Recipe.required_ingredients` with:

```python
required_ingredient_ids: tuple[str, ...] = Field(min_length=1)
```

Do not normalize IDs. In `catalog.py`, change `load_catalog` to accept an
`IngredientRegistry`, but do not add the unknown-ID check until its RED in
Step 3. In the same minimum migration, update `RAW_CATALOG` to use these ID
tuples and pass the registry to its module-level loader so importing the module
remains valid:

```python
from pantrypilot.ingredients import INGREDIENT_REGISTRY, IngredientRegistry

("eggs", "spinach", "olive-oil")
("black-beans", "corn-tortillas", "avocado", "lime")
("noodles", "peanuts", "soy-sauce")
("lentils", "carrots", "celery", "vegetable-broth")

CATALOG = load_catalog(RAW_CATALOG, INGREDIENT_REGISTRY)
```

Do not migrate ranking or `RankedRecipe` yet; the focused local loader test can
pass independently. Rerun the named test and expect PASS.

- [ ] **Step 3: Add unknown and duplicate catalog-ID tests before completing migration**

Add and run these one at a time:

```python
def test_load_catalog_rejects_unknown_ingredient_ids():
    record = {**VALID_RECIPE, "required_ingredient_ids": ["eggs", "unknown"]}

    with pytest.raises(
        ValueError,
        match="unknown ingredient id 'unknown' in recipe 'test-recipe'",
    ):
        load_catalog([record], INGREDIENT_REGISTRY)


def test_load_catalog_rejects_duplicate_required_ingredient_ids():
    record = {**VALID_RECIPE, "required_ingredient_ids": ["eggs", "eggs"]}

    with pytest.raises(ValidationError, match="duplicate required ingredient id"):
        load_catalog([record], INGREDIENT_REGISTRY)
```

Commands:

```powershell
uv run pytest tests/test_catalog.py::test_load_catalog_rejects_unknown_ingredient_ids -v
uv run pytest tests/test_catalog.py::test_load_catalog_rejects_duplicate_required_ingredient_ids -v
```

Expected for each RED: the invalid record is accepted or fails for the wrong
reason. For the unknown ID, add the loader check:

```python
raise ValueError(
    f"unknown ingredient id '{ingredient_id}' in recipe '{recipe.id}'"
)
```

For duplicate IDs, add the model validator:

```python
@field_validator("required_ingredient_ids")
@classmethod
def reject_duplicate_required_ingredient_ids(
    cls, values: tuple[str, ...]
) -> tuple[str, ...]:
    seen: set[str] = set()
    for ingredient_id in values:
        if ingredient_id in seen:
            raise ValueError(f"duplicate required ingredient id: {ingredient_id}")
        seen.add(ingredient_id)
    return values
```

Rerun each named rule after its minimum implementation and expect PASS.

- [ ] **Step 4: Define the final raw catalog IDs and explicit result model**

Replace `RankedRecipe(Recipe)` with a frozen, extra-forbidden explicit model
containing the existing public result fields:

```python
class RankedRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    required_ingredients: tuple[str, ...] = Field(min_length=1)
    calories: int | FiniteFloat = Field(ge=0)
    protein_g: FiniteFloat = Field(ge=0)
    prep_minutes: StrictInt = Field(ge=0)
    final_score: float
    matched_ingredients: tuple[str, ...]
    missing_ingredients: tuple[str, ...]
    score_breakdown: ScoreBreakdown
    explanation: str
```

Update the approved-catalog assertion in `tests/test_catalog.py` to expect
`required_ingredient_ids`, pass `INGREDIENT_REGISTRY` to every local loader
call, and change the old invalid `required_ingredients` cases to
`required_ingredient_ids`. Run:

```powershell
uv run pytest tests/test_catalog.py -v
```

Expected: PASS. Do not run or commit with the ranking/API suite still migrated
only halfway; continue within this task.

- [ ] **Step 5: Add a failing ID-based matching test**

Update the `make_recipe` helper in `tests/test_ranking.py` to construct
`required_ingredient_ids`, defaulting to `("eggs", "spinach", "olive-oil")`.
Import `INGREDIENT_REGISTRY`. Replace the stable-order test with:

```python
def test_matching_compares_ids_and_returns_canonical_names_in_recipe_order():
    matched, missing = match_ingredients(
        make_recipe(),
        {"spinach", "eggs"},
        INGREDIENT_REGISTRY,
    )

    assert matched == ("eggs", "spinach")
    assert missing == ("olive oil",)
```

Run:

```powershell
uv run pytest tests/test_ranking.py::test_matching_compares_ids_and_returns_canonical_names_in_recipe_order -v
```

Expected RED: `match_ingredients` still accepts normalized strings and cannot
map `olive-oil` to `olive oil`.

- [ ] **Step 6: Migrate low-level ranking helpers to IDs**

Implement the final helper behavior:

```python
def is_eligible(
    recipe: Recipe,
    excluded_ingredient_ids: Collection[str],
    max_prep_minutes: int,
) -> bool:
    return recipe.prep_minutes <= max_prep_minutes and not set(
        recipe.required_ingredient_ids
    ).intersection(excluded_ingredient_ids)


def match_ingredients(
    recipe: Recipe,
    pantry_ingredient_ids: Collection[str],
    ingredient_registry: IngredientRegistry,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    pantry_ids = set(pantry_ingredient_ids)
    matched_ids = tuple(
        ingredient_id
        for ingredient_id in recipe.required_ingredient_ids
        if ingredient_id in pantry_ids
    )
    missing_ids = tuple(
        ingredient_id
        for ingredient_id in recipe.required_ingredient_ids
        if ingredient_id not in pantry_ids
    )
    return (
        tuple(
            ingredient_registry.by_id[ingredient_id].canonical_name
            for ingredient_id in matched_ids
        ),
        tuple(
            ingredient_registry.by_id[ingredient_id].canonical_name
            for ingredient_id in missing_ids
        ),
    )
```

Change `calculate_score` and `render_explanation` denominators from
`len(recipe.required_ingredients)` to
`len(recipe.required_ingredient_ids)`. Update existing direct helper calls in
`tests/test_ranking.py` to pass IDs and the registry. Replace the superseded
string-level plural/synonym ranking test with this ID-boundary test; Task 2 and
the evaluation fixture now own surface-form resolution coverage:

```python
def test_matching_uses_only_resolved_canonical_ids():
    recipe = make_recipe(required=("olive-oil", "black-beans"))

    matched, missing = match_ingredients(
        recipe,
        {"oil", "beans"},
        INGREDIENT_REGISTRY,
    )

    assert matched == ()
    assert missing == ("olive oil", "black beans")
```

Run the named matching tests, then all non-pipeline scoring/explanation tests.
Expected: PASS with the existing numeric expectations unchanged.

- [ ] **Step 7: Add the failing end-to-end resolver/ranking test**

Adapt existing pipeline assertions to read `.results` only after the new
response is implemented. Before changing `rank_recipes`, add this focused test:

```python
def test_rank_recipes_resolves_aliases_and_unknown_pantry_terms_before_matching():
    request = make_request(
        pantry_items=[
            "black bean",
            "corn tortillas",
            "avocado",
            "lime",
            "mystery ingredient",
            "black beans",
        ],
        min_protein_g=0.0,
        max_prep_minutes=30,
        excluded_ingredients=["peanut"],
        limit=50,
    )

    response = rank_recipes(request, CATALOG, INGREDIENT_REGISTRY)
    tacos = next(result for result in response.results if result.id == "black-bean-tacos")

    assert [result.id for result in response.results] == [
        "black-bean-tacos",
        "spinach-omelet",
    ]
    assert tacos.matched_ingredients == (
        "black beans",
        "corn tortillas",
        "avocado",
        "lime",
    )
    assert tacos.missing_ingredients == ()
    assert tacos.score_breakdown.pantry_coverage.value == 1.0
    assert tacos.score_breakdown.pantry_coverage.contribution == 0.7
    assert tacos.final_score == 0.9167
    assert [item.match_type for item in response.ingredient_resolution.pantry_items] == [
        "alias",
        "canonical",
        "canonical",
        "canonical",
        "unresolved",
        "canonical",
    ]
    assert response.ingredient_resolution.excluded_ingredients[0].ingredient_id == (
        "peanuts"
    )
```

Import `CATALOG` from `pantrypilot.catalog` for this test.

Run:

```powershell
uv run pytest tests/test_ranking.py::test_rank_recipes_resolves_aliases_and_unknown_pantry_terms_before_matching -v
```

Expected RED: current `rank_recipes` does not accept a registry, return a
`RankingResponse`, resolve aliases, or expose evidence.

- [ ] **Step 8: Implement the successful ID-based ranking pipeline**

Add the grouped model to `ingredients.py`:

```python
class IngredientResolutionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pantry_items: tuple[IngredientResolution, ...]
    excluded_ingredients: tuple[IngredientResolution, ...]
```

Add `ingredient_resolution: IngredientResolutionEvidence` to
`RankingResponse`. In `rank_recipes`:

1. call `resolve_ingredients` once for each request list;
2. build `IngredientResolutionEvidence` from the complete ordered tuples;
3. build pantry/exclusion ID sets from non-null IDs;
4. filter recipes by exclusion IDs and preparation time;
5. match required IDs and map them to canonical names;
6. preserve existing scoring, explanation, sorting, and limiting;
7. return one `RankingResponse` with limited results, their count, and the
   evidence.

The construction has this final outline:

```python
pantry_resolutions = resolve_ingredients(request.pantry_items, ingredient_registry)
excluded_resolutions = resolve_ingredients(
    request.excluded_ingredients, ingredient_registry
)
ingredient_resolution = IngredientResolutionEvidence(
    pantry_items=pantry_resolutions,
    excluded_ingredients=excluded_resolutions,
)
pantry_ids = {
    resolution.ingredient_id
    for resolution in pantry_resolutions
    if resolution.ingredient_id is not None
}
excluded_ids = {
    resolution.ingredient_id
    for resolution in excluded_resolutions
    if resolution.ingredient_id is not None
}
```

Build `RankedRecipe.required_ingredients` by mapping every recipe ID through
`ingredient_registry.by_id`. Return:

```python
results = limit_ranked_recipes(sort_ranked_recipes(ranked_recipes), request.limit)
return RankingResponse(
    results=results,
    returned_count=len(results),
    ingredient_resolution=ingredient_resolution,
)
```

Do not add unresolved-exclusion rejection until its separate RED in Step 11.
Rerun the named test and expect PASS.

- [ ] **Step 9: Migrate and verify all direct ranking regressions**

Update every existing `tests/test_ranking.py` call to:

- construct `Recipe.required_ingredient_ids`;
- pass `INGREDIENT_REGISTRY` to `match_ingredients` and `rank_recipes`;
- inspect `response.results` instead of treating the return as a list;
- retain every existing score, explanation, ordering, hard-time, soft-protein,
  exclusion-precedence, and post-sort-limit assertion.

Change the post-sort-limit fixture's low recipe from the unregistered
`("missing",)` ID to registered `("celery",)`, while keeping the high recipe at
`("eggs",)`. This preserves the original lower-score/higher-score behavior
without constructing invalid recipe identities.

Add the explicit Feature 001 arithmetic control next to the Feature 002 test:

```python
def test_black_bean_taco_exact_match_baseline_score_remains_reconstructable():
    tacos = next(recipe for recipe in CATALOG if recipe.id == "black-bean-tacos")

    final_score, breakdown = calculate_score(
        tacos,
        matched_count=3,
        min_protein_g=0.0,
        max_prep_minutes=30,
    )

    assert breakdown.pantry_coverage.value == 0.75
    assert breakdown.pantry_coverage.contribution == 0.525
    assert breakdown.protein_fit.contribution == 0.2
    assert breakdown.time_fit.contribution == 0.0167
    assert final_score == 0.7417
```

This is a regression control for unchanged Feature 001 arithmetic and should
pass immediately. Run:

```powershell
uv run pytest tests/test_catalog.py tests/test_ranking.py -v
```

Expected: all catalog and ranking tests pass.

- [ ] **Step 10: Add the unresolved-exclusion domain RED**

Add this exact temporary missing-symbol guard beside the existing ranking
imports:

```python
try:
    from pantrypilot.ranking import UnresolvedExcludedIngredientsError
except ImportError as exc:
    if "cannot import name 'UnresolvedExcludedIngredientsError'" not in str(exc):
        raise
    UnresolvedExcludedIngredientsError = None
```

Then add the test:

```python
def test_rank_recipes_rejects_unresolved_exclusions_with_complete_evidence():
    if UnresolvedExcludedIngredientsError is None:
        pytest.fail("expected production behavior is not implemented")

    request = make_request(
        pantry_items=["black bean"],
        excluded_ingredients=["groundnut"],
    )

    with pytest.raises(UnresolvedExcludedIngredientsError) as exc_info:
        rank_recipes(request, CATALOG, INGREDIENT_REGISTRY)

    evidence = exc_info.value.ingredient_resolution
    assert evidence.pantry_items[0].ingredient_id == "black-beans"
    assert evidence.excluded_ingredients[0].model_dump() == {
        "input": "groundnut",
        "normalized": "groundnut",
        "ingredient_id": None,
        "canonical_name": None,
        "match_type": "unresolved",
    }
```

Run:

```powershell
uv run pytest tests/test_ranking.py::test_rank_recipes_rejects_unresolved_exclusions_with_complete_evidence -v
```

Expected RED: ranking currently ignores the unresolved exclusion and returns
results.

- [ ] **Step 11: Implement the one fail-closed domain exception**

Add:

```python
class UnresolvedExcludedIngredientsError(ValueError):
    ingredient_resolution: IngredientResolutionEvidence

    def __init__(
        self,
        ingredient_resolution: IngredientResolutionEvidence,
    ) -> None:
        super().__init__("all excluded ingredients must resolve before ranking")
        self.ingredient_resolution = ingredient_resolution
```

Immediately after building complete evidence and before filtering or scoring,
raise it when:

```python
any(
    resolution.match_type == "unresolved"
    for resolution in ingredient_resolution.excluded_ingredients
)
```

Immediately after the exception exists, remove the temporary guard and in-test
`None` check and restore this ordinary top-level import before rerunning GREEN:

```python
from pantrypilot.ranking import UnresolvedExcludedIngredientsError
```

Rerun the named test and all ranking tests. Expected: PASS.

- [ ] **Step 12: Add the successful API evidence contract RED**

Before changing `app.py`, add this test to `tests/test_api.py`:

```python
def test_meal_rankings_exposes_alias_duplicate_and_unresolved_pantry_evidence():
    response = client.post(
        "/v1/meal-rankings",
        json={
            "pantry_items": ["black bean", "black beans", "unknown"],
            "min_protein_g": 0.0,
            "max_prep_minutes": 30,
            "excluded_ingredients": ["peanut"],
            "limit": 50,
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert [item["match_type"] for item in body["ingredient_resolution"]["pantry_items"]] == [
        "alias",
        "canonical",
        "unresolved",
    ]
    assert [item["ingredient_id"] for item in body["ingredient_resolution"]["pantry_items"]] == [
        "black-beans",
        "black-beans",
        None,
    ]
    assert body["ingredient_resolution"]["excluded_ingredients"][0] == {
        "input": "peanut",
        "normalized": "peanut",
        "ingredient_id": "peanuts",
        "canonical_name": "peanuts",
        "match_type": "alias",
    }
    assert "peanut-noodles" not in {result["id"] for result in body["results"]}
```

Run:

```powershell
uv run pytest tests/test_api.py::test_meal_rankings_exposes_alias_duplicate_and_unresolved_pantry_evidence -v
```

Expected RED: the route still calls the old signature and constructs the old
response.

- [ ] **Step 13: Adapt the thin route to the pure final response**

Change only the successful route body:

```python
return rank_recipes(request, CATALOG, INGREDIENT_REGISTRY)
```

Import `INGREDIENT_REGISTRY`. Do not duplicate resolution or ranking rules in
the route. Rerun the named API test and expect PASS.

- [ ] **Step 14: Add the unresolved-exclusion HTTP RED and map it**

Add:

```python
def test_meal_rankings_returns_fail_closed_422_for_unresolved_exclusion():
    response = client.post(
        "/v1/meal-rankings",
        json={
            **VALID_REQUEST,
            "pantry_items": [],
            "excluded_ingredients": ["groundnut"],
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "type": "unresolved_excluded_ingredients",
            "message": "All excluded ingredients must resolve before ranking.",
            "ingredient_resolution": {
                "pantry_items": [],
                "excluded_ingredients": [
                    {
                        "input": "groundnut",
                        "normalized": "groundnut",
                        "ingredient_id": None,
                        "canonical_name": None,
                        "match_type": "unresolved",
                    }
                ],
            },
        }
    }
```

Run and expect RED with the exception escaping or a generic `500`:

```powershell
uv run pytest tests/test_api.py::test_meal_rankings_returns_fail_closed_422_for_unresolved_exclusion -v
```

Then catch only `UnresolvedExcludedIngredientsError` in the route and raise:

```python
from fastapi import HTTPException

raise HTTPException(
    status_code=422,
    detail={
        "type": "unresolved_excluded_ingredients",
        "message": "All excluded ingredients must resolve before ranking.",
        "ingredient_resolution": (
            exc.ingredient_resolution.model_dump(mode="json")
        ),
    },
) from exc
```

Rerun and expect PASS. Do not change the existing
`RequestValidationError` handler or generic unexpected-error behavior.

- [ ] **Step 15: Update exact Feature 001 API responses additively**

Update the existing exact successful-response assertion by adding the expected
canonical evidence for `" Eggs "`, `"spinach"`, `"EGGS"`, and `"peanuts"`.
Update the existing empty-result response to include:

```python
"ingredient_resolution": {
    "pantry_items": [],
    "excluded_ingredients": [],
}
```

Retain every result field and numeric expectation unchanged. Add an explicit
canonical compatibility assertion:

```python
def test_canonical_inputs_preserve_feature_001_result_order_and_scores():
    response = client.post(
        "/v1/meal-rankings",
        json={
            **VALID_REQUEST,
            "excluded_ingredients": [],
            "max_prep_minutes": 45,
            "limit": 50,
        },
    )

    assert response.status_code == 200
    assert [
        (result["id"], result["final_score"])
        for result in response.json()["results"]
    ] == [
        ("spinach-omelet", 0.7334),
        ("peanut-noodles", 0.2156),
        ("black-bean-tacos", 0.1964),
        ("lentil-soup", 0.176),
    ]
```

These values were recorded from fresh Feature 001 output during planning with
the exact request shown. This is a regression assertion and should pass
without additional production changes.

- [ ] **Step 16: Run Task 3 focused and full checks**

Run:

```powershell
uv run pytest tests/test_catalog.py -v
uv run pytest tests/test_ranking.py -v
uv run pytest tests/test_api.py -v
uv run pytest -v
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: all tests and checks pass. Confirm the Black Bean Tacos resolver test
returns `0.9167`, the baseline control returns `0.7417`, canonical API order
and scores match Feature 001, an alias exclusion blocks the recipe, and an
unresolved exclusion returns the exact fail-closed `422`.

- [ ] **Step 17: Commit Task 3, then independently review its commit range**

Use the `TASK_BASE` recorded before Step 1. After Step 16 is green, inspect the
exact intended eight-file diff:

```powershell
git diff -- src/pantrypilot/ingredients.py src/pantrypilot/models.py src/pantrypilot/catalog.py src/pantrypilot/ranking.py src/pantrypilot/app.py tests/test_catalog.py tests/test_ranking.py tests/test_api.py
```

Then stage only those files and make the planned task commit:

```powershell
git add src/pantrypilot/ingredients.py src/pantrypilot/models.py src/pantrypilot/catalog.py src/pantrypilot/ranking.py src/pantrypilot/app.py tests/test_catalog.py tests/test_ranking.py tests/test_api.py
git commit -m "feat: rank recipes by canonical ingredient identity"
git rev-parse HEAD
```

Record that final command's output as `TASK_HEAD`. Using the
`superpowers:subagent-driven-development` review-package workflow, require
independent specification-compliance and code-quality reviews of
`TASK_BASE..TASK_HEAD` with special attention to:

- no duplicate source of truth between IDs and display names;
- complete current-catalog registry coverage;
- one resolver for pantry and exclusions;
- unresolved hard-constraint safety;
- additive API evidence only;
- unchanged ranking arithmetic, result fields, explanation, and ordering;
- pure domain dependency direction and absence of non-goals.

For any Critical or Important finding, follow the Global Constraints fix loop,
using focused TDD for behavior changes and
`fix: address canonical ranking review findings` for each focused correction
commit. Run scoped re-review against each recorded `FIX_BASE..HEAD` range until
the reviewers clear all Critical and Important findings. Do not amend or
squash the task or fix commits. Only then mark Task 3 complete.

---

### Task 4: Versioned Evaluation Fixture and Registry Consistency

**Files:**

- Create: `src/pantrypilot/evaluation.py`
- Create: `evaluations/ingredient-resolution-v1.json`
- Create: `tests/test_evaluation.py`

**Interfaces:**

- Consumes: `IngredientRegistry`, `INGREDIENT_REGISTRY`,
  `normalize_ingredient`, and `resolve_ingredient`.
- Produces: frozen `EvaluationCase` and `EvaluationFixture` models plus
  `load_evaluation_fixture(path, ingredient_registry)`.
- Establishes the approved 28 labels before metric implementation.
- Includes the owner-required explicit test that every registered canonical
  name and alias appears exactly in the fixture and that every category agrees
  with the registry.

- [ ] **Step 1: Add the basic fixture-loader RED**

Create `tests/test_evaluation.py` with this exact guard for the absent module.
It re-raises a missing dependency inside that module rather than misreporting
it as the intended RED:

```python
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from pantrypilot.ingredients import INGREDIENT_REGISTRY, resolve_ingredient

try:
    from pantrypilot.evaluation import load_evaluation_fixture
except ModuleNotFoundError as exc:
    if exc.name != "pantrypilot.evaluation":
        raise
    load_evaluation_fixture = None

FIXTURE_PATH = Path("evaluations/ingredient-resolution-v1.json")


def test_load_evaluation_fixture_validates_version_and_case_shape(tmp_path):
    if load_evaluation_fixture is None:
        pytest.fail("expected production behavior is not implemented")

    path = tmp_path / "fixture.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "input": " Black Bean ",
                        "expected_ingredient_id": "black-beans",
                        "category": "alias",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    fixture = load_evaluation_fixture(path, INGREDIENT_REGISTRY)

    assert fixture.schema_version == 1
    assert fixture.cases[0].input == "black bean"
    assert fixture.cases[0].expected_ingredient_id == "black-beans"
    assert fixture.cases[0].category == "alias"
```

Run:

```powershell
uv run pytest tests/test_evaluation.py::test_load_evaluation_fixture_validates_version_and_case_shape -v
```

Expected: explicit `FAILED` because the evaluation module does not exist.

- [ ] **Step 2: Implement the fixture models and basic loader only**

Create `src/pantrypilot/evaluation.py` with:

```python
import json
from pathlib import Path

from pydantic import BaseModel, field_validator

from pantrypilot.ingredients import IngredientRegistry
from pantrypilot.normalization import normalize_ingredient


class EvaluationCase(BaseModel):
    input: str
    expected_ingredient_id: str | None
    category: str

    @field_validator("input")
    @classmethod
    def normalize_input(cls, value: str) -> str:
        return normalize_ingredient(value)


class EvaluationFixture(BaseModel):
    schema_version: int
    cases: tuple[EvaluationCase, ...]


def load_evaluation_fixture(
    path: Path,
    ingredient_registry: IngredientRegistry,
) -> EvaluationFixture:
    return EvaluationFixture.model_validate(
        json.loads(path.read_text(encoding="utf-8"))
)
```

Immediately after the production module exists, remove the temporary guard and
in-test `None` check and restore this ordinary top-level import before the
GREEN run:

```python
from pantrypilot.evaluation import load_evaluation_fixture
```

The registry parameter is intentionally unused until its reference-validation
RED in Step 5. Rerun the named test and expect PASS.

- [ ] **Step 3: Add invalid fixture-schema rules one at a time**

Add this helper and parameterized schema rule:

```python
def write_fixture(tmp_path, data) -> Path:
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    "data",
    [
        {"schema_version": 2, "cases": []},
        {"schema_version": 1, "cases": []},
        {
            "schema_version": 1,
            "cases": [
                {
                    "input": "   ",
                    "expected_ingredient_id": None,
                    "category": "unresolved",
                }
            ],
        },
        {
            "schema_version": 1,
            "cases": [
                {
                    "input": "unknown",
                    "expected_ingredient_id": None,
                    "category": "negative",
                }
            ],
        },
        {
            "schema_version": 1,
            "cases": [
                {
                    "input": "unknown",
                    "expected_ingredient_id": None,
                    "category": "unresolved",
                    "notes": "not approved",
                }
            ],
        },
        {
            "schema_version": 1,
            "cases": [],
            "dataset_name": "future",
        },
    ],
)
def test_load_evaluation_fixture_rejects_invalid_schema(tmp_path, data):
    with pytest.raises((ValidationError, ValueError)):
        load_evaluation_fixture(
            write_fixture(tmp_path, data),
            INGREDIENT_REGISTRY,
        )
```

Run before completing schema constraints:

```powershell
uv run pytest tests/test_evaluation.py::test_load_evaluation_fixture_rejects_invalid_schema -v
```

Expected RED: at least one unimplemented boundary is accepted. Add only the
following Pydantic constraints, rerun, and expect the whole rule PASS. Blank
input already fails through the previously test-driven normalization primitive.

```python
from typing import Literal

from pydantic import ConfigDict, Field


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: str
    expected_ingredient_id: str | None
    category: Literal["canonical", "alias", "unresolved"]


class EvaluationFixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    cases: tuple[EvaluationCase, ...] = Field(min_length=1)
```

Keep the existing `input` validator on `EvaluationCase` when applying this
shape.

Then add a separate immutability RED:

```python
def test_evaluation_fixture_models_are_frozen(tmp_path):
    fixture = load_evaluation_fixture(
        write_fixture(
            tmp_path,
            {
                "schema_version": 1,
                "cases": [
                    {
                        "input": "eggs",
                        "expected_ingredient_id": "eggs",
                        "category": "canonical",
                    }
                ],
            },
        ),
        INGREDIENT_REGISTRY,
    )

    with pytest.raises(ValidationError):
        fixture.schema_version = 2
    with pytest.raises(ValidationError):
        fixture.cases[0].category = "alias"
```

Run it and expect RED, then change both configs to
`ConfigDict(extra="forbid", frozen=True)`, rerun, and expect PASS:

```powershell
uv run pytest tests/test_evaluation.py::test_evaluation_fixture_models_are_frozen -v
```

- [ ] **Step 4: Add duplicate normalized-input rejection**

Add:

```python
def test_load_evaluation_fixture_rejects_duplicate_normalized_inputs(tmp_path):
    path = write_fixture(
        tmp_path,
        {
            "schema_version": 1,
            "cases": [
                {
                    "input": "black bean",
                    "expected_ingredient_id": "black-beans",
                    "category": "alias",
                },
                {
                    "input": " BLACK BEAN ",
                    "expected_ingredient_id": "black-beans",
                    "category": "alias",
                },
            ],
        },
    )

    with pytest.raises(ValidationError, match="duplicate evaluation input"):
        load_evaluation_fixture(path, INGREDIENT_REGISTRY)
```

Run and expect RED:

```powershell
uv run pytest tests/test_evaluation.py::test_load_evaluation_fixture_rejects_duplicate_normalized_inputs -v
```

Then add this validator to `EvaluationFixture`:

```python
@field_validator("cases")
@classmethod
def reject_duplicate_inputs(
    cls, cases: tuple[EvaluationCase, ...]
) -> tuple[EvaluationCase, ...]:
    seen: set[str] = set()
    for case in cases:
        if case.input in seen:
            raise ValueError(f"duplicate evaluation input: {case.input}")
        seen.add(case.input)
    return cases
```

Rerun and expect PASS.

- [ ] **Step 5: Add unknown expected-ID rejection**

Add:

```python
def test_load_evaluation_fixture_rejects_unknown_expected_id(tmp_path):
    path = write_fixture(
        tmp_path,
        {
            "schema_version": 1,
            "cases": [
                {
                    "input": "future ingredient",
                    "expected_ingredient_id": "future-ingredient",
                    "category": "canonical",
                }
            ],
        },
    )

    with pytest.raises(
        ValueError,
        match="unknown expected ingredient id: future-ingredient",
    ):
        load_evaluation_fixture(path, INGREDIENT_REGISTRY)
```

Run before adding the registry-reference check:

```powershell
uv run pytest tests/test_evaluation.py::test_load_evaluation_fixture_rejects_unknown_expected_id -v
```

Expected RED: the fixture loads. Add only this registry-reference check, rerun,
and expect PASS:

```python
fixture = EvaluationFixture.model_validate(
    json.loads(path.read_text(encoding="utf-8"))
)
for case in fixture.cases:
    if (
        case.expected_ingredient_id is not None
        and case.expected_ingredient_id not in ingredient_registry.by_id
    ):
        raise ValueError(
            "unknown expected ingredient id: "
            f"{case.expected_ingredient_id}"
        )
return fixture
```

- [ ] **Step 6: Add the owner-required registry coverage/category test**

Add this exact test before creating the approved fixture:

```python
def test_v1_fixture_covers_all_registered_terms_with_consistent_categories():
    fixture = load_evaluation_fixture(FIXTURE_PATH, INGREDIENT_REGISTRY)

    expected_registered_cases = {
        (ingredient.canonical_name, ingredient.id, "canonical")
        for ingredient in INGREDIENT_REGISTRY.by_id.values()
    } | {
        (alias, ingredient.id, "alias")
        for ingredient in INGREDIENT_REGISTRY.by_id.values()
        for alias in ingredient.aliases
    }
    actual_registered_cases = {
        (case.input, case.expected_ingredient_id, case.category)
        for case in fixture.cases
        if case.category != "unresolved"
    }

    assert actual_registered_cases == expected_registered_cases

    for case in fixture.cases:
        resolution = resolve_ingredient(case.input, INGREDIENT_REGISTRY)
        if case.category == "unresolved":
            assert case.expected_ingredient_id is None
            assert resolution.match_type == "unresolved"
            assert resolution.ingredient_id is None
        else:
            assert case.expected_ingredient_id is not None
            assert resolution.match_type == case.category
            assert resolution.ingredient_id == case.expected_ingredient_id

    assert {
        case.input
        for case in fixture.cases
        if case.category == "unresolved"
    } == {
        "eggplant",
        "black bean sauce",
        "tortilla chips",
        "peanut oil",
        "lentil pasta",
        "carrot cake",
        "vegetable shortening",
    }
```

This proves all of the following with set equality rather than counts alone:

- every registered canonical name occurs exactly as `canonical`;
- every registered alias occurs exactly as `alias`;
- no unregistered positive fixture term exists;
- every positive expected ID matches the registry;
- every `unresolved` case has a null label and the current registry abstains.
- the seven approved confusable negatives cannot be replaced with easier
  arbitrary unknowns merely to preserve zero false positives.

Run:

```powershell
uv run pytest tests/test_evaluation.py::test_v1_fixture_covers_all_registered_terms_with_consistent_categories -v
```

Expected RED: the approved v1 fixture file is absent.

- [ ] **Step 7: Create the complete approved v1 fixture**

Create `evaluations/ingredient-resolution-v1.json` with exactly:

```json
{
  "schema_version": 1,
  "cases": [
    {"input": "eggs", "expected_ingredient_id": "eggs", "category": "canonical"},
    {"input": "spinach", "expected_ingredient_id": "spinach", "category": "canonical"},
    {"input": "olive oil", "expected_ingredient_id": "olive-oil", "category": "canonical"},
    {"input": "black beans", "expected_ingredient_id": "black-beans", "category": "canonical"},
    {"input": "corn tortillas", "expected_ingredient_id": "corn-tortillas", "category": "canonical"},
    {"input": "avocado", "expected_ingredient_id": "avocado", "category": "canonical"},
    {"input": "lime", "expected_ingredient_id": "lime", "category": "canonical"},
    {"input": "noodles", "expected_ingredient_id": "noodles", "category": "canonical"},
    {"input": "peanuts", "expected_ingredient_id": "peanuts", "category": "canonical"},
    {"input": "soy sauce", "expected_ingredient_id": "soy-sauce", "category": "canonical"},
    {"input": "lentils", "expected_ingredient_id": "lentils", "category": "canonical"},
    {"input": "carrots", "expected_ingredient_id": "carrots", "category": "canonical"},
    {"input": "celery", "expected_ingredient_id": "celery", "category": "canonical"},
    {"input": "vegetable broth", "expected_ingredient_id": "vegetable-broth", "category": "canonical"},
    {"input": "egg", "expected_ingredient_id": "eggs", "category": "alias"},
    {"input": "black bean", "expected_ingredient_id": "black-beans", "category": "alias"},
    {"input": "corn tortilla", "expected_ingredient_id": "corn-tortillas", "category": "alias"},
    {"input": "peanut", "expected_ingredient_id": "peanuts", "category": "alias"},
    {"input": "lentil", "expected_ingredient_id": "lentils", "category": "alias"},
    {"input": "carrot", "expected_ingredient_id": "carrots", "category": "alias"},
    {"input": "vegetable stock", "expected_ingredient_id": "vegetable-broth", "category": "alias"},
    {"input": "eggplant", "expected_ingredient_id": null, "category": "unresolved"},
    {"input": "black bean sauce", "expected_ingredient_id": null, "category": "unresolved"},
    {"input": "tortilla chips", "expected_ingredient_id": null, "category": "unresolved"},
    {"input": "peanut oil", "expected_ingredient_id": null, "category": "unresolved"},
    {"input": "lentil pasta", "expected_ingredient_id": null, "category": "unresolved"},
    {"input": "carrot cake", "expected_ingredient_id": null, "category": "unresolved"},
    {"input": "vegetable shortening", "expected_ingredient_id": null, "category": "unresolved"}
  ]
}
```

Rerun the owner-required test. Expected: PASS.

- [ ] **Step 8: Assert version/category counts without weakening set coverage**

Add:

```python
def test_v1_fixture_has_the_approved_version_and_category_counts():
    fixture = load_evaluation_fixture(FIXTURE_PATH, INGREDIENT_REGISTRY)

    assert fixture.schema_version == 1
    assert len(fixture.cases) == 28
    assert sum(case.category == "canonical" for case in fixture.cases) == 14
    assert sum(case.category == "alias" for case in fixture.cases) == 7
    assert sum(case.category == "unresolved" for case in fixture.cases) == 7
```

Run and expect PASS without production changes. The preceding set-equality test
remains the authoritative coverage check; counts alone are insufficient.

- [ ] **Step 9: Run Task 4 focused and broader checks**

Run:

```powershell
uv run pytest tests/test_evaluation.py -v
uv run pytest tests/test_ingredients.py tests/test_evaluation.py -v
uv run pytest -v
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: all tests and checks pass, including explicit registry/fixture set
equality and category consistency.

- [ ] **Step 10: Commit Task 4, then independently review its commit range**

Use the `TASK_BASE` recorded before Step 1. After Step 9 is green, inspect the
exact intended diff:

```powershell
git diff -- src/pantrypilot/evaluation.py evaluations/ingredient-resolution-v1.json tests/test_evaluation.py
```

Then stage only those files and make the planned task commit:

```powershell
git add src/pantrypilot/evaluation.py evaluations/ingredient-resolution-v1.json tests/test_evaluation.py
git commit -m "test: add ingredient resolution evaluation fixture"
git rev-parse HEAD
```

Record that final command's output as `TASK_HEAD`. Using the
`superpowers:subagent-driven-development` review-package workflow, require
independent specification-compliance and code-quality reviews of
`TASK_BASE..TASK_HEAD` for exact fixture contents, schema validation, path
handling, duplicate prevention, test independence, full registered-term
coverage, category consistency, and resistance to metric gaming.

For any Critical or Important finding, follow the Global Constraints fix loop,
using focused TDD for behavior changes and
`fix: address evaluation fixture review findings` for each focused correction
commit. Run scoped re-review against each recorded `FIX_BASE..HEAD` range until
the reviewers clear all Critical and Important findings. Do not amend or
squash the task or fix commits. Only then mark Task 4 complete.

---

### Task 5: Exact-Match Baseline, Metrics, Error Analysis, and CLI

**Files:**

- Modify: `src/pantrypilot/evaluation.py`
- Modify: `tests/test_evaluation.py`

**Interfaces:**

- Consumes: the validated v1 fixture, application registry, and resolver.
- Produces: `EvaluationPrediction`, `ResolutionMetrics`,
  `ResolverComparison`, `resolve_exact_name`, `evaluate_resolver`,
  `compare_resolvers`, and `main`.
- Both systems receive the same `fixture.cases` tuple.

- [ ] **Step 1: Add the complete confusion-counting RED**

Replace the existing evaluation import with the ordinary import of the Task 4
symbols, and add this exact temporary guard only for the absent Task 5 symbol:

```python
from pantrypilot.evaluation import EvaluationCase, load_evaluation_fixture

try:
    from pantrypilot.evaluation import evaluate_resolver
except ImportError as exc:
    if "cannot import name 'evaluate_resolver'" not in str(exc):
        raise
    evaluate_resolver = None
```

Then add:

```python
def test_evaluate_resolver_uses_the_approved_confusion_count_rules():
    if evaluate_resolver is None:
        pytest.fail("expected production behavior is not implemented")

    cases = (
        EvaluationCase(
            input="eggs",
            expected_ingredient_id="eggs",
            category="canonical",
        ),
        EvaluationCase(
            input="black bean",
            expected_ingredient_id="black-beans",
            category="alias",
        ),
        EvaluationCase(
            input="vegetable stock",
            expected_ingredient_id="vegetable-broth",
            category="alias",
        ),
        EvaluationCase(
            input="eggplant",
            expected_ingredient_id=None,
            category="unresolved",
        ),
        EvaluationCase(
            input="carrot cake",
            expected_ingredient_id=None,
            category="unresolved",
        ),
    )
    predictions = {
        "eggs": "eggs",
        "black bean": None,
        "vegetable stock": "peanuts",
        "eggplant": "eggs",
        "carrot cake": None,
    }

    metrics = evaluate_resolver(cases, predictions.get)

    assert (
        metrics.true_positives,
        metrics.false_positives,
        metrics.false_negatives,
        metrics.true_negatives,
    ) == (1, 2, 2, 1)
    assert metrics.precision == 0.3333
    assert metrics.recall == 0.3333
    assert [case.input for case in metrics.false_positive_cases] == [
        "vegetable stock",
        "eggplant",
    ]
    assert [case.input for case in metrics.false_negative_cases] == [
        "black bean",
        "vegetable stock",
    ]

    all_abstained = evaluate_resolver(cases[:1], lambda _value: None)
    assert all_abstained.precision == 0.0
    assert all_abstained.recall == 0.0
```

Run:

```powershell
uv run pytest tests/test_evaluation.py::test_evaluate_resolver_uses_the_approved_confusion_count_rules -v
```

Expected: explicit missing-behavior RED. This one focused rule covers TP, FP,
FN, TN, correct abstention, over-resolution, positive abstention, the
wrong-identity FP+FN rule, inspectable error ordering, rounding, and the zero
denominator before metric production code exists.

- [ ] **Step 2: Implement metric models and one-pass classification**

Add:

```python
from collections.abc import Callable, Sequence


class EvaluationPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    input: str
    category: Literal["canonical", "alias", "unresolved"]
    expected_ingredient_id: str | None
    predicted_ingredient_id: str | None


class ResolutionMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    false_positive_cases: tuple[EvaluationPrediction, ...]
    false_negative_cases: tuple[EvaluationPrediction, ...]


def evaluate_resolver(
    cases: Sequence[EvaluationCase],
    resolver: Callable[[str], str | None],
) -> ResolutionMetrics:
    true_positives = 0
    false_positives: list[EvaluationPrediction] = []
    false_negatives: list[EvaluationPrediction] = []
    true_negatives = 0

    for case in cases:
        predicted_id = resolver(case.input)
        prediction = EvaluationPrediction(
            input=case.input,
            category=case.category,
            expected_ingredient_id=case.expected_ingredient_id,
            predicted_ingredient_id=predicted_id,
        )
        if case.expected_ingredient_id is None:
            if predicted_id is None:
                true_negatives += 1
            else:
                false_positives.append(prediction)
        elif predicted_id == case.expected_ingredient_id:
            true_positives += 1
        else:
            false_negatives.append(prediction)
            if predicted_id is not None:
                false_positives.append(prediction)

    false_positive_count = len(false_positives)
    false_negative_count = len(false_negatives)
    precision_denominator = true_positives + false_positive_count
    recall_denominator = true_positives + false_negative_count
    return ResolutionMetrics(
        true_positives=true_positives,
        false_positives=false_positive_count,
        false_negatives=false_negative_count,
        true_negatives=true_negatives,
        precision=round(
            true_positives / precision_denominator, 4
        ) if precision_denominator else 0.0,
        recall=round(
            true_positives / recall_denominator, 4
        ) if recall_denominator else 0.0,
        false_positive_cases=tuple(false_positives),
        false_negative_cases=tuple(false_negatives),
    )
```

Immediately after the production symbol exists, remove the temporary guard and
in-test `None` check and restore this ordinary top-level import before the
GREEN run:

```python
from pantrypilot.evaluation import (
    EvaluationCase,
    evaluate_resolver,
    load_evaluation_fixture,
)
```

Rerun the named test and expect PASS.

- [ ] **Step 3: Add a compact metric regression rule**

Add this focused parameter-free test before assuming the other branches work:

```python
def test_evaluate_resolver_counts_correct_resolutions_abstentions_and_over_resolution():
    cases = (
        EvaluationCase(
            input="eggs",
            expected_ingredient_id="eggs",
            category="canonical",
        ),
        EvaluationCase(
            input="black bean",
            expected_ingredient_id="black-beans",
            category="alias",
        ),
        EvaluationCase(
            input="eggplant",
            expected_ingredient_id=None,
            category="unresolved",
        ),
    )
    predictions = {
        "eggs": "eggs",
        "black bean": None,
        "eggplant": "eggs",
    }

    metrics = evaluate_resolver(cases, predictions.get)

    assert (
        metrics.true_positives,
        metrics.false_positives,
        metrics.false_negatives,
        metrics.true_negatives,
    ) == (1, 1, 1, 0)
    assert metrics.precision == 0.5
    assert metrics.recall == 0.5
```

Run:

```powershell
uv run pytest tests/test_evaluation.py::test_evaluate_resolver_counts_correct_resolutions_abstentions_and_over_resolution -v
```

Expected: PASS if Step 2 is correct. Treat any failure as a metric defect and
fix it before proceeding.

- [ ] **Step 4: Add the Feature 001 exact-name baseline RED**

Add this exact temporary missing-symbol guard:

```python
try:
    from pantrypilot.evaluation import resolve_exact_name
except ImportError as exc:
    if "cannot import name 'resolve_exact_name'" not in str(exc):
        raise
    resolve_exact_name = None
```

Then add:

```python
@pytest.mark.parametrize(
    ("value", "expected_id"),
    [
        (" BLACK BEANS ", "black-beans"),
        ("black bean", None),
        ("eggplant", None),
    ],
)
def test_exact_name_baseline_uses_normalized_canonical_names_only(
    value, expected_id
):
    if resolve_exact_name is None:
        pytest.fail("expected production behavior is not implemented")

    assert resolve_exact_name(value, INGREDIENT_REGISTRY) == expected_id
```

Run:

```powershell
uv run pytest tests/test_evaluation.py::test_exact_name_baseline_uses_normalized_canonical_names_only -v
```

Expected RED: baseline function is absent.

Implement without scanning aliases as candidates:

```python
def resolve_exact_name(
    value: str,
    ingredient_registry: IngredientRegistry,
) -> str | None:
    normalized = normalize_ingredient(value)
    ingredient_id = ingredient_registry.by_term.get(normalized)
    if ingredient_id is None:
        return None
    ingredient = ingredient_registry.by_id[ingredient_id]
    return ingredient_id if normalized == ingredient.canonical_name else None
```

Remove the temporary guard and in-test `None` check and restore this complete
ordinary top-level import before rerunning GREEN:

```python
from pantrypilot.evaluation import (
    EvaluationCase,
    evaluate_resolver,
    load_evaluation_fixture,
    resolve_exact_name,
)
```

Rerun and expect PASS.

- [ ] **Step 5: Add the approved comparison RED**

Add this exact temporary missing-symbol guard:

```python
try:
    from pantrypilot.evaluation import compare_resolvers
except ImportError as exc:
    if "cannot import name 'compare_resolvers'" not in str(exc):
        raise
    compare_resolvers = None
```

Then add:

```python
def test_v1_comparison_improves_recall_with_zero_false_positives():
    if compare_resolvers is None:
        pytest.fail("expected production behavior is not implemented")

    fixture = load_evaluation_fixture(FIXTURE_PATH, INGREDIENT_REGISTRY)

    comparison = compare_resolvers(fixture, INGREDIENT_REGISTRY)

    baseline = comparison.exact_name_baseline
    resolver = comparison.canonical_alias_resolver
    assert (
        baseline.true_positives,
        baseline.false_positives,
        baseline.false_negatives,
        baseline.true_negatives,
    ) == (14, 0, 7, 7)
    assert baseline.precision == 1.0
    assert baseline.recall == 0.6667
    assert [case.input for case in baseline.false_negative_cases] == [
        "egg",
        "black bean",
        "corn tortilla",
        "peanut",
        "lentil",
        "carrot",
        "vegetable stock",
    ]
    assert (
        resolver.true_positives,
        resolver.false_positives,
        resolver.false_negatives,
        resolver.true_negatives,
    ) == (21, 0, 0, 7)
    assert resolver.precision == 1.0
    assert resolver.recall == 1.0
    assert resolver.false_positive_cases == ()
    assert resolver.false_negative_cases == ()
    assert comparison.recall_improved is True
    assert comparison.zero_false_positives is True
```

Run:

```powershell
uv run pytest tests/test_evaluation.py::test_v1_comparison_improves_recall_with_zero_false_positives -v
```

Expected RED: comparison function/model is absent.

- [ ] **Step 6: Implement same-fixture comparison**

Add:

```python
from functools import partial

from pantrypilot.ingredients import resolve_ingredient


class ResolverComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fixture_schema_version: int
    exact_name_baseline: ResolutionMetrics
    canonical_alias_resolver: ResolutionMetrics
    recall_improved: bool
    zero_false_positives: bool


def _resolve_canonical_alias(
    value: str,
    ingredient_registry: IngredientRegistry,
) -> str | None:
    return resolve_ingredient(value, ingredient_registry).ingredient_id


def compare_resolvers(
    fixture: EvaluationFixture,
    ingredient_registry: IngredientRegistry,
) -> ResolverComparison:
    baseline = evaluate_resolver(
        fixture.cases,
        partial(resolve_exact_name, ingredient_registry=ingredient_registry),
    )
    resolver = evaluate_resolver(
        fixture.cases,
        partial(_resolve_canonical_alias, ingredient_registry=ingredient_registry),
    )
    return ResolverComparison(
        fixture_schema_version=fixture.schema_version,
        exact_name_baseline=baseline,
        canonical_alias_resolver=resolver,
        recall_improved=resolver.recall > baseline.recall,
        zero_false_positives=resolver.false_positives == 0,
    )
```

Remove the temporary guard and in-test `None` check and restore this complete
ordinary top-level import before rerunning GREEN:

```python
from pantrypilot.evaluation import (
    EvaluationCase,
    compare_resolvers,
    evaluate_resolver,
    load_evaluation_fixture,
    resolve_exact_name,
)
```

Both calls must receive the exact same `fixture.cases` object. Rerun the named
test and expect PASS.

- [ ] **Step 7: Add successful CLI output RED**

Add this exact temporary missing-symbol guard:

```python
try:
    from pantrypilot.evaluation import main
except ImportError as exc:
    if "cannot import name 'main'" not in str(exc):
        raise
    main = None
```

Then add:

```python
def test_evaluation_cli_prints_deterministic_comparison_json(capsys):
    if main is None:
        pytest.fail("expected production behavior is not implemented")

    exit_code = main([str(FIXTURE_PATH)])

    first_output = capsys.readouterr().out
    assert exit_code == 0
    parsed = json.loads(first_output)
    assert parsed["exact_name_baseline"]["recall"] == 0.6667
    assert parsed["canonical_alias_resolver"]["recall"] == 1.0
    assert parsed["recall_improved"] is True
    assert parsed["zero_false_positives"] is True

    assert main([str(FIXTURE_PATH)]) == 0
    assert capsys.readouterr().out == first_output
```

Run:

```powershell
uv run pytest tests/test_evaluation.py::test_evaluation_cli_prints_deterministic_comparison_json -v
```

Expected RED: CLI function is absent.

- [ ] **Step 8: Implement the standard-library CLI success path**

Add:

```python
import argparse

from pantrypilot.ingredients import INGREDIENT_REGISTRY


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate PantryPilot ingredient resolution."
    )
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args(argv)
    fixture = load_evaluation_fixture(args.fixture, INGREDIENT_REGISTRY)
    comparison = compare_resolvers(fixture, INGREDIENT_REGISTRY)
    print(comparison.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Remove the temporary guard and in-test `None` check and restore this complete
ordinary top-level import before rerunning GREEN:

```python
from pantrypilot.evaluation import (
    EvaluationCase,
    compare_resolvers,
    evaluate_resolver,
    load_evaluation_fixture,
    main,
    resolve_exact_name,
)
```

Rerun and expect PASS.

- [ ] **Step 9: Add CLI acceptance-threshold failure RED**

Add:

```python
def test_evaluation_cli_fails_when_an_acceptance_threshold_is_missed(
    tmp_path, capsys
):
    no_improvement_path = write_fixture(
        tmp_path,
        {
            "schema_version": 1,
            "cases": [
                {
                    "input": "eggplant",
                    "expected_ingredient_id": "eggs",
                    "category": "alias",
                }
            ],
        },
    )

    exit_code = main([str(no_improvement_path)])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["recall_improved"] is False

    false_positive_path = tmp_path / "false-positive.json"
    false_positive_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cases": [
                    {
                        "input": "black bean",
                        "expected_ingredient_id": "black-beans",
                        "category": "alias",
                    },
                    {
                        "input": "egg",
                        "expected_ingredient_id": None,
                        "category": "unresolved",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([str(false_positive_path)])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert output["recall_improved"] is True
    assert output["zero_false_positives"] is False
```

Run:

```powershell
uv run pytest tests/test_evaluation.py::test_evaluation_cli_fails_when_an_acceptance_threshold_is_missed -v
```

Expected RED before the final return-condition branch: CLI returns success for
both failing fixtures. Replace `return 0` with:

```python
return (
    0
    if comparison.recall_improved and comparison.zero_false_positives
    else 1
)
```

Rerun and expect PASS.

- [ ] **Step 10: Add concise invalid-fixture CLI handling**

Add this test before catching loader errors:

```python
def test_evaluation_cli_reports_invalid_fixture_without_traceback(
    tmp_path, capsys
):
    path = tmp_path / "invalid.json"
    path.write_text("{", encoding="utf-8")

    exit_code = main([str(path)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert json.loads(captured.err)["error"].startswith(
        "invalid evaluation fixture:"
    )
```

Run:

```powershell
uv run pytest tests/test_evaluation.py::test_evaluation_cli_reports_invalid_fixture_without_traceback -v
```

Expected RED: `JSONDecodeError` escapes and produces a traceback.

Import `sys` and Pydantic's `ValidationError`, then wrap only fixture loading:

```python
try:
    fixture = load_evaluation_fixture(args.fixture, INGREDIENT_REGISTRY)
except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
    print(
        json.dumps(
            {"error": f"invalid evaluation fixture: {exc}"},
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    return 2
```

Do not catch metric/programming defects. Rerun and expect PASS.

- [ ] **Step 11: Run the real evaluation command and inspect errors**

Run:

```powershell
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
```

Expected JSON:

- baseline `(TP, FP, FN, TN) = (14, 0, 7, 7)`;
- baseline precision `1.0`, recall `0.6667`;
- baseline false negatives are the seven alias rows;
- resolver `(TP, FP, FN, TN) = (21, 0, 0, 7)`;
- resolver precision and recall `1.0`;
- resolver false-positive and false-negative arrays are empty;
- both acceptance booleans are `true`;
- process exit code is zero.

- [ ] **Step 12: Run Task 5 focused and broader checks**

Run:

```powershell
uv run pytest tests/test_evaluation.py -v
uv run pytest -v
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: all tests and checks pass and the fixture-consistency test from Task
4 remains green.

- [ ] **Step 13: Commit Task 5, then independently review its commit range**

Use the `TASK_BASE` recorded before Step 1. After Steps 11-12 are green,
inspect the exact intended diff:

```powershell
git diff -- src/pantrypilot/evaluation.py tests/test_evaluation.py
```

Then stage only those files and make the planned task commit:

```powershell
git add src/pantrypilot/evaluation.py tests/test_evaluation.py
git commit -m "feat: evaluate ingredient resolution against baseline"
git rev-parse HEAD
```

Record that final command's output as `TASK_HEAD`. Using the
`superpowers:subagent-driven-development` review-package workflow, require
independent specification-compliance and code-quality reviews of
`TASK_BASE..TASK_HEAD` for fair same-fixture comparison, exact metric
definitions, deterministic output, one-pass counting, zero-denominator
handling, inspectable errors, and CLI exit behavior.

For any Critical or Important finding, follow the Global Constraints fix loop,
using focused TDD for behavior changes and
`fix: address resolution evaluation review findings` for each focused
correction commit. Run scoped re-review against each recorded `FIX_BASE..HEAD`
range until the reviewers clear all Critical and Important findings. Do not
amend or squash the task or fix commits. Only then mark Task 5 complete.

---

### Task 6: Record the Approved Roadmap Sequence

**Files:**

- Modify: `docs/roadmap.md`
- Modify: `docs/product/vision.md`

**Interfaces:**

- Consumes: the owner-approved Feature 002 -> Feature 003 -> later retrieval
  amendment.
- Produces: consistent committed roadmap and vision ordering without bringing
  any later feature into this implementation.

- [ ] **Step 1: Replace roadmap Phases 2–4 with the approved sequence**

In `docs/roadmap.md`, replace the current persistence/entity-resolution blocks
with these exact stages:

```markdown
## Phase 2: Measured ingredient entity resolution

- Introduce stable canonical ingredient IDs and human-readable names.
- Resolve canonical terms and a small explicit alias registry deterministically.
- Keep unsupported terms unresolved and apply the same identities to pantry
  matching and hard exclusions.
- Compare resolution with the normalized exact-name baseline on a versioned
  labeled fixture.

Evidence: complete catalog coverage, inspectable resolution evidence, zero
false-positive resolutions on the approved fixture, and strictly higher recall
than the exact-name baseline.

## Phase 3: Persistence and durable data contracts

- Persist recipes, pantry state, and ranking requests using established
  canonical ingredient identities.
- Add schema migrations and stable identifiers.
- Separate domain behavior from storage without changing ranking semantics.
- Add production-oriented API error handling and request tracing.

Evidence: migration tests, contract tests, and equivalent ranking results across
in-memory and persisted data.

## Phase 4: Retrieval at meaningful catalog scale

- Grow the recipe catalog only when representative product needs justify it.
- Retrieve candidate recipes efficiently before applying ranking.
- Measure candidate recall and latency against a full-catalog baseline.
- Preserve canonical ingredient and hard-constraint behavior through retrieval.

Evidence: a representative catalog-scale benchmark, retrieval recall and
latency metrics, and unchanged eligibility for hard exclusions.
```

Renumber the existing stages without otherwise changing their scope:

- current food-waste/optimization Phase 4 -> Phase 5;
- current personalization Phase 5 -> Phase 6;
- current learned ranking Phase 6 -> Phase 7;
- current LLM/tool Phase 7 -> Phase 8.

Move the old entity-resolution-phase quantity/unit bullet into the first Phase
5 pantry-state bullet so it reads:

```markdown
- Track pantry ingredient quantities, units, purchase dates, and estimated
  spoilage windows.
```

No Feature 002 code or current-status claim belongs in this roadmap edit.

- [ ] **Step 2: Correct the one product-vision sequence paragraph**

Replace the first paragraph under `## Intended system evolution` with:

```markdown
PantryPilot begins with an in-memory recipe catalog and transparent weighted
ranking. The system then gains measured ingredient entity resolution so later
persistence can store stable canonical identities. Persistence and durable data
contracts follow without changing ranking semantics. Retrieval is introduced
only when catalog scale makes full-catalog ranking meaningfully inefficient.
Once those foundations are reliable, the system can support multi-meal planning
and constrained food-waste optimization.
```

Leave all other product principles and long-term capabilities unchanged.

- [ ] **Step 3: Verify sequence consistency and scope**

Run:

```powershell
rg -n "Phase [2-8]:|entity resolution|Persistence|Retrieval|quantities|units" docs/roadmap.md
rg -n "entity resolution|Persistence|Retrieval|multi-meal" docs/product/vision.md
rg -n "fuzzy|embedding|LLM ingredient|database migration" docs/roadmap.md docs/product/vision.md
git diff --check
uv run pytest -q
```

Expected:

- roadmap phases are numbered 2 through 8 exactly once and in the approved
  order;
- entity resolution precedes persistence, which precedes retrieval;
- quantities and units occur in the later planning stage, not Feature 002;
- the non-goal scan finds only pre-existing future-roadmap concepts in their
  later approved phases, not Feature 002 commitments;
- no whitespace errors exist.
- the full regression suite still passes.

- [ ] **Step 4: Commit Task 6, then independently review its commit range**

Use the `TASK_BASE` recorded before Step 1. After Step 3 is green, inspect the
exact intended diff:

```powershell
git diff -- docs/roadmap.md docs/product/vision.md
```

Then stage only those files and make the planned task commit:

```powershell
git add docs/roadmap.md docs/product/vision.md
git commit -m "docs: sequence entity resolution before persistence"
git rev-parse HEAD
```

Record that final command's output as `TASK_HEAD`. Using the
`superpowers:subagent-driven-development` review-package workflow, require
independent specification-compliance and code-quality reviews of
`TASK_BASE..TASK_HEAD` for the exact approved amendment, minimal wording,
phase consistency, and absence of accidental scope changes.

For any Critical or Important finding, follow the Global Constraints fix loop.
If a finding exposes a behavior regression, use focused TDD; otherwise make the
minimum documentation correction. Use
`docs: address roadmap sequence review findings` for each focused correction
commit. Run scoped re-review against each recorded `FIX_BASE..HEAD` range until
the reviewers clear all Critical and Important findings. Do not amend or
squash the task or fix commits. Only then mark Task 6 complete.

---

### Task 7: Learning Guide, README, Verification, and Whole-Branch Review

**Files:**

- Create: `docs/learning/002-ingredient-entity-resolution.md`
- Modify: `README.md`

**Interfaces:**

- Consumes: implemented code, passing tests, the approved design, and fresh
  Task 5 evaluation output.
- Produces: complete learning documentation, current repository status, exact
  commands, mock-interview guidance, exactly two exercises, final verification
  evidence, and broad independent review.

- [ ] **Step 1: Capture fresh evaluation and verification facts for prose**

Run before writing measured claims:

```powershell
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
uv run pytest tests/test_normalization.py tests/test_ingredients.py tests/test_catalog.py tests/test_ranking.py tests/test_api.py tests/test_evaluation.py -q
```

Expected evaluation facts to record exactly:

- fixture v1 has 28 cases: 14 canonical, seven aliases, seven unresolved;
- baseline: TP 14, FP 0, FN 7, TN 7, precision `1.0000`, recall `0.6667`;
- resolver: TP 21, FP 0, FN 0, TN 7, precision `1.0000`, recall `1.0000`;
- baseline errors are the seven explicit aliases;
- Feature 002 has strictly higher recall and zero false positives.

If fresh output differs, stop and diagnose the implementation or fixture. Do
not adjust the learning prose or acceptance threshold to hide the difference.

- [ ] **Step 2: Write every required learning section**

Create `docs/learning/002-ingredient-entity-resolution.md` with these exact
top-level sections and project-specific content:

```markdown
# Feature 002: Measured ingredient entity resolution

## What we built
Explain the 14-entity immutable registry, seven explicit aliases, ID-based
catalog, shared resolver, structured evidence, fail-closed exclusions, v1
fixture, baseline comparison, and unchanged ranking formula.

## Why it exists
Explain Feature 001's normalized string equality, the black-bean plural miss,
why identity differs from normalization, and why a measured deterministic step
precedes heuristics or learned resolution.

## Architecture / data flow
Trace raw validated request terms -> text normalization -> canonical/alias exact
lookup or abstention -> pantry/exclusion ID sets -> fail-closed exclusion check
-> recipe ID eligibility/matching -> canonical-name evidence -> unchanged score,
explanation, ordering, and API serialization.

## File-by-file responsibilities
Explain normalization.py, ingredients.py, models.py, catalog.py, ranking.py,
app.py, evaluation.py, the JSON fixture, all six test files, the approved
design and implementation plan, roadmap/vision, README, and this learning
guide.

## Core algorithms and concepts
Define normalization versus resolution, stable canonical identity, canonical
name, explicit alias, abstention, determinism, precision, recall, TP, FP, FN,
TN, wrong-identity double counting, fair baseline comparison, and hard-
constraint safety. State explicitly that there is no generic plural rule.

## Worked examples
Show: canonical `black beans`; alias `black bean`; unresolved `black bean
sauce`; `vegetable stock` -> `vegetable-broth`; `peanut` exclusion blocking
Peanut Noodles; and unresolved `groundnut` producing 422 rather than an unsafe
ranking. Work the taco score from 3/4 and 0.7417 to 4/4 and 0.9167 with every
returned contribution.

## Evaluation
Describe the fixture schema/version, registry-coverage/category-consistency
test, exact-name baseline, same-fixture comparison, metric formulas and count
rules, the fresh results from Step 1, seven baseline false negatives, zero
resolver errors, and the limitation that a small alias-complete curated fixture
does not estimate real-world prevalence or production recall.

## Testing strategy
Explain what normalization, registry/resolver, catalog, ranking, API,
evaluation, and full-regression tests each prove and why local fixtures isolate
rules from application data.

## Common failure cases
Explain over-resolution, unsupported inputs, duplicate IDs, invalid ID format,
same-entity duplicate aliases, cross-identity term collisions, orphan recipe
IDs, duplicate recipe IDs, unsafe ignored exclusions, evidence/data mismatch,
and registry/fixture drift.

## Commands
Include the exact commands listed in Step 3 below.

## Mock interview
Include the ten questions and guided answers listed in Step 4 below.

## Exercises
Include exactly the two exercises listed in Step 5 below.

## Concepts required before merge
Include the checklist listed in Step 6 below.
```

Replace each instruction above with concise explanatory prose. Do not leave
imperative planning text in the learning document.

- [ ] **Step 3: Include exact setup, test, evaluation, and run commands**

The learning guide's `## Commands` section must include:

```powershell
uv sync --locked --python 3.12
uv run pytest tests/test_normalization.py -v
uv run pytest tests/test_ingredients.py -v
uv run pytest tests/test_catalog.py -v
uv run pytest tests/test_ranking.py -v
uv run pytest tests/test_api.py -v
uv run pytest tests/test_evaluation.py -v
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
uv run pytest
uv run ruff format --check .
uv run ruff check .
git diff --check
uv run uvicorn pantrypilot.app:app --app-dir src
```

Explain which commands are focused checks, full verification, evaluation, and
local application startup.

- [ ] **Step 4: Write at least eight substantive mock-interview questions**

Use these ten questions with concise guided answers:

1. **How is normalization different from entity resolution?** Normalization
   changes surface form deterministically; resolution maps supported different
   forms to one identity.
2. **Why store recipe ingredient IDs instead of canonical names?** Names can
   change for display, while stable IDs preserve references and future durable
   contracts.
3. **Why are singular/plural forms explicit aliases?** A general rule can merge
   distinct foods and is unsafe for exclusions; explicit mappings are reviewed
   and measurable.
4. **Why is abstention valuable?** It prevents guesses from increasing false
   positives and makes unsupported coverage visible.
5. **Why must pantry and exclusions share a resolver?** Different identity
   systems could allow an alias to match positively while bypassing the same
   hard exclusion.
6. **Why reject an unresolved exclusion?** Returning results would imply a hard
   safety constraint was enforced when the system could not identify it.
7. **How are wrong-identity predictions counted?** They add one FP for the
   incorrect entity and one FN for missing the expected entity.
8. **Why compare against normalized exact names on the same fixture?** It
   isolates the improvement supplied by aliases and prevents dataset
   differences from confounding metrics.
9. **Why does 1.0000 fixture recall not prove production readiness?** The
   fixture is small, curated, and contains all approved aliases; real input
   distribution and vocabulary are broader.
10. **Why implement entity identity before persistence?** Persistence should
    store stable canonical references rather than freeze ambiguous display
    strings into a durable schema.

- [ ] **Step 5: Include exactly two owner exercises**

Use exactly these exercises and no third numbered or unnumbered exercise:

1. Propose one sensible alias and two confusable negative terms, update the
   registry and fixture with strict TDD, and explain how the coverage/category
   test prevents registry/fixture drift.
2. Construct a synthetic wrong-identity evaluation case by hand, calculate its
   TP/FP/FN/TN effect, then add a local evaluator test and compare the output.

- [ ] **Step 6: Add the explicit concepts-before-merge checklist**

The final checklist must require the owner to explain:

- normalization versus resolution;
- stable ID versus canonical display name;
- explicit aliases and collision validation;
- conservative abstention;
- shared pantry/exclusion identities and fail-closed exclusions;
- recipe-ID/catalog integrity;
- TP, FP, FN, TN, precision, and recall;
- why wrong identity counts as FP and FN;
- fair same-fixture baseline comparison;
- fixture coverage/category consistency;
- why the measured results are limited to the curated fixture;
- unchanged scoring, explanations, ordering, and hard filters;
- strict TDD and independent review boundaries.

- [ ] **Step 7: Update README current status and links**

Replace the Feature 001-only current status with concise text stating that
Feature 002 is implemented, recipes now use canonical ingredient identities,
explicit aliases are resolved deterministically, unsupported terms abstain,
and evaluation improves recall over the Feature 001 baseline with zero false
positives on the v1 fixture. Do not copy the full architecture or metric table.

Under project documents, retain Feature 001 links and add relative links to:

```text
docs/superpowers/specs/2026-08-08-ingredient-entity-resolution-design.md
docs/learning/002-ingredient-entity-resolution.md
```

Add the evaluation command after the existing quick-start commands:

```powershell
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
```

- [ ] **Step 8: Verify learning-document completeness mechanically**

Run:

```powershell
rg -n "What we built|Why it exists|Architecture / data flow|File-by-file responsibilities|Core algorithms and concepts|Worked examples|Evaluation|Testing strategy|Common failure cases|Commands|Mock interview|Exercises|Concepts required before merge" docs/learning/002-ingredient-entity-resolution.md
rg -n "normalization|canonical identity|alias|abstention|precision|recall|false positive|false negative|hard constraint|0.7417|0.9167|0.6667|1.0000" docs/learning/002-ingredient-entity-resolution.md
rg -n "uv sync --locked|test_ingredients|test_evaluation|pantrypilot.evaluation|ruff format --check|ruff check|git diff --check" docs/learning/002-ingredient-entity-resolution.md
rg -n "Feature 002|ingredient-entity-resolution-design|002-ingredient-entity-resolution|pantrypilot.evaluation" README.md
rg -n "T[B]D|T[O]DO|F[I]XME|implement la[t]er|fill i[n]|similar t[o]" docs/learning/002-ingredient-entity-resolution.md README.md
```

Expected: every required heading, concept, metric, command, and README link is
found; the unfinished-marker scan has no matches. Manually confirm `Exercises` has
exactly two exercises and `Mock interview` has ten questions.

- [ ] **Step 9: Invoke verification-before-completion and run fresh checks**

Read and apply `superpowers:verification-before-completion`, then run from the
worktree root:

```powershell
uv --version
uv python find 3.12
uv lock --check
uv sync --locked --python 3.12
uv run python --version
uv run pytest tests/test_normalization.py -v
uv run pytest tests/test_ingredients.py -v
uv run pytest tests/test_catalog.py -v
uv run pytest tests/test_ranking.py -v
uv run pytest tests/test_api.py -v
uv run pytest tests/test_evaluation.py -v
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
uv run pytest -v
uv run ruff format --check .
uv run ruff check .
git diff --check
git status --short --branch
```

Expected evidence:

- Python is 3.12.x and `uv.lock` is current and unchanged;
- every focused group and the full suite pass;
- evaluation prints the exact approved counts/metrics and exits zero;
- Ruff formatting/lint and whitespace checks pass;
- status lists only the intended learning guide and README before their commit.

- [ ] **Step 10: Audit scope and dependencies**

Run:

```powershell
uv tree
rg -n "sqlalchemy|database|migration|repository|service class|factory|embedding|vector|openai|anthropic|fuzzy|levenshtein|stem|lemma|docker|auth" src tests pyproject.toml
git diff --stat 9eaf6f0
git diff 9eaf6f0 -- pyproject.toml uv.lock
```

Expected: no new direct dependency or lockfile change; no non-goal technology
in source/tests; the branch diff is limited to the approved code, fixture,
tests, review artifacts, roadmap/vision, README, and learning document.

- [ ] **Step 11: Commit Task 7, then independently review its commit range**

Use the `TASK_BASE` recorded before Step 1. After Steps 8-10 are green, inspect
the exact intended diff:

```powershell
git diff -- docs/learning/002-ingredient-entity-resolution.md README.md
```

Then stage only those files and make the planned task commit:

```powershell
git add docs/learning/002-ingredient-entity-resolution.md README.md
git commit -m "docs: explain measured ingredient resolution"
git rev-parse HEAD
```

Record that final command's output as `TASK_HEAD`. Using the
`superpowers:subagent-driven-development` review-package workflow, require
independent specification-compliance and code-quality reviews of
`TASK_BASE..TASK_HEAD` for every learning requirement, technical accuracy,
interview usefulness, command accuracy, metric honesty, exactly two exercises,
and consistency with implemented code.

For any Critical or Important finding, follow the Global Constraints fix loop.
If a finding exposes a behavior or command defect, use focused TDD or an
executable command check as appropriate; otherwise make the minimum prose
correction. Use `docs: address ingredient resolution learning review findings`
for each focused correction commit. Run scoped re-review against each recorded
`FIX_BASE..HEAD` range until the reviewers clear all Critical and Important
findings. Do not amend or squash the task or fix commits. Only then mark Task 7
complete and continue to final whole-branch verification.

- [ ] **Step 12: Run fresh post-commit verification**

Invoke `superpowers:verification-before-completion` again and rerun:

```powershell
uv lock --check
uv run pytest
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
uv run ruff format --check .
uv run ruff check .
git diff --check
git status --short --branch
```

Expected: all commands pass, metrics remain exact, and the branch is clean.

- [ ] **Step 13: Require broad whole-branch independent reviews**

Request two fresh read-only reviewers over the approved design and
`git diff 9eaf6f0...HEAD`:

1. specification-compliance reviewer: every approved behavior, acceptance
   criterion, non-goal, documentation requirement, and fixture label;
2. code-quality reviewer: correctness, hard-constraint safety, validation,
   dependency direction, simplicity, deterministic behavior, test quality,
   API compatibility, evaluation math, and owner explainability.

Reviewers report findings in severity order with file/line references. If any
Critical or Important finding remains, record `BRANCH_FIX_BASE` at the current
`HEAD`, reopen the responsible task, add a focused failing test where behavior
changes, make the minimum fix, rerun the relevant scoped checks, and inspect
the exact fix diff. Before staging, write out a literal `git add` command
containing only the confirmed paths shown by that diff; do not use a wildcard
or stage the whole worktree. Commit the correction before re-review:

```powershell
git commit -m "fix: address ingredient resolution review findings"
```

Then rerun Step 12, request scoped re-review of
`BRANCH_FIX_BASE..HEAD`, and repeat the fix-commit/re-review loop as necessary.
After scoped findings are clear, rerun both whole-branch reviews against the
updated `9eaf6f0...HEAD`. Do not amend or squash any task or review-fix commit.

Do not claim Feature 002 complete until both reviewers report no remaining
critical or important findings and fresh verification passes. This internal
review supplements rather than replaces the owner's later Claude Code review.

---

## Planned Commit Boundaries

| Boundary | Deliverable | Conventional commit |
|---|---|---|
| 0 | Approved Feature 002 design | `docs: design measured ingredient resolution` |
| 0a | Approved implementation plan | `docs: plan measured ingredient resolution` |
| 1 | Single-term normalization and validated immutable registry | `feat: add validated ingredient registry` |
| 2 | Resolution evidence and approved application identities | `feat: add deterministic ingredient resolver` |
| 3 | ID-based catalog/ranking, shared exclusions, API evidence | `feat: rank recipes by canonical ingredient identity` |
| 4 | Versioned fixture, validation, full registry/category consistency | `test: add ingredient resolution evaluation fixture` |
| 5 | Exact-name baseline, metrics, error analysis, comparison CLI | `feat: evaluate ingredient resolution against baseline` |
| 6 | Approved entity-resolution-before-persistence sequence | `docs: sequence entity resolution before persistence` |
| 7 | Learning guide, README, commands, interview material | `docs: explain measured ingredient resolution` |
| Task review fix, only if required | Confirmed task-scoped corrections retained after the initial task commit | Task-specific message stated in Tasks 1-7 |
| Whole-branch review fix, only if required | Confirmed final-review corrections | `fix: address ingredient resolution review findings` |

No planned commit includes `pyproject.toml` or `uv.lock`. No commit is pushed
without separate owner authorization.

## Acceptance and Test Coverage Map

| Requirement | Planned evidence |
|---|---|
| Stable machine IDs and canonical names | Task 1 record/index tests; Task 2 exact application registry |
| Complete current-catalog identity coverage | Task 3 loader/approved catalog tests |
| Invalid registry data rejected | Task 1 ID, blank, unknown-field, duplicate, and collision rules |
| Invalid catalog identity data rejected | Task 3 unknown/duplicate required-ID tests |
| Canonical resolution | Task 2 canonical evidence test |
| Explicit alias resolution | Task 2 alias evidence test |
| Unsupported terms abstain | Task 2 unresolved evidence and fixture negative tests |
| Pantry resolves before matching | Task 3 integrated taco/evidence test |
| Same resolver for exclusions | Task 3 `peanut` alias evidence and blocked recipe |
| Supported exclusion alias is hard | Task 3 domain and API result assertions |
| Unresolved exclusion fails closed | Task 3 domain exception and exact API `422` |
| Canonical Feature 001 compatibility | Existing regressions plus Task 3 exact score/order assertion |
| Weights/formula unchanged | Existing scoring tests and taco `0.7417`/`0.9167` controls |
| Reconstructable scores | Existing Decimal/contribution tests and taco contributions |
| Inspectable resolution evidence | Task 2 model tests and Task 3 exact API evidence |
| Determinism | Task 2 repeated lookup, existing repeated request, Task 5 repeated CLI output |
| Versioned labeled fixture | Task 4 schema/version and exact JSON |
| Same fixture for both systems | Task 5 `compare_resolvers` passes `fixture.cases` to both evaluators |
| Strictly higher recall | Task 5 baseline `0.6667`, resolver `1.0000`, comparison boolean |
| Zero Feature 002 false positives | Task 5 counts, empty error tuple, CLI exit guard |
| All registered terms covered by fixture | Task 4 owner-required set-equality test |
| Fixture categories agree with registry | Task 4 owner-required resolver/category loop |
| Focused domain tests | Tasks 1–5 normalization, registry, catalog, ranking, evaluation tests |
| API contract tests | Task 3 evidence, alias exclusion, unresolved `422`, compatibility |
| Feature 001 regressions | Existing full suite retained and run at every broader boundary |
| Roadmap sequence | Task 6 heading/content scans and review |
| Complete learning document | Task 7 content scans, ten interview questions, exactly two exercises |
| No non-goal technology | Global constraints, dependency/diff scans, every independent review |
| Final verification | Task 7 fresh lock, tests, evaluation, Ruff, diff, and status output |

## Plan Self-Review Checklist

- [x] Every approved design section maps to a named task, test, command, and
  review boundary.
- [x] All eleven initial missing-module or missing-symbol REDs have exact
  test-side guards, explicit `pytest.fail` assertions, and exact instructions
  to restore ordinary top-level imports before GREEN verification and commit.
- [x] Task 1 proves both `IngredientRegistry.by_id` and
  `IngredientRegistry.by_term` reject mutation.
- [x] The owner-requested fixture coverage/category-consistency assertion is an
  explicit test with full registered-term set equality and per-case resolver
  checks, not a count-only approximation.
- [x] Final names and types are consistent across registry, catalog, ranking,
  API, evaluation, tests, and documentation.
- [x] The recipe-ID migration and dependent ranking/API changes share one
  vertical task so no planned commit leaves the branch broken.
- [x] Each production behavior has an explicit RED command, minimum GREEN
  implementation, focused pass, broader pass, task commit, immutable
  `TASK_BASE..TASK_HEAD` review, and committed fix/re-review boundary.
- [x] Existing Feature 001 regression behavior is preserved rather than
  rewritten around new expected scores.
- [x] The exact taco arithmetic and canonical multi-result score snapshot were
  verified against the current implementation during planning.
- [x] Pantry and exclusions use one resolver; unresolved exclusions fail before
  scoring and expose the same evidence structure.
- [x] The fixture is fixed before metric code and contains all approved terms
  plus confusable negatives.
- [x] Metric definitions handle wrong identities as both FP and FN, define zero
  denominators, retain inspectable cases, and use the same fixture.
- [x] No task adds a dependency, persistence, retrieval, ontology framework,
  heuristic resolution, generated explanation, or other non-goal.
- [x] Roadmap edits implement only the approved sequence amendment.
- [x] Learning documentation includes every required section, ten interview
  questions, exactly two exercises, exact commands, measured results, and
  limitations.
- [x] Every task has independent specification and quality review; final work
  is committed before its recorded-range reviews, review corrections remain as
  separate commits, and final work has separate whole-branch reviews and fresh
  verification.
- [x] The plan contains no unfinished decision or unspecified implementation
  interface.

## Approved Decisions and Remaining Ambiguity

- The design was approved on 2026-08-08 without behavioral changes.
- The explicit fixture coverage/category-consistency test requested at plan
  approval is fully specified in Task 4 and does not alter the approved
  registry or fixture contents.
- The implementation-plan revision changes only executable TDD guard mechanics
  and commit/review sequencing; it does not change feature behavior,
  architecture, aliases, fixture labels, API contracts, metrics, tasks, or
  acceptance criteria.
- Canonical compatibility scores for the existing 45-minute API request were
  freshly measured during planning as `0.7334`, `0.2156`, `0.1964`, and
  `0.1760` in the existing order.
- Registry records remain Python data; the labeled fixture remains JSON.
- Unknown pantry items return evidence and no match; unknown exclusions return
  the fixed fail-closed `422`.
- No design ambiguity remains. Implementation must stop for owner direction if
  repository state or behavior contradicts these approved contracts.
