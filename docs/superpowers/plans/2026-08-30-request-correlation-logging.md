# Request Correlation and Privacy-Safe Structured Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every PantryPilot HTTP request one server-owned correlation ID, return it in `X-Request-ID`, and emit exactly one privacy-safe structured completion record while preserving all existing public response and ranking contracts.

**Architecture:** Register one pure ASGI `RequestLoggingMiddleware` inside Starlette's outer `ServerErrorMiddleware` and outside FastAPI/Starlette `ExceptionMiddleware`. The middleware keeps all mutable request data in one `__call__` invocation or the unique ASGI scope, wraps `send` to replace `X-Request-ID` and capture status, observes normalized route metadata after routing, emits one allowlist-built completion `LogRecord`, and owns the correlated sanitized response for unexpected exceptions while re-raising the original exception. Existing FastAPI and PantryPilot exception handlers continue to own their current public bodies.

**Tech Stack:** Python 3.12, Python standard-library `logging`, `time`, `uuid`, `asyncio`, `concurrent.futures`, and `threading`, FastAPI 0.140.0, Starlette 1.3.1 pure ASGI types and `PlainTextResponse`, Pytest 9.1.1 captured logging, Ruff, uv, and Markdown. No dependency is added.

**Spec:** `docs/superpowers/specs/2026-08-29-request-correlation-logging-design.md`

## Global Constraints

- Work only in `C:\Users\sathv\Projects\pantrypilot\.worktrees\request-correlation-logging` on branch `feat/request-correlation-logging`; the reviewed planning baseline is exact commit `6ec60c0407c02dd03d2a1db9953f2d4aef295ccc`.
- The owner-approved design at `docs/superpowers/specs/2026-08-29-request-correlation-logging-design.md` is authoritative. Do not redesign the feature during execution.
- Register one pure ASGI middleware. Do not use `BaseHTTPMiddleware`, `@app.middleware("http")`, route dependencies, multiple logging handlers, a catch-all FastAPI exception handler, OpenTelemetry, or another observability framework.
- Preserve this stack: Starlette `ServerErrorMiddleware` -> PantryPilot request middleware -> FastAPI/Starlette `ExceptionMiddleware` -> existing handlers -> router/endpoints.
- Process HTTP scopes only. Lifespan and WebSocket scopes pass through unchanged and emit no Feature 007 event.
- Generate every request ID with `uuid.uuid4().hex`; accept only the generated 32 lowercase hexadecimal characters matching `[0-9a-f]{32}` as the authoritative ID. Exact length and maximum length are both 32.
- Ignore inbound `X-Request-ID` completely. Never validate, echo, propagate, or log it. Replace every downstream `X-Request-ID`, case-insensitively, with the generated value.
- Add no client-ID trust or propagation policy; the current product owns every request ID itself.
- Return correlation only in the `X-Request-ID` header. Do not add it to any response body.
- Store the generated value at `scope["pantrypilot.request_id"]`.
- Obtain `pantrypilot.request` through standard-library logging. The message and `event_name` are exactly `request_completed`.
- Every completion record has exactly six stable custom fields: `event_name: str`, `request_id: str`, `http_method: str`, `http_route: str`, `http_status_code: int`, and `duration_ms: float`.
- Build records from that explicit allowlist. Do not accept or merge arbitrary payload dictionaries and do not serialize request, response, validation, exception, model, body, or header objects.
- Emit INFO for success, redirects, and expected 4xx responses; WARNING for handled 5xx responses such as the saved-pantry 503; and ERROR with standard `exc_info` for unexpected 500 failures.
- Emit no separate PantryPilot exception event. The traceback-bearing ERROR `request_completed` record is the single PantryPilot completion event for an unexpected request failure.
- A handled `PantryStoreError` record is WARNING and has no `exc_info`, exception text, chained cause, path, or SQL detail.
- Use normalized code-owned route metadata from `scope["route"].path_format` when it is a string; otherwise use exactly `unmatched`. Never fall back to the raw path, URL, or query string.
- The installed FastAPI 0.140.0 / Starlette 1.3.1 planning probe exposed `/items/{item_id}` after a 405. Keep an executable 405 test as the framework proof. Stop implementation if that test contradicts this approved assumption; do not add a raw-path workaround.
- The installed slash-redirect planning probe exposed no normalized route. Its approved representation is therefore `unmatched`; the raw redirect path remains absent from the PantryPilot record.
- Measure with `time.perf_counter_ns()` and compute `round((end_ns - start_ns) / 1_000_000, 3)`. The result is a non-negative float in milliseconds with no textual trailing-zero or latency-threshold contract.
- Keep request ID, start time, response status, exception state, and completion decision local to one ASGI invocation and/or its unique request scope. Middleware-instance state contains only the wrapped ASGI application.
- Do not add a `ContextVar`. Synchronous endpoints require no ambient correlation state; the middleware invocation retains its own wrapped `send` and local variables while endpoint work runs in a worker thread.
- Preserve all existing successful bodies, FastAPI `HTTPException` behavior, saved-pantry-not-found 404, unmatched default 404, all 422 contracts, `RequestValidationError` serialization, and the exact saved-pantry 503 body.
- An unexpected exception before response start sends exact status 500, body `Internal Server Error`, content type `text/plain; charset=utf-8`, and the authoritative header; emits one ERROR completion with `exc_info`; then re-raises the original exception.
- Because the correlated 500 starts before re-raise, the outer `ServerErrorMiddleware` must not send a second response. Preserve both `TestClient` modes: `raise_server_exceptions=False` inspects the response; the default surfaces the original exception.
- An exception after response start sends no second response, emits one ERROR completion using the started status and `exc_info`, and re-raises the original exception.
- Do not add response buffering, body replay, streaming abstractions, background-task machinery, or speculative streaming support.
- Normal PantryPilot request records never contain request/response bodies, pantry ingredients, saved-pantry contents, exclusions, validation input/errors, raw paths, query values, `Authorization`, `Cookie`, arbitrary inbound headers, inbound request IDs, client IPs, database paths, SQLite statements, secrets, credentials, or environment names/values.
- Privacy is allowlist collection, not collect-then-redact. Unexpected `exc_info` is the narrow diagnostic exception; traceback tests use deliberately non-sensitive exception text.
- Install no handler or formatter; force no named-logger level; change no `propagate` value, root configuration, logger/root filter, handler formatter, or process-wide `LogRecordFactory`.
- Tests and deployment own capture, thresholds, handlers, formatter rendering, sinks, retention, and shipping. Do not change application logging merely to force INFO visibility under arbitrary deployment configuration.
- Do not configure, replace, or suppress Uvicorn access/error logging. Host logging of a re-raised exception is independent and does not count as a duplicate PantryPilot completion event.
- Startup/lifespan failures have no HTTP request and therefore receive no Feature 007 ID, response header, or completion record. Add no startup logging infrastructure.
- Add no request/ranking history, analytics, tracking, product telemetry, OpenTelemetry, trace export, aggregation, dashboards, alerts, metrics, authentication, accounts, multiple pantries, client-IP storage, request/response-body storage, retrieval/indexing/embeddings/ANN, catalog expansion, ranking changes, quantities/units, spoilage, multi-meal planning, personalization, learned ranking, LLM integration, branch protection, dependency upgrades, unrelated refactoring, or hosted observability.
- Use TDD for behavior changes: add the focused failing test, run it and confirm the named failure, add the minimum production behavior, rerun the focus, then run the relevant broader regression slice.
- Planned commit commands are future boundaries, not authorization. Commit only after the owner approves this plan and explicitly authorizes implementation commits. Never push, create a pull request, merge, or change repository settings from this plan.

