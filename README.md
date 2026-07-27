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

**Feature 001: Explainable Pantry-Based Meal Ranking** is implemented.
`POST /v1/meal-rankings` ranks the in-memory recipe catalog from pantry
ingredients and constraints, returning deterministic score evidence and fixed
explanations.

## Quick start

```powershell
uv sync --locked --python 3.12
uv run pytest
uv run uvicorn pantrypilot.app:app --app-dir src
```

## Project documents

- [Product vision](docs/product/vision.md)
- [Roadmap](docs/roadmap.md)
- [Feature 001 design](docs/superpowers/specs/2026-07-25-explainable-meal-ranking-design.md)
- [Feature 001 learning guide](docs/learning/001-explainable-meal-ranking.md)
- [Contributor instructions](AGENTS.md)

## Engineering workflow

After the foundation commit, feature work happens on focused branches rather
than directly on `main`. Each implemented feature must include tests, learning
documentation, and mock-interview questions. Changes use conventional commits
and receive an independent review before integration.
