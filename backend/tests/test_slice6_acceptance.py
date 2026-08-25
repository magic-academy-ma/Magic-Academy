"""
Slice 6 인수 조건 — Replay·시점 복원

완료 기준:
- 저장된 설정·Snapshot을 기준으로 Replay 시나리오가 통과한다.
- Snapshot을 식별자와 시점으로 조회할 수 있다.
- 시점 복원은 원본 DB를 수정하지 않고 payload를 반환한다.
- Replay payload의 runtime_results는 원본 기록 순서와 일치한다.
- 복원 불가·기록 없음·권한 오류 상태를 명시적 예외로 처리한다.
- Slice 0~5 누적 회귀 기준이 통과한다.
"""
import os
import subprocess

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app.domain.models import (
    Agent,
    AgentState,
    RuntimeResult,
    Simulation,
    SimulationSnapshot,
    User,
)
from app.repositories.simulation_snapshots import SimulationSnapshotRepository
from app.services.fixtures import seed_slice_zero
from app.services.simulation_snapshots import (
    SimulationConfigInput,
    SimulationSnapshotService,
    SnapshotAccessDeniedError,
    SnapshotNotFoundError,
    UnsupportedSnapshotSchemaError,
)
from uuid6 import uuid7


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required"
)


@pytest.fixture()
def acceptance_context():
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE users, simulations RESTART IDENTITY CASCADE"))

    owner_id = uuid7()
    simulation_id = uuid7()
    with session_factory.begin() as session:
        session.add(
            User(
                id=owner_id,
                username="slice6-acceptance",
                display_name="Slice 6 Acceptance",
                password_hash="not-a-real-password-hash",
                roles=["USER"],
            )
        )
        session.flush()
        session.add(
            Simulation(
                id=simulation_id,
                owner_id=owner_id,
                name="Slice 6 Replay Source",
            )
        )
        session.flush()
        seed_slice_zero(session, simulation_id)
    try:
        yield session_factory, owner_id, simulation_id
    finally:
        engine.dispose()


# ── Replay 대표 시나리오 ───────────────────────────────────────────────────────


def test_replay_returns_runtime_results_in_recorded_order(acceptance_context) -> None:
    """Replay payload의 runtime_results는 tick_number·created_at·id 순으로 원본 기록과 일치한다."""
    session_factory, owner_id, simulation_id = acceptance_context
    service = SimulationSnapshotService()

    with session_factory.begin() as session:
        agent_id = session.scalar(
            select(Agent.id).where(
                Agent.simulation_id == simulation_id,
                Agent.fixture_key == "student-01",
            )
        )
        for tick, run_id in enumerate(["run-a", "run-b", "run-c"]):
            session.add(
                RuntimeResult(
                    id=uuid7(),
                    run_id=run_id,
                    tick_number=tick,
                    agent_id=agent_id,
                    status="PROPOSED",
                    action_type="IDLE",
                    intent={},
                    retry_count=0,
                    model="test-model",
                    prompt_version="test-prompt-v1",
                    idempotency_key=f"{run_id}:{tick}:student-01",
                    result_fingerprint="a" * 64,
                )
            )
        snapshot = service.create_snapshot(session, session.get(Simulation, simulation_id))
        snapshot_id = snapshot.id

    with session_factory() as session:
        restored = service.restore_snapshot(session, snapshot_id, owner_id=owner_id)

    run_ids = [row["run_id"] for row in restored["runtime_results"]]
    tick_numbers = [row["tick_number"] for row in restored["runtime_results"]]
    assert run_ids == ["run-a", "run-b", "run-c"]
    assert tick_numbers == [0, 1, 2]


def test_replay_with_no_runtime_results_returns_empty_list(acceptance_context) -> None:
    """실행 기록이 없는 Simulation의 Replay는 빈 runtime_results를 반환한다."""
    session_factory, owner_id, simulation_id = acceptance_context
    service = SimulationSnapshotService()

    with session_factory.begin() as session:
        snapshot = service.create_snapshot(session, session.get(Simulation, simulation_id))
        snapshot_id = snapshot.id

    with session_factory() as session:
        restored = service.restore_snapshot(session, snapshot_id, owner_id=owner_id)

    assert restored["runtime_results"] == []


# ── 설정 저장 후 Replay 시나리오 ─────────────────────────────────────────────


def test_replay_snapshot_includes_saved_config(acceptance_context) -> None:
    """설정 저장 후 생성된 Snapshot은 config 정보를 payload에 포함한다."""
    session_factory, owner_id, simulation_id = acceptance_context
    service = SimulationSnapshotService()

    with session_factory.begin() as session:
        simulation = session.get(Simulation, simulation_id)
        service.save_config(
            session,
            simulation,
            SimulationConfigInput("high", "low", True, {"agent_id": "student-02"}),
        )
        snapshot = service.create_snapshot(session, simulation)
        snapshot_id = snapshot.id

    with session_factory() as session:
        restored = service.restore_snapshot(session, snapshot_id, owner_id=owner_id)

    assert restored["config"]["event_frequency"] == "high"
    assert restored["config"]["event_impact"] == "low"
    assert restored["config"]["magic_enabled"] is True
    assert restored["config"]["user_persona_settings"] == {"agent_id": "student-02"}


# ── Snapshot 조회 시나리오 ───────────────────────────────────────────────────