---

## Planned File Structure and Responsibilities

### Create

- `src/pantrypilot/request_logging.py` — the only new production module. It owns the pure ASGI HTTP lifecycle observer, named logger lookup, authoritative response-header replacement, normalized-route selection, duration calculation, completion-record construction, severity, and unexpected-error response/re-raise behavior. This boundary keeps protocol/logging mechanics out of the already route-focused `app.py` without creating a package, interface hierarchy, formatter, serializer, or generic logging framework.
- `tests/test_request_logging.py` — focused HTTP- and ASGI-level acceptance evidence for Feature 007. A new file is smaller and more maintainable than adding another large concern to the existing 1,108-line `tests/test_api.py`; it reuses `create_app` and real endpoints rather than duplicating domain behavior.
- `docs/learning/007-request-correlation-logging.md` — the feature learning guide, practical explanation, and mock-interview answer guidance.

### Modify

- `src/pantrypilot/app.py:27-59` — import `RequestLoggingMiddleware` and register it once immediately after `FastAPI(...)` construction. Do not change routes, exception handlers, lifespan work, or response bodies.
- `README.md:14-31,189-216` — move current status to Feature 007, add the minimum operational contract for `X-Request-ID`, `pantrypilot.request`, and `request_completed`, and link the design, plan, and learning guide.
- `docs/product/vision.md:139-158` — add one narrow current-boundary paragraph recording ephemeral privacy-safe request correlation and its explicit infrastructure limits.
- `docs/roadmap.md:38-51` — record completion of Phase 3 request tracing while keeping ranking-request persistence/history deferred pending purpose, privacy, and retention semantics.

### Test without modifying

- `tests/test_api.py` — existing success, validation, 404, 422, 503, startup, and exact-body contracts.
- `tests/test_pantry_store.py`, `tests/test_database.py`, and `tests/test_catalog_store.py` — current storage failure, rollback, schema, startup, and database-detail behavior.
- `tests/test_ranking.py`, `tests/test_ranking_parity.py`, and `tests/test_saved_pantry_ranking_parity.py` — formulas, explanations, ordering, eligibility, limiting, durable-catalog parity, and inline/saved parity.
- `tests/test_catalog.py` and `tests/test_ingredients.py` — catalog and ingredient-resolution regressions.

### Explicitly unchanged

- `pyproject.toml` and `uv.lock` — no dependency or logging package is needed.
- `src/pantrypilot/models.py`, `ranking.py`, `pantry_store.py`, `catalog_store.py`, `database.py`, `ingredients.py`, and `catalog.py` — Feature 007 observes HTTP lifecycle behavior and does not alter domain, storage, persistence, or ranking contracts.
- All existing test files — new observability evidence lives in the focused test module; existing tests remain unedited regression oracles.
- The approved design — execution argues from it and does not revise it for convenience.

The implementation file map is therefore two production-file changes, one focused test file, and four narrow documentation changes. No additional helper module, configuration file, schema, dependency, or test-support package is justified.

---

## Verified Framework Assumptions

- A planning-only runtime probe on the locked environment observed middleware order `ServerErrorMiddleware`, `ProbeMiddleware`, `ExceptionMiddleware` after `FastAPI.add_middleware(...)`.
- A POST to registered GET route `/items/{item_id}` returned 405 and left `scope["route"].path_format == "/items/{item_id}"` for the pure ASGI middleware.
- A trailing-slash redirect returned 307 and left no route metadata, so `unmatched` is the exact conservative result on the installed stack.
- A pure ASGI probe that sent `PlainTextResponse("Internal Server Error", status_code=500)` and then re-raised produced the exact inspectable response when `raise_server_exceptions=False` and propagated the original `RuntimeError` under the default TestClient mode.

These are executable implementation assumptions, not a license to broaden the architecture. The 405 test is a hard stop if the implementation environment changes behavior.

---

## Pre-Implementation Plan Baseline

This section belongs to the future implementation thread. It does not authorize implementation or a commit in this planning thread.

- [ ] **Step 1: Revalidate the reviewed plan baseline**

Run exactly these read-only commands from the linked worktree:

```powershell
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short --branch
git rev-parse --git-dir
git rev-parse --git-common-dir
git diff --check
```

Expected: root `C:/Users/sathv/Projects/pantrypilot/.worktrees/request-correlation-logging`; branch `feat/request-correlation-logging`; HEAD `6ec60c0407c02dd03d2a1db9953f2d4aef295ccc`; the plan is the only uncommitted path; Git dir ends in `.git/worktrees/request-correlation-logging`; common dir is the primary checkout's `.git`; `git diff --check` exits 0. Stop without correcting any mismatch.

- [ ] **Step 2: Commit only the owner-reviewed plan when explicitly authorized**

```powershell
git add docs/superpowers/plans/2026-08-30-request-correlation-logging.md
git diff --cached --check
git diff --cached --name-only
git commit -m "docs: add request correlation logging plan"
```

Expected: the staged and committed path is exactly `docs/superpowers/plans/2026-08-30-request-correlation-logging.md`; no production, test, generated, environment, or local database file is included. Do not push.

- [ ] **Step 3: Require a clean implementation starting point**

```powershell
git status --short --branch
git log -2 --oneline --decorate
```

Expected: clean `feat/request-correlation-logging`; the plan commit follows the approved design commit. Task 1 starts only after owner/architect plan approval and implementation authorization.

---

### Task 1: Add the Normal and Handled Request Completion Contract

**Files:**

- Create: `src/pantrypilot/request_logging.py`
- Create: `tests/test_request_logging.py`
- Modify: `src/pantrypilot/app.py:27-59`
- Inspect only: `tests/test_api.py`, `src/pantrypilot/app.py`

**Interfaces:**

- Consumes Starlette `ASGIApp`, `Scope`, `Receive`, `Send`, and `Message`; Python `logging`, `time`, and `uuid`; and FastAPI's `add_middleware` registration.
- Produces one concrete class and no other public abstraction: constructor
  `RequestLoggingMiddleware(app: ASGIApp)` and method
  `RequestLoggingMiddleware.__call__(self, scope: Scope, receive: Receive, send: Send) -> None`.

