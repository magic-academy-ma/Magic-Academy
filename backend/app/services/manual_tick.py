from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import (
    Agent,
    AgentState,
    Event,
    EventParticipant,
    Relationship,
    RuntimeResult,
    Simulation,
    StudentProfile,
)
from app.services.database_runtime_results import DatabaseRuntimeResultSink
from app.services.event_magic_phase import EventAndMagicResult, run_event_and_magic_phase
from app.services.policy_commit import PolicyCommitResult, evaluate_and_apply_policy
from app.services.runtime_input_adapter import RuntimeInputAdapter
from app.services.runtime_orchestrator import RuntimeOrchestrator
from app.services.simulation_tick import SimulationTickService
from app.simulation.agent_runtime import (
    AgentRuntime,
    AgentRuntimeResult,
    Block,
    ScheduleSummary,
    SignalIntensity,
    StateSignalType,
)
from app.simulation.event_master import (
    AgentSummary as EventMasterAgentSummary,
    RelationshipSummary as EventMasterRelationshipSummary,
)
from app.simulation.magic_layer import STUDENT_MISSING_STREAK_TICKS, AgentSnapshot as MagicAgentSnapshot
from app.simulation.policy.models import (
    AgentSnapshot as PolicyAgentSnapshot,
    RelationshipSnapshot,
)
from app.simulation.policy.registries.signal_policy import get_state_delta
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
    event_and_magic_result: EventAndMagicResult


