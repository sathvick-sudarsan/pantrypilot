# Feature 007: Request correlation and privacy-safe structured logging

Status: Owner-approved design

Design date: 2026-08-29

Owner approval date: 2026-08-29

GitHub issue: [#13](https://github.com/sathvick-sudarsan/pantrypilot/issues/13)

## 1. Context and verified baseline

PantryPilot has explicit HTTP success and failure contracts but no
application-owned identity connecting a user-observed response with its
server-side request event. Feature 007 adds that narrow correlation contract
without creating request history, analytics, or telemetry infrastructure.

This design was prepared from linked worktree
`request-correlation-logging`, branch `feat/request-correlation-logging`, at
commit `af30ffe660b763e17c844d4da38924a54b5ac5bc`. The worktree was clean before
the design file was created.

Repository and installed-framework inspection established the following:

- PantryPilot has four synchronous FastAPI route functions. FastAPI executes
  synchronous endpoints in AnyIO worker threads.
- Successful responses are Pydantic-backed JSON responses produced by the
  existing route functions and ranking pipeline.
- Application `HTTPException` values use FastAPI's existing HTTP exception
  behavior. PantryPilot relies on that behavior for its current structured
  `404` and `422` details.
- PantryPilot's `RequestValidationError` handler preserves existing validation
  details while replacing non-finite float inputs with serializable strings.
- PantryPilot's narrow `PantryStoreError` handler returns the exact sanitized
  `503 saved_pantry_unavailable` response.
- Unexpected exceptions currently receive Starlette's plain-text
  `Internal Server Error` response and continue propagating so the host or
  `TestClient` can observe them.
- An unmatched route currently returns FastAPI's default
  `404 {"detail":"Not Found"}` response.
- Startup migrations and catalog hydration occur during lifespan before the
  application serves requests. A startup failure therefore has no HTTP
  response to correlate.
- PantryPilot currently has no application request logger, request ID, or
  response correlation header.
- The authoritative baseline contains 374 tests. Ingredient-resolution v2 has
  precision `1.0`, recall `1.0`, zero false positives, and zero false
  negatives.

Feature 006 remains the current product boundary: 24 official recipes, a
startup-loaded immutable catalog snapshot, one durable application-local saved
pantry, exhaustive ranking, and no retrieval layer. Feature 007 changes no
catalog, persistence, ingredient-resolution, eligibility, ranking,
explanation, ordering, or limiting behavior.

## 2. Problem and capability

Successful requests, expected errors, saved-pantry availability failures, and
unexpected server errors lack a common server-owned identity. An operator
cannot take an identifier from a response and locate the corresponding
PantryPilot request-completion event.

Feature 007 adds:

- one opaque PantryPilot-owned request ID per HTTP request;
- one `X-Request-ID` response header carrying that ID;
- exactly one bounded structured PantryPilot completion record per HTTP
  request;
- privacy-safe route identity, status, severity, and monotonic duration;
- traceback-bearing internal evidence for unexpected exceptions while clients
  receive a sanitized response; and
- tests proving correlation, concurrency isolation, failure behavior, logging
  ownership, and privacy without an external telemetry service.

This completes the request-tracing portion of Roadmap Phase 3. It does not
store request or ranking history.

## 3. Alternatives considered

### Registered pure ASGI middleware -- approved

One registered pure ASGI middleware owns request-ID generation, request-local
state, timing, response-header interception, status capture, privacy-safe route
identity, completion logging, and unexpected-error response correlation.
Existing FastAPI exception handlers remain unchanged inside it.

This provides one lifecycle owner across successful responses, handled
exceptions, unmatched routes, and unexpected exceptions. It also operates on
ASGI response-start messages directly, so the authoritative header and status
are captured at the actual protocol boundary.

### `BaseHTTPMiddleware` or `@app.middleware("http")` -- rejected

The request/response interface is superficially shorter, but
`BaseHTTPMiddleware` introduces a task boundary and has documented
`ContextVar` propagation limitations. Its response abstraction is also a less
direct fit for observing response-start and unexpected-error propagation.
Feature 007 does not require `ContextVar`, but it should not add middleware
with known propagation constraints when pure ASGI middleware is small and
directly models the required lifecycle.

### Dependencies and exception handlers as joint owners -- rejected

A route dependency cannot cover unmatched routes. Splitting completion
behavior among success middleware, validation handlers, HTTP exception
handlers, and a catch-all exception handler creates several emission sites and
raises missing-header and duplicate-event risks. Existing handlers should keep
owning their public response contracts; one middleware should observe all of
them.

### External observability middleware or service -- rejected

OpenTelemetry, tracing exporters, logging libraries, and aggregation services
add dependency, configuration, retention, and deployment policy that Issue #13
does not require. Python logging, FastAPI, Starlette, and the ASGI protocol are
sufficient.

## 4. Approved middleware topology

The request middleware is registered as pure ASGI middleware in the FastAPI
application. The intended stack is:

```text
Starlette ServerErrorMiddleware
  PantryPilot request middleware
    FastAPI / Starlette ExceptionMiddleware
      existing exception handlers
      router / endpoints
```

Starlette's `ServerErrorMiddleware` remains outermost. PantryPilot middleware
therefore sees responses from inner handled-exception processing and sees
unexpected exceptions before they reach the outer server-error layer.

The PantryPilot middleware processes HTTP scopes only. Lifespan and WebSocket
scopes pass through unchanged. It does not inspect or change their messages and
does not emit Feature 007 request-completion records for them.

All mutable request state remains local to one `__call__` invocation or that
request's ASGI scope. The middleware instance holds only immutable application
configuration, such as the wrapped ASGI application. It never stores a current
request ID, timer, status, exception, or response state on itself.

## 5. Request-ID contract

PantryPilot generates every request ID server-side with `uuid.uuid4().hex`.
The stable syntax is exactly 32 lowercase hexadecimal characters matching
`[0-9a-f]{32}`. Its exact and maximum length are both 32 characters.

Inbound `X-Request-ID` is ignored completely. PantryPilot does not validate,
echo, trust, propagate, or log any inbound value. This prevents clients from
choosing collisions, supplying unbounded values, or injecting log content. No
proxy trust policy is needed for the current single-service product.

The generated ID is returned through the `X-Request-ID` response header only.
It is not added to successful or error bodies. On every `http.response.start`,
the middleware replaces any downstream `X-Request-ID` header, case
insensitively, with the authoritative PantryPilot value while preserving all
other headers.

The request ID is stored at the PantryPilot-specific request-scope key
`scope["pantrypilot.request_id"]`. This is request-local access, not shared
middleware-instance state and not a public API body contract.

## 6. Normal HTTP request flow

For each HTTP request, the middleware performs this sequence:

1. Generate the request ID with `uuid.uuid4().hex`.
2. Store the ID at `scope["pantrypilot.request_id"]`.
3. Record the start value with `time.perf_counter_ns()`.
4. Call the inner application using a wrapped ASGI `send` callable.
5. On `http.response.start`, replace any downstream `X-Request-ID`, add the
   authoritative value, and capture the integer response status.
6. After the inner application completes, derive the privacy-safe route
   identity from code-owned routing metadata.
7. Compute the duration and emit exactly one PantryPilot
   `request_completed` record.

The middleware does not read, copy, retain, or buffer request or response
bodies. Normal completion timing ends after the inner ASGI application has
finished sending the response through the wrapped `send` callable.

Handled exceptions are responses from the middleware's perspective. Existing
FastAPI and PantryPilot handlers build the public response, the wrapped `send`
adds the correlation header and captures status, and the middleware emits one
completion record after the response completes.

## 7. Unexpected exceptions and diagnostic ownership

### Exception before response start

When an unexpected `Exception` escapes the inner application before any
response has started, PantryPilot middleware:

1. Uses the request's existing server-generated request ID.
2. Sends the exact sanitized response:
   - status `500`;
   - body `Internal Server Error`;
   - content type `text/plain; charset=utf-8`; and
   - the authoritative `X-Request-ID` header.
3. Emits exactly one `pantrypilot.request` `request_completed` record at
   `ERROR`, containing all stable fields and standard `exc_info` for the
   original exception.
4. Re-raises the original exception.

The sanitized response passes through the same wrapped `send` path as any
other response. Starlette's outer `ServerErrorMiddleware` therefore observes
the `http.response.start` message and marks the response as started. When the
original exception is re-raised into that outer middleware, it does not send a
second response because a response has already started. It continues
re-raising the exception according to Starlette's normal error model.

The ownership boundary is deliberate:

- PantryPilot emits exactly one application completion event and exactly one
  PantryPilot traceback-bearing event; they are the same ERROR LogRecord.
- The ASGI host may independently log the propagated uncaught exception
  according to deployment configuration. Host error reporting is not a second
  PantryPilot completion event.
- PantryPilot does not suppress the original exception and does not configure
  or suppress Uvicorn error logging to remove host-level reporting.

The resulting `TestClient` behavior is part of the design evidence:

- `raise_server_exceptions=False` can inspect the complete sanitized 500
  response and `X-Request-ID` header.
- The default `raise_server_exceptions=True` surfaces the original exception
  to the test caller after the response has been sent.

### Exception after response start

PantryPilot currently has no streaming responses or background response tasks
that can fail after response start. If such an exception nevertheless occurs,
the middleware must not attempt a second HTTP response. It emits one ERROR
completion record using the already-started status and `exc_info`, then
re-raises the original exception. The request ID is already present in the
started response.

Feature 007 adds no response buffering, body replay, or speculative streaming
machinery. Any future streaming-specific reliability contract requires a
separate design.

## 8. Existing public response contracts

Feature 007 preserves:

- every existing successful response body and response model;
- FastAPI's default and PantryPilot's application `HTTPException` behavior;
- the existing saved-pantry-not-found `404` response;
- the existing unmatched-route `404 {"detail":"Not Found"}` response;
- all existing `422` response contracts;
- PantryPilot's current `RequestValidationError` serialization behavior;
- the exact saved-pantry availability response:

```json
{
  "detail": {
    "type": "saved_pantry_unavailable",
    "message": "Saved pantry is unavailable."
  }
}
```

The intended new public surface is the `X-Request-ID` header and the now-exact
sanitized unexpected-500 contract. Correlation does not enter response bodies.

Existing public `422` bodies may legitimately contain request-derived
ingredient-resolution evidence, including submitted inputs. Preserving that
public API behavior does not authorize persisting the same values in logs.

## 9. Privacy-safe route identity

For a matched route, the completion record uses normalized, code-owned routing
metadata such as `scope["route"].path_format`. Existing examples include:

- `/v1/meal-rankings`;
- `/v1/saved-pantry`; and
- `/v1/saved-pantry/meal-rankings`.

For an unmatched request, the exact route value is the literal `unmatched`.
The middleware never falls back to `scope["path"]`, a request URL, or a query
string.

A method mismatch such as `405 Method Not Allowed` uses the normalized matched
route template when Starlette exposes it through the route scope. If no
normalized matched template is available, the privacy-safe fallback remains
`unmatched`; raw request data is never substituted.

Redirect responses use a normalized matched route only when the router exposes
one. Otherwise they also use `unmatched`. This conservative representation is
preferable to persisting arbitrary raw paths.

## 10. Stable PantryPilot logging contract

The named logger is:

```text
pantrypilot.request
```

The message and event identity are:

```text
request_completed
```

Every completion record has exactly these stable custom `LogRecord` fields:

- `event_name`: string, exactly `"request_completed"`;
- `request_id`: string matching `[0-9a-f]{32}`;
- `http_method`: string from the HTTP ASGI scope;
- `http_route`: normalized code-owned route template or exactly
  `"unmatched"`;
- `http_status_code`: integer response status; and
- `duration_ms`: non-negative float rounded to three decimal digits.

Normal record construction is explicit and bounded. It does not accept or
merge an arbitrary payload dictionary. It does not serialize a request,
response, exception, validation error, model, body, header collection, or
other open-ended object.

Unexpected failures additionally carry standard logging `exc_info`. There is
no separate PantryPilot application exception event. The traceback-bearing
ERROR `request_completed` record is the one PantryPilot completion event for
that request.

The logger name, message/event identity, stable custom fields and types,
chosen severity, and unexpected-error `exc_info` behavior are application
contracts. A formatter's textual or JSON representation is not.

## 11. Logging configuration ownership

PantryPilot obtains `pantrypilot.request` through the Python standard-library
logging API and emits records at the approved severity. It does not:

- install a handler on the named logger or root logger;
- install a formatter on any handler;
- force a level on the named logger;
- change the named logger's `propagate` setting;
- change root-logger handlers, filters, level, or propagation behavior; or
- change the process-wide `LogRecordFactory`.

Formatters belong to logging handlers, not `Logger` objects. PantryPilot does
not describe a logger as owning a formatter and does not create a default
handler merely to make INFO records visible.

An application-owned level on `pantrypilot.request` would not guarantee
visibility because deployment handlers may still filter or discard records.
It would also override a deployment's threshold policy. The named logger's
effective level therefore remains deployment-controlled.

Deployment and tests own:

- logging thresholds;
- handlers and their formatters;
- sinks and rendering;
- timestamps and process metadata;
- retention; and
- shipping.

Tests explicitly enable and capture the named logger at the required level.
A deployment may choose text, JSON, stderr, files, or another ordinary logging
sink without changing the PantryPilot event schema. No logging configuration
is forced by PantryPilot merely to make INFO visible. Tests may configure
capture directly, and no external backend is required to verify the
application contract.

## 12. Severity policy

The completion-record severity is:

- `INFO` for successful responses and redirects;
- `INFO` for expected `4xx` responses, including validation errors,
  application `HTTPException` responses, unmatched `404`, and `405`;
- `WARNING` for handled `5xx` responses, currently the known saved-pantry
  `503`; and
- `ERROR` with `exc_info` for an unexpected `500`.

Expected client errors are ordinary request outcomes rather than operational
warnings. A known availability failure is actionable but distinct from an
unexpected programming or application failure.

`PantryStoreError` completion records do not include exception details or
`exc_info`. Their fixed public 503 body and WARNING completion event contain no
database path, SQL text, SQLite error, exception string, or chained cause.

## 13. Duration contract

The middleware measures elapsed request time with:

```text
time.perf_counter_ns()
```

It computes:

```text
round((end_ns - start_ns) / 1_000_000, 3)
```

The stable `duration_ms` contract is non-negative milliseconds, represented as
a float and rounded to three decimal digits. It does not promise three
displayed decimal places because textual rendering belongs to the deployment
handler's formatter.

The monotonic performance counter is appropriate for elapsed time because
wall-clock adjustments cannot move it backward and the nanosecond integer API
avoids float loss during measurement. Feature 007 introduces no request-latency
threshold or hosted timing gate.

## 14. Concurrency and synchronous endpoints

Feature 007 does not require a `ContextVar`:

- Each HTTP ASGI invocation owns its request ID, start time, captured status,
  exception state, and completion decision in local variables or its unique
  request scope.
- Middleware instance state remains immutable across requests.
- PantryPilot's synchronous FastAPI endpoints may execute in worker threads,
  but they do not need ambient correlation state to produce the approved
  behavior.
- The awaiting middleware invocation remains in control of the response
  `send` path and receives the endpoint's response or propagated exception, so
  it retains the correct correlation ID.

Overlapping requests therefore cannot exchange IDs unless shared mutable state
is introduced, which this design prohibits. A future requirement to
automatically enrich arbitrary domain-layer logs with a request ID would be a
separate design change and could reassess `ContextVar` propagation. Feature
007 does not add that unused mechanism.

## 15. Privacy and data minimization

Default PantryPilot request records never contain:

- request bodies;
- response bodies;
- pantry ingredients;
- saved-pantry contents;
- excluded ingredients;
- validation input or validation errors;
- raw paths;
- query-string values;
- `Authorization` values;
- `Cookie` values;
- arbitrary inbound headers;
- inbound request IDs;
- client IP addresses;
- database paths;
- SQLite statements;
- secrets or credentials; or
- environment names or values.

The middleware does not inspect these values to redact them after collection;
it never collects them for the event. The record is built only from the six
approved stable fields. It never serializes request, response, validation, or
exception objects into a structured payload.

Unexpected `exc_info` is the narrow diagnostic exception to the otherwise
bounded payload. The structured fields still contain no exception string,
class, dictionary, or cause. A traceback may inherently include internal
exception evidence, so deployment owns access control, formatting, retention,
and shipping policy for ERROR diagnostics. Tests use deliberately
non-sensitive exception text and do not claim that arbitrary exception
messages are safe for public exposure.

Feature 007 is request correlation, not request history, behavioral analytics,
or user tracking. It persists no log records itself and stores no request IDs
in SQLite.

## 16. Uvicorn and embedded-execution boundary

PantryPilot request logging is separate from Uvicorn access and error logging.
Feature 007 does not configure, replace, suppress, or depend on Uvicorn
loggers.

Uvicorn access logging may independently include raw paths, query data, client
information, or other deployment metadata. That creates a separate privacy and
retention decision for the operator. The privacy contract in this design
applies to `pantrypilot.request` completion records; it does not claim to
sanitize host-owned access logs.

On an unexpected exception, PantryPilot sends its correlated sanitized 500,
emits one PantryPilot ERROR completion record, and re-raises. Uvicorn or another
ASGI host may independently log that propagated exception. PantryPilot does
not treat host logging as a duplicate application completion event and does
not interfere with it.

The contract remains useful without OpenTelemetry, a log aggregator, a trace
exporter, or another telemetry service. Pytest or an in-memory standard-library
handler can capture records directly, and an ordinary deployment logging
configuration can render the same records locally.

## 17. Startup behavior

Startup and lifespan failures occur without an HTTP request. They receive no
Feature 007 request ID, response header, or `request_completed` event. Existing
startup fail-closed behavior remains unchanged, and the ASGI host continues to
own startup-failure reporting.

Feature 007 adds no separate startup logger, startup event schema, migration
telemetry, or recovery subsystem.

## 18. Testing strategy

Focused request-correlation tests must prove the following behavior while
preserving all existing API and domain tests.

### Request ID and successful completion

- Every covered HTTP response contains `X-Request-ID` matching exactly
  `[0-9a-f]{32}`.
- Using a deterministic generated ID, an inbound `X-Request-ID`, including an
  oversized or log-like sentinel, is ignored and differs from the generated
  response value.
- The response header ID exactly equals the `request_id` field on the one
  captured completion record.
- A successful request emits exactly one `pantrypilot.request`
  `request_completed` record at INFO with the exact stable fields and types.
- Existing successful response bodies remain byte- or object-compatible as
  appropriate; ranking, explanation, ordering, and inline/saved parity tests
  remain unchanged.

### Handled errors

- A `RequestValidationError` retains its existing exact `422` behavior and
  emits one INFO completion record.
- Existing application `404` and `422` `HTTPException` bodies remain exact and
  each emits one INFO completion record.
- A saved-pantry `PantryStoreError` retains the exact fixed
  `503 saved_pantry_unavailable` body and emits one WARNING completion record
  without exception details or `exc_info`.
- A `405` uses the available normalized matched route template and emits one
  INFO record.

### Route privacy

- An unmatched route records exactly `http_route == "unmatched"`.
- Unique raw-path and query-string sentinels are absent from captured
  PantryPilot records.
- No test permits raw path or query data as a fallback when normalized route
  metadata is unavailable.

### Unexpected exceptions

- With `raise_server_exceptions=False`, an unexpected exception returns status
  500, exact body `Internal Server Error`, exact content type
  `text/plain; charset=utf-8`, and the matching `X-Request-ID`.
- The request emits exactly one PantryPilot `request_completed` ERROR record
  with the stable fields and non-null `exc_info`.
- Deliberately non-sensitive internal exception evidence is available through
  formatted traceback evidence but absent from the client response.
- With default `raise_server_exceptions=True`, the original exception reaches
  the test caller after the sanitized response has been sent, and exactly one
  PantryPilot ERROR completion record exists.
- Duplicate-event assertions are scoped to `pantrypilot.request`. Tests do not
  assert that an ASGI host is forbidden from independently logging the
  propagated server error.
- A focused ASGI-level test makes an inner application send
  `http.response.start` and then raise. It proves that middleware sends no
  second response-start message, emits one ERROR record using the started
  status and `exc_info`, and re-raises.

### Duration and concurrency

- A controlled fake monotonic clock proves the exact numeric computation and
  rounding contract.
- `duration_ms` is asserted as a non-negative float. Tests do not assert
  trailing zeroes or any deployment-rendered string.
- Two deliberately overlapping requests through PantryPilot's synchronous
  ranking path receive distinct IDs. Each response ID matches only its own
  completion record, proving that worker-thread execution cannot exchange
  request correlation state.

### Privacy-negative evidence

- Distinct sentinels represent pantry input, saved-pantry content, exclusions,
  validation input, raw path, query value, `Authorization`, `Cookie`, an
  arbitrary inbound header, inbound request ID, database path, SQL-like text,
  secret, credential, and environment-like value.
- Captured application-record messages, stable custom fields, and normal
  record attributes contain none of those sentinels.
- One unresolved-input `422` test proves that a request-derived sentinel may
  remain in its approved public response while being absent from all captured
  PantryPilot records.
- Unexpected traceback tests use separate, deliberately non-sensitive text;
  privacy evidence does not depend on placing a real secret in an exception.

### Logging configuration and backend independence

- Tests explicitly enable and capture `pantrypilot.request` at the required
  level using pytest or standard-library logging only.
- Before application creation and request execution, tests snapshot the named
  logger and root logger levels, handler identities, filters, and propagation
  where applicable; the process-wide `LogRecordFactory`; and each pre-existing
  handler's formatter identity.
- After execution, every captured configuration value is unchanged. This
  proves PantryPilot did not install a handler or formatter, force a named
  level, alter propagation, reconfigure root logging, replace a pre-existing
  handler formatter, or replace the process-wide record factory.
- No test requires Uvicorn, OpenTelemetry, aggregation, shipping, or another
  external telemetry backend to inspect the application record contract.

### Startup boundary

- A representative lifespan/startup failure emits no Feature 007
  `request_completed` record because no HTTP request occurred.
- Existing startup fail-closed tests and behavior remain unchanged.

Tests assert stable `LogRecord` attributes and public HTTP contracts, not
incidental text or JSON formatting chosen by a deployment handler.

## 19. Documentation scope

The eventual implementation adds
`docs/learning/007-request-correlation-logging.md`. It teaches:

- correlation IDs versus logs, metrics, and distributed traces;
- what a request ID does and does not provide;
- privacy-safe request logging and why bodies and pantry inputs are excluded;
- normalized route templates versus arbitrary raw paths;
- middleware and exception-handler interaction;
- monotonic elapsed-time measurement;
- concurrency and request-scoped correlation, including synchronous routes;
- internal traceback evidence versus sanitized clients;
- named-logger, handler-formatter, and root-logger ownership;
- the separate Uvicorn access/error logging boundary;
- captured-log testing without external services; and
- mock-interview questions and answer guidance for these topics.

The owner-understanding checkpoint follows the established project pattern:
one attempt followed by corrections and explanation rather than repeated
quizzing for perfect wording.

The README eventually summarizes the `X-Request-ID` header and
`pantrypilot.request` event contract and links the learning document. Product
vision and roadmap changes only record completion of Roadmap Phase 3 request
tracing. They must not claim that PantryPilot has log aggregation, metrics,
distributed tracing, dashboards, alerting, or broader observability
infrastructure.

## 20. Security and operational considerations

- Server-owned IDs prevent untrusted clients from controlling the correlation
  namespace or log field length.
- Fixed route templates bound cardinality and prevent arbitrary URLs from
  becoming PantryPilot log data.
- The request event is allowlist-built from six fields rather than collected
  broadly and redacted later.
- Known storage exceptions retain their sanitized public response and do not
  attach database diagnostics to the completion event.
- Unexpected exceptions retain internal traceback evidence only on the ERROR
  record; clients receive no exception data.
- Re-raising unexpected exceptions preserves Starlette, Uvicorn, and
  `TestClient` error semantics.
- No middleware-instance mutable request state exists, preventing concurrent
  requests from overwriting one another.
- Logger and root configuration remain deployment-owned, avoiding surprising
  process-wide side effects or duplicate handler installation.
- No request ID or request event is persisted by PantryPilot.

## 21. Scope and non-goals

Feature 007 does not introduce:

- request or ranking history;
- analytics, user tracking, or product telemetry;
- OpenTelemetry, distributed tracing, trace export, or propagation protocols;
- log shipping, aggregation, dashboards, alerts, or metrics infrastructure;
- authentication, accounts, users, ownership, or multiple pantries;
- request/response body storage or client-IP storage;
- retrieval, indexing, embeddings, ANN, or candidate generation;
- recipe-catalog expansion;
- ranking, eligibility, explanation, ordering, or ingredient-resolution
  changes;
- quantities, units, purchase dates, spoilage, or multi-meal planning;
- personalization, learned ranking, or LLM integration;
- deployment, branch protection, or repository-governance changes;
- unrelated refactoring or dependency upgrades;
- a startup logging subsystem;
- response buffering or speculative streaming support; or
- a new observability dependency.

The design prefers existing Python, FastAPI, Starlette, and standard-library
capabilities. No new dependency is approved.

## 22. Authoritative verification contract

Implementation acceptance retains these exact commands:

```powershell
uv lock --check
uv run pytest
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v2.json
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

The current baseline is:

- 374 tests;
- ingredient-resolution v2 precision `1.0`;
- ingredient-resolution v2 recall `1.0`;
- false positives `0`; and
- false negatives `0`.

Feature 007 adds no latency threshold.

## 23. Acceptance criteria

Feature 007 implementation is acceptable only when:

1. every covered HTTP response has a server-generated 32-character lowercase
   hexadecimal `X-Request-ID`, and inbound request IDs are ignored;
2. the response ID exactly matches the one bounded PantryPilot completion
   record for that request;
3. successful, validation, application-error, unmatched, known-503, and
   unexpected-error paths emit the approved event count, fields, routes, and
   severity;
4. existing successful bodies and `404`, `422`, and saved-pantry `503`
   contracts remain compatible;
5. unmatched requests never record a raw path or query, while matched requests
   use normalized code-owned route metadata;
6. unexpected exceptions receive the exact correlated sanitized 500, emit one
   PantryPilot ERROR record with `exc_info`, and re-raise without a second HTTP
   response;
7. both `TestClient` exception modes behave according to section 7;
8. post-response-start exceptions receive no second response and still emit
   one ERROR completion record before propagation;
9. duration uses the approved monotonic float-millisecond and rounding
   contract without a latency threshold;
10. overlapping synchronous requests cannot exchange request IDs;
11. privacy-negative tests prove prohibited request, header, pantry, storage,
    and environment sentinels are absent from PantryPilot records even when an
    approved public 422 body contains request-derived evidence;
12. PantryPilot changes no named/root logger configuration, handler formatter,
    propagation setting, or process-wide `LogRecordFactory`;
13. Uvicorn access/error logging remains an independent deployment concern;
14. startup failures emit no Feature 007 request-completion event;
15. no request history, telemetry backend, new observability dependency, or
    unrelated feature is added;
16. the learning document, README summary, and narrow vision/roadmap status are
    complete; and
17. the authoritative verification contract passes at or above the stated
    baseline with unchanged ingredient-resolution results.

## 24. Design self-review

- **Placeholder check:** The design contains no placeholder marker,
  provisional field, unresolved route rule, or unspecified response contract.
- **Architecture consistency:** One registered pure ASGI middleware owns
  correlation and completion observation. Existing exception handlers remain
  inner response owners; outer `ServerErrorMiddleware` and the ASGI host retain
  unexpected-error propagation.
- **Public API compatibility:** The request ID is header-only. Existing
  successful, 404, 422, and 503 bodies remain unchanged; only the unexpected
  500 contract is made exact as authorized by Issue #13.
- **Privacy:** Normal records are allowlist-built from six bounded fields.
  Unmatched routes never fall back to raw paths or queries. Known storage
  failures carry no exception details.
- **Logging ownership:** PantryPilot obtains a named logger but configures no
  logger, handler, handler formatter, root state, propagation setting, or
  record factory. Deployment/test configuration remains authoritative.
- **Error ownership:** An unexpected pre-response exception produces one
  correlated sanitized response and one PantryPilot ERROR event, then
  re-raises. Outer Starlette middleware observes that response already started
  and does not send another. Host logging is explicitly independent rather
  than misclassified as a duplicate PantryPilot event.
- **Concurrency:** Every mutable value is request-local. Worker-thread endpoint
  execution needs no ambient context, so no `ContextVar` is introduced.
- **Scope:** The design adds no persistence, analytics, telemetry service,
  streaming infrastructure, dependency, ranking change, or unrelated
  refactoring.
- **Test alignment:** The test strategy covers every architecture branch,
  public contract, privacy boundary, logger-ownership invariant, concurrency
  claim, and non-goal that requires executable evidence.
