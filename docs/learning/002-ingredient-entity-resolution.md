# Feature 002: Measured ingredient entity resolution

## What we built

Feature 002 adds a canonical identity layer between ingredient text and meal
ranking. A validated immutable registry contains 14 canonical ingredients and
seven reviewed aliases. Recipes store stable ingredient IDs, while the API
continues to return human-readable canonical names.

One deterministic resolver handles both pantry items and excluded ingredients.
It returns structured evidence for every submitted term: the original input,
normalized text, resolved ID and canonical name when known, and whether the
match was canonical, an alias, or unresolved. Unsupported pantry terms abstain
and do not match. Unsupported exclusions fail closed, because PantryPilot
cannot honestly claim to enforce a hard constraint it cannot identify.

A versioned 28-case fixture compares this resolver with Feature 001's
normalized exact-name baseline. The ranking formula remains unchanged:

```text
0.70 * pantry_coverage + 0.20 * protein_fit + 0.10 * time_fit
```

Preparation time and exclusions remain hard filters; minimum protein remains a
soft target. Contribution rounding, reconstructable scores, fixed
explanations, deterministic score/ID ordering, and post-sort limiting are also
unchanged.

## Why it exists

Feature 001 trims and lowercases ingredient text, then matches by normalized
string equality. That is a useful baseline, but it cannot express identity:
`"black bean"` and `"black beans"` remain different strings, so the singular
pantry term misses the Black Bean Tacos ingredient.

Normalization changes the surface form of one string. Entity resolution maps
different approved surface forms to one stable identity. Feature 002 makes
that distinction explicit and measurable before trying heuristics or learned
methods. Exact aliases are easy to inspect, collision-check, test, and defend;
unknown terms remain visible rather than being guessed.

## Architecture / data flow

The request-to-response flow is:

```text
validated raw request terms
    -> trim and lowercase each term
    -> exact canonical-name/alias lookup, or abstain
    -> reject the request if any exclusion is unresolved
    -> pantry-ID and exclusion-ID sets
    -> filter recipe IDs by exclusions and preparation time
    -> match recipe ingredient IDs against pantry IDs
    -> map IDs to canonical-name result evidence
    -> unchanged score, explanation, sorting, and limiting
    -> FastAPI response with term-level resolution evidence
```

Every request occurrence produces evidence in input order, including
duplicates. Resolved IDs are deduplicated with sets only for matching, so a
repeated pantry alias cannot inflate coverage. Recipe ingredient order controls
the required, matched, and missing canonical-name fields.

The domain functions receive the immutable registry and catalog explicitly and
do not import FastAPI. The HTTP layer validates transport data, supplies the
application data, and maps the one unresolved-exclusion domain outcome to the
documented `422` response.

## File-by-file responsibilities

- `src/pantrypilot/normalization.py` owns the single-term trim/lower primitive
  and stable exact deduplication for term sequences.
- `src/pantrypilot/ingredients.py` defines canonical records, immutable
  `MappingProxyType` indexes, registry validation, the 14 application
  identities, seven aliases, resolution evidence, and exact lookup functions.
- `src/pantrypilot/models.py` defines the validated request, ID-based internal
  recipe, explicit public ranked recipe, score shapes, and response evidence.
- `src/pantrypilot/catalog.py` validates the four immutable recipes against the
  registry and rejects unknown or duplicate ingredient and recipe IDs.
- `src/pantrypilot/ranking.py` resolves both request term lists once, fails
  closed on unresolved exclusions, matches IDs, maps canonical names into
  results, and preserves Feature 001 filtering, scoring, explanations, order,
  and limiting.
- `src/pantrypilot/app.py` is the thin FastAPI adapter. It passes the catalog
  and registry to the domain and renders the fixed unresolved-exclusion `422`.
- `src/pantrypilot/evaluation.py` validates fixtures, implements the exact-name
  baseline, calculates inspectable metrics, compares both systems, and exposes
  the deterministic module CLI.
- `evaluations/ingredient-resolution-v1.json` is the versioned labeled dataset
  with 14 canonical, seven alias, and seven unresolved cases.
- `tests/test_normalization.py` proves normalization stays text-only and has no
  plural, punctuation, whitespace, or synonym heuristics.
