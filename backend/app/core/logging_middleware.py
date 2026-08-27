"""Structured one-line-JSON request logging (Slice 7 contract §6.2).

Only the allow-listed fields below are ever logged. In particular this
middleware never reads or logs: headers (Authorization/cookies included),
query strings, request/response bodies, or path params other than the
three explicitly allowed identifiers — so no JWT, password, API key,
secret, prompt text or free-form user input can reach the log line.
"""

import json
import logging
import time
import uuid
from datetime import UTC, datetime

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import get_settings

logger = logging.getLogger("magic_academy.request")

# The only path-parameter names ever copied into a log line.
ALLOWED_PATH_PARAM_KEYS = ("simulation_id", "share_id", "run_id", "tick_number")


def _operation(request: Request) -> str:
    route = request.scope.get("route")
    path_template = getattr(route, "path", None) or request.url.path
    return f"{request.method} {path_template}"


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        start = time.monotonic()
        request_id = str(uuid.uuid4())
        trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.trace_id = trace_id

        status_code = 500
        error_code = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            error_code = "UNHANDLED_EXCEPTION"
            raise
        finally:
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            record: dict[str, object] = {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": "ERROR" if status_code >= 500 else "INFO",
                "service": "magic-academy-backend",
                "environment": settings.environment,
                "trace_id": trace_id,
                "request_id": request_id,
                "operation": _operation(request),
                "result": status_code,
                "duration_ms": duration_ms,
            }
            if error_code:
                record["error_code"] = error_code
            path_params = dict(request.path_params)
            for key in ALLOWED_PATH_PARAM_KEYS:
                if key in path_params:
                    record[key] = str(path_params[key])
            logger.info(json.dumps(record, sort_keys=True))
