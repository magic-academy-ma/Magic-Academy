from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import User
from app.services.simulations import require_owned_simulation
from app.simulation.tick_engine import (
    TickConflictError,
    TickEngine,
    TickResult,
    TickRollbackError,
    WorldSnapshot,
)


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
    status: str
    participant_ids: list[str]
    runtime_outputs: dict[str, dict]
    retrieved_memories: list[AgentMemoryResponse] = []


def make_tick_router(engine: TickEngine) -> APIRouter:
    router = APIRouter(tags=["ticks"])

    @router.post(
        "/simulations/{simulation_id}/ticks/advance",
        response_model=TickAdvanceResponse,
    )
    async def advance_tick(
        simulation_id: UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_user_role),
    ) -> TickAdvanceResponse:
        require_owned_simulation(db, simulation_id, current_user)

        # TODO: PR #39 연결 후 DB에서 agents, events 조회 및 TickEngine 호출
        snapshot = WorldSnapshot(simulation_id=str(simulation_id), current_tick=0)
        try:
            result: TickResult = await engine.run_tick(
                agents=[],
                event=None,  # type: ignore[arg-type]
                snapshot=snapshot,
            )
        except TickConflictError as exc:
            raise HTTPException(status_code=409, detail="Tick is already running") from exc
        except TickRollbackError as exc:
            raise HTTPException(status_code=500, detail="Tick rolled back due to runtime failure") from exc

        # snapshot.data["memories"]: agent_id -> list[MemoryItem]
        # engine.run_tick(...)에 넘긴 snapshot 객체가 참조로 그대로 전달되므로,
        # memory_retriever가 주입돼 있다면 위 호출이 끝난 시점에 이미 채워져 있음.
        memories_by_agent: dict[str, list] = snapshot.data.get("memories", {})

        return TickAdvanceResponse(
            status=result.status,
            participant_ids=result.participant_ids,
            runtime_outputs=result.runtime_outputs,
            retrieved_memories=[
                AgentMemoryResponse(
                    agent_id=agent_id,
                    memory_ids_passed=memory_ids,
                    memories=[
                        AgentMemoryItem(
                            id=m.id,
                            content=m.content,
                            memory_type=m.memory_type,
                            importance=m.importance,
                            created_tick=m.created_tick,
                            event_id=m.event_id,
                        )
                        for m in memories_by_agent.get(agent_id, [])
                    ],
                )
                for agent_id, memory_ids in result.retrieval_traces.items()
            ],
        )

    return router