- `self.app` is the only instance attribute. Request ID, clock values, response status, wrapped send, and completion state are invocation-local.
- HTTP scope output: `scope["pantrypilot.request_id"]: str`.
- Logger contract: `logging.getLogger("pantrypilot.request")`; message `request_completed`; custom fields `event_name`, `request_id`, `http_method`, `http_route`, `http_status_code`, and `duration_ms`.
- `src/pantrypilot/app.py` consumes only `RequestLoggingMiddleware` through `application.add_middleware(RequestLoggingMiddleware)`.

- [ ] **Step 1: Create focused failing tests for correlation, routing, timing, and handled responses**

Create `tests/test_request_logging.py` with these shared fixtures and assertions:

```python
import asyncio
import logging
import re
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

import pantrypilot.app as app_module
import pantrypilot.request_logging as request_logging
from pantrypilot.app import create_app
from pantrypilot.pantry_store import PantryStoreError
from pantrypilot.request_logging import RequestLoggingMiddleware

LOGGER_NAME = "pantrypilot.request"
REQUEST_ID_PATTERN = re.compile(r"[0-9a-f]{32}\Z")
STABLE_FIELDS = {
    "event_name",
    "request_id",
    "http_method",
    "http_route",
    "http_status_code",
    "duration_ms",
}
VALID_REQUEST = {
    "pantry_items": ["eggs", "spinach"],
    "min_protein_g": 0.0,
    "max_prep_minutes": 30,
    "excluded_ingredients": [],
    "limit": 1,
}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(create_app(tmp_path / "catalog.sqlite3")) as test_client:
        yield test_client


def request_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.name == LOGGER_NAME]


def assert_completion(
    record: logging.LogRecord,
    *,
    level: int,
    method: str,
    route: str,
    status: int,
) -> None:
    standard_fields = set(logging.makeLogRecord({}).__dict__) | {
        "message",
        "asctime",
    }
    assert record.getMessage() == "request_completed"
    assert record.levelno == level
    assert record.event_name == "request_completed"
    assert type(record.event_name) is str
    assert REQUEST_ID_PATTERN.fullmatch(record.request_id)
    assert type(record.request_id) is str
    assert record.http_method == method
    assert type(record.http_method) is str
    assert record.http_route == route
    assert type(record.http_route) is str
    assert record.http_status_code == status
    assert type(record.http_status_code) is int
    assert type(record.duration_ms) is float
    assert record.duration_ms >= 0.0
    assert set(record.__dict__) - standard_fields == STABLE_FIELDS
```

Add the successful request test with a deterministic server ID and a hostile inbound value:

```python
def test_success_correlates_server_id_header_and_one_info_record(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated = "0123456789abcdef0123456789abcdef"
    inbound = "INBOUND-ID-MUST-BE-IGNORED:" + ("log-like-content" * 64)
    monkeypatch.setattr(
        request_logging.uuid,
        "uuid4",
        lambda: UUID(hex=generated),
    )

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        response = client.post(
            "/v1/meal-rankings",
            json=VALID_REQUEST,
            headers={"X-Request-ID": inbound},
        )

    records = request_records(caplog)
    assert response.status_code == 200
    assert response.headers["x-request-id"] == generated
    assert REQUEST_ID_PATTERN.fullmatch(response.headers["x-request-id"])
    assert generated not in response.text
    assert len(records) == 1
    assert records[0].request_id == response.headers["x-request-id"]
    assert inbound not in repr(records[0].__dict__)
    assert_completion(
        records[0],
        level=logging.INFO,
        method="POST",
        route="/v1/meal-rankings",
        status=200,
    )
```

Add a direct ASGI test whose inner app emits mixed-case duplicate downstream correlation headers. Capture sent messages and assert the one `http.response.start` contains exactly one `(b"x-request-id", generated.encode("ascii"))` pair and no downstream value. Also assert the HTTP scope contains the same value at `pantrypilot.request_id` and that one record was emitted.

Add a direct ASGI fake-clock test with a route object `SimpleNamespace(path_format="/items/{item_id}")`, clock values `1_000_000_000` and `1_001_234_567`, and a 204 inner response:

```python
def test_fake_monotonic_clock_uses_exact_millisecond_rounding(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticks = iter((1_000_000_000, 1_001_234_567))
    monkeypatch.setattr(request_logging.time, "perf_counter_ns", lambda: next(ticks))

    async def inner_app(scope, receive, send) -> None:
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    sent: list[dict[str, object]] = []

    async def send(message) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/items/private-value",
        "route": SimpleNamespace(path_format="/items/{item_id}"),
    }
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        asyncio.run(RequestLoggingMiddleware(inner_app)(scope, receive, send))

    record = request_records(caplog)[0]
    assert record.duration_ms == 1.235
    assert type(record.duration_ms) is float
    assert record.duration_ms >= 0.0
    assert record.http_route == "/items/{item_id}"
```

Add these exact HTTP tests in the same task:

- `test_validation_422_keeps_public_contract_and_logs_info`: omit `limit` from `VALID_REQUEST`; assert status 422, the first detail has `type == "missing"` and `loc == ["body", "limit"]`, one INFO record, route `/v1/meal-rankings`, no `exc_info`, and header/record ID equality. The unchanged exact validation tests in `tests/test_api.py` remain the full body oracle.
- `test_application_422_keeps_resolution_body_and_logs_info`: POST `VALID_REQUEST` with `excluded_ingredients=["groundnut"]`; assert the exact existing `unresolved_excluded_ingredients` body, including the complete unresolved resolution object, one INFO record, route `/v1/meal-rankings`, no `exc_info`, and header/record ID equality.
- `test_saved_pantry_404_keeps_exact_body_and_logs_info`: GET absent `/v1/saved-pantry`; assert the exact existing `saved_pantry_not_found` JSON, one INFO record, normalized route, no `exc_info`, and header/record ID equality.
- `test_saved_pantry_503_keeps_exact_body_and_logs_warning_without_exception`: monkeypatch `app_module.load_saved_pantry` to raise `PantryStoreError("DATABASE_PATH_SENTINEL: SELECT SQL_SENTINEL")`; assert the exact existing `saved_pantry_unavailable` JSON, one WARNING record, normalized route, `record.exc_info is None`, and absence of both sentinels from `record.getMessage()` and `repr(record.__dict__)`.
- `test_405_uses_normalized_route`: DELETE `/v1/saved-pantry`; assert exact 405 body `{"detail": "Method Not Allowed"}`, INFO, status 405, route `/v1/saved-pantry`, one event, and correlation equality. If the route is not normalized on the installed framework, stop and report the contradiction.
- `test_redirect_without_route_metadata_is_info_and_unmatched`: request `/v1/saved-pantry/` with redirects disabled; assert 307, INFO, status 307, route `unmatched`, and absence of the raw request path from the record.
- `test_unmatched_404_is_private`: request `/PRIVATE_RAW_PATH_SENTINEL?q=PRIVATE_QUERY_SENTINEL`; assert exact default 404 JSON, INFO, status 404, route `unmatched`, and absence of both sentinels from all PantryPilot record values.
- `test_non_http_scope_passes_through_without_correlation`: invoke the middleware directly with a representative lifespan scope, have the inner app record the unchanged scope and messages, and assert no `pantrypilot.request_id` key and no PantryPilot completion record.