- `tests/test_ingredients.py` proves registry validation and immutability,
  canonical and alias resolution, abstention, evidence invariants, and
  determinism.
- `tests/test_catalog.py` proves recipe-to-registry integrity, approved catalog
  contents, input validation, and immutability.
- `tests/test_ranking.py` proves ID matching, alias behavior, fail-closed hard
  exclusions, unchanged scores and explanations, deterministic ordering, and
  post-sort limiting with isolated local fixtures.
- `tests/test_api.py` proves externally visible resolution evidence, canonical
  compatibility, alias exclusions, unresolved-exclusion `422` responses,
  validation behavior, determinism, and generic error secrecy.
- `tests/test_evaluation.py` proves fixture validation and registry coverage,
  confusion-count rules, exact metrics and error cases, CLI determinism and
  exit codes, and repository-root execution of the published command.
- `pyproject.toml` declares the explicit `uv_build` build backend so the
  `src`-layout package is installed and the module command works without a
  test-only import path; `uv.lock` records that reproducibly. No runtime
  dependency or console script was added for Feature 002.
- `docs/superpowers/specs/2026-08-08-ingredient-entity-resolution-design.md`
  records the approved behavior and trade-offs; the corresponding plan in
  `docs/superpowers/plans/` records the TDD, review, and commit sequence.
- `docs/product/vision.md` and `docs/roadmap.md` place measured entity
  resolution before persistence, with retrieval deferred until catalog scale
  justifies it.
- `README.md` states the implemented feature and exposes its design, learning,
  and evaluation entry points; this guide explains the resulting system and
  the concepts the owner should be able to defend.

## Core algorithms and concepts

**Normalization versus resolution.** Normalization deterministically trims and
lowercases one string. It deliberately preserves internal whitespace,
punctuation, wording, and plurality. Resolution takes that normalized string
and performs one exact registry lookup to find a supported identity.

**Canonical identity and name.** A stable kebab-case ID such as
`vegetable-broth` is the machine reference used by recipes and future durable
contracts. Its canonical name, `vegetable broth`, is the human-readable value
returned in recipe evidence. A display name could change without requiring the
identity to change.

**Explicit aliases.** An alias is a reviewed alternate term that maps to one
canonical ID. There is no generic plural rule: `black bean` is registered, but
that does not make `black bean sauce` resolve. Registry construction rejects
duplicate IDs, duplicate terms, and ambiguous cross-identity collisions rather
than choosing according to record order.

**Abstention and determinism.** A missing term-index entry returns
`unresolved` with no ID or canonical name. The resolver does not return a
candidate, similarity score, or closest value. Exact normalized lookup against
immutable indexes means identical input and registry data produce identical
evidence.

**Evaluation counts.** For an expected non-null identity, a correct prediction
is a true positive (TP). A differing or missing prediction is a false negative
(FN). Any incorrect non-null prediction is a false positive (FP), including a
resolution for an expected-unresolved case. Both expected and predicted null
is a true negative (TN). A wrong identity therefore adds one FP for introducing
the wrong entity and one FN for missing the expected entity.

```text
precision = TP / (TP + FP)
recall    = TP / (TP + FN)
```

The evaluator rounds precision and recall to four decimal places and returns
`0.0` when the corresponding denominator is zero.

Precision asks how often produced identities were correct; recall asks how
many expected identities were found. Both systems receive the same parsed
fixture, so the comparison isolates the behavior changed by explicit aliases
rather than a difference in datasets.

**Hard-constraint safety.** An unresolved pantry term can only lose a positive
match, so PantryPilot returns it as visible abstention. An unresolved exclusion
could conceal an ingredient the caller intended to block, so ranking stops
before scoring. Canonical terms and aliases use the same resolver and identity
space for both positive matching and exclusions.

## Worked examples

- Canonical input `black beans` normalizes to the registered canonical name and
  resolves to ID `black-beans` with match type `canonical`.
- Explicit alias `black bean` resolves to `black-beans` with canonical name
  `black beans` and match type `alias`.
- Unsupported `black bean sauce` remains unresolved. Exact lookup prevents a
  substring match from over-resolving it.
