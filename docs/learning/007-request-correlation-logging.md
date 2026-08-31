# Feature 007: Request correlation and privacy-safe structured logging

## Capability and non-goals

Feature 007 gives every HTTP response a server-owned `X-Request-ID` and emits
one `pantrypilot.request` `request_completed` completion record. It connects a
response to its application event without changing response bodies.

It adds no request history, persistence, analytics, user tracking, metrics,
distributed tracing, aggregation, dashboards, alerts, hosted observability,
or deployment configuration.

## Correlation IDs, logs, metrics, and distributed traces

A correlation ID is an opaque value that connects one response to one
application event. It is not a log collection, a latency or error metric, a
cross-service trace-propagation protocol, an aggregation mechanism, or user
history. This feature emits one bounded event; deployment may render or route
that event, but PantryPilot does not build an observability system.

## Request-ID ownership, capabilities, and limits

PantryPilot generates each ID with `uuid.uuid4().hex`, so its stable form is
32 lowercase hexadecimal characters. It ignores every inbound `X-Request-ID`:
clients cannot choose the namespace, collisions, or field length, and the
response header is authoritative.

That ownership bounds trust, format, and length. It does not authenticate a
caller, identify a user, or correlate work across multiple services. The ID is
not added to any response body or persisted by PantryPilot.

## Privacy-safe allowlist logging

Each normal completion record is explicitly built from exactly six fields:
`event_name`, `request_id`, `http_method`, `http_route`, `http_status_code`,
and `duration_ms`. The event name is exactly `request_completed`.

The record never collects request or response bodies, pantry data, headers,
raw paths, query values, client IPs, storage details, or environment data. An
allowlist is safer than collecting a broad request object and attempting to
redact it afterward.

## Normalized routes instead of raw paths

Matched records use code-owned route templates such as
`/v1/saved-pantry`, not the raw URL. This bounds cardinality and keeps
user-controlled path values out of the event. A 405 can use its matched route
template when the framework exposes one.

If no normalized template is available, the route is exactly `unmatched`.
That intentionally gives less detail than a raw-path fallback; it protects the
privacy boundary for unmatched requests and redirects without route metadata.

## Pure ASGI middleware and exception ownership

The registered pure ASGI layer sits between Starlette's
`ServerErrorMiddleware` and `ExceptionMiddleware`. It observes handled
responses from the inner application, replaces any downstream request-ID
header, and emits one completion record after the response.

For an unexpected exception before response start, it sends the correlated,
sanitized `500 Internal Server Error`, logs once at ERROR, and re-raises the
original exception. Existing inner handlers keep their public response
contracts; the outer server middleware and ASGI host keep exception
propagation. An exception after response start reuses the started status,
logs once, and never attempts a second response.

## Monotonic duration measurement

Elapsed time uses `perf_counter_ns`, a monotonic clock that is not moved
backward by wall-clock adjustments. The completion field is:

```text
round((end_ns - start_ns) / 1_000_000, 3)
```

`duration_ms` is a non-negative float in milliseconds. The feature promises no
display format, trailing zeroes, latency SLO, threshold, or hosted timing gate.

## Concurrency and synchronous FastAPI endpoints

Request ID, timer, response status, exception state, and completion decision
are invocation-local. FastAPI may run synchronous endpoints in worker threads,
while the awaiting middleware invocation still owns its own ASGI send path and
correlation state. Overlapping requests therefore keep distinct IDs.

No `ContextVar` is needed because Feature 007 does not enrich arbitrary domain
logs. If that broader requirement appears later, it needs its own design rather
than unused ambient state now.

## Internal traceback evidence and sanitized clients

An unexpected failure emits one ERROR record with standard `exc_info`, giving
operators internal traceback evidence. The client receives the fixed sanitized
500 body rather than exception details, and the original exception is
re-raised for the host or default `TestClient` behavior.

`exc_info` is not a guarantee that deliberately sensitive exception strings
are safe. Deployment owns diagnostic access, rendering, retention, and
shipping; this feature does not make arbitrary exception text suitable for
exposure.

## Logger, handler, formatter, and root ownership

PantryPilot emits through the named `pantrypilot.request` logger at INFO for
expected outcomes, WARNING for handled 5xx responses, and ERROR with
`exc_info` for unexpected failures. It does not set levels, add handlers or
formatters, change propagation, configure the root logger, or replace the
process-wide `LogRecordFactory`.

