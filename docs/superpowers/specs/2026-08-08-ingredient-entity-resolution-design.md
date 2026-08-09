# Feature 002: Measured ingredient entity resolution

Status: Approved

Design date: 2026-08-08

Approved: 2026-08-08

## Summary

Feature 002 adds a small deterministic ingredient identity layer between raw
request text and Feature 001's matching rules. A validated registry assigns
each supported ingredient a stable ID, canonical human-readable name, and
explicit aliases. Recipes refer to those IDs internally. Pantry items and
exclusions resolve through the same registry before eligibility or scoring.

The resolver returns an identity only for a normalized canonical name or an
explicit registered alias. Unsupported terms remain unresolved. An unresolved
pantry term contributes no match and is exposed in response evidence. An
unresolved exclusion rejects the ranking request because the system cannot
truthfully enforce that hard constraint.

A small versioned JSON fixture evaluates both Feature 001's normalized
exact-name baseline and the new canonical/alias resolver. The fixture is fixed
in this design before implementation. It includes all current canonical names,
all approved Feature 002 aliases, and deliberately confusable negative cases.

The ranking formula, weights, score rounding, hard preparation-time filter,
fixed explanations, ordering, and post-sort limiting do not change.

## Authority and approved sequencing amendment

The existing repository documents and Feature 001 implementation are the
source of truth. The owner-approved exception is the feature sequence:

```text
Feature 001 deterministic ranking
    -> Feature 002 measured ingredient entity resolution
    -> Feature 003 persistence and durable data contracts
    -> retrieval when catalog scale makes it meaningful
```

The current roadmap and one sentence in the product vision still place
persistence before entity resolution. Feature 002 will make the smallest
documentation correction needed to reflect the approved sequence. Roadmap
Phase 2 becomes measured ingredient entity resolution, Phase 3 becomes
persistence and durable data contracts, and a new Phase 4 contains retrieval
at meaningful catalog scale. The current optimization, personalization,
learned-ranking, and LLM stages shift to Phases 5 through 8 without changing
their content. Quantity and unit work remains deferred to the later planning
stage rather than entering Feature 002. The corresponding product-vision
sentence receives the same ordering correction. This amendment does not bring
persistence or retrieval into Feature 002.

## Verified Feature 001 baseline

The repository currently contains four immutable recipes, a Pydantic request
boundary, and pure ranking helpers. Request and recipe ingredient strings are
trimmed, lowercased, and deduplicated before exact string comparison. The same
normalized-string mechanism handles pantry matches and exclusions.

The existing test suite was run before this design was written: 85 tests pass.
The current implementation also confirms the required Black Bean Tacos
arithmetic for pantry input `black bean`, `corn tortillas`, `avocado`, and
`lime`, with a zero protein target and 30-minute maximum:

| System | Coverage | Pantry contribution | Protein | Time | Final |
|---|---:|---:|---:|---:|---:|
| Feature 001 exact strings | 0.7500 | 0.5250 | 0.2000 | 0.0167 | 0.7417 |
| Feature 002 resolved IDs | 1.0000 | 0.7000 | 0.2000 | 0.0167 | 0.9167 |

The Feature 002 row was calculated with the existing `calculate_score`
function using four matches. It does not assume different weights or rounding.

## Goals

- Give every current catalog ingredient a stable machine-readable ID and a
  canonical display name.
- Resolve normalized canonical terms and a small explicit alias set
  deterministically.
- Abstain on unsupported text rather than guess.
- Use the same resolved IDs for pantry matching and hard exclusions.
- Preserve current result fields and Feature 001 ranking semantics for
  canonical inputs.
- Expose per-request-term resolution evidence, including unresolved terms.
- Reject unsafe ranking when any hard exclusion is unresolved.
- Compare the new resolver objectively with the Feature 001 baseline on one
  versioned labeled fixture.
- Teach canonical identity, abstention, precision, recall, and error analysis
  through tests and learning documentation.

## Non-goals

