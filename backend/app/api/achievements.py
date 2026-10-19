from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import User
from app.services.achievements import (
    grant_event_witness_achievements,
    grant_inspector_achievements,
    list_achievements,
)

router = APIRouter(prefix="/achievements", tags=["achievements"])


class InspectorWitnessRequest(BaseModel):
    simulation_id: UUID
    agent_id: UUID


class EventWitnessRequest(BaseModel):
    simulation_id: UUID
    event_id: UUID


@router.get("")
def achievements(db: Session = Depends(get_db), owner: User = Depends(require_user_role)) -> dict:
    return {"data": list_achievements(db, owner)}


@router.post("/free/inspector")
def witness_inspector(
    body: InspectorWitnessRequest,
    db: Session = Depends(get_db),
    owner: User = Depends(require_user_role),
) -> dict:
    granted = grant_inspector_achievements(db, owner, body.simulation_id, body.agent_id)
    db.commit()
    return {"data": {"new_achievements": sorted(granted)}}


@router.post("/free/event")
def witness_event(
    body: EventWitnessRequest,
    db: Session = Depends(get_db),
    owner: User = Depends(require_user_role),
) -> dict:
    granted = grant_event_witness_achievements(db, owner, body.simulation_id, body.event_id)
    db.commit()
    return {"data": {"new_achievements": sorted(granted)}}
