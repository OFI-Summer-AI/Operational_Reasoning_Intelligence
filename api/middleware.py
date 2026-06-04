"""CORS, request ID, and structured access logging middleware."""
import time
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        t0 = time.monotonic()
        response = await call_next(request)
        latency_ms = int((time.monotonic() - t0) * 1000)

        logger.info(
            "http.request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
            request_id=request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response