Feature 002 does not add fuzzy matching, edit distance, stemming,
lemmatization, embeddings, vector search, learned models, model training, LLM
calls, generated explanations, quantities, units, nutrition expansion,
persistence, databases, migrations, CRUD, external APIs, catalog-scale
retrieval, ranking changes, personalization, feedback, optimization,
authentication, frontend work, or Docker.

It also does not create a food ontology, repository/service/factory layer,
dependency-injection framework, registry plugin system, or runtime registry
administration API.

## Considered approaches

### 1. Validated canonical registry and ID-based recipe references

This is the recommended approach. A compact in-code registry owns canonical
ingredients and aliases. Raw catalog records refer to ingredient IDs, while
API results continue to expose canonical names. A registry loader builds
immutable ID and term indexes and rejects collisions before the application
starts.

Advantages:

- Ingredient identity is explicit and durable rather than reconstructed from
  display text.
- Recipe validity is checked once at catalog load.
- Pantry and exclusion matching naturally share one ID set operation.
- Later persistence can store the same IDs without making persistence part of
  this feature.

Cost: the internal `Recipe` shape changes and `RankedRecipe` can no longer
inherit that internal model because the API must keep returning names rather
than internal ID fields. This is a focused separation, not a general domain
layer.

### 2. Keep recipe strings and resolve them during every ranking request

This has a smaller initial diff: recipes retain `required_ingredients`, and
the ranking loop resolves recipe strings alongside request strings.

It is rejected because canonical identity would remain transient, invalid
recipe references would be rediscovered during requests, and the same static
catalog text would be resolved repeatedly. It also leaves a weaker contract
for Feature 003 persistence.

### 3. Extend normalization with singular/plural or synonym heuristics

This could make examples such as `black bean` appear to work with little code.
It is rejected because it has no stable identity, can over-resolve hard
exclusions, makes collisions difficult to validate, and violates the explicit
non-goals. Similar-looking negative examples in the evaluation fixture exist
to demonstrate why this approach is unsafe.

An external JSON registry was also considered. Fourteen canonical entities do
not justify packaging and path-loading behavior for application data. The
registry remains ordinary reviewed Python data; only the evaluation fixture is
external JSON because it is a labeled dataset consumed by an evaluation
command.

## Recommended architecture

```text
HTTP request
    -> existing Pydantic request validation
    -> resolve every pantry and exclusion term once
         normalized canonical name -> canonical ID
         normalized explicit alias -> canonical ID
         otherwise                 -> unresolved
    -> reject request if any exclusion is unresolved
    -> build pantry-ID and exclusion-ID sets
    -> filter recipes by exclusion IDs and preparation time
    -> partition each recipe's required IDs into matched/missing IDs
    -> map result IDs to canonical display names
    -> existing score, explanation, ordering, and limiting rules
    -> response with results and request-term resolution evidence
```

The domain remains pure and receives the immutable catalog and registry as
arguments. FastAPI stays a transport adapter. No storage or service
abstraction is introduced.

## Canonical ingredient registry

### Canonical entity

Each registry record has exactly three fields:

```python
class CanonicalIngredient(BaseModel):
    id: str
    canonical_name: str
    aliases: tuple[str, ...]
```

The model is frozen and rejects unknown fields. IDs use lowercase ASCII
kebab-case (`[a-z0-9]+(?:-[a-z0-9]+)*`). The encoding is intentionally boring:
it is readable in logs and suitable for later durable references. An ID is an
opaque identity after assignment; renaming a canonical display name must not
silently change the ID.

Canonical names and aliases use the existing Feature 001 text normalization:
trim leading/trailing whitespace and lowercase, while preserving internal
whitespace, punctuation, plurality, and wording. The normalized canonical name
is the human-readable name returned by the API.

The application registry contains exactly the identities needed by the current
catalog:

