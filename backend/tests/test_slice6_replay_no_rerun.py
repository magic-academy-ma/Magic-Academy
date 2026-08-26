import os
from uuid import UUID

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from uuid6 import uuid7

from app.domain.models import Agent, RuntimeResult, Simulation, SimulationSnapshot, User
from app.services.fixtures import seed_slice_zero
from app.services.simulation_snapshots import (
    SimulationSnapshotService,
    SnapshotNotFoundError,
    UnsupportedSnapshotSchemaError,
)
from app.simulation.agent_runtime import (
    AgentContext,
    AgentRuntime,
    AgentRuntimeInput,
    AgentStateContext,
    BigFiveContext,
    Block,
    EventSummary,
    MockLLMClient,
    ScheduleSummary,
)
from app.simulation.instrumentation import get_counts, reset_counters
from app.simulation.replay_guard import ReplayGuard, ReplayModeError
from app.simulation.tick_engine import (
    AgentType,
    TickAgent,
    TickEngine,
    TickEvent,
    WorldSnapshot,
)
from tests.runtime_factories import make_runtime_result


# ─── 6: Tick guard — participants 유무와 무관하게 replay mode에서 진입 자체가 차단되는지 ──


async def test_replay_blocks_tick_regardless_of_participant_count():
    """Replay mode must block TickEngine.run_tick() at the entry boundary,
    whether or not any participant was selected for the tick."""
    call_log: list[str] = []

    async def runtime(agents, event, snapshot):
        call_log.append("runtime-called")
        return {a.id: make_runtime_result(a.id) for a in agents}

    engine = TickEngine(runtime=runtime)
    student = TickAgent(id="s-1", agent_type=AgentType.STUDENT, is_active=True)
    event_with_participant = TickEvent(id="evt-1", event_type="class", participant_ids={"s-1"})
    event_without_participant = TickEvent(id="evt-2", event_type="class", participant_ids=set())

    # Normal mode with a participant: a real tick instruments tick + runtime.
    reset_counters()
    snapshot = WorldSnapshot(simulation_id="sim-guard-1", current_tick=0, data={})
    await engine.run_tick(agents=[student], event=event_with_participant, snapshot=snapshot)
    counts = get_counts()
    assert counts["tick_calls"] == 1
    assert counts["runtime_calls"] == 1
    assert call_log == ["runtime-called"]

    # Replay mode with a participant present: must block before the runtime callback.
    call_log.clear()
    reset_counters()
    with pytest.raises(ReplayModeError):
        with ReplayGuard():
            await engine.run_tick(
                agents=[student],
                event=event_with_participant,
                snapshot=WorldSnapshot(simulation_id="sim-guard-1", current_tick=0, data={}),
            )
    counts = get_counts()
    assert counts["tick_calls"] == 0
    assert counts["runtime_calls"] == 0
    assert counts["llm_calls"] == 0
    assert call_log == []

    # Replay mode with ZERO participants: entry itself must still be blocked.
    # This is the fix for the bug where assert_not_replay() only ran inside
    # `if participants:`, so an empty-participant tick slipped through replay mode.
    reset_counters()
    with pytest.raises(ReplayModeError):
        with ReplayGuard():
            await engine.run_tick(
                agents=[],
                event=event_without_participant,
                snapshot=WorldSnapshot(simulation_id="sim-guard-2", current_tick=0, data={}),
            )
    counts = get_counts()
    assert counts["tick_calls"] == 0
    assert counts["runtime_calls"] == 0
    assert counts["llm_calls"] == 0
    assert call_log == []


# ─── 6: Runtime/LLM guard — AgentRuntime의 실제 LLM 호출 직전에 replay guard가 동작하는지 ──


