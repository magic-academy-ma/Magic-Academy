from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas import (
    AgentDetailResponse,
    AgentStateDetailResponse,
    DecisionExplanationDetailResponse,
    MemoryResponse,
    RelationshipResponse,
)
from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import User
from app.services.agents import (
    get_agent_detail,
    get_agent_state,
    get_decision_explanation,
    list_agent_memories,
    list_agent_relationships,
)

router = APIRouter(prefix="/agents", tags=["agents"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(require_user_role)]


@router.get("/{agent_id}", response_model=AgentDetailResponse)
def get_detail(agent_id: UUID, db: DatabaseSession, current_user: CurrentUser):
    return get_agent_detail(db, agent_id, current_user)


@router.get("/{agent_id}/state", response_model=AgentStateDetailResponse)
def get_state(agent_id: UUID, db: DatabaseSession, current_user: CurrentUser):
    return get_agent_state(db, agent_id, current_user)


@router.get("/{agent_id}/memories", response_model=list[MemoryResponse])
def get_memories(
    agent_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=10)] = 5,
):
    return list_agent_memories(db, agent_id, current_user, limit)


@router.get("/{agent_id}/relationships", response_model=list[RelationshipResponse])
def get_relationships(agent_id: UUID, db: DatabaseSession, current_user: CurrentUser):
    return list_agent_relationships(db, agent_id, current_user)


@router.get("/{agent_id}/decision-explanation", response_model=DecisionExplanationDetailResponse)
def get_explanation(
    agent_id: UUID,
    db: DatabaseSession,
    current_user: CurrentUser,
    tick: Annotated[int, Query(ge=0)],
):
    return get_decision_explanation(db, agent_id, current_user, tick)
