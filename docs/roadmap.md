# PantryPilot roadmap

The roadmap adds complexity only after the previous stage provides a measured,
tested baseline.

## Phase 0: Project foundation

- Record the product vision, engineering workflow, and contribution rules.
- Approve the first feature design before adding application code.
- Establish independent review and branch-based development.

Evidence: a clean foundation commit and an approved Feature 001 specification.

## Phase 1: Deterministic ranking baseline

- Implement the explainable pantry-based meal-ranking API.
- Normalize exact ingredient strings and apply hard constraints.
- Rank an in-memory recipe catalog with transparent score components.
- Return deterministic explanations and ordering.
- Add automated tests, learning documentation, and mock-interview questions.

Evidence: reproducible API responses, reconstructable scores, and passing
behavioral tests.

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

## Phase 5: Food-waste and constrained meal-plan optimization

- Track pantry ingredient quantities, units, purchase dates, and estimated
  spoilage windows.
- Plan multiple meals jointly rather than ranking one meal at a time.
- Optimize ingredient reuse, expected waste, nutrition, budget, and time under
  explicit constraints.
- Explain constraint violations and trade-offs when no feasible plan exists.

Evidence: solver-backed plans, feasibility tests, scenario benchmarks, and
measured waste reduction against greedy ranking.

## Phase 6: Personalization and feedback

- Capture explicit ratings, selections, skips, and substitutions.
- Build user preference features while preserving hard dietary constraints.
- Address cold-start behavior and distinguish stated from observed preference.
- Add feedback-quality monitoring and privacy-aware retention rules.

Evidence: replayable feedback data, personalized offline metrics, and documented
cold-start behavior.

## Phase 7: Learned ranking, calibration, and experimentation

- Train a learned ranker against the deterministic and personalized baselines.
- Define offline ranking metrics and guardrail metrics.
- Calibrate acceptance or satisfaction predictions.
- Add model versioning, reproducible training, drift checks, and experiment
  assignment.
- Run controlled experiments only after offline gains and safety checks.

Evidence: reproducible training artifacts, baseline comparisons, calibration
plots, model cards, and experiment readouts.

## Phase 8: Reliable LLM and tool interfaces

- Expose ranking, retrieval, planning, and explanation capabilities as typed
  tools.
- Add an LLM interface only as an orchestrator over trusted product functions.
- Validate tool arguments, constrain execution, and ground responses in tool
  results.
- Add traces, evaluation suites, fallback behavior, cost monitoring, and
  adversarial reliability tests.

Evidence: tool-call success metrics, grounded-response evaluations, observable
failure handling, and clear proof that the LLM layer improves usability without
replacing the recommendation system.
