import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import User
from app.services.manual_tick import TickAlreadyRunningError, advance_manual_tick
from app.services.simulations import require_owned_simulation


class DecisionExplanationResponse(BaseModel):
    alternatives: list[dict]
    influencing_factors: list[dict]


class AgentTickResultResponse(BaseModel):
    agent_id: UUID
    agent_name: str
    runtime_status: str
    action_type: str
    utterance: str | None
    motivation_summary: str
    decision_explanation: DecisionExplanationResponse
    retry_count: int
    failure_reason: str | None


class RelationshipDeltaResponse(BaseModel):
    effect_id: str
    rule_id: str
    source_agent_id: UUID
    target_agent_id: UUID
    metric: str
    delta: int
    before: int
    after_preview: int
    reason: str


class TickAdvanceResponse(BaseModel):
    simulation_id: UUID
    previous_tick: int
    current_tick: int
    current_day: int
    status: str
    relationship_deltas: list[RelationshipDeltaResponse]
    agent_results: list[AgentTickResultResponse]


router = APIRouter(tags=["ticks"])


@router.post(
    "/simulations/{simulation_id}/ticks/advance",
    response_model=TickAdvanceResponse,
)
def advance_tick(
    simulation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
):
    simulation = require_owned_simulation(db, simulation_id, current_user)
    try:
        result = asyncio.run(advance_manual_tick(db, simulation))
        db.commit()
    except TickAlreadyRunningError:
        db.rollback()
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                "code": "TICK_ALREADY_RUNNING",
                "message": "이미 진행 중인 Tick이 있습니다.",
                }
            },
        )
    except Exception:
        db.rollback()
        raise

    return TickAdvanceResponse(
        simulation_id=simulation.id,
        previous_tick=result.previous_tick,
        current_tick=result.current_tick,
        current_day=result.current_day,
        status="COMPLETED",
        relationship_deltas=[
            RelationshipDeltaResponse(
                effect_id=effect.effect_id,
                rule_id=effect.rule_id,
                source_agent_id=UUID(effect.source_agent_id),
                target_agent_id=UUID(effect.target_agent_id),
                metric=effect.metric,
                delta=effect.after_preview - effect.before,
                before=effect.before,
                after_preview=effect.after_preview,
                reason=effect.reason,
            )
            for effect in result.policy_result.relationship_effects
            if effect.target_agent_id is not None
        ],
        agent_results=[
            AgentTickResultResponse(
                agent_id=runtime_result.agent_id,
                agent_name=result.agent_names[runtime_result.agent_id],
                runtime_status=runtime_result.status,
                action_type=runtime_result.intent.action_type,
                utterance=runtime_result.intent.utterance,
                motivation_summary=runtime_result.intent.motivation_summary,
                decision_explanation=runtime_result.intent.decision_explanation.model_dump(),
                retry_count=runtime_result.retry_count,
                failure_reason=runtime_result.failure_reason,
            )
            for runtime_result in result.runtime_results
        ],
    )