- Alias `vegetable stock` resolves to `vegetable-broth`, whose canonical name is
  `vegetable broth`.
- Excluding `peanut` resolves to `peanuts` through the shared resolver and
  blocks Peanut Noodles, whose recipe record requires the `peanuts` identity.
- Excluding unsupported `groundnut` produces the fixed fail-closed `422`
  instead of returning a ranking that might violate the requested constraint.

For Black Bean Tacos, use pantry input `black bean`, `corn tortillas`,
`avocado`, and `lime`, with `min_protein_g = 0` and
`max_prep_minutes = 30`. Feature 001 misses the singular term:

```text
pantry coverage      = 3 / 4 = 0.7500
pantry contribution  = 0.7500 * 0.70 = 0.5250
protein fit          = 1.0000
protein contribution = 1.0000 * 0.20 = 0.2000
time fit             = 1 - 25 / 30 = 0.1667
time contribution    = round((1 - 25 / 30) * 0.10, 4) = 0.0167
final score          = 0.5250 + 0.2000 + 0.0167 = 0.7417
```

Feature 002 resolves `black bean` to `black-beans`, so all four IDs match:

```text
pantry coverage      = 4 / 4 = 1.0000
pantry contribution  = 1.0000 * 0.70 = 0.7000
protein fit          = 1.0000
protein contribution = 1.0000 * 0.20 = 0.2000
time fit             = 1 - 25 / 30 = 0.1667
time contribution    = round((1 - 25 / 30) * 0.10, 4) = 0.0167
final score          = 0.7000 + 0.2000 + 0.0167 = 0.9167
```

The improvement comes only from identity resolution; the scoring formula and
all non-pantry contributions are identical.

## Evaluation

`ingredient-resolution-v1.json` declares `schema_version: 1`. Every case has
an input, an expected ingredient ID or `null`, and a category of `canonical`,
`alias`, or `unresolved`. Loading rejects the wrong schema version, unknown
fields or IDs, blank or duplicate normalized inputs, invalid categories, and
empty fixtures.

A registry-consistency test proves set equality between every registered
canonical name or alias and every positive fixture input. It also resolves
each row and verifies that canonical rows are canonical matches, alias rows are
alias matches, and unresolved rows abstain. That protects both coverage and
category accuracy when the registry or fixture changes.

The Feature 001 baseline applies the same trim/lower normalization but returns
an ID only when the input equals a canonical name; it does not consult aliases.
The Feature 002 resolver and baseline then evaluate the same 28 parsed cases
using the count rules above. Fresh Task 7 output measured:

| System | TP | FP | FN | TN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| Feature 001 exact-name baseline | 14 | 0 | 7 | 7 | 1.0000 | 0.6667 |
| Feature 002 canonical/alias resolver | 21 | 0 | 0 | 7 | 1.0000 | 1.0000 |

The baseline's seven false negatives are exactly `egg`, `black bean`,
`corn tortilla`, `peanut`, `lentil`, `carrot`, and `vegetable stock`. Feature
002 has strictly higher recall, zero false-positive resolutions, and no error
cases on this fixture.

These results do not estimate real-world prevalence or production recall. The
fixture is small, curated, and intentionally covers every approved alias. It
proves the registry's declared behavior and guards known confusable negatives;
it does not represent the much broader distribution of user vocabulary.

## Testing strategy

Normalization tests hold the text transform at the Feature 001 boundary.
Registry/resolver tests prove valid identity construction, collision rejection,
immutability, evidence invariants, exact alias behavior, and abstention.
Catalog tests prove every recipe references a registered ID and invalid
application data fails early.

Ranking tests exercise pure ID matching, hard filters, scoring, explanation,
sorting, limiting, and the taco regression without HTTP. API tests separately
prove serialized success evidence, canonical-input compatibility, validation,
alias exclusions, and the fail-closed `422`. Evaluation tests prove fixture
integrity, metric arithmetic, inspectable errors, deterministic output,
acceptance exit codes, and the real repository-root CLI command.

Small local registries and recipes isolate individual domain rules from the
application data. Approved application-fixture tests then catch drift across
the registry, catalog, and evaluation dataset. Running the complete suite is
the Feature 001 regression layer and proves the new identity boundary did not
quietly change established ranking behavior.

