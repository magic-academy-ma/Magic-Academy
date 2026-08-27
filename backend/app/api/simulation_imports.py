from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.schemas import SimulationResponse
from app.api.slice7_errors import Slice7ErrorRoute
from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import User
from app.services.simulation_imports import import_share

router = APIRouter(tags=["simulation-imports"], route_class=Slice7ErrorRoute)


@router.post("/shares/{share_id}/imports", response_model=SimulationResponse, status_code=201)
def create_import(
    share_id: UUID,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> SimulationResponse:
    simulation = import_share(db, current_user, share_id, idempotency_key)
    return SimulationResponse.model_validate(simulation)
