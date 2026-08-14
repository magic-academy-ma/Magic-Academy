from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.simulation.tick_engine import (
    AgentType,
    TickAgent,
    TickConflictError,
    TickEngine,
    TickEvent,
    TickResult,
    TickRollbackError,
    WorldSnapshot,
)


class AgentIn(BaseModel):
    id: str
    agent_type: AgentType
    is_active: bool


class EventIn(BaseModel):
    id: str
    event_type: str
    participant_ids: list[str]


class SnapshotIn(BaseModel):
    simulation_id: str
    current_tick: int


class TickRequest(BaseModel):
    agents: list[AgentIn]
    event: EventIn
    snapshot: SnapshotIn


class TickResponse(BaseModel):
    status: str
    participant_ids: list[str]
    runtime_outputs: dict[str, dict]


def make_tick_router(engine: TickEngine) -> APIRouter:
    router = APIRouter(tags=["ticks"])

    @router.post(
        "/tick/{simulation_id}/run",
        response_model=TickResponse,
    )
    async def run_tick(simulation_id: str, body: TickRequest) -> TickResponse:
        agents = [
            TickAgent(id=a.id, agent_type=a.agent_type, is_active=a.is_active)
            for a in body.agents
        ]
        event = TickEvent(
            id=body.event.id,
            event_type=body.event.event_type,
            participant_ids=set(body.event.participant_ids),
        )
        snapshot = WorldSnapshot(
            simulation_id=body.snapshot.simulation_id,
            current_tick=body.snapshot.current_tick,
        )

        try:
            result: TickResult = await engine.run_tick(
                agents=agents, event=event, snapshot=snapshot
            )
        except TickConflictError as exc:
            raise HTTPException(status_code=409, detail="Tick is already running") from exc
        except TickRollbackError as exc:
            raise HTTPException(status_code=500, detail="Tick rolled back due to runtime failure") from exc
        # TODO: 전체 에러 핸들링 리팩 시 RuntimeExecutionError 외 예외(코드 버그 등) 처리 추가

        return TickResponse(
            status=result.status,
            participant_ids=result.participant_ids,
            runtime_outputs=result.runtime_outputs,
        )

    return router