| ID | Canonical name | Explicit Feature 002 aliases |
|---|---|---|
| `eggs` | `eggs` | `egg` |
| `spinach` | `spinach` | none |
| `olive-oil` | `olive oil` | none |
| `black-beans` | `black beans` | `black bean` |
| `corn-tortillas` | `corn tortillas` | `corn tortilla` |
| `avocado` | `avocado` | none |
| `lime` | `lime` | none |
| `noodles` | `noodles` | none |
| `peanuts` | `peanuts` | `peanut` |
| `soy-sauce` | `soy sauce` | none |
| `lentils` | `lentils` | `lentil` |
| `carrots` | `carrots` | `carrot` |
| `celery` | `celery` | none |
| `vegetable-broth` | `vegetable broth` | `vegetable stock` |

These aliases are explicit product decisions, not outputs of a generic plural
rule. For example, registering `carrot` does not cause `carrot cake` to
resolve.

### Registry value and indexes

`load_ingredient_registry(records) -> IngredientRegistry` returns one frozen
standard-library dataclass containing read-only mappings:

- `by_id`: canonical ID to `CanonicalIngredient`;
- `by_term`: normalized canonical name or normalized alias to canonical ID.

`MappingProxyType` prevents callers from mutating the validated indexes. One
value object is justified because passing two unrelated dictionaries could
break their invariant. It is not an interface or plugin abstraction.

### Registry validation

Registry construction rejects deterministically:

- an invalid or duplicate canonical ID;
- a blank canonical name or alias;
- an unknown record field;
- a repeated alias within one entity after normalization;
- an alias equal to its own canonical name after normalization;
- duplicate canonical names across entities;
- any canonical-name/alias or alias/alias collision across identities.

A collision is never resolved by record order. Error messages identify the
normalized term and conflicting IDs without exposing request data or secrets.
The module-level application registry is loaded at import, so invalid committed
registry data prevents application startup.

## Normalization and resolution

Normalization remains a text operation; resolution is an identity operation.
The existing plural and synonym failures exist because normalization cannot
answer whether two different strings mean the same ingredient.

`normalize_ingredient(value: str) -> str` becomes the single-value primitive
for the existing `normalize_ingredients` helper and for registry loading and
resolution. It performs only Feature 001 trim/lower behavior and rejects a
blank result. `normalize_ingredients` retains stable exact deduplication for
its existing callers and tests.

`resolve_ingredient(value, registry) -> IngredientResolution` performs one
normalized exact lookup. Its external evidence shape is:

```python
class IngredientResolution(BaseModel):
    input: str
    normalized: str
    ingredient_id: str | None
    canonical_name: str | None
    match_type: Literal["canonical", "alias", "unresolved"]
```

The invariant is:

- `canonical`: the normalized input equals the entity's canonical name;
- `alias`: the normalized input equals an explicit alias;
- `unresolved`: both identity fields are `None`.

The resolver never returns candidates, confidence, or a closest value. Lookup
is an exact dictionary operation, so identical normalized input and registry
produce identical evidence.

`resolve_ingredients(values, registry)` preserves input order and returns one
evidence record per submitted value, including duplicates. Matching later
deduplicates resolved IDs through a set. Keeping every input occurrence in the
evidence makes normalization and alias behavior inspectable without allowing
duplicates to affect coverage.

## Recipe and catalog relationship to identities

The internal `Recipe` model changes from display strings to:

```python
required_ingredient_ids: tuple[str, ...]
```

The raw four-recipe catalog uses the approved canonical IDs. The catalog loader
accepts the registry explicitly and rejects:

- a required ID absent from the registry;
- duplicate required IDs within a recipe;
- an empty required-ID tuple;
- duplicate recipe IDs or any existing invalid recipe field.

The application constructs the registry first and then calls
`load_catalog(RAW_CATALOG, INGREDIENT_REGISTRY)`. This guarantees complete
current-catalog coverage at startup.

`RankedRecipe` becomes an explicit response model rather than inheriting the
internal `Recipe`. It keeps every existing response field, including
`required_ingredients`, `matched_ingredients`, and `missing_ingredients` as
canonical names. Internal `required_ingredient_ids` are exposed only through
request resolution evidence where they explain a match; they are not added to
every recipe result.

This separation avoids leaking an internal catalog field while preserving the
Feature 001 HTTP result contract.

## Ranking and hard-constraint integration

The pure entry point becomes conceptually:

```python
rank_recipes(request, recipes, ingredient_registry) -> RankingResponse
```

It resolves pantry and exclusion values once, then compares only canonical ID
sets with `Recipe.required_ingredient_ids`.

Pantry behavior:

- resolved canonical names and aliases participate in matching;
- multiple terms resolving to one ID count once;
- unresolved terms do not match and remain visible in evidence.

Exclusion behavior:

- canonical names and aliases build the same exclusion-ID set;
- a recipe containing any excluded ID is ineligible, even if that ID is also
  in the pantry;
- an unresolved excluded term aborts ranking before any recipe is scored.

Rejecting unresolved exclusions is a deliberate fail-closed rule. Ignoring an
unknown pantry term merely misses a positive match; ignoring an unknown allergy
or exclusion could return a recipe the caller believed was blocked. The system
therefore abstains from identity guessing and from making an unsafe ranking.

A single domain exception carries the already-built resolution evidence for
this case. It exists only so the HTTP adapter can map the domain outcome to the
documented `422`; there is no exception hierarchy.

Preparation-time eligibility, protein scoring, weights, contribution rounding,
final-score reconstruction, fixed explanation text, exposed-score/ID sorting,
and post-sort limiting remain exactly as Feature 001 defines them. Matched and
missing canonical names retain recipe ingredient order. Pantry coverage uses
the count of matched required IDs divided by the count of required IDs, which
is arithmetically identical to Feature 001 because catalog validation forbids
duplicate IDs.

## API contract

The request schema and endpoint remain unchanged:

```http
POST /v1/meal-rankings
```

A successful response adds one top-level field:

```json
{
  "results": [],
  "returned_count": 0,
  "ingredient_resolution": {
    "pantry_items": [
      {
        "input": " black bean ",
        "normalized": "black bean",
        "ingredient_id": "black-beans",
        "canonical_name": "black beans",
        "match_type": "alias"
      },
      {
        "input": "mystery ingredient",
        "normalized": "mystery ingredient",
        "ingredient_id": null,
        "canonical_name": null,
        "match_type": "unresolved"
      }
    ],
    "excluded_ingredients": []
  }
}
```

The example omits ranked results only to focus on the additive field. Actual
eligible results retain the complete Feature 001 shape.

When any nonblank exclusion is unresolved, the endpoint returns `422` without
ranking results:

