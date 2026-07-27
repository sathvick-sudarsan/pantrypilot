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

The repository is at the project-foundation stage. No application code or
dependencies have been added.

The first vertical slice is **Feature 001: Explainable Pantry-Based Meal
Ranking**. A versioned API will rank an in-memory recipe catalog from pantry
ingredients and constraints, returning score components and deterministic
explanations.

## Project documents

- [Product vision](docs/product/vision.md)
- [Roadmap](docs/roadmap.md)
- [Feature 001 design](docs/superpowers/specs/2026-07-25-explainable-meal-ranking-design.md)
- [Contributor instructions](AGENTS.md)

## Engineering workflow

After the foundation commit, feature work happens on focused branches rather
than directly on `main`. Each implemented feature must include tests, learning
documentation, and mock-interview questions. Changes use conventional commits
and receive an independent review before integration.
