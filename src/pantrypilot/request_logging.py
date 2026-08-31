import logging
import time
import uuid

from starlette.responses import PlainTextResponse
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
            arguments: dict[str, object] = {}
            if exc_info:
                arguments["exc_info"] = True
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
                **arguments,
            )

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
            emit_completion(logging.WARNING if response_status >= 500 else logging.INFO)