## Common failure cases

- **Over-resolution:** substring, stemming, or generic singularization could
  turn `peanut oil` into `peanuts`; exact explicit lookup abstains instead.
- **Unsupported input:** an unknown pantry item remains inspectable and cannot
  contribute a match. An unknown exclusion must stop ranking, not disappear.
- **Invalid IDs:** blank or non-kebab-case machine IDs are rejected before they
  can enter stable recipe references.
- **Duplicate identity data:** duplicate IDs, an alias repeated within one
  entity, or an alias equal to its own canonical name are deterministic errors.
- **Cross-identity collisions:** two entities cannot claim the same normalized
  canonical name or alias; registry order never decides the winner.
- **Orphan or duplicate recipe data:** the catalog loader rejects an ingredient
  ID absent from the registry, a repeated required ID, or a duplicate recipe
  ID before the application serves requests.
- **Unsafe exclusions:** using a different resolver for exclusions, or ignoring
  unresolved exclusions, could falsely imply that a hard constraint was
  enforced. Both lists share one resolver and unknown exclusions fail closed.
- **Evidence/data mismatch:** per-input evidence must retain duplicates and
  order even though ID sets deduplicate matching; result names must map from the
  same IDs used for eligibility and scoring.
- **Registry/fixture drift:** adding or relabeling a registry term without the
  corresponding fixture case breaks the full-coverage/category test instead of
  silently making the metric incomplete.

## Commands

Install the locked environment, run each focused layer, evaluate both systems,
then run full tests and static checks:

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
```

Start the local API after setup with:

```powershell
uv run uvicorn pantrypilot.app:app --app-dir src
```

## Mock interview

1. **How is normalization different from entity resolution?** Normalization
   changes surface form deterministically, such as trimming and lowercasing.
   Resolution maps supported different forms to one stable identity.
2. **Why store recipe ingredient IDs instead of canonical names?** Names can
   change for display, while stable IDs preserve recipe references and future
   durable contracts.
3. **Why are singular/plural forms explicit aliases?** A general rule can merge
   distinct foods and is unsafe for exclusions. Explicit mappings are reviewed,
   collision-checked, and measurable.
4. **Why is abstention valuable?** It prevents guesses from increasing false
   positives and makes unsupported vocabulary visible for later analysis.
5. **Why must pantry and exclusions share a resolver?** Different identity
   systems could let an alias match positively while bypassing the same hard
   exclusion.
6. **Why reject an unresolved exclusion?** Returning results would imply the
   hard safety constraint was enforced even though the system could not
   identify it.
7. **How are wrong-identity predictions counted?** They add one FP for the
   incorrect entity introduced and one FN for the expected entity missed.
8. **Why compare against normalized exact names on the same fixture?** It
   isolates the improvement supplied by aliases and prevents dataset
   differences from confounding the metrics.
9. **Why does 1.0000 fixture recall not prove production readiness?** The
   fixture is small, curated, and contains all approved aliases; real input
   distributions and vocabulary are much broader.
10. **Why implement entity identity before persistence?** Persistence should
    store stable canonical references rather than freeze ambiguous display
    strings into a durable schema.

## Exercises

1. Propose one sensible alias and two confusable negative terms, update the
   registry and fixture with strict TDD, and explain how the coverage/category
   test prevents registry/fixture drift.
2. Construct a synthetic wrong-identity evaluation case by hand, calculate its
   TP/FP/FN/TN effect, then add a local evaluator test and compare the output.

## Concepts required before merge

The owner should be able to explain:

- [ ] normalization versus resolution;
- [ ] a stable ID versus a canonical display name;
- [ ] explicit aliases and collision validation;
- [ ] conservative abstention;
- [ ] shared pantry/exclusion identities and fail-closed exclusions;
- [ ] recipe-ID and catalog integrity;
- [ ] TP, FP, FN, TN, precision, and recall;
- [ ] why a wrong identity counts as both an FP and an FN;
- [ ] fair same-fixture baseline comparison;
- [ ] fixture coverage and category consistency;
- [ ] why the measured results are limited to the curated fixture;
- [ ] unchanged scoring, explanations, ordering, and hard filters; and
- [ ] strict TDD and independent review boundaries.
