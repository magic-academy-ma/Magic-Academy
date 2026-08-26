from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.schemas import SimulationShareCreateRequest, SimulationShareResponse
from app.core.database import get_db
from app.core.security import get_current_user, require_user_role
from app.domain.models import User
from app.services.simulation_shares import (
    cancel_simulation_share,
    create_simulation_share,
    get_public_simulation_shares,
    get_simulation_share_detail,
)

router = APIRouter(tags=["simulation-shares"])
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


@router.post("/simulations/{simulation_id}/share", response_model=SimulationShareResponse, status_code=status.HTTP_201_CREATED)
def create_share_v1(
    simulation_id: UUID,
    request: SimulationShareCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> SimulationShareResponse:
    return SimulationShareResponse.model_validate(
        create_simulation_share(
            db,
            current_user,
            simulation_id,
            visibility=request.visibility,
            export_payload=request.export_payload,
        )
    )


@router.post("/simulations/{simulation_id}/shares", response_model=SimulationShareResponse, status_code=status.HTTP_201_CREATED)
def create_share_v2(
    simulation_id: UUID,
    request: SimulationShareCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> SimulationShareResponse:
    return create_share_v1(simulation_id, request, db, current_user)


@router.delete("/simulations/{simulation_id}/share", status_code=status.HTTP_204_NO_CONTENT)
def delete_share_v1(
    simulation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> None:
    cancel_simulation_share(db, current_user, simulation_id)
    return None


@router.delete("/simulations/{simulation_id}/shares", status_code=status.HTTP_204_NO_CONTENT)
def delete_share_v2(
    simulation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> None:
    return delete_share_v1(simulation_id, db, current_user)


@router.get("/shared", response_model=list[SimulationShareResponse])
def list_public_shares_v1(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(optional_current_user),
) -> list[SimulationShareResponse]:
    del current_user
    return [SimulationShareResponse.model_validate(share) for share in get_public_simulation_shares(db)]


@router.get("/shares", response_model=list[SimulationShareResponse])
def list_public_shares_v2(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(optional_current_user),
) -> list[SimulationShareResponse]:
    return list_public_shares_v1(db, current_user)


@router.get("/shared/{share_id}", response_model=SimulationShareResponse)
def get_share_detail_v1(
    share_id: UUID,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(optional_current_user),
) -> SimulationShareResponse:
    return SimulationShareResponse.model_validate(get_simulation_share_detail(db, share_id, current_user))


@router.get("/shares/{share_id}", response_model=SimulationShareResponse)
def get_share_detail_v2(
    share_id: UUID,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(optional_current_user),
) -> SimulationShareResponse:
    return get_share_detail_v1(share_id, db, current_user)
