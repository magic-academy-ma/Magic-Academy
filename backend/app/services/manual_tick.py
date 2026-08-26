from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import Agent, Event, EventParticipant, Simulation
from app.services.database_runtime_results import DatabaseRuntimeResultSink
from app.services.policy_commit import PolicyCommitResult, evaluate_and_apply_policy
from app.services.runtime_input_adapter import RuntimeInputAdapter
from app.services.runtime_orchestrator import RuntimeOrchestrator
from app.services.simulation_tick import SimulationTickService
from app.simulation.agent_runtime import (
    AgentRuntime,
    AgentRuntimeResult,
    Block,
    EventType,
    ScheduleSummary,
)
from app.simulation.tick_engine import (
    AgentType,
    MemoryItem,
    PolicyFn,
    TickAgent,
    TickEngine,
    TickEvent,
    WorldSnapshot,
)


class TickAlreadyRunningError(Exception):
    pass


@dataclass(frozen=True)
class ManualTickResult:
    previous_tick: int
    current_tick: int
    current_day: int
    agent_names: dict[UUID, str]
    runtime_results: tuple[AgentRuntimeResult, ...]
    policy_result: PolicyCommitResult
    retrieval_traces: dict[str, list[str]]
    retrieved_memories: dict[str, tuple[MemoryItem, ...]]


def tick_position(tick_number: int) -> tuple[int, Block]:
    if tick_number < 1:
        raise ValueError("tick_number must be positive")
    current_day = ((tick_number - 1) // 3) + 1
    block = (Block.MORNING, Block.AFTERNOON, Block.EVENING)[
        (tick_number - 1) % 3
    ]
    return current_day, block


async def advance_manual_tick(
    db: Session,
    simulation: Simulation,
    *,
    runtime: AgentRuntime,
    policy: PolicyFn | None = None,
) -> ManualTickResult:
    locked = db.scalar(
        select(
            text(
                "pg_try_advisory_xact_lock(hashtextextended(:simulation_id, 0))"
            )
        ).params(simulation_id=str(simulation.id))
    )
    if not locked:
        raise TickAlreadyRunningError

    db.refresh(simulation, with_for_update=True)
    previous_tick = simulation.current_tick
    current_tick = previous_tick + 1
    current_day, block = tick_position(current_tick)
    run_id = uuid7()

    event = db.scalar(
        select(Event)
        .where(
            Event.simulation_id == simulation.id,
            Event.event_type == "class",
            Event.status.in_(("scheduled", "ongoing")),
        )
        .order_by(Event.created_at, Event.id)
        .limit(1)
    )
    if event is None or event.location_id is None:
        raise RuntimeError("Slice 1 CLASS Event fixture is missing")
    participants = list(
        db.scalars(
            select(EventParticipant)
            .where(EventParticipant.event_id == event.id)
            .order_by(EventParticipant.created_at, EventParticipant.id)
        )
    )
    agents = list(
        db.scalars(
            select(Agent)
            .where(
                Agent.simulation_id == simulation.id,
                Agent.deleted_at.is_(None),
            )
            .order_by(Agent.fixture_key)
        )
    )
    participant_ids = {participant.agent_id for participant in participants}
    preselected_ids = [
        agent.id
        for agent in agents
        if agent.fixture_key == "student-01"
        or (agent.agent_type == "professor" and agent.id in participant_ids)
    ]
    if not any(agent.fixture_key == "student-01" for agent in agents):
        raise RuntimeError("Slice 1 student fixture is missing")

    service = SimulationTickService(
        RuntimeInputAdapter(
            RuntimeOrchestrator(
                runtime,
                DatabaseRuntimeResultSink(db),
            )
        )
    )
    schedule = ScheduleSummary(
        event_id=event.id,
        schedule_type=EventType.CLASS,
        is_mandatory=True,
        location_id=event.location_id,
        start_tick=current_tick,
        end_tick=current_tick,
    )
    batch = None
    policy_result = None

    async def run_runtime_batch(
        selected_agents: list[TickAgent],
        _event: TickEvent,
        _snapshot: WorldSnapshot,
    ) -> dict[str, AgentRuntimeResult]:
        nonlocal batch
        batch = service.run_runtime_phase(
            db,
            simulation_id=simulation.id,
            run_id=run_id,
            tick_number=current_tick,
            block=block,
            preselected_agent_ids=[UUID(agent.id) for agent in selected_agents],
            schedule=schedule,
            events=[event],
            event_participants={event.id: participants},
        )
        return {str(result.agent_id): result for result in batch.results}

    async def evaluate_policy_batch(policy_inputs):
        nonlocal policy_result
        policy_result = evaluate_and_apply_policy(
            db,
            simulation_id=simulation.id,
            run_id=run_id,
            tick_number=current_tick,
            runtime_results=tuple(item.runtime_result for item in policy_inputs),
        )
        if policy is not None:
            await policy(policy_inputs)

    candidates_by_id = {agent.id: agent for agent in agents}
    tick_candidates = [
        TickAgent(
            id=str(agent_id),
            agent_type=(
                AgentType.PROFESSOR
                if candidates_by_id[agent_id].agent_type == "professor"
                else AgentType.STUDENT
            ),
            is_active=candidates_by_id[agent_id].active_status == "active",
        )
        for agent_id in preselected_ids
    ]
    snapshot = WorldSnapshot(
        simulation_id=str(simulation.id),
        current_tick=previous_tick,
    )
    tick_result = await TickEngine(
        runtime=run_runtime_batch,
        policy=evaluate_policy_batch,
    ).run_tick(
        tick_candidates,
        TickEvent(
            id=str(event.id),
            event_type=event.event_type,
            participant_ids={str(agent_id) for agent_id in participant_ids},
        ),
        snapshot,
    )
    if tick_result.status != "completed" or batch is None or policy_result is None:
        raise RuntimeError("TickEngine completed without a Runtime batch")
    simulation.current_tick = current_tick
    simulation.current_day = current_day
    db.flush()
    return ManualTickResult(
        previous_tick=previous_tick,
        current_tick=current_tick,
        current_day=current_day,
        agent_names={agent.id: agent.name for agent in agents},
        runtime_results=batch.results,
        policy_result=policy_result,
        retrieval_traces=tick_result.retrieval_traces,
        retrieved_memories={
            agent_id: tuple(memories)
            for agent_id, memories in snapshot.data.get("memories", {}).items()
        },
    )
