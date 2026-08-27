from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import EventCreateRequest, EventResponse, LatestEventResponse
from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import User
from app.services.events import (
    InvalidEventLocationError,
    create_event,
    event_participant_agent_ids,
    latest_event,
    list_events,
)
from app.services.realtime_events import build_event_created_event, connection_manager
from app.services.simulations import require_owned_simulation

router = APIRouter(prefix="/simulations/{simulation_id}/events", tags=["events"])


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create(
    simulation_id: UUID,
    request: EventCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> EventResponse:
    require_owned_simulation(db, simulation_id, current_user)
    try:
        event = create_event(
            db,
            simulation_id=simulation_id,
            event_type=request.event_type,
            title=request.title,
            description=request.description,
            simulation_day=request.simulation_day,
            location_id=request.location_id,
        )
        realtime_event = build_event_created_event(event)
        db.commit()
    except InvalidEventLocationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Location does not belong to simulation",
        ) from exc
    except Exception:
        db.rollback()
        raise

    background_tasks.add_task(
        connection_manager.broadcast,
        simulation_id,
        [realtime_event],
    )
    return EventResponse.model_validate(event)


@router.get("", response_model=list[EventResponse])
def get_all(
    simulation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> list[EventResponse]:
    require_owned_simulation(db, simulation_id, current_user)
    return [EventResponse.model_validate(event) for event in list_events(db, simulation_id)]


def _metadata_int(metadata: dict, key: str) -> int | None:
    value = metadata.get(key)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


@router.get("/latest", response_model=LatestEventResponse)
def get_latest(
    simulation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> LatestEventResponse:
    require_owned_simulation(db, simulation_id, current_user)
    event = latest_event(db, simulation_id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No event found")
    metadata = event.event_metadata or {}
    return LatestEventResponse(
        id=event.id,
        simulation_id=event.simulation_id,
        location_id=event.location_id,
        event_type=event.event_type,
        title=event.title,
        description=event.description,
        status=event.status,
        simulation_day=event.simulation_day,
        created_at=event.created_at,
        tick=_metadata_int(metadata, "tick"),
        importance=_metadata_int(metadata, "importance"),
        target_agent_ids=event_participant_agent_ids(db, event.id),
    )
