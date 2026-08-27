from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import User
from app.services.world_map import get_world_map

router = APIRouter(prefix="/simulations/{simulation_id}/world", tags=["world-map"])


@router.get("/map")
def get_map(
    simulation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> dict:
    return {"data": get_world_map(db, simulation_id, current_user)}
