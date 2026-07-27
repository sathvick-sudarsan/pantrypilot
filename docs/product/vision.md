# PantryPilot product vision

## Mission

PantryPilot is an intelligent grocery and meal-planning assistant. Its long-term
goal is to help users decide what to cook and what to buy while jointly
optimizing:

- Nutrition
- Budget
- Ingredient reuse
- Food-waste reduction
- Preparation time
- Dietary constraints
- Personal preferences

The product should turn a user's available food, constraints, history, and
goals into recommendations whose trade-offs are useful, measurable, and
explainable.

## Why this project exists

PantryPilot serves two connected purposes:

1. Build a useful decision-support product for meal and grocery planning.
2. Provide a structured environment for learning and demonstrating software
   engineering and production AI/ML engineering.

The repository should demonstrate more than prompt engineering. Over time it
must contain defensible examples of:

- Recommendation and ranking systems
- Information retrieval
- Ingredient and recipe entity resolution
- Constrained optimization
- User modeling and preference learning
- Calibrated prediction
- Offline evaluation and online experimentation
- Production API design
- Testing, observability, and operational reliability
- Reliable LLM and tool-calling workflows

## Product principles

### Decisions before conversation

The core product is a recommendation and planning system. A conversational
interface may eventually make that system easier to use, but it must call
measurable capabilities rather than replace them with unstructured generation.

### Deterministic baseline before learned behavior

Each learned or probabilistic system should be compared with a simple,
understandable baseline. Early deterministic behavior creates test fixtures,
evaluation data, product vocabulary, and failure cases for later ML work.

### Hard constraints remain hard

Safety, allergies, dietary exclusions, and explicit user limits must not be
quietly traded away by a ranking score. Soft preferences may influence order;
hard constraints determine eligibility.

### Explanations come from evidence

Recommendations should expose the inputs and score components that caused them.
Generated explanations may be added later, but they must remain grounded in
structured ranking evidence.

### Optimization should reflect real trade-offs

The mature system should reason jointly about nutrition, price, waste,
ingredient reuse, preparation time, and preference instead of optimizing a
single proxy such as recipe similarity.

### Reliability is a product feature

Validation, deterministic interfaces, tests, monitoring, traceability,
calibration, and graceful failure are part of the product rather than cleanup
work postponed until deployment.

## Intended system evolution

PantryPilot begins with an in-memory recipe catalog and transparent weighted
ranking. The system then gains persistence and stable data contracts, followed
by ingredient entity resolution and retrieval. Once the data model is reliable,
it can support multi-meal planning and constrained food-waste optimization.

User feedback then enables preference models and personalization. Logged
decisions and outcomes support offline evaluation, calibrated predictions,
experimentation, and learned ranking. LLM and tool interfaces arrive only after
these capabilities have explicit contracts and evaluation methods, allowing a
language model to orchestrate trusted tools instead of inventing product logic.

## Users and representative decisions

The initial user is someone asking, "What can I cook with what I have under
these constraints?" Future decisions include:

- Which meals best use ingredients already on hand?
- What small purchase unlocks the most useful meals?
- Which weekly plan meets nutrition and budget limits?
- Which plan consumes ingredients before they spoil?
- How should recommendations change after explicit and observed feedback?
- How confident is the system that a recommendation will be accepted?

## Engineering and learning goals

The project owner is developing skill in software engineering, ML engineering,
Git, testing, architecture, and code review. Work must therefore be:

- Small enough to review and explain
- Organized around explicit interfaces and focused files
- Tested at the level where behavior lives
- Documented with the reasoning behind important decisions
- Accompanied by learning notes and mock-interview questions
- Committed in frequent, meaningful conventional commits
- Independently reviewed before integration

Codex is the primary implementer. Claude Code is the independent reviewer.
After the foundation commit, implementation must not happen directly on
`main`, and two writing agents must never share a worktree.

## Portfolio standard

Each major stage should produce evidence that can be discussed in an
engineering interview:

- A clearly stated user problem and baseline
- Versioned contracts and reproducible behavior
- Tests tied to failure modes
- Metrics appropriate to the system
- Documented trade-offs and rejected alternatives
- Evaluation showing whether additional complexity improved results
- Operational signals showing how the system behaves in production

## Current boundary

Feature 001 is an explainable pantry-based meal-ranking API. It intentionally
uses exact normalized ingredient matching, a small in-memory recipe catalog,
hard exclusion and preparation-time filters, and a deterministic weighted
score.

The first feature does not include synonyms, fuzzy matching, embeddings, LLM
calls, persistence, authentication, a frontend, Docker, or external recipe
APIs. Those capabilities should be introduced only when the roadmap reaches
the problem they solve.