Deployments and tests own levels, handlers, formatters, rendering, sinks,
retention, and shipping. INFO is therefore an event severity, not a promise
that a deployment will show it.

## Uvicorn logging remains separate

Uvicorn access and error logs are outside the `pantrypilot.request` privacy
contract. They may independently include raw paths, query data, client
information, or other host metadata. PantryPilot neither configures nor
suppresses them, and a host error report after a re-raised exception is not a
second PantryPilot completion event.

## Captured-log testing without an external service

Pytest log capture or an in-memory standard-library handler can inspect the
LogRecord fields, event count, severity, and unexpected-error `exc_info`.
Tests explicitly enable capture for the named logger and verify the application
does not mutate logger or root configuration. No OpenTelemetry, exporter,
aggregator, or hosted service is required.

## Run and inspect

```powershell
uv sync --locked --python 3.12
uv run pytest tests/test_request_logging.py tests/test_api.py -v
uv run uvicorn pantrypilot.app:app --app-dir src
```

Use a test-owned capture handler or pytest's `caplog` fixture to inspect the
stable fields. Do not add a production handler merely to make INFO visible.

## Practical exercises

1. Capture a successful request record and compare its `request_id` with the
   response `X-Request-ID`. Success: they match exactly and there is one event.
2. Send `DELETE /v1/saved-pantry` to observe 405, then request an unknown URL.
   Explain why the first can use a normalized route while the second is
   `unmatched` rather than the raw path.
3. Replace the monotonic clock with a fake sequence and verify the exact
   `round((end_ns - start_ns) / 1_000_000, 3)` result. Explain why a wall clock
   is unsuitable for elapsed duration.
4. Trigger an unexpected exception with `TestClient` first using
   `raise_server_exceptions=False`, then with the default mode. Inspect the
   sanitized correlated 500 in the first case and the original propagated
   exception in the second.
5. Make two synchronous ranking requests overlap in worker threads. Capture
   both events and show that each response ID matches only its own record.

## Mock-interview questions and answer guidance

Attempt each answer once, then compare it with the guidance and correct the
explanation in your own words; the goal is owner understanding, not repeated
quizzing for exact wording.

1. **What does a correlation ID provide, and what does it not provide?** It
   connects one response to one application event; it is not logs, metrics,
   user history, aggregation, or distributed trace propagation.
2. **Why generate IDs server-side and ignore inbound values?** It bounds the
   namespace, format, and length against untrusted input, but does not
   authenticate callers or connect multiple services.
3. **Why build records from an allowlist?** The six fixed fields avoid bodies,
   pantry data, headers, paths, queries, IPs, storage details, and environment
   data instead of risking incomplete redaction.
4. **Why use normalized routes and `unmatched`?** Templates bound cardinality
   and exclude user path values; the less-specific fallback is safer than raw
   request data, including for routes without available metadata.
5. **Why does pure ASGI middleware own completion observation?** It sees
   response-start messages and handled inner responses, while preserving
   existing exception handlers and one emission site.
6. **What happens on an unexpected pre-start exception?** The middleware sends
   a correlated sanitized 500, emits one ERROR with `exc_info`, then re-raises
   so the outer middleware and host retain their normal error behavior.
7. **Why use `perf_counter_ns`, and what is the formula?** It is monotonic;
   duration is `round((end_ns - start_ns) / 1_000_000, 3)`, not a display or
   latency-SLO promise.
8. **Why is no `ContextVar` needed for synchronous endpoints?** Each ASGI
   invocation keeps local state while worker-thread routes execute; no domain
   logging enrichment is in scope.
9. **How do traceback diagnostics remain distinct from client output?** ERROR
   records have internal `exc_info`, clients get a fixed sanitized body, and
   sensitive exception strings still require deployment controls.
10. **Who owns logger configuration?** PantryPilot emits through one named
    logger; deployments and tests own levels, handlers, formatters, sinks,
    retention, and shipping, so INFO need not be visible.
11. **How do Uvicorn logs relate to this contract?** They are independent host
    logs with their own privacy decision; a host error log is not another
    PantryPilot completion record.
12. **How can this be tested without a service?** Pytest capture or an
    in-memory standard-library handler proves event fields and severity without
    OpenTelemetry or a hosted backend.
