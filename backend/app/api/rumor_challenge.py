from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import User
from app.services import rumor_challenge as service
from app.services.runtime_dependency import get_agent_runtime

router = APIRouter(prefix='/challenges/rumor', tags=['rumor-chapter'])


class StartRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    seed: int = Field(ge=0, le=2**63 - 1)


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: UUID
    expected_revision: int = Field(ge=0)


class InvestigateRequest(CommandRequest):
    actor: str
    topic: Literal['RUMOR', 'SOURCE', 'OBSERVED', 'VERIFY', 'COMPARE']
    statement_indices: list[int] = Field(default_factory=list, max_length=2)


class InterveneRequest(CommandRequest):
    choice: Literal['WATCH', 'SHARE', 'REQUEST_TESTIMONY', 'REQUEST_CORRECTION', 'PUBLISH_FACT']
    target: str | None = None
    information_id: Literal['R0', 'R1', 'R2', 'F', 'S'] | None = None


@router.post('', status_code=201)
def start(request: StartRequest, db: Session = Depends(get_db), owner: User = Depends(require_user_role)):
    return {'data': service.start(db, owner, request.request_id, request.seed)}


@router.get('/current')
def current(db: Session = Depends(get_db), owner: User = Depends(require_user_role)):
    return {'data': service.current(db, owner)}


@router.get('/{run_id}')
def get_one(run_id: UUID, db: Session = Depends(get_db), owner: User = Depends(require_user_role)):
    return {'data': service.response(db, service.owned(db, run_id, owner))}


@router.post('/{run_id}/advance')
def advance(run_id: UUID, request: CommandRequest, db: Session = Depends(get_db),
            owner: User = Depends(require_user_role), runtime=Depends(get_agent_runtime)):
    return {'data': service.command(db, owner, run_id, 'advance', request.model_dump(mode='json'), runtime)}


@router.post('/{run_id}/investigate')
def investigate(run_id: UUID, request: InvestigateRequest, db: Session = Depends(get_db),
                owner: User = Depends(require_user_role), runtime=Depends(get_agent_runtime)):
    return {'data': service.command(db, owner, run_id, 'investigate', request.model_dump(mode='json'), runtime)}


@router.post('/{run_id}/intervene')
def intervene(run_id: UUID, request: InterveneRequest, db: Session = Depends(get_db), owner: User = Depends(require_user_role)):
    return {'data': service.command(db, owner, run_id, 'intervene', request.model_dump(mode='json'))}


@router.post('/{run_id}/recover')
def recover(run_id: UUID, request: CommandRequest, db: Session = Depends(get_db), owner: User = Depends(require_user_role)):
    return {'data': service.recover(db, owner, run_id, request.model_dump(mode='json'))}
