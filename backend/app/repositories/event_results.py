"""Read the persisted result, not a recomputed live-world representation."""

from copy import deepcopy
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.models import EventBatchResult


def get_event_result(session: Session, simulation_id: UUID, tick_number: int) -> dict | None:
    """Callers must first enforce Simulation ownership."""
    row = session.get(EventBatchResult, (simulation_id, tick_number))
    return None if row is None else deepcopy(row.result_payload)
