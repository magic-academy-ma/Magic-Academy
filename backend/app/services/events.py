from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import Event, EventParticipant, Location


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


def _events_for_simulation(simulation_id: UUID):
    return select(Event).where(Event.simulation_id == simulation_id)


def list_events(db: Session, simulation_id: UUID) -> list[Event]:
    return list(
        db.scalars(
            _events_for_simulation(simulation_id).order_by(Event.created_at, Event.id)
        )
    )


def latest_event(db: Session, simulation_id: UUID) -> Event | None:
    """Return the most recent event of a simulation.

    "Latest" reuses the ordering key of ``list_events`` (``created_at``, ``id``)
    in reverse; no new priority rule is introduced.
    """
    return db.scalar(
        _events_for_simulation(simulation_id)
        .order_by(Event.created_at.desc(), Event.id.desc())
        .limit(1)
    )


def event_participant_agent_ids(db: Session, event_id: UUID) -> list[UUID]:
    return list(
        db.scalars(
            select(EventParticipant.agent_id)
            .where(EventParticipant.event_id == event_id)
            .order_by(EventParticipant.agent_id)
        )
    )
