from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.schemas import AgentResponse, SimulationCreateRequest, SimulationResponse
from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import User
from app.services.simulations import create_simulation, get_agent_responses, require_owned_simulation

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post("", response_model=SimulationResponse, status_code=status.HTTP_201_CREATED)
def create(
    request: SimulationCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> SimulationResponse:
    return SimulationResponse.model_validate(create_simulation(db, current_user, request.name))


@router.get("/{simulation_id}", response_model=SimulationResponse)
def get_one(
    simulation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> SimulationResponse:
    return SimulationResponse.model_validate(require_owned_simulation(db, simulation_id, current_user))


@router.get("/{simulation_id}/agents", response_model=list[AgentResponse])
def get_agents(
    simulation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> list[AgentResponse]:
    return get_agent_responses(db, simulation_id, current_user)