@pytest.fixture()
def runtime_input() -> AgentRuntimeInput:
    agent_id = UUID("00000000-0000-0000-0000-000000000001")
    location_id = UUID("10000000-0000-0000-0000-000000000001")
    event_id = UUID("20000000-0000-0000-0000-000000000001")
    return AgentRuntimeInput(
        run_id="issue121-llm-guard-run",
        tick_number=0,
        block=Block.MORNING,
        agent=AgentContext(
            agent_id=agent_id,
            fixture_key="student-01",
            agent_type="student",
            name="아델",
            mbti="ISTJ",
            big_five=BigFiveContext(
                openness=-25,
                conscientiousness=25,
                extraversion=-25,
                agreeableness=-20,
                emotional_stability=0,
            ),
            state=AgentStateContext(hunger=25, fatigue=15, stress=20, satisfaction=60, mood=0),
            current_location_id=location_id,
            active_status=True,
        ),
        nearby_agents=[],
        relationships=[],
        memories=[],
        events=[
            EventSummary(
                event_id=event_id,
                event_type="class",
                location_id=location_id,
                participant_agent_ids=[agent_id],
                title="통합마법학",
            )
        ],
        schedule=ScheduleSummary(
            event_id=event_id,
            schedule_type="class",
            is_mandatory=True,
            location_id=location_id,
            start_tick=0,
            end_tick=0,
        ),
        valid_agent_ids=[agent_id],
        valid_location_ids=[location_id],
    )


class _NeverCalledLLMClient:
    """LLM client stub that fails loudly if generate() is ever invoked."""

    def __init__(self) -> None:
        self.call_count = 0

    def generate(self, runtime_input: AgentRuntimeInput) -> object:
        self.call_count += 1
        raise AssertionError("LLM client generate() must not be called during replay")


class _CountingLLMClient(MockLLMClient):
    def __init__(self) -> None:
        super().__init__()
        self.call_count = 0

    def generate(self, runtime_input: AgentRuntimeInput) -> object:
        self.call_count += 1
        return super().generate(runtime_input)


def test_replay_guard_blocks_llm_client_before_generate(runtime_input: AgentRuntimeInput) -> None:
    spy = _NeverCalledLLMClient()
    runtime = AgentRuntime(spy)

    reset_counters()
    with pytest.raises(ReplayModeError):
        with ReplayGuard():
            runtime.run(runtime_input)

    assert spy.call_count == 0
    assert get_counts()["llm_calls"] == 0

    # Normal mode: the same runtime input succeeds and does reach the LLM client.
    normal_spy = _CountingLLMClient()
    normal_runtime = AgentRuntime(normal_spy)
    reset_counters()
    result = normal_runtime.run(runtime_input)
    assert normal_spy.call_count == 1
    assert get_counts()["llm_calls"] == 1
    assert result.status.value == "PROPOSED"


# ─── 7~11: 실제 저장 데이터 기반 Replay 검증 (PostgreSQL integration) ──────────────

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")


@pytest.fixture()
def replay_context():
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE users, simulations RESTART IDENTITY CASCADE"))

    owner_id = uuid7()
    simulation_id = uuid7()
    with session_factory.begin() as session:
        session.add(
            User(
                id=owner_id,
                username="issue121-owner",
                display_name="Issue 121 Owner",
                password_hash="not-a-real-password-hash",
                roles=["USER"],
            )
        )
        session.flush()
        session.add(
            Simulation(id=simulation_id, owner_id=owner_id, name="Issue 121 Replay Source")
        )
        session.flush()
        seed_slice_zero(session, simulation_id)
    try:
        yield session_factory, owner_id, simulation_id
    finally:
        engine.dispose()


def _persist_tick(
    session_factory,
    simulation_id: UUID,
    *,
    run_id: str,
    tick_number: int,
    agent_fixture_key: str,
    fingerprint_seed: str,
) -> tuple[UUID, UUID, UUID]:
    """Persist one real RuntimeResult row and its SimulationSnapshot for a tick,
    mirroring what the production Runtime/persistence path would already have
    written by the time a tick completes. Does not touch TickEngine, AgentRuntime,
    or the LLM client."""
    service = SimulationSnapshotService()
    with session_factory.begin() as session:
        simulation = session.get(Simulation, simulation_id)
        simulation.current_tick = tick_number
        agent_id = session.scalar(
            select(Agent.id).where(
                Agent.simulation_id == simulation_id,
                Agent.fixture_key == agent_fixture_key,
            )
        )
        runtime_result_id = uuid7()
        session.add(
            RuntimeResult(
                id=runtime_result_id,
                run_id=run_id,
                tick_number=tick_number,
                agent_id=agent_id,
                status="PROPOSED",
                action_type="IDLE",
                intent={},
                retry_count=0,
                model="test-model",
                prompt_version="test-prompt-v1",
                idempotency_key=f"{run_id}:{tick_number}:{agent_fixture_key}",
                result_fingerprint=(fingerprint_seed * 64)[:64],
            )
        )
        session.flush()
        snapshot = service.create_snapshot(session, simulation)
        snapshot_id = snapshot.id
    return runtime_result_id, snapshot_id, agent_id


