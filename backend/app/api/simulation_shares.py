from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.schemas import (
    SimulationShareCreateRequest,
    SimulationShareDetailResponse,
    SimulationShareSummaryResponse,
)
from app.api.slice7_errors import Slice7ErrorRoute
from app.core.database import get_db
from app.core.security import get_current_user, require_user_role
from app.domain.models import User
from app.services.simulation_shares import (
    cancel_simulation_share,
    create_simulation_share,
    get_public_simulation_shares,
    get_simulation_share_detail,
)

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
