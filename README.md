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

**Feature 004: Durable Saved Pantry** is implemented. Recipes and one current
application-local pantry are durable in a versioned local SQLite store. Recipe
ranking remains deterministic, and the Feature 002 evaluation remains
database-independent.

## Quick start

```powershell
uv sync --locked --python 3.12
uv run pytest
uv run uvicorn pantrypilot.app:app --app-dir src
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
```

## Durable catalog and saved pantry

PantryPilot stores recipes in a local SQLite file. On startup it migrates a
fresh store, seeds the approved four recipes only when both catalog tables are
empty, reloads the complete catalog as validated immutable `Recipe` objects,
and serves inline ranking requests from that in-memory snapshot. Inline ranking
has no request-time SQLite I/O; saved ranking performs one durable pantry read.
Startup never falls back to Python seed data after a storage failure.

PantryPilot keeps one application-local current pantry in the same SQLite
database as the durable recipe catalog. Saved pantry state contains only
canonical ingredient IDs; canonical names are derived from the code-owned
ingredient registry. Inline ranking remains available and unchanged.

The default file is `pantrypilot.sqlite3` in the process working directory.
Override it on PowerShell with:

```powershell
$env:PANTRYPILOT_DB_PATH = "C:\path\to\catalog.sqlite3"
uv run uvicorn pantrypilot.app:app --reload
```

The configured path's parent directory must already exist. The SQLite file may
be absent; PantryPilot creates it on successful first startup, but it does not
create missing parent directories.

Automatic startup migration and seeding assume PantryPilot's current
single-process deployment. SQLite persistence and saved-pantry writes are local
to that deployment; multi-worker coordination is deferred.

Stop the application before moving or deleting the local database. Deleting a
development database is an explicit reset: the next successful startup creates
and seeds a fresh store. Never commit the database file.

## Saved-pantry API

All saved-pantry items resolve through the code-owned ingredient registry. A
successful replacement deduplicates them and returns ascending canonical-ID
order. An empty list establishes an empty pantry; it does not mean absent.
If any submitted item is unresolved, the whole replacement is rejected and the
previous saved pantry stays unchanged.

- `PUT /v1/saved-pantry` — replace the complete current pantry.

  ```json
  {"pantry_items": ["black bean", "eggs", "olive oil"]}
  ```

- `GET /v1/saved-pantry` — inspect the established pantry.

- `POST /v1/saved-pantry/meal-rankings` — rank with saved state.

  ```json
  {
    "min_protein_g": 20.0,
    "max_prep_minutes": 30,
    "excluded_ingredients": [],
    "limit": 5
  }
  ```

- `POST /v1/meal-rankings` — rank with required inline `pantry_items`.

  ```json
  {
    "pantry_items": ["black beans", "eggs", "olive oil"],
    "min_protein_g": 20.0,
    "max_prep_minutes": 30,
    "excluded_ingredients": [],
    "limit": 5
  }
  ```

An absent saved pantry returns `404`:

```json
{
  "detail": {
    "type": "saved_pantry_not_found",
    "message": "No saved pantry has been established."
  }
}
```

An unresolved replacement returns `422` without writing any submitted item:

```json
{
  "detail": {
    "type": "unresolved_pantry_items",
    "message": "All pantry items must resolve before saving.",
    "ingredient_resolution": {
      "pantry_items": [
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

Known saved-pantry storage failures return `503` without paths or SQL details:

```json
{
  "detail": {
    "type": "saved_pantry_unavailable",
    "message": "Saved pantry is unavailable."
  }
}
```

## Project documents

- [Product vision](docs/product/vision.md)
- [Roadmap](docs/roadmap.md)
- [Feature 001 design](docs/superpowers/specs/2026-07-25-explainable-meal-ranking-design.md)
- [Feature 001 learning guide](docs/learning/001-explainable-meal-ranking.md)
- [Feature 002 design](docs/superpowers/specs/2026-08-08-ingredient-entity-resolution-design.md)
- [Feature 002 learning guide](docs/learning/002-ingredient-entity-resolution.md)
- [Feature 003 design](docs/superpowers/specs/2026-08-15-durable-recipe-catalog-design.md)
- [Feature 003 learning guide](docs/learning/003-durable-recipe-catalog.md)
- [Feature 004 design](docs/superpowers/specs/2026-08-16-durable-saved-pantry-design.md)
- [Feature 004 learning guide](docs/learning/004-durable-saved-pantry.md)
- [Contributor instructions](AGENTS.md)

## Engineering workflow

After the foundation commit, feature work happens on focused branches rather
than directly on `main`. Each implemented feature must include tests, learning
documentation, and mock-interview questions. Changes use conventional commits
and receive an independent review before integration.
