# PantryPilot contributor instructions

Read `docs/product/vision.md`, `docs/roadmap.md`, and the relevant approved
design before changing the repository.

## Working rules

- After the foundation commit, never work directly on `main`.
- Use one writing agent per worktree; do not allow concurrent writers.
- Keep changes small, focused, explicit, and easy for the project owner to
  explain.
- Prefer pure functions and existing language or framework features over new
  abstractions and dependencies.
- Do not add speculative infrastructure or features outside the approved scope.
- Add focused tests for every implemented feature or bug fix.
- Add learning documentation and mock-interview questions for every feature.
- Use conventional commits and frequent meaningful commits.
- Never commit secrets, credentials, local environment files, or generated
  caches.
- Do not commit or push unless the user has authorized that action.

## Review expectations

Explain important decisions in plain language. Review for correctness,
security, scope, test quality, understandable design, and consistency with the
approved specification. Surface uncertainty rather than hiding it.
