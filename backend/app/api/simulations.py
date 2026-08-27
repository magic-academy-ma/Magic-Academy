from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, status
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
from app.repositories.event_results import get_event_result
from app.repositories.simulation_snapshots import SimulationConfigRepository
from app.services.realtime_events import (
    build_simulation_status_event,
    connection_manager,
)
from app.services.simulation_snapshots import magic_off_eligible
from app.services.simulations import (
    InvalidSimulationStatusTransitionError,
    create_simulation,
    get_agent_responses,
    require_owned_simulation,
    update_simulation_status,
)

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.get("/{simulation_id}/event-results/{tick_number}")
def read_event_result(
    simulation_id: UUID,
    tick_number: int = Path(ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> dict:
    """Return the stored Tick result only after enforcing ownership."""
    require_owned_simulation(db, simulation_id, current_user)
    result = get_event_result(db, simulation_id, tick_number)
    if result is None:
        raise HTTPException(status_code=404, detail="Event result not found")
    return result


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
    simulation = require_owned_simulation(db, simulation_id, current_user)
    response = SimulationResponse.model_validate(simulation)
    # 별도 GET /parameters 를 만들지 않고 기존 Simulation 조회 응답에 최신
    # simulation_config 파라미터를 실어 준다 (PR2 스펙 §10).
    config = SimulationConfigRepository().latest(db, simulation.id)
    if config is not None:
        response.event_frequency = config.event_frequency
        response.event_impact = config.event_impact
        response.magic_layer_frequency = config.magic_layer_frequency
        response.magic_layer_impact = config.magic_layer_impact
        response.magic_enabled = config.magic_enabled
        response.magic_off_eligible = magic_off_eligible(config.magic_layer_impact)
        response.config_version = config.version
    return response


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