- [ ] **Step 2: Run the focused tests and confirm the intended failure**

```powershell
uv run pytest tests/test_request_logging.py -v
```

Expected: collection fails because `pantrypilot.request_logging` and `RequestLoggingMiddleware` do not exist. No production behavior is added before this failure is observed.

- [ ] **Step 3: Implement the minimum normal/handled pure ASGI observer**

Create `src/pantrypilot/request_logging.py` with this complete normal/handled implementation; Task 2 adds only the approved unexpected-exception branch:

```python
import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_LOGGER = logging.getLogger("pantrypilot.request")
REQUEST_ID_HEADER = b"x-request-id"


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        scope["pantrypilot.request_id"] = request_id
        start_ns = time.perf_counter_ns()
        response_status: int | None = None

        async def send_with_request_id(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != REQUEST_ID_HEADER
                ]
                headers.append((REQUEST_ID_HEADER, request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        def emit_completion(level: int, *, exc_info: bool = False) -> None:
            assert response_status is not None
            route = getattr(scope.get("route"), "path_format", None)
            http_route = route if isinstance(route, str) else "unmatched"
            REQUEST_LOGGER.log(
                level,
                "request_completed",
                extra={
                    "event_name": "request_completed",
                    "request_id": request_id,
                    "http_method": scope["method"],
                    "http_route": http_route,
                    "http_status_code": response_status,
                    "duration_ms": round(
                        (time.perf_counter_ns() - start_ns) / 1_000_000,
                        3,
                    ),
                },
                exc_info=exc_info,
            )

        await self.app(scope, receive, send_with_request_id)
        assert response_status is not None
        emit_completion(
            logging.WARNING if response_status >= 500 else logging.INFO
        )
```

Modify only app construction in `src/pantrypilot/app.py`:

```python
from pantrypilot.request_logging import RequestLoggingMiddleware

application = FastAPI(title="PantryPilot", lifespan=lifespan)
application.add_middleware(RequestLoggingMiddleware)
```

Do not move or edit the existing exception handlers or routes. `add_middleware` is the only topology change.

- [ ] **Step 4: Run focused and public-contract tests**

```powershell
uv run pytest tests/test_request_logging.py -v
uv run pytest tests/test_api.py -v
uv run pytest tests/test_ranking.py tests/test_ranking_parity.py tests/test_saved_pantry_ranking_parity.py -v
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: every Task 1 request-logging test passes; all existing exact API bodies and ranking/parity behavior pass unchanged; Ruff and whitespace checks exit 0. The pre-existing unexpected-500 API tests may still pass their old generic-body assertion, but Task 2's new header/event/propagation tests do not exist yet.

- [ ] **Step 5: Review the Task 1 diff**

```powershell
git diff -- src/pantrypilot/request_logging.py src/pantrypilot/app.py tests/test_request_logging.py
git diff -- src/pantrypilot/models.py src/pantrypilot/ranking.py src/pantrypilot/pantry_store.py pyproject.toml uv.lock
```

Expected: the first diff contains only the pure ASGI module, one registration, and focused tests; the second diff is empty. Confirm there is one logger lookup, one middleware registration, no handler/formatter/configuration call, no request-body read, no raw-path fallback, and no mutable request value on `self`.

- [ ] **Step 6: Commit the independently testable normal/handled slice when authorized**

```powershell
git add src/pantrypilot/request_logging.py src/pantrypilot/app.py tests/test_request_logging.py
git commit -m "feat: add request completion logging"
```

Do not push.

---

### Task 2: Correlate Unexpected Failures and Prove Isolation Boundaries

**Files:**

- Modify: `src/pantrypilot/request_logging.py`
- Modify: `tests/test_request_logging.py`
- Inspect only: `src/pantrypilot/app.py`, `tests/test_api.py`, `tests/test_pantry_store.py`, `tests/test_database.py`

**Interfaces:**

- Retains the Task 1 `RequestLoggingMiddleware` constructor, ASGI call signature, scope key, logger name, message, and six stable fields unchanged.
- Adds only Starlette `PlainTextResponse` inside the same module for an unexpected exception before response start.
- `emit_completion(logging.ERROR, exc_info=True)` runs while the original exception is active, then a bare `raise` preserves propagation.
- No ContextVar, shared completion flag, response buffer, catch-all FastAPI handler, second event, or exception serializer is produced.

- [ ] **Step 1: Add failing tests for both unexpected-exception branches**

Add a `safe_client` fixture using `raise_server_exceptions=False`, then add:

```python
NON_SENSITIVE_DIAGNOSTIC = "NON_SENSITIVE_DIAGNOSTIC_EVIDENCE"


@pytest.fixture
def safe_client(tmp_path: Path) -> Iterator[TestClient]:
    with TestClient(
        create_app(tmp_path / "safe-catalog.sqlite3"),
        raise_server_exceptions=False,
    ) as test_client:
        yield test_client