def _replay_tick(
    session,
    service: SimulationSnapshotService,
    *,
    owner_id: UUID,
    run_id: str,
    tick_number: int,
    snapshot_id: UUID,
):
    """Minimal read-only Replay path proving Issue #121's no-rerun contract.

    Composed only of already-existing persistence code — a direct read of the
    persisted RuntimeResult rows plus SimulationSnapshotRepository.get /
    SimulationSnapshotService.restore_snapshot. It never invokes TickEngine,
    AgentRuntime, or an LLM client, and never creates a new RuntimeResult or
    SimulationSnapshot row.

    NOTE: no real HTTP Replay read endpoint exists yet on this Slice 6 base —
    see the Task 4 report's Slice 6 integration TODO. This function stands in
    for that read path using only already-existing persistence code.
    """
    runtime_rows = list(
        session.scalars(
            select(RuntimeResult)
            .where(RuntimeResult.run_id == run_id, RuntimeResult.tick_number == tick_number)
            .order_by(RuntimeResult.agent_id)
        )
    )
    if not runtime_rows:
        raise SnapshotNotFoundError(
            f"no RuntimeResult recorded for run {run_id} at tick {tick_number}"
        )

    snapshot = service.snapshots.get(session, snapshot_id)
    if snapshot is None:
        raise SnapshotNotFoundError(f"no snapshot recorded with id {snapshot_id}")

    if snapshot.tick_number != tick_number:
        raise UnsupportedSnapshotSchemaError(
            "RuntimeResult.tick_number does not match SimulationSnapshot.tick_number"
        )

    restored = service.restore_snapshot(session, snapshot.id, owner_id=owner_id)
    return runtime_rows, restored


def test_replay_reads_persisted_runtime_results_and_snapshots_without_rerun(
    replay_context,
) -> None:
    session_factory, owner_id, simulation_id = replay_context
    run_id = "issue121-run-1"

    result_id_0, snapshot_id_0, agent_id_0 = _persist_tick(
        session_factory,
        simulation_id,
        run_id=run_id,
        tick_number=0,
        agent_fixture_key="student-01",
        fingerprint_seed="a",
    )
    result_id_1, snapshot_id_1, agent_id_1 = _persist_tick(
        session_factory,
        simulation_id,
        run_id=run_id,
        tick_number=1,
        agent_fixture_key="student-02",
        fingerprint_seed="b",
    )

    with session_factory() as session:
        before_runtime_count = session.scalar(select(func.count()).select_from(RuntimeResult))
        before_snapshot_count = session.scalar(
            select(func.count()).select_from(SimulationSnapshot)
        )

    service = SimulationSnapshotService()
    reset_counters()
    with session_factory() as session:
        with ReplayGuard():
            rows_0, restored_0 = _replay_tick(
                session,
                service,
                owner_id=owner_id,
                run_id=run_id,
                tick_number=0,
                snapshot_id=snapshot_id_0,
            )
            rows_1, restored_1 = _replay_tick(
                session,
                service,
                owner_id=owner_id,
                run_id=run_id,
                tick_number=1,
                snapshot_id=snapshot_id_1,
            )

    counts = get_counts()
    assert counts["tick_calls"] == 0
    assert counts["runtime_calls"] == 0
    assert counts["llm_calls"] == 0

    # 저장된 기록과 Replay 결과의 순서·식별자·내용 일치
    assert [row.id for row in rows_0] == [result_id_0]
    assert [row.id for row in rows_1] == [result_id_1]
    assert rows_0[0].agent_id == agent_id_0
    assert rows_1[0].agent_id == agent_id_1
    assert rows_0[0].run_id == run_id == rows_1[0].run_id
    assert rows_0[0].tick_number == 0
    assert rows_1[0].tick_number == 1
    assert rows_0[0].action_type == "IDLE" == rows_1[0].action_type
    assert restored_0["simulation"]["id"] == str(simulation_id) == restored_1["simulation"]["id"]

    with session_factory() as session:
        after_runtime_count = session.scalar(select(func.count()).select_from(RuntimeResult))
        after_snapshot_count = session.scalar(select(func.count()).select_from(SimulationSnapshot))

    # Replay 자체는 새 RuntimeResult/Snapshot을 만들지 않는다 (DB write 0).
    assert after_runtime_count == before_runtime_count
    assert after_snapshot_count == before_snapshot_count


