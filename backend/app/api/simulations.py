from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    AgentResponse,
    SimulationCreateRequest,
    SimulationResponse,
    SimulationStatusUpdateRequest,
)
from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import User
from app.services.realtime_events import (
    build_simulation_status_event,
    connection_manager,
)
from app.services.simulations import (
    InvalidSimulationStatusTransitionError,
    create_simulation,
    get_agent_responses,
    require_owned_simulation,
    update_simulation_status,
)

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


@router.patch("/{simulation_id}/status", response_model=SimulationResponse)
def update_status(
    simulation_id: UUID,
    request: SimulationStatusUpdateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> SimulationResponse:
    simulation = require_owned_simulation(db, simulation_id, current_user)
    try:
        update_simulation_status(db, simulation, request.status)
        realtime_event = build_simulation_status_event(simulation.id, simulation.status)
        db.commit()
    except InvalidSimulationStatusTransitionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invalid simulation status transition",
        ) from exc
    except Exception:
        db.rollback()
        raise

    background_tasks.add_task(
        connection_manager.broadcast,
        simulation.id,
        [realtime_event],
    )
    return SimulationResponse.model_validate(simulation)


@router.get("/{simulation_id}/agents", response_model=list[AgentResponse])
def get_agents(
    simulation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> list[AgentResponse]:
    return get_agent_responses(db, simulation_id, current_user)