```json
{
  "detail": {
    "type": "unresolved_excluded_ingredients",
    "message": "All excluded ingredients must resolve before ranking.",
    "ingredient_resolution": {
      "pantry_items": [],
      "excluded_ingredients": [
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

The message is fixed transport text, not a generated explanation. Existing
Pydantic request validation errors retain their current standard
`{"detail": [...]}` behavior and non-finite-value serialization handler.
Unexpected failures remain generic `500` responses.

## Feature 001 compatibility

For requests that use current canonical ingredient names:

- recipe eligibility is unchanged;
- matched and missing canonical names are unchanged;
- pantry coverage and all other score values are unchanged;
- explanations are unchanged;
- ordering and limiting are unchanged;
- repeated requests remain deterministic.

The request schema does not change. The successful response has one intentional
additive top-level `ingredient_resolution` field. Existing exact full-response
contract tests will be updated to include it; result objects themselves do not
gain or lose fields.

Internal compatibility is intentionally narrower. `Recipe` stores IDs,
`RankedRecipe` stops inheriting it, `load_catalog` requires a registry, and
`rank_recipes` requires a registry and returns the full response so evidence is
created once. These are repository-internal interfaces with focused tests, not
published API contracts.

## Evaluation fixture

The committed fixture lives at:

```text
evaluations/ingredient-resolution-v1.json
```

Its schema is:

```json
{
  "schema_version": 1,
  "cases": [
    {
      "input": "black bean",
      "expected_ingredient_id": "black-beans",
      "category": "alias"
    }
  ]
}
```

`schema_version` must equal `1`; unknown fields, blank inputs, duplicate
normalized inputs, invalid categories, and expected IDs absent from the
registry are rejected. `category` is one of `canonical`, `alias`, or
`unresolved` and supports grouped error analysis; it does not affect scoring.

The approved v1 fixture contains these 28 cases:

### Canonical terms: 14 expected resolutions

`eggs`, `spinach`, `olive oil`, `black beans`, `corn tortillas`, `avocado`,
`lime`, `noodles`, `peanuts`, `soy sauce`, `lentils`, `carrots`, `celery`, and
`vegetable broth`, each labeled with its canonical ID.

### Explicit aliases: 7 expected resolutions

| Input | Expected ID |
|---|---|
| `egg` | `eggs` |
| `black bean` | `black-beans` |
| `corn tortilla` | `corn-tortillas` |
| `peanut` | `peanuts` |
| `lentil` | `lentils` |
| `carrot` | `carrots` |
| `vegetable stock` | `vegetable-broth` |

### Confusable unsupported terms: 7 expected abstentions

`eggplant`, `black bean sauce`, `tortilla chips`, `peanut oil`, `lentil pasta`,
`carrot cake`, and `vegetable shortening` are labeled with
`expected_ingredient_id: null`.

The positive rows represent current product behavior rather than aliases added
after seeing a score. The negative rows would expose substring, token, or
generic singularization over-resolution. The fixture is intentionally small;
it is coverage evidence for this registry, not an estimate of real-world term
frequency or production quality.

## Baseline and metric definitions

Both systems receive every row from the same parsed fixture:

1. `exact_name_baseline`: apply Feature 001 trim/lower normalization, then
   return an ID only when the normalized text equals a canonical name. Aliases
   are not consulted.
2. `canonical_alias_resolver`: use the Feature 002 registry term index and
   otherwise abstain.

For each case:

- true positive (TP): the expected ID is non-null and prediction equals it;
- false positive (FP): a non-null prediction differs from the expected value,
  including resolving a case labeled unresolved;
- false negative (FN): the expected ID is non-null and prediction differs,
  including abstention or prediction of the wrong ID;
- true negative (TN): both expected value and prediction are null.

A wrong-identity prediction therefore counts as both one FP and one FN: it
introduced an incorrect entity and missed the correct one.

```text
precision = TP / (TP + FP)
recall    = TP / (TP + FN)
```

The evaluator reports TP, FP, FN, TN, four-decimal precision and recall, and
the expected/predicted values for every FP and FN. A zero denominator yields
`0.0`; the approved fixture contains positive labels, so neither approved
system has an undefined denominator.

The fixed fixture implies these contractual expected results, to be confirmed
by fresh evaluation output during implementation and final verification:

| System | TP | FP | FN | TN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| Feature 001 exact-name baseline | 14 | 0 | 7 | 7 | 1.0000 | 0.6667 |
| Feature 002 canonical/alias resolver | 21 | 0 | 0 | 7 | 1.0000 | 1.0000 |

Thus Feature 002 must have strictly higher recall and exactly zero false
positive resolutions. Tests assert the counts, comparison, and inspectable
baseline false negatives rather than checking only rounded metrics.

## Evaluation flow

`pantrypilot.evaluation` owns fixture validation, the baseline resolver,
metric calculation, comparison, and a standard-library `argparse` entry point.
The reproducible command is:

```powershell
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
```

It prints deterministic JSON for both systems and exits nonzero when the new
resolver does not beat baseline recall or has any false positives. Evaluation
logic is pure beneath the file/CLI adapter, so unit tests can pass fixture
objects directly. No dataframe, metrics, CLI, or ML dependency is added.

## Error handling and deterministic behavior

- Invalid registry and catalog data fail application import/startup.
- Invalid evaluation files fail the evaluation command with a concise
  validation error and nonzero exit.
- Valid unknown pantry terms produce successful evidence with no identity.
- Valid unknown exclusion terms produce the documented fail-closed `422`.
- Existing blank-list-item and numeric request validation remains Pydantic
  `422` behavior before resolution.
- Direct dictionary lookup is the only resolution selection mechanism.
- Registry record order cannot choose among conflicts because collisions are
  rejected.
- Evidence preserves request order; matching uses sets of IDs; result
  ingredient order follows the recipe; result ordering follows Feature 001.

## Testing boundaries

### Normalization tests

Prove the new single-value primitive retains Feature 001 trim/lower behavior,
blank rejection, and no punctuation, internal-whitespace, plural, or synonym
heuristics. Existing stable deduplication tests remain.

### Registry and resolver tests

Prove canonical and alias resolution, exact normalization, abstention,
evidence invariants, repeated-input evidence, immutability, duplicate IDs, ID
format validation, duplicate terms, same-entity duplicates, cross-entity
collisions, and unknown fields.

### Catalog tests

Prove all 14 application ingredients are valid registry references, catalog
load fails for an unknown or duplicate required ID, existing recipe validation
still applies, and the loaded collections remain immutable.

### Ranking tests

Prove canonical pantry compatibility, alias matching, ID-level deduplication,
unknown pantry non-matching, alias-based hard exclusion, exclusion precedence,
fail-closed unresolved exclusions, stable canonical-name partitions, unchanged
score math, unchanged tie-breaking, and post-sort limiting. A focused Black
Bean Tacos regression asserts `0.7417` for the standalone baseline calculation
and `0.9167` through the Feature 002 resolver under the documented inputs.

### API tests

Prove the additive resolution evidence contract for canonical, alias,
duplicate, and unresolved pantry terms; the unresolved-exclusion `422`; a
supported exclusion alias blocking the canonical recipe; unchanged result
objects and scores for canonical inputs; existing request validation; empty
eligible results; deterministic requests; and generic `500` secrecy.

### Evaluation tests

Prove fixture schema validation, fair same-fixture comparison, exact TP/FP/FN/TN
definitions including wrong-identity double counting, inspectable error cases,
the approved metric counts, strict recall improvement, zero Feature 002 false
positives, deterministic output, and CLI failure when an acceptance threshold
is not met.

The existing full suite remains the Feature 001 regression layer. No test
asserts fuzzy, inferred, or unapproved alias behavior.

## Expected file responsibilities

- `src/pantrypilot/normalization.py`: retain Feature 001 normalization and add
  the reusable single-value primitive.
- `src/pantrypilot/ingredients.py`: own canonical models, immutable registry
  loading/validation, application records, and pure deterministic resolution.
- `src/pantrypilot/models.py`: change internal recipes to canonical IDs,
  separate the ranked response model, and add top-level resolution evidence to
  `RankingResponse`.
- `src/pantrypilot/catalog.py`: reference and validate canonical IDs while
  preserving the four recipes and their displayed behavior.
- `src/pantrypilot/ranking.py`: resolve request terms once, enforce fail-closed
  exclusions, compare IDs, map canonical names into existing result fields,
  and preserve all Feature 001 score/order rules.
- `src/pantrypilot/app.py`: pass the registry and map the one unresolved-hard-
  constraint domain error to the documented `422`.
- `src/pantrypilot/evaluation.py`: validate the fixture, implement the exact-
  name baseline, calculate inspectable metrics, compare systems, and expose
  the evaluation CLI.
- `evaluations/ingredient-resolution-v1.json`: contain the fixed 28 labeled
  cases.
- `tests/test_ingredients.py`: cover registry and resolver behavior.
- `tests/test_evaluation.py`: cover fixture, metrics, comparison, and CLI
  behavior.
- `tests/test_normalization.py`, `tests/test_catalog.py`,
  `tests/test_ranking.py`, and `tests/test_api.py`: add focused Feature 002
  coverage while retaining Feature 001 regressions.
- `docs/roadmap.md` and `docs/product/vision.md`: record only the approved
  sequence correction and defer retrieval to meaningful catalog scale.
- `docs/learning/002-ingredient-entity-resolution.md`: provide the complete
  Feature 002 learning guide.
- `README.md`: update current status and link the new learning guide after the
  feature is implemented.

`pyproject.toml` and `uv.lock` are expected to remain unchanged because the
standard library and existing Pydantic dependency cover the design.

## Learning documentation

`docs/learning/002-ingredient-entity-resolution.md` will include:

- what was built and why Feature 001 exact matching is insufficient;
- the raw-term -> normalization -> resolution -> canonical-ID -> ranking flow;
- file-by-file responsibilities;
- normalization versus resolution, identities, aliases, abstention,
  determinism, precision, recall, FP, FN, baseline comparison, and hard-
  constraint safety;
- worked canonical, alias, unresolved, exclusion, and Black Bean Tacos
  examples;
- fixture structure, exact metric definitions, fresh measured results, error
  analysis, and the limitations of a small hand-curated fixture;
- the purpose of each unit, catalog, ranking, API, evaluation, and regression
  test layer;
- common failure cases including over-resolution, unresolved text, collisions,
  unsafe exclusions, and orphan catalog IDs;
- exact setup, focused-test, full-test, format, lint, evaluation, and
  application commands;
- at least eight conceptual mock-interview questions with concise guided
  answers;
- exactly two independent exercises;
- an explicit before-merge concept checklist.

The document records measured metrics only from fresh final evaluation output,
not from assumption.

## Risks and trade-offs

### Small curated registry and fixture

The resolver will have high measured precision but limited coverage. Its
`1.0000` recall applies only to the approved fixture, which contains all
approved aliases. The learning guide must state that this does not estimate
production recall. New aliases require product review, collision validation,
fixture updates, and re-evaluation.

### Additive response change

Adding top-level evidence is externally visible and exact-response clients
must accept the new field. This is the minimum change that makes unresolved
request terms inspectable without modifying every ranked recipe.

### Fail-closed unknown exclusions

Rejecting an unresolved exclusion is stricter than Feature 001, which silently
failed to match unknown exclusion strings. The stricter behavior is limited to
noncanonical inputs and is preferred because hard constraints cannot be
claimed as enforced otherwise.

### Internal recipe migration

Switching raw catalog ingredients to IDs touches existing catalog and ranking
tests. It is intentional one-time migration work that establishes the stable
identity Feature 003 needs. It does not add persistence or a generalized data
access layer.

## Acceptance-criteria coverage

1. Frozen canonical records provide stable IDs and canonical names.
2. ID-based catalog load proves complete current-catalog coverage.
3. Registry and catalog loaders reject all specified invalid data.
4. Canonical terms resolve through the canonical-name index.
5. Only explicit aliases resolve through the alias index.
6. Missing terms return structured unresolved evidence.
7. Pantry terms resolve before ID matching.
8. Exclusions use the identical resolver and ID space.
9. A supported exclusion alias blocks its canonical recipe identity.
10. Canonical-input result eligibility, scores, explanations, and order remain
    compatible.
11. Ranking weights and formulas remain unchanged.
12. Existing contribution/final-score reconstruction remains unchanged.
13. Success and unresolved-exclusion responses expose structured evidence.
14. Exact normalized lookup and immutable indexes guarantee determinism.
15. The v1 JSON fixture is committed and schema-versioned.
16. One comparison function evaluates both systems on the same parsed cases.
17. Fixed cases require resolver recall `1.0000` over baseline `0.6667`.
18. Fixed negative cases require zero resolver false positives.
19. Focused normalization, registry, catalog, ranking, and evaluation tests
    cover domain behavior.
20. API tests cover all externally observable success and failure behavior.
21. Existing Feature 001 tests remain and gain canonical-input regressions.
22. Final work must pass the required lock, test, Ruff, whitespace, status, and
    evaluation commands before completion is claimed.
23. Roadmap and vision receive the approved sequencing correction.
24. The required Feature 002 learning document covers every named learning
    section, at least eight interview questions, and exactly two exercises.
25. The design adds no non-goal technology.

## Scope conclusion

This remains one coherent PR: one small identity registry, one deterministic
resolver, one internal recipe-ID migration, one additive evidence contract,
one versioned evaluation fixture and evaluator, focused regression coverage,
and the required documentation. It deliberately stops before quantities,
persistence, retrieval, heuristics, or probabilistic resolution.