def test_replay_fails_explicitly_when_runtime_result_is_missing(replay_context) -> None:
    """9-A: Runtime 기록 없음 → 재실행 금지, 명시적 오류."""
    session_factory, owner_id, simulation_id = replay_context
    run_id = "issue121-run-missing-runtime"

    service = SimulationSnapshotService()
    with session_factory.begin() as session:
        simulation = session.get(Simulation, simulation_id)
        simulation.current_tick = 0
        snapshot = service.create_snapshot(session, simulation)
        snapshot_id = snapshot.id

    reset_counters()
    with session_factory() as session:
        with pytest.raises(SnapshotNotFoundError, match="RuntimeResult"):
            with ReplayGuard():
                _replay_tick(
                    session,
                    service,
                    owner_id=owner_id,
                    run_id=run_id,
                    tick_number=0,
                    snapshot_id=snapshot_id,
                )

    counts = get_counts()
    assert counts["tick_calls"] == 0
    assert counts["runtime_calls"] == 0
    assert counts["llm_calls"] == 0


def test_replay_fails_explicitly_when_snapshot_is_missing(replay_context) -> None:
    """9-B: 요청 Tick에 Snapshot 없음 → 새 Snapshot 생성 금지, 명시적 오류."""
    session_factory, owner_id, simulation_id = replay_context
    run_id = "issue121-run-missing-snapshot"
    _persist_tick(
        session_factory,
        simulation_id,
        run_id=run_id,
        tick_number=0,
        agent_fixture_key="student-01",
        fingerprint_seed="c",
    )
    missing_snapshot_id = uuid7()

    with session_factory() as session:
        before_snapshot_count = session.scalar(
            select(func.count()).select_from(SimulationSnapshot)
        )

    service = SimulationSnapshotService()
    reset_counters()
    with session_factory() as session:
        with pytest.raises(SnapshotNotFoundError, match="snapshot"):
            with ReplayGuard():
                _replay_tick(
                    session,
                    service,
                    owner_id=owner_id,
                    run_id=run_id,
                    tick_number=0,
                    snapshot_id=missing_snapshot_id,
                )

    counts = get_counts()
    assert counts["tick_calls"] == 0
    assert counts["runtime_calls"] == 0
    assert counts["llm_calls"] == 0

    with session_factory() as session:
        after_snapshot_count = session.scalar(select(func.count()).select_from(SimulationSnapshot))
    assert after_snapshot_count == before_snapshot_count


def test_replay_fails_explicitly_when_runtime_result_tick_mismatches_snapshot_tick(
    replay_context,
) -> None:
    """9-C: RuntimeResult의 tick과 Snapshot tick 불일치 → fallback 금지, 명시적 오류."""
    session_factory, owner_id, simulation_id = replay_context
    run_id = "issue121-run-tick-mismatch"
    service = SimulationSnapshotService()

    # RuntimeResult는 tick 1에 기록되지만,
    _persist_tick(
        session_factory,
        simulation_id,
        run_id=run_id,
        tick_number=1,
        agent_fixture_key="student-01",
        fingerprint_seed="d",
    )
    # Replay 호출에 전달되는 snapshot은 tick 0의 것 — 정합성 불일치 상황.
    with session_factory.begin() as session:
        simulation = session.get(Simulation, simulation_id)
        simulation.current_tick = 0
        mismatched_snapshot = service.create_snapshot(session, simulation)
        mismatched_snapshot_id = mismatched_snapshot.id

    reset_counters()
    with session_factory() as session:
        with pytest.raises(UnsupportedSnapshotSchemaError, match="tick_number"):
            with ReplayGuard():
                _replay_tick(
                    session,
                    service,
                    owner_id=owner_id,
                    run_id=run_id,
                    tick_number=1,
                    snapshot_id=mismatched_snapshot_id,
                )

    counts = get_counts()
    assert counts["tick_calls"] == 0
    assert counts["runtime_calls"] == 0
    assert counts["llm_calls"] == 0