def tick_position(tick_number: int) -> tuple[int, Block]:
    if tick_number < 1:
        raise ValueError("tick_number must be positive")
    current_day = ((tick_number - 1) // 3) + 1
    block = (Block.MORNING, Block.AFTERNOON, Block.EVENING)[
        (tick_number - 1) % 3
    ]
    return current_day, block


def _reaction_stress_delta(intent: dict) -> int:
    """RuntimeResult.intent에 이미 저장된 Reaction stress signal의 합산 delta.

    registries.signal_policy.get_state_delta와 동일한 규칙을 재사용한다 —
    새 계산 규칙이 아니라 evaluate_and_apply_policy가 실제로 적용한 것과
    같은 함수를 그대로 호출해 역산 정확도를 보장한다.
    """
    total = 0
    for signal in intent.get("reaction", {}).get("state_signals", []):
        signal_type_value = signal.get("signal_type")
        if signal_type_value not in (
            StateSignalType.STRESS_UP.value,
            StateSignalType.STRESS_DOWN.value,
        ):
            continue
        total += get_state_delta(
            StateSignalType(signal_type_value), SignalIntensity(signal["intensity"])
        )
    return total


def _reconstruct_recent_stress(
    db: Session,
    *,
    agent_ids: list[UUID],
    current_tick: int,
    current_stress_by_agent: dict[UUID, int],
    window: int = STUDENT_MISSING_STREAK_TICKS,
) -> dict[UUID, tuple[int, ...]]:
    """최근 window tick의 stress 값을 기존 RuntimeResult 기록에서 역산한다.

    새 history 저장소나 migration을 추가하지 않는다 — RuntimeResult.intent는
    Task2 Runtime batch가 매 tick 이미 저장하는 값이며, 그 안의 Reaction
    stress signal은 evaluate_and_apply_policy가 실제로 적용한 delta와 동일한
    규칙(get_state_delta)으로 재현 가능하다. 현재 Tick 흐름에서 stress를
    바꾸는 유일한 경로가 이 Runtime Reaction이므로(§Event/Magic 효과는 아직
    커밋되지 않음, Task 5(#105) 이후 반영) 역산 결과가 실제 DB 값과 일치한다.

    tick 연속성이 끊기면(그 tick에 RuntimeResult가 없음) 그 지점에서 멈춘다 —
    불확실한 값을 추정하지 않는다. 결과가 window보다 짧으면 호출부의
    "10/10" 스트릭 조건을 자연히 만족하지 못해 안전한 방향(미발생)으로
    동작한다.
    """
    if not agent_ids:
        return {}
    earliest_tick = max(current_tick - window, 0)
    rows = list(
        db.scalars(
            select(RuntimeResult)
            .where(
                RuntimeResult.agent_id.in_(agent_ids),
                RuntimeResult.tick_number >= earliest_tick,
                RuntimeResult.tick_number < current_tick,
            )
            .order_by(RuntimeResult.agent_id, RuntimeResult.tick_number.desc())
        )
    )
    rows_by_agent: dict[UUID, list[RuntimeResult]] = {}
    for row in rows:
        rows_by_agent.setdefault(row.agent_id, []).append(row)

    history: dict[UUID, tuple[int, ...]] = {}
    for agent_id in agent_ids:
        current = current_stress_by_agent.get(agent_id)
        if current is None:
            continue
        values = [current]
        running = current
        expected_tick = current_tick - 1
        for row in rows_by_agent.get(agent_id, []):
            if row.tick_number != expected_tick:
                break
            running -= _reaction_stress_delta(row.intent)
            values.append(running)
            expected_tick -= 1
        history[agent_id] = tuple(reversed(values))
    return history


def _run_event_and_magic_phase(
    db: Session,
    *,
    simulation_id: UUID,
    run_id: UUID,
    tick: int,
    agents: list[Agent],
) -> EventAndMagicResult:
    """Event Master -> Magic Layer -> Policy/Resolver 최소 wiring (Issue #101).

    Task 3의 실종/저주 상태 전이는 여기서 적용하지 않는다 (missing_agent_ids만
    special_events에 담겨 Task 5가 EventBatch로 변환한다). STUDENT_MISSING
    판정용 recent_stress는 새 history 저장소 없이 기존 RuntimeResult 기록에서
    역산한다 (``_reconstruct_recent_stress``).
    """
    agent_ids = [agent.id for agent in agents]
    states = list(
        db.scalars(select(AgentState).where(AgentState.agent_id.in_(agent_ids)))
    )
    states_by_agent_id = {state.agent_id: state for state in states}
    student_profiles = {
        profile.agent_id: profile
        for profile in db.scalars(
            select(StudentProfile).where(StudentProfile.agent_id.in_(agent_ids))
        )
    }
    relationships = list(
        db.scalars(
            select(Relationship).where(Relationship.simulation_id == simulation_id)
        )
    )
    recent_stress_by_agent = _reconstruct_recent_stress(
        db,
        agent_ids=agent_ids,
        current_tick=tick,
        current_stress_by_agent={
            agent_id: state.stress for agent_id, state in states_by_agent_id.items()
        },
    )

    agent_summaries: list[EventMasterAgentSummary] = []
    magic_snapshots: list[MagicAgentSnapshot] = []
    agent_state_snapshots: dict[str, PolicyAgentSnapshot] = {}
    for agent in agents:
        state = states_by_agent_id.get(agent.id)
        if state is None:
            continue
        is_active = agent.active_status == "active"
        major_id = None
        year = None
        if agent.id in student_profiles:
            major_id = student_profiles[agent.id].interest_field
            year = student_profiles[agent.id].grade
        agent_summaries.append(
            EventMasterAgentSummary(
                agent_id=str(agent.id),
                name=agent.name,
                role=agent.agent_type,
                major_id=major_id,
                year=year,
                active_status=is_active,
                current_location_id=(
                    str(state.location_id) if state.location_id else None
                ),
                mood=state.mood,
                stress=state.stress,
                fatigue=state.fatigue,
            )
        )
        magic_snapshots.append(
            MagicAgentSnapshot(
                agent_id=str(agent.id),
                agent_type=agent.agent_type,
                active_status=is_active,
                current_location_id=(
                    str(state.location_id) if state.location_id else None
                ),
                fatigue=state.fatigue,
                is_cursed=agent.cursed_until_tick is not None,
                recent_stress=recent_stress_by_agent.get(agent.id, (state.stress,)),
            )
        )
        agent_state_snapshots[str(agent.id)] = PolicyAgentSnapshot(
            agent_id=str(agent.id),
            hunger=state.hunger,
            fatigue=state.fatigue,
            stress=state.stress,
            satisfaction=state.satisfaction,
            mood=state.mood,
        )

    magic_relationship_snapshots = [
        RelationshipSnapshot(
            source_agent_id=str(relationship.source_agent_id),
            target_agent_id=str(relationship.target_agent_id),
            trust=relationship.trust,
            tension=relationship.tension,
            affection=relationship.affection,
            closeness=relationship.closeness,
            rivalry=relationship.rivalry,
            dependency=relationship.dependency,
        )
        for relationship in relationships
    ]
    event_master_relationship_summaries = [
        EventMasterRelationshipSummary(
            source_agent_id=str(relationship.source_agent_id),
            target_agent_id=str(relationship.target_agent_id),
            affection=relationship.affection,
            closeness=relationship.closeness,
        )
        for relationship in relationships
    ]

    return run_event_and_magic_phase(
        run_id=str(run_id),
        tick=tick,
        agent_summaries=agent_summaries,
        agent_state_snapshots=agent_state_snapshots,
        magic_agent_snapshots=magic_snapshots,
        event_master_relationship_summaries=event_master_relationship_summaries,
        magic_relationship_snapshots=magic_relationship_snapshots,
    )


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
    event_and_magic_result = _run_event_and_magic_phase(
        db,
        simulation_id=simulation.id,
        run_id=run_id,
        tick=current_tick,
        agents=agents,
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
        schedule_type="class",
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
        event_and_magic_result=event_and_magic_result,
    )
