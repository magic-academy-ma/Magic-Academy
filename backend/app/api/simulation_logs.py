from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import SimulationLogEntryResponse
from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import User
from app.services.simulation_logs import list_simulation_logs
from app.services.simulations import require_owned_simulation

router = APIRouter(prefix="/simulations/{simulation_id}/logs", tags=["logs"])


@router.get("", response_model=list[SimulationLogEntryResponse])
def get_all(
    simulation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> list[SimulationLogEntryResponse]:
    require_owned_simulation(db, simulation_id, current_user)
    return list_simulation_logs(db, simulation_id)
