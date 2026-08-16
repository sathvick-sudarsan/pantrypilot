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

**Feature 003: Durable Recipe Catalog** is implemented. Recipes now load from a
versioned local SQLite store into an immutable startup snapshot. The existing
deterministic ingredient-resolution and ranking behavior is unchanged, and the
Feature 002 evaluation remains database-independent.

## Quick start

```powershell
uv sync --locked --python 3.12
uv run pytest
uv run uvicorn pantrypilot.app:app --app-dir src
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
```

## Durable recipe catalog

PantryPilot stores recipes in a local SQLite file. On startup it migrates a
fresh store, seeds the approved four recipes only when both catalog tables are
empty, reloads the complete catalog as validated immutable `Recipe` objects,
and serves ranking requests from that in-memory snapshot. Ranking requests do
not query SQLite, and startup never falls back to Python seed data after a
storage failure.

The default file is `pantrypilot.sqlite3` in the process working directory.
Override it on PowerShell with:

```powershell
$env:PANTRYPILOT_DB_PATH = "C:\path\to\catalog.sqlite3"
uv run uvicorn pantrypilot.app:app --reload
```

Stop the application before moving or deleting the local database. Deleting a
development database is an explicit reset: the next successful startup creates
and seeds a fresh store. Never commit the database file.

## Project documents

- [Product vision](docs/product/vision.md)
- [Roadmap](docs/roadmap.md)
- [Feature 001 design](docs/superpowers/specs/2026-07-25-explainable-meal-ranking-design.md)
- [Feature 001 learning guide](docs/learning/001-explainable-meal-ranking.md)
- [Feature 002 design](docs/superpowers/specs/2026-08-08-ingredient-entity-resolution-design.md)
- [Feature 002 learning guide](docs/learning/002-ingredient-entity-resolution.md)
- [Feature 003 design](docs/superpowers/specs/2026-08-15-durable-recipe-catalog-design.md)
- [Feature 003 learning guide](docs/learning/003-durable-recipe-catalog.md)
- [Contributor instructions](AGENTS.md)

## Engineering workflow

After the foundation commit, feature work happens on focused branches rather
than directly on `main`. Each implemented feature must include tests, learning
documentation, and mock-interview questions. Changes use conventional commits
and receive an independent review before integration.
