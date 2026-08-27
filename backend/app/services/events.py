from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import Event, Location


class InvalidEventLocationError(Exception):
    pass


def create_event(
    db: Session,
    *,
    simulation_id: UUID,
    event_type: str,
    title: str,
    description: str | None,
    simulation_day: int,
    location_id: UUID | None,
) -> Event:
    if location_id is not None:
        location = db.scalar(
            select(Location).where(
                Location.id == location_id,
                Location.simulation_id == simulation_id,
            )
        )
        if location is None:
            raise InvalidEventLocationError
    event = Event(
        id=uuid7(),
        simulation_id=simulation_id,
        location_id=location_id,
        event_type=event_type,
        title=title,
        description=description,
        status="scheduled",
        simulation_day=simulation_day,
        event_metadata={},
    )
    db.add(event)
    db.flush()
    return event


def list_events(db: Session, simulation_id: UUID) -> list[Event]:
    return list(
        db.scalars(
            select(Event)
            .where(Event.simulation_id == simulation_id)
            .order_by(Event.created_at, Event.id)
        )
    )
