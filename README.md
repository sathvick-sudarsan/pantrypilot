# PantryPilot

PantryPilot is an intelligent grocery and meal-planning assistant designed to
help people decide what to cook and what to buy while balancing nutrition,
budget, ingredient reuse, food-waste reduction, preparation time, dietary
constraints, and personal preferences.

The project is also a serious AI/ML engineering portfolio and learning
environment. It will progress from a measurable deterministic baseline to
entity resolution, constrained optimization, personalization, learned ranking,
experimentation, and reliable LLM tool use. It is intentionally not starting as
a recipe chatbot or external-API wrapper.

## Current status

**Feature 002: Measured Ingredient Entity Resolution** is implemented. Recipes
now use canonical ingredient identities; explicit aliases resolve
deterministically, while unsupported terms abstain. On the v1 fixture, the
resolver improves recall over Feature 001's exact-name baseline with zero false
positives. `POST /v1/meal-rankings` retains deterministic ranking and exposes
structured resolution evidence.

## Quick start

```powershell
uv sync --locked --python 3.12
uv run pytest
uv run uvicorn pantrypilot.app:app --app-dir src
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
```

## Project documents

- [Product vision](docs/product/vision.md)
- [Roadmap](docs/roadmap.md)
- [Feature 001 design](docs/superpowers/specs/2026-07-25-explainable-meal-ranking-design.md)
- [Feature 001 learning guide](docs/learning/001-explainable-meal-ranking.md)
- [Feature 002 design](docs/superpowers/specs/2026-08-08-ingredient-entity-resolution-design.md)
- [Feature 002 learning guide](docs/learning/002-ingredient-entity-resolution.md)
- [Contributor instructions](AGENTS.md)

## Engineering workflow

After the foundation commit, feature work happens on focused branches rather
than directly on `main`. Each implemented feature must include tests, learning
documentation, and mock-interview questions. Changes use conventional commits
and receive an independent review before integration.
