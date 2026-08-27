from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.schemas import (
    SimulationShareCreateRequest,
    SimulationShareDetailResponse,
    SimulationShareSummaryResponse,
)
from app.core.database import get_db
from app.core.security import get_current_user, require_user_role
from app.domain.models import User
from app.services.simulation_shares import (
    ShareAccessDeniedError,
    ShareNotFoundError,
    SimulationNotReadyForShareError,
    cancel_simulation_share,
    create_simulation_share,
    get_public_simulation_shares,
    get_simulation_share_detail,
)


class Slice7APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


class Slice7ErrorRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_handler = super().get_route_handler()

        async def handler(request: Request):
            try:
                return await original_handler(request)
            except Slice7APIError as exc:
                return _error_response(exc.status_code, exc.code, exc.message)
            except ShareNotFoundError as exc:
                return _error_response(404, "SHARE_NOT_FOUND", str(exc))
            except ShareAccessDeniedError as exc:
                return _error_response(403, "SHARE_ACCESS_DENIED", str(exc))
            except SimulationNotReadyForShareError as exc:
                return _error_response(409, "SIMULATION_SHARE_NOT_READY", str(exc))
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


router = APIRouter(tags=["simulation-shares"], route_class=Slice7ErrorRoute)
optional_bearer_scheme = HTTPBearer(auto_error=False)


def optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None


@router.post(
    "/simulations/{simulation_id}/shares",
    response_model=SimulationShareDetailResponse,
    status_code=201,
)
def create_share(
    simulation_id: UUID,
    request: SimulationShareCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> SimulationShareDetailResponse:
    share = create_simulation_share(
        db,
        current_user,
        simulation_id,
        visibility=request.visibility,
        title=request.title,
        description=request.description,
    )
    return SimulationShareDetailResponse.model_validate(share)


@router.delete("/shares/{share_id}", status_code=204)
def cancel_share(
    share_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> None:
    cancel_simulation_share(db, current_user, share_id)
    return None


@router.get("/shares", response_model=list[SimulationShareSummaryResponse])
def list_shares(
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[SimulationShareSummaryResponse]:
    shares = get_public_simulation_shares(db, query=q, limit=limit, offset=offset)
    return [SimulationShareSummaryResponse.model_validate(share) for share in shares]


@router.get("/shares/{share_id}", response_model=SimulationShareDetailResponse)
def get_share_detail(
    share_id: UUID,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(optional_current_user),
) -> SimulationShareDetailResponse:
    share = get_simulation_share_detail(db, share_id, current_user)
    return SimulationShareDetailResponse.model_validate(share)
