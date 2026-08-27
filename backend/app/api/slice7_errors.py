from collections.abc import Callable

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.services.simulation_imports import (
    ImportIdempotencyConflictError,
    InvalidSharePayloadError,
    ShareImportFailedError,
    ShareNotFoundForImportError,
    SharePersonaTargetInvalidError,
    UnsupportedShareSchemaVersionError,
)
from app.services.simulation_shares import (
    ShareAccessDeniedError,
    ShareNotFoundError,
    SimulationNotReadyForShareError,
)


class Slice7APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


class Slice7ErrorRoute(APIRoute):
    """Shared canonical error mapping for every Slice 7 sharing/import route.

    Maps the Slice 7 contract's error table
    (docs/04-feature-specs/slice-7-config-sharing-import-deployment.md §5) to
    responses, mirroring the Slice6ErrorRoute pattern already used by
    app/api/simulation_history.py.
    """

    def get_route_handler(self) -> Callable:
        original_handler = super().get_route_handler()

        async def handler(request: Request):
            try:
                return await original_handler(request)
            except Slice7APIError as exc:
                return _error_response(exc.status_code, exc.code, exc.message)
            except ShareNotFoundError as exc:
                return _error_response(404, "SHARE_NOT_FOUND", str(exc))
            except ShareNotFoundForImportError as exc:
                return _error_response(404, "SHARE_NOT_FOUND", str(exc))
            except ShareAccessDeniedError as exc:
                return _error_response(403, "SHARE_ACCESS_DENIED", str(exc))
            except SimulationNotReadyForShareError as exc:
                return _error_response(409, "SIMULATION_SHARE_NOT_READY", str(exc))
            except ImportIdempotencyConflictError as exc:
                return _error_response(409, "IMPORT_IDEMPOTENCY_CONFLICT", str(exc))
            except UnsupportedShareSchemaVersionError as exc:
                return _error_response(422, "UNSUPPORTED_SHARE_SCHEMA_VERSION", str(exc))
            except SharePersonaTargetInvalidError as exc:
                return _error_response(422, "SHARE_PERSONA_TARGET_INVALID", str(exc))
            except InvalidSharePayloadError as exc:
                return _error_response(422, "INVALID_SHARE_PAYLOAD", str(exc))
            except ShareImportFailedError as exc:
                return _error_response(500, "SHARE_IMPORT_FAILED", str(exc))
            except RequestValidationError:
                return _error_response(422, "INVALID_SHARE_REQUEST", "Invalid request")
            except HTTPException as exc:
                codes = {
                    401: "AUTHENTICATION_REQUIRED",
                    403: "SHARE_ACCESS_DENIED",
                    404: "SHARE_NOT_FOUND",
                }
                return _error_response(
                    exc.status_code, codes.get(exc.status_code, "INVALID_SHARE_REQUEST"), str(exc.detail)
                )

        return handler