def test_unexpected_failure_returns_exact_correlated_500_and_one_error(
    safe_client: TestClient,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_ranking(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError(NON_SENSITIVE_DIAGNOSTIC)

    monkeypatch.setattr(app_module, "rank_recipes", fail_ranking)
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        response = safe_client.post("/v1/meal-rankings", json=VALID_REQUEST)

    records = request_records(caplog)
    assert response.status_code == 500
    assert response.content == b"Internal Server Error"
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert REQUEST_ID_PATTERN.fullmatch(response.headers["x-request-id"])
    assert NON_SENSITIVE_DIAGNOSTIC not in response.text
    assert len(records) == 1
    assert records[0].request_id == response.headers["x-request-id"]
    assert records[0].levelno == logging.ERROR
    assert records[0].http_status_code == 500
    assert_completion(
        records[0],
        level=logging.ERROR,
        method="POST",
        route="/v1/meal-rankings",
        status=500,
    )
    assert records[0].exc_info is not None
    assert str(records[0].exc_info[1]) == NON_SENSITIVE_DIAGNOSTIC
    assert NON_SENSITIVE_DIAGNOSTIC in caplog.text
```

Add `test_default_testclient_reraises_original_after_one_error`: use an ordinary `TestClient`, monkeypatch the same failure, assert `pytest.raises(RuntimeError, match=NON_SENSITIVE_DIAGNOSTIC)`, and assert exactly one `pantrypilot.request` record at ERROR with non-null `exc_info`. Do not assert absence of independent host/test harness error logging.

Add the ASGI-level post-start test without an async test dependency:

```python
def test_exception_after_response_start_sends_no_second_start(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sent: list[dict[str, object]] = []

    async def response_then_fail(scope, receive, send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 206,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        raise RuntimeError(NON_SENSITIVE_DIAGNOSTIC)

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/PRIVATE_POST_START_PATH",
    }
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        with pytest.raises(RuntimeError, match=NON_SENSITIVE_DIAGNOSTIC):
            asyncio.run(
                RequestLoggingMiddleware(response_then_fail)(scope, receive, send)
            )

    starts = [message for message in sent if message["type"] == "http.response.start"]
    records = request_records(caplog)
    assert len(starts) == 1
    assert len(records) == 1
    response_headers = dict(starts[0]["headers"])
    assert REQUEST_ID_PATTERN.fullmatch(response_headers[b"x-request-id"].decode())
    assert records[0].request_id == response_headers[b"x-request-id"].decode()
    assert_completion(
        records[0],
        level=logging.ERROR,
        method="GET",
        route="unmatched",
        status=206,
    )
    assert records[0].exc_info is not None
```

- [ ] **Step 2: Add privacy, concurrency, configuration, and startup evidence**

Extend the existing module import block only when this task adds the tests that
use these names. Keep `sqlite3` with the standard-library imports and
`CatalogStoreError` with the `pantrypilot` imports:

```python
import sqlite3

from pantrypilot.catalog_store import CatalogStoreError
```

Add one allowlist-negative test with these distinct sentinels:

```python
PRIVACY_SENTINELS = {
    "PANTRY_INPUT_SENTINEL_007",
    "SAVED_PANTRY_DATA_SENTINEL_007",
    "EXCLUDED_INPUT_SENTINEL_007",
    "VALIDATION_INPUT_SENTINEL_007",
    "RAW_PATH_SENTINEL_007",
    "QUERY_VALUE_SENTINEL_007",
    "AUTHORIZATION_SENTINEL_007",
    "COOKIE_SENTINEL_007",
    "ARBITRARY_HEADER_SENTINEL_007",
    "INBOUND_REQUEST_ID_SENTINEL_007",
    "CLIENT_IP_SENTINEL_007",
    "DATABASE_PATH_SENTINEL_007",
    "SELECT_SQL_SENTINEL_007",
    "SECRET_SENTINEL_007",
    "CREDENTIAL_SENTINEL_007",
    "CHAINED_CAUSE_SENTINEL_007",
    "FEATURE007_ENV_NAME_SENTINEL",
    "ENV_VALUE_SENTINEL_007",
}
```

Inside `test_normal_and_handled_records_exclude_every_privacy_sentinel`:

1. Set environment variable `FEATURE007_ENV_NAME_SENTINEL=ENV_VALUE_SENTINEL_007` with `monkeypatch.setenv`.
2. Create the database at `tmp_path / "DATABASE_PATH_SENTINEL_007.sqlite3"` and construct `TestClient(application, client=("CLIENT_IP_SENTINEL_007", 65000))` so the ASGI client tuple contains a recognizable value.
3. POST inline ranking with pantry item `PANTRY_INPUT_SENTINEL_007` and exclusion `EXCLUDED_INPUT_SENTINEL_007`; assert both inputs remain in the exact approved public 422 ingredient-resolution evidence and its completion is INFO on `/v1/meal-rankings`.
4. POST a request with extra field `future_field="VALIDATION_INPUT_SENTINEL_007"`; assert that sentinel remains in the public validation 422 detail and its completion is INFO.
5. Insert marker 1 plus durable ingredient ID `SAVED_PANTRY_DATA_SENTINEL_007` directly through `sqlite3` into the initialized test database, then GET `/v1/saved-pantry`; assert the exact safe 503, one WARNING completion, and no `exc_info`. This makes the saved-pantry sentinel actual corrupt durable content rather than merely submitted request text.
6. GET `/RAW_PATH_SENTINEL_007?q=QUERY_VALUE_SENTINEL_007` with `Authorization`, `Cookie`, `X-Arbitrary-Header`, and hostile inbound `X-Request-ID` values from the sentinel set; assert the unmatched completion is INFO and records exactly `unmatched`.
7. Monkeypatch `app_module.load_saved_pantry` to raise one `PantryStoreError` containing the database-path, SQL-like, secret, credential, and environment sentinels `from RuntimeError("CHAINED_CAUSE_SENTINEL_007")`; GET `/v1/saved-pantry` and assert the exact safe 503, WARNING, and no `exc_info`.
8. Filter only `pantrypilot.request` records, assert one per issued request, assert every normal/handled record has `exc_info is None`, build `captured = "\n".join(record.getMessage() + repr(record.__dict__) for record in records)`, and assert every string in `PRIVACY_SENTINELS` is absent.

This is the required asymmetric proof: request-derived unresolved and validation inputs remain in their approved public 422 responses but never enter the PantryPilot completion records.

Add the deliberately overlapping synchronous-route test:

```python
def test_overlapping_synchronous_requests_keep_ids_isolated(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    barrier = Barrier(2)
    real_rank_recipes = app_module.rank_recipes

    def overlapping_rank(*args, **kwargs):
        barrier.wait(timeout=5)
        return real_rank_recipes(*args, **kwargs)

    monkeypatch.setattr(app_module, "rank_recipes", overlapping_rank)
    with TestClient(create_app(tmp_path / "concurrent.sqlite3")) as client:
        with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(
                        client.post,
                        "/v1/meal-rankings",
                        json=VALID_REQUEST,
                    )
                    for _ in range(2)
                ]
                responses = [future.result(timeout=10) for future in futures]

    records = request_records(caplog)
    response_ids = [response.headers["x-request-id"] for response in responses]
    record_ids = [record.request_id for record in records]
    assert all(response.status_code == 200 for response in responses)
    assert len(set(response_ids)) == 2
    assert len(records) == 2
    assert sorted(record_ids) == sorted(response_ids)
    assert all(record_ids.count(request_id) == 1 for request_id in response_ids)
```

Add this logger snapshot helper and configuration-ownership test. Enter test-owned capture before taking the baseline so pytest's temporary capture configuration is not attributed to PantryPilot:

```python
def logger_snapshot(logger: logging.Logger) -> tuple[object, ...]:
    return (
        logger.level,
        tuple(logger.handlers),
        tuple(logger.filters),
        logger.propagate,
        tuple(handler.formatter for handler in logger.handlers),
    )


def test_application_does_not_reconfigure_logging(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    named_logger = logging.getLogger(LOGGER_NAME)
    root_logger = logging.getLogger()

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        named_before = logger_snapshot(named_logger)
        root_before = logger_snapshot(root_logger)
        factory_before = logging.getLogRecordFactory()

        with TestClient(create_app(tmp_path / "logging-state.sqlite3")) as client:
            response = client.post("/v1/meal-rankings", json=VALID_REQUEST)

        assert response.status_code == 200
        assert logger_snapshot(named_logger) == named_before
        assert logger_snapshot(root_logger) == root_before
        assert logging.getLogRecordFactory() is factory_before
```

The tuples preserve the exact handler/filter objects and each pre-existing handler's formatter object. Do not assert a particular initial level, propagation value, handler count, formatter, or factory; assert only that PantryPilot leaves the deployment/test-owned state unchanged.

Add `test_startup_failure_emits_no_request_completion`: within test-owned log capture, create `create_app(tmp_path)` where `tmp_path` is a directory and assert entering `TestClient` raises the existing `CatalogStoreError`; assert `request_records(caplog) == []`.

- [ ] **Step 3: Run the unexpected-error focus and observe the missing contract**

```powershell
uv run pytest tests/test_request_logging.py::test_unexpected_failure_returns_exact_correlated_500_and_one_error tests/test_request_logging.py::test_default_testclient_reraises_original_after_one_error tests/test_request_logging.py::test_exception_after_response_start_sends_no_second_start -v
```

Expected after Task 1: FAIL because an exception bypasses the normal completion emission; the outer server-error response has no PantryPilot `X-Request-ID`; the post-start case has no PantryPilot ERROR completion record. The original exceptions still propagate under the raising modes.

- [ ] **Step 4: Add the minimum unexpected-exception branch**

Import `PlainTextResponse` and replace Task 1's final `await self.app(...)` plus normal emission with this exact control flow:

```python
from starlette.responses import PlainTextResponse


        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            if response_status is None:
                response = PlainTextResponse(
                    "Internal Server Error",
                    status_code=500,
                )
                await response(scope, receive, send_with_request_id)
            emit_completion(logging.ERROR, exc_info=True)
            raise
        else:
            assert response_status is not None
            emit_completion(
                logging.WARNING if response_status >= 500 else logging.INFO
            )
```

Do not catch `BaseException`, suppress the exception, add a FastAPI handler, attach exception text as a custom field, or emit another log call. The pre-response `PlainTextResponse` passes through the same wrapped send, so status capture and authoritative header replacement remain single-path behavior.

- [ ] **Step 5: Run all Feature 007 tests and the relevant regression slices**

```powershell
uv run pytest tests/test_request_logging.py -v
uv run pytest tests/test_api.py tests/test_pantry_store.py tests/test_database.py tests/test_catalog_store.py -v
uv run pytest tests/test_ranking.py tests/test_ranking_parity.py tests/test_saved_pantry_ranking_parity.py tests/test_catalog.py tests/test_ingredients.py -v
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: exact correlated 500 behavior passes in both TestClient modes; the post-start probe has one start and one ERROR event; privacy sentinels are absent; overlapping synchronous requests retain unique matching IDs; logger/root/factory snapshots are unchanged; startup emits no request event; all existing API, storage, catalog, ranking, explanation, ordering, eligibility, limiting, resolution, and parity tests pass unchanged.

- [ ] **Step 6: Review duplicate-event, exception, privacy, and shared-state risks**

```powershell
rg -n "REQUEST_LOGGER\.|getLogger|basicConfig|addHandler|setLevel|propagate|setLogRecordFactory|ContextVar|scope\[\"path\"\]|query_string|headers|request\.body|response\.body" src/pantrypilot/request_logging.py src/pantrypilot/app.py
git diff -- src/pantrypilot/request_logging.py tests/test_request_logging.py
git diff -- src/pantrypilot/models.py src/pantrypilot/ranking.py src/pantrypilot/pantry_store.py src/pantrypilot/catalog_store.py src/pantrypilot/database.py pyproject.toml uv.lock
```

Expected: one named logger, one completion call inside the request-local emitter, no configuration API, no ContextVar, no raw-path/query/body/header collection except bounded response-header replacement, and no prohibited-file diff. `exc_info=True` appears only on the unexpected ERROR branch; handled 503 records have no exception evidence.

- [ ] **Step 7: Commit the completed failure and isolation contract when authorized**

```powershell
git add src/pantrypilot/request_logging.py tests/test_request_logging.py
git commit -m "feat: correlate unexpected request failures"
```

Do not push.

---

### Task 3: Document the Exact Operational Boundary

**Files:**

- Create: `docs/learning/007-request-correlation-logging.md`
- Modify: `README.md:14-31,189-216`
- Modify: `docs/product/vision.md:139-158`
- Modify: `docs/roadmap.md:38-51`
- Inspect only: `docs/learning/004-durable-saved-pantry.md`, `docs/learning/006-representative-catalog-expansion.md`

**Interfaces:**

- Consumes the verified `X-Request-ID`, `pantrypilot.request`, `request_completed`, six-field schema, severity policy, privacy boundary, and middleware/error behavior from Tasks 1-2.
- Produces documentation only. No executable configuration, deployment sink, logger formatter, external service, or new promise is introduced.

- [ ] **Step 1: Write the Feature 007 learning guide in established project style**

Create `docs/learning/007-request-correlation-logging.md` with these exact sections and content boundaries:

```markdown
# Feature 007: Request correlation and privacy-safe structured logging

## Capability and non-goals
## Correlation IDs, logs, metrics, and distributed traces
## Request-ID ownership, capabilities, and limits
## Privacy-safe allowlist logging
## Normalized routes instead of raw paths
## Pure ASGI middleware and exception ownership
## Monotonic duration measurement
## Concurrency and synchronous FastAPI endpoints
## Internal traceback evidence and sanitized clients
## Logger, handler, formatter, and root ownership
## Uvicorn logging remains separate
## Captured-log testing without an external service
## Run and inspect
## Practical exercises
## Mock-interview questions and answer guidance
```

Explain all of the following in those sections:

- correlation IDs connect one response to one application event; they are not logs, latency/error metrics, cross-service trace propagation, aggregation, or user history;
- server generation and ignored inbound IDs bound trust, format, and length but do not authenticate a caller or correlate multiple services;
- normal records are allowlist-built from six fields and never collect bodies, pantry data, headers, paths, queries, client IPs, storage details, or environment data;
- normalized route templates bound cardinality and protect user-controlled path values; `unmatched` is intentionally less specific than a raw fallback;
- the pure ASGI layer sits between `ServerErrorMiddleware` and `ExceptionMiddleware`, observes handled responses, sends a correlated sanitized response for an unexpected pre-start exception, logs once, and re-raises;
- `perf_counter_ns` is monotonic and duration is `round((end_ns - start_ns) / 1_000_000, 3)` with no display-format or latency-SLO promise;
- invocation-local state remains correct while synchronous routes execute in worker threads; no ContextVar is needed because domain logs are not being enriched;
- unexpected `exc_info` is internal diagnostic evidence, client bodies remain sanitized, and deliberately sensitive exception strings are not made safe by this feature;
- applications emit through a named logger while deployments/tests own levels, handlers, formatters, sinks, retention, and shipping;
- Uvicorn access/error logs may independently contain other data and are outside the `pantrypilot.request` privacy contract;
- pytest capture or an in-memory standard-library handler proves fields and severity without OpenTelemetry or a hosted service;
- practical exercises cover matching a response header to a captured record, 405 versus unmatched routing, a fake monotonic clock, the two TestClient exception modes, and overlapping synchronous requests;
- mock-interview questions include concise answer guidance for every topic above and follow the established one-attempt-then-correction owner-understanding pattern.

- [ ] **Step 2: Make the minimum README update**

Update current status to Feature 007 without removing the established Feature 006 catalog baseline. Add this operational summary in substance:

```markdown
## Request correlation and logging

Every PantryPilot HTTP response carries a server-generated `X-Request-ID`.
PantryPilot ignores inbound values and emits one `pantrypilot.request`
`request_completed` LogRecord with request ID, method, normalized route (or
`unmatched`), status, and monotonic duration. Expected outcomes are INFO,
handled 5xx responses are WARNING, and unexpected failures are ERROR with
internal traceback evidence while clients receive the exact sanitized 500.

PantryPilot installs no logging handler or formatter and does not configure the
root logger. Deployment owns rendering, sinks, retention, and shipping. The
event excludes request/response bodies, pantry data, raw paths, query values,
headers, client IPs, and storage details; it is request correlation, not
request history, metrics, distributed tracing, or hosted observability.
```

Add Feature 007 design, plan, and learning-guide links under Project documents. Do not add deployment configuration or claim that INFO is always visible.

- [ ] **Step 3: Record only supported vision and roadmap status**

Append this narrow current-boundary statement to `docs/product/vision.md`:

```markdown
Feature 007 adds ephemeral, server-owned request IDs and one privacy-safe
application completion record per HTTP request. PantryPilot persists neither
request IDs nor events and adds no metrics, distributed traces, aggregation,
dashboards, alerts, or hosted observability infrastructure.
```

In Roadmap Phase 3, preserve the phase's historical goals and add a status paragraph in substance:

```markdown
Status: recipe and saved-pantry persistence, schema migrations, stable durable
identities, storage/domain separation, production-oriented API errors, and
privacy-safe request tracing are implemented. Ranking-request persistence and
history remain deferred until their purpose, privacy, and retention semantics
are approved.
```

Do not mark OpenTelemetry, metrics, distributed traces, aggregation, dashboards, alerts, hosted infrastructure, or ranking-request persistence complete.

- [ ] **Step 4: Verify documentation accuracy and links**

```powershell
rg -n "X-Request-ID|pantrypilot\.request|request_completed|007-request-correlation-logging" README.md docs/learning/007-request-correlation-logging.md docs/product/vision.md docs/roadmap.md
rg -n "OpenTelemetry|metrics|distributed traces|aggregation|dashboards|alerts|hosted observability|request history|ranking-request" README.md docs/learning/007-request-correlation-logging.md docs/product/vision.md docs/roadmap.md
git diff --check
```

Expected: the first search finds the exact public/event names and learning link; every second-search occurrence explicitly distinguishes a non-goal, deferred capability, or deployment-owned boundary rather than claiming implementation.

- [ ] **Step 5: Run docs-adjacent tests and commit when authorized**

```powershell
uv run pytest tests/test_request_logging.py tests/test_api.py -v
git diff -- README.md docs/learning/007-request-correlation-logging.md docs/product/vision.md docs/roadmap.md
git diff --check
```

Expected: Feature 007 and existing API contracts pass; documentation describes only verified behavior and no infrastructure overclaim.

```powershell
git add README.md docs/learning/007-request-correlation-logging.md docs/product/vision.md docs/roadmap.md
git commit -m "docs: document request correlation logging"
```

Do not push.

---

### Task 4: Complete Authoritative Verification and Scope Audit

**Files:**

- Verify: every file named in the plan's create/modify/test map
- Modify after a failure: only the file directly responsible, using the same focused failing-test cycle before rerunning this task
- Do not commit an unreviewed fix or amend earlier commits without owner authorization

**Interfaces:**

- Consumes the completed Task 1-3 implementation and documentation.
- Produces verification evidence only; no benchmark threshold, generated artifact, deployment configuration, push, or pull request.

- [ ] **Step 1: Run the focused Feature 007 contract**

```powershell
uv run pytest tests/test_request_logging.py -v
```

Expected: request ID syntax/ownership/header equality, one-event count, stable fields/types, success/redirect/4xx/503/error severity, normalized and unmatched routes, exact timing, handled public bodies, both unexpected-failure modes, no second post-start response, privacy negatives, logging configuration ownership, startup exclusion, and overlapping-request isolation all pass.

- [ ] **Step 2: Run API, storage, and startup regressions**

```powershell
uv run pytest tests/test_api.py tests/test_pantry_store.py tests/test_database.py tests/test_catalog_store.py -v
```

Expected: successful bodies, RequestValidationError serialization, application 404/422, exact saved-pantry 503, generic unexpected 500 privacy, startup fail-closed behavior, storage rollback/integrity, and catalog hydration all remain compatible.

- [ ] **Step 3: Run ranking, catalog, and ingredient-resolution regressions**

```powershell
uv run pytest tests/test_ranking.py tests/test_ranking_parity.py tests/test_saved_pantry_ranking_parity.py tests/test_catalog.py tests/test_ingredients.py tests/test_evaluation.py -v
```

Expected: formulas, explanations, ordering, eligibility, limiting, inline/saved parity, catalog behavior, pantry-derived ranking, and ingredient-resolution evidence pass unchanged.

- [ ] **Step 4: Run the authoritative repository contract exactly**

Run each command separately:

```powershell
uv lock --check
uv run pytest
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v2.json
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: every command exits 0; the suite exceeds the approved 374-test baseline only by the focused Feature 007 tests; ingredient-resolution v2 reports precision `1.0`, recall `1.0`, FP `0`, and FN `0`; there is no latency or benchmark threshold.

- [ ] **Step 5: Audit the final file and dependency scope**

```powershell
git status --short --branch
git diff 6ec60c0407c02dd03d2a1db9953f2d4aef295ccc --name-status
git diff 6ec60c0407c02dd03d2a1db9953f2d4aef295ccc -- pyproject.toml uv.lock src/pantrypilot/models.py src/pantrypilot/ranking.py src/pantrypilot/pantry_store.py src/pantrypilot/catalog_store.py src/pantrypilot/database.py src/pantrypilot/ingredients.py src/pantrypilot/catalog.py
git log --oneline --decorate 6ec60c0407c02dd03d2a1db9953f2d4aef295ccc..HEAD
```

Expected: changed implementation paths match this plan; the prohibited dependency/domain/storage diff is empty; no database, cache, credential, environment, captured log, or generated file exists; local commit subjects match the intended sequence; nothing has been pushed.

- [ ] **Step 6: Re-run the design coverage and self-review audit**

Compare the actual diff and test names against every item in the Approved Design Coverage Map and Plan Self-Review Record below. If a required assertion lacks executable evidence, return to the responsible task, write the focused failing test, make the minimum correction, rerun that task's focused and broader commands, then repeat the authoritative contract. Stop after reporting verified local implementation; do not push or open a pull request.

---

## Intended Commit Boundaries

1. `docs: add request correlation logging plan` — this owner-reviewed plan only, after explicit authorization and before Task 1.
2. `feat: add request completion logging` — Task 1 pure ASGI normal/handled observer, one app registration, and correlation/route/timing/severity tests.
3. `feat: correlate unexpected request failures` — Task 2 exact sanitized failures, `exc_info`/re-raise behavior, post-start protection, privacy, concurrency, logger-ownership, and startup evidence.
4. `docs: document request correlation logging` — Task 3 learning guide, README summary/links, and narrow vision/roadmap status.

Task 4 produces verification evidence and no planned commit. No commit is pushed and no pull request is created by this plan.

---

## Approved Design Coverage Map

- Pure ASGI topology, HTTP-only processing, and unchanged inner handlers: Tasks 1-2.
- Server-owned `uuid.uuid4().hex`, exact syntax/length, ignored inbound ID, authoritative replacement, header-only exposure, and scope key: Task 1.
- One named logger, one `request_completed` message/event, exact six custom fields/types, allowlist construction, and no arbitrary payload merge: Task 1.
- INFO success/redirect/4xx, WARNING handled 503 without exception details, and ERROR unexpected 500 with `exc_info`: Tasks 1-2.
- Normalized matched routes, exact `unmatched` fallback, 405 framework proof, redirect fallback, and raw path/query exclusion: Tasks 1-2.
- Exact `perf_counter_ns` formula, float, non-negative value, three-digit rounding, and no latency threshold: Tasks 1 and 4.
- Invocation-local mutable state, synchronous worker-thread overlap, unique IDs, and no ContextVar: Task 2.
- Existing success, HTTPException, 404, 422, RequestValidationError, and saved-pantry 503 public bodies: Tasks 1, 2, and 4.
- Exact pre-start correlated sanitized 500, one ERROR event, client traceback exclusion, inspectable non-raising TestClient mode, original-exception propagation, and no duplicate PantryPilot event: Task 2.
- Post-response-start status reuse, one ERROR event, no second start, and original propagation: Task 2.
- Every named privacy sentinel plus the public-422/log asymmetry: Task 2.
- No named/root logger, handler, formatter, filter, propagation, or LogRecordFactory changes; capture without an external backend: Task 2.
- Uvicorn separation and no host-log suppression: Tasks 2-3.
- Startup/lifespan failure receives no request ID/event and no startup infrastructure: Task 2.
- Ranking, explanation, ordering, eligibility, inline/saved parity, catalog, pantry, and ingredient-resolution regressions: Tasks 1, 2, and 4.
- Learning topics, mock-interview guidance, README contract, and narrow vision/roadmap completion language: Task 3.
- No dependency, persistence, telemetry, infrastructure, unrelated feature, or non-goal creep: every task, audited in Task 4.
- Full uv/pytest/evaluator/Ruff/whitespace contract and approved baseline metrics: Task 4.

---

## Plan Self-Review Record

1. **Complete spec coverage:** Every design section and acceptance criterion maps to a task and executable evidence in the coverage map.
2. **Placeholder scan:** The plan contains no deferred implementation marker, unspecified handler, unnamed test, or instruction to imitate another task. Task 1 gives the exact constructor/call interface and the complete incremental body in its implementation step.
3. **Type/name consistency:** `RequestLoggingMiddleware`, `REQUEST_LOGGER`, `REQUEST_ID_HEADER`, `scope["pantrypilot.request_id"]`, `pantrypilot.request`, `request_completed`, and all six custom field names are consistent across production, tests, and docs.
4. **Privacy evidence:** Task 2 names separate sentinels for pantry input, saved durable data, exclusions, validation input, raw path, query, authorization, cookie, arbitrary header, inbound ID, client IP, database path, SQL-like text, secret, credential, chained cause, environment name, and environment value; it also pins the asymmetric public 422 case.
5. **Duplicate-event safety:** Normal/handled and unexpected branches are mutually exclusive; both call one request-local emitter once. No handler or second exception event exists, and every error test filters specifically to `pantrypilot.request`.
6. **Exception propagation:** Pre-start failures send through the wrapped `send`, log under the active exception, and bare-raise. Post-start failures never send another response and bare-raise with the started status.
7. **Response compatibility:** The middleware mutates only response-start headers; existing API tests remain unchanged body oracles. No response body gains a correlation ID.
8. **Route privacy:** Route selection accepts only a string `path_format`; every absence becomes exact `unmatched`. No production access to `scope["path"]`, URL, or query exists.
9. **Logging ownership:** Production performs only `getLogger` and `Logger.log`; tests snapshot levels, handlers, filters, propagation, formatter identities, root state, and record factory after test-owned capture is enabled.
10. **No shared-state creep:** `self.app` is the only middleware-instance attribute; no ContextVar, current request, clock, status, exception, or flag is shared.
11. **Smallest file structure:** One focused production module and one focused test module avoid both `app.py` bloat and a logging framework. Existing domain/storage/test files stay unchanged.
12. **Task ordering:** Normal/handled lifecycle establishes the shared send/log path before error ownership reuses it; complete behavioral evidence precedes documentation; authoritative verification is last.
13. **Focused commands:** Each behavior task names an initial failing command, focused pass, broader regressions, Ruff, and whitespace checks; final verification repeats the repository contract. Task 1's scaffold imports only names used by Task 1, while Task 2 introduces `sqlite3` and `CatalogStoreError` with their consuming privacy/startup tests.
14. **Commit boundaries:** Each future commit is independently reviewable: reviewed plan, normal/handled lifecycle, failure/isolation contract, and documentation. No scaffolding-only production commit exists.
15. **Documentation claims:** README, vision, roadmap, and learning text explicitly deny metrics, traces, aggregation, dashboards, alerts, hosted infrastructure, and request history while recording only request tracing.
16. **Non-goals:** No task introduces persistence, analytics, bodies, client IPs, Uvicorn configuration, startup logging, streaming machinery, dependencies, ranking changes, or unrelated cleanup.
17. **Framework assumption:** The installed 405 behavior was directly observed and is pinned by a hard-stop integration test. Redirect behavior is conservatively pinned to `unmatched` on the same installed stack.
18. **Verification baseline:** The exact six authoritative commands, 374-test baseline, and ingredient-resolution precision/recall/FP/FN values are recorded; no benchmark or latency gate was added.

Execution ends after Task 4 evidence is reported. Do not push, create a pull request, or begin unrelated work.
