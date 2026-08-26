import asyncio
from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import User
from app.repositories.memory_repository import MemoryRepository
from app.services.manual_tick import (
    TickAlreadyRunningError,
    advance_manual_tick,
    create_memory_callbacks,
    create_policy_callback,
)
from app.services.runtime_dependency import (
    get_agent_runtime,
    get_memory_repository,
    get_policy_evaluator,
)
from app.services.simulations import require_owned_simulation
from app.simulation.agent_runtime import AgentRuntime
from app.simulation.policy.models import PolicyEvaluationInput, PolicyEvaluationResult


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


class AgentMemoryItem(BaseModel):
    id: str
    content: str
    memory_type: str
    importance: int
    created_tick: int
    event_id: str | None = None


class AgentMemoryResponse(BaseModel):
    agent_id: str
    memory_ids_passed: list[str]
    memories: list[AgentMemoryItem]


class TickAdvanceResponse(BaseModel):
    simulation_id: UUID
    previous_tick: int
    current_tick: int
    current_day: int
    status: str
    agent_results: list[AgentTickResultResponse]
    retrieved_memories: list[AgentMemoryResponse] = Field(default_factory=list)


router = APIRouter(tags=["ticks"])


@router.post(
    "/simulations/{simulation_id}/ticks/advance",
    response_model=TickAdvanceResponse,
)
def advance_tick(
    simulation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
    runtime: AgentRuntime = Depends(get_agent_runtime),
    policy_evaluator: Callable[
        [PolicyEvaluationInput], PolicyEvaluationResult
    ] = Depends(get_policy_evaluator),
    memory_repository: MemoryRepository = Depends(get_memory_repository),
):
    simulation = require_owned_simulation(db, simulation_id, current_user)
    memory_retriever, memory_store = create_memory_callbacks(db, memory_repository)
    try:
        result = asyncio.run(
            advance_manual_tick(
                db,
                simulation,
                runtime=runtime,
                policy=create_policy_callback(db, simulation.id, policy_evaluator),
                policy_version="policy-mvp-0.1",
                memory_retriever=memory_retriever,
                memory_store=memory_store,
            )
        )
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
        retrieved_memories=[
            AgentMemoryResponse(
                agent_id=agent_id,
                memory_ids_passed=memory_ids,
                memories=[
                    AgentMemoryItem(
                        id=memory.id,
                        content=memory.content,
                        memory_type=memory.memory_type,
                        importance=memory.importance,
                        created_tick=memory.created_tick,
                        event_id=memory.event_id,
                    )
                    for memory in result.retrieved_memories.get(agent_id, ())
                ],
            )
            for agent_id, memory_ids in result.retrieval_traces.items()
        ],
    )