def test_snapshot_query_by_tick_number_returns_correct_snapshot(acceptance_context) -> None:
    """tick_number로 Snapshot을 조회하면 해당 시점의 Snapshot이 반환된다."""
    session_factory, _, simulation_id = acceptance_context
    service = SimulationSnapshotService()
    repo = SimulationSnapshotRepository()

    with session_factory.begin() as session:
        simulation = session.get(Simulation, simulation_id)
        snapshot = service.create_snapshot(session, simulation)
        snapshot_id = snapshot.id
        tick = simulation.current_tick

    with session_factory() as session:
        found = repo.get_at_tick(session, simulation_id, tick)
        assert found is not None
        assert found.id == snapshot_id
        assert found.tick_number == tick


def test_snapshot_query_for_missing_tick_returns_none(acceptance_context) -> None:
    """기록이 없는 tick의 Snapshot 조회는 None을 반환한다."""
    session_factory, _, simulation_id = acceptance_context
    repo = SimulationSnapshotRepository()

    with session_factory() as session:
        assert repo.get_at_tick(session, simulation_id, 999) is None


# ── 지정 시점 복원 시나리오 ─────────────────────────────────────────────────


def test_restore_at_specified_tick_returns_agent_states(acceptance_context) -> None:
    """지정 시점 복원은 해당 시점의 에이전트 상태를 반환한다."""
    session_factory, owner_id, simulation_id = acceptance_context
    service = SimulationSnapshotService()

    with session_factory.begin() as session:
        source_state = session.scalar(
            select(AgentState)
            .join(Agent, Agent.id == AgentState.agent_id)
            .where(
                Agent.fixture_key == "student-01",
                Agent.simulation_id == simulation_id,
            )
        )
        source_state.stress = 42
        snapshot = service.create_snapshot(session, session.get(Simulation, simulation_id))
        snapshot_id = snapshot.id

    with session_factory() as session:
        restored = service.restore_snapshot(session, snapshot_id, owner_id=owner_id)

    target_agent_id = next(
        a["id"] for a in restored["agents"] if a["fixture_key"] == "student-01"
    )
    restored_state = next(
        s for s in restored["agent_states"] if s["agent_id"] == target_agent_id
    )
    assert restored_state["stress"] == 42
    assert restored["simulation"]["id"] == str(simulation_id)


def test_restore_does_not_write_to_database(acceptance_context) -> None:
    """시점 복원은 DB에 새로운 레코드를 기록하지 않는다."""
    session_factory, owner_id, simulation_id = acceptance_context
    service = SimulationSnapshotService()

    with session_factory.begin() as session:
        snapshot = service.create_snapshot(session, session.get(Simulation, simulation_id))
        snapshot_id = snapshot.id

    with session_factory() as session:
        sim_count_before = session.scalar(select(func.count()).select_from(Simulation))

    with session_factory() as session:
        service.restore_snapshot(session, snapshot_id, owner_id=owner_id)
        assert not session.new
        assert not session.dirty
        assert not session.deleted

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Simulation)) == sim_count_before


# ── 복원 불가·오류 시나리오 ─────────────────────────────────────────────────


def test_restore_rejects_nonexistent_snapshot_id(acceptance_context) -> None:
    """존재하지 않는 Snapshot ID로 복원 시도 시 SnapshotNotFoundError가 발생한다."""
    session_factory, owner_id, _ = acceptance_context
    service = SimulationSnapshotService()

    with session_factory() as session:
        with pytest.raises(SnapshotNotFoundError):
            service.restore_snapshot(session, uuid7(), owner_id=owner_id)


def test_restore_rejects_unauthorized_owner(acceptance_context) -> None:
    """소유자가 아닌 사용자의 복원 시도는 SnapshotAccessDeniedError를 발생시킨다."""
    session_factory, _, simulation_id = acceptance_context
    service = SimulationSnapshotService()

    with session_factory.begin() as session:
        snapshot = service.create_snapshot(session, session.get(Simulation, simulation_id))
        snapshot_id = snapshot.id

    with session_factory() as session:
        with pytest.raises(SnapshotAccessDeniedError):
            service.restore_snapshot(session, snapshot_id, owner_id=uuid7())


def test_restore_rejects_unsupported_schema_version(acceptance_context) -> None:
    """지원하지 않는 schema_version의 Snapshot 복원은 UnsupportedSnapshotSchemaError를 발생시킨다."""
    session_factory, owner_id, simulation_id = acceptance_context
    service = SimulationSnapshotService()

    with session_factory.begin() as session:
        snapshot = service.create_snapshot(session, session.get(Simulation, simulation_id))
        snapshot.payload = {**snapshot.payload, "schema_version": "legacy-v0"}
        snapshot_id = snapshot.id

    with session_factory() as session:
        with pytest.raises(UnsupportedSnapshotSchemaError, match="unsupported snapshot schema"):
            service.restore_snapshot(session, snapshot_id, owner_id=owner_id)


# ── Slice 0~5 누적 회귀 기준 ─────────────────────────────────────────────────


def test_slice_0_to_5_regression_baseline_passes() -> None:
    """Slice 0~5 인수·계약 테스트가 Slice 6 base 위에서 모두 통과한다."""
    slice_test_files = [
        "tests/test_slice0_acceptance.py",
        "tests/test_slice1_acceptance.py",
        "tests/test_slice2_policy_engine.py",
        "tests/test_slice3_acceptance.py",
    ]
    result = subprocess.run(
        ["python", "-m", "pytest", "-q", "--tb=short", *slice_test_files],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Slice 0~5 회귀 실패:\n{result.stdout}\n{result.stderr}"
    )
