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


def assert_correlated_completion(
    response,
    caplog: pytest.LogCaptureFixture,
    *,
    level: int,
    method: str,
    route: str,
    status: int,
) -> logging.LogRecord:
    records = request_records(caplog)
    assert len(records) == 1
    assert response.headers["x-request-id"] == records[0].request_id
    assert_completion(
        records[0],
        level=level,
        method=method,
        route=route,
        status=status,
    )
    return records[0]


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


def test_replaces_mixed_case_duplicate_downstream_request_id_headers(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated = "0123456789abcdef0123456789abcdef"
    monkeypatch.setattr(
        request_logging.uuid,
        "uuid4",
        lambda: UUID(hex=generated),
    )

    async def inner_app(scope, receive, send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"X-Request-ID", b"downstream-one"),
                    (b"x-request-id", b"downstream-two"),
                    (b"content-type", b"text/plain"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    sent: list[dict[str, object]] = []

    async def send(message) -> None:
        sent.append(message)

    scope = {"type": "http", "method": "GET"}
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        asyncio.run(RequestLoggingMiddleware(inner_app)(scope, receive, send))

    starts = [message for message in sent if message["type"] == "http.response.start"]
    assert len(starts) == 1
    headers = starts[0]["headers"]
    assert headers.count((b"x-request-id", generated.encode("ascii"))) == 1
    assert all(
        name.lower() != b"x-request-id" or value == generated.encode("ascii")
        for name, value in headers
    )
    assert scope["pantrypilot.request_id"] == generated
    assert len(request_records(caplog)) == 1


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


def test_validation_422_keeps_public_contract_and_logs_info(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        response = client.post(
            "/v1/meal-rankings",
            json={key: value for key, value in VALID_REQUEST.items() if key != "limit"},
        )

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "missing"
    assert response.json()["detail"][0]["loc"] == ["body", "limit"]
    record = assert_correlated_completion(
        response,
        caplog,
        level=logging.INFO,
        method="POST",
        route="/v1/meal-rankings",
        status=422,
    )
    assert record.exc_info is None


def test_application_422_keeps_resolution_body_and_logs_info(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        response = client.post(
            "/v1/meal-rankings",
            json={**VALID_REQUEST, "excluded_ingredients": ["groundnut"]},
        )

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "type": "unresolved_excluded_ingredients",
            "message": "All excluded ingredients must resolve before ranking.",
            "ingredient_resolution": {
                "pantry_items": [
                    {
                        "input": "eggs",
                        "normalized": "eggs",
                        "ingredient_id": "eggs",
                        "canonical_name": "eggs",
                        "match_type": "canonical",
                    },
                    {
                        "input": "spinach",
                        "normalized": "spinach",
                        "ingredient_id": "spinach",
                        "canonical_name": "spinach",
                        "match_type": "canonical",
                    },
                ],
                "excluded_ingredients": [
                    {
                        "input": "groundnut",
                        "normalized": "groundnut",
                        "ingredient_id": None,
                        "canonical_name": None,
                        "match_type": "unresolved",
                    }
                ],
            },
        }
    }
    record = assert_correlated_completion(
        response,
        caplog,
        level=logging.INFO,
        method="POST",
        route="/v1/meal-rankings",
        status=422,
    )
    assert record.exc_info is None


def test_saved_pantry_404_keeps_exact_body_and_logs_info(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        response = client.get("/v1/saved-pantry")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {
            "type": "saved_pantry_not_found",
            "message": "No saved pantry has been established.",
        }
    }
    record = assert_correlated_completion(
        response,
        caplog,
        level=logging.INFO,
        method="GET",
        route="/v1/saved-pantry",
        status=404,
    )
    assert record.exc_info is None


def test_saved_pantry_503_keeps_exact_body_and_logs_warning_without_exception(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_read(*_args: object, **_kwargs: object) -> None:
        raise PantryStoreError("DATABASE_PATH_SENTINEL: SELECT SQL_SENTINEL")

    monkeypatch.setattr(app_module, "load_saved_pantry", fail_read)
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        response = client.get("/v1/saved-pantry")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "type": "saved_pantry_unavailable",
            "message": "Saved pantry is unavailable.",
        }
    }
    record = assert_correlated_completion(
        response,
        caplog,
        level=logging.WARNING,
        method="GET",
        route="/v1/saved-pantry",
        status=503,
    )
    assert record.exc_info is None
    assert "DATABASE_PATH_SENTINEL" not in record.getMessage()
    assert "SELECT SQL_SENTINEL" not in repr(record.__dict__)


def test_405_uses_normalized_route(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        response = client.delete("/v1/saved-pantry")

    assert response.status_code == 405
    assert response.json() == {"detail": "Method Not Allowed"}
    assert_correlated_completion(
        response,
        caplog,
        level=logging.INFO,
        method="DELETE",
        route="/v1/saved-pantry",
        status=405,
    )


def test_redirect_without_route_metadata_is_info_and_unmatched(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        response = client.get("/v1/saved-pantry/", follow_redirects=False)

    assert response.status_code == 307
    record = assert_correlated_completion(
        response,
        caplog,
        level=logging.INFO,
        method="GET",
        route="unmatched",
        status=307,
    )
    assert "/v1/saved-pantry/" not in repr(record.__dict__)


def test_unmatched_404_is_private(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        response = client.get("/PRIVATE_RAW_PATH_SENTINEL?q=PRIVATE_QUERY_SENTINEL")

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
    record = assert_correlated_completion(
        response,
        caplog,
        level=logging.INFO,
        method="GET",
        route="unmatched",
        status=404,
    )
    assert "PRIVATE_RAW_PATH_SENTINEL" not in repr(record.__dict__)
    assert "PRIVATE_QUERY_SENTINEL" not in repr(record.__dict__)


def test_non_http_scope_passes_through_without_correlation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    seen_scopes: list[dict[str, object]] = []
    sent: list[dict[str, object]] = []
    scope: dict[str, object] = {"type": "lifespan", "state": {}}

    async def inner_app(inner_scope, receive, send) -> None:
        seen_scopes.append(inner_scope)
        await send({"type": "lifespan.startup.complete"})

    async def receive() -> dict[str, object]:
        return {"type": "lifespan.startup"}

    async def send(message) -> None:
        sent.append(message)

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        asyncio.run(RequestLoggingMiddleware(inner_app)(scope, receive, send))

    assert seen_scopes == [scope]
    assert sent == [{"type": "lifespan.startup.complete"}]
    assert "pantrypilot.request_id" not in scope
    assert request_records(caplog) == []
