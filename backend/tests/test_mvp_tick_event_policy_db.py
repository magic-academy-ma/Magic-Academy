"""MVP Tick 시간 및 Event 발생 정책 — DB 통합 테스트.

계약: docs/04-feature-specs/mvp-tick-event-policy.md
TEST_DATABASE_URL 이 있어야 실행된다 (CI: alembic upgrade head 후 pytest).
"""

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain.models import Simulation, User
from app.repositories.simulation_snapshots import (
    SimulationConfigRepository,
    SimulationSnapshotRepository,
)
from app.services.event_frequency_history import build_event_parameters
from app.services.fixtures import seed_slice_zero
from app.services.manual_tick import advance_manual_tick, tick_position
from app.services.night_transition import (
    NightSkipConflictError,
    NightSkipNotAllowedError,
    skip_night,
)
from app.simulation.agent_runtime import AgentRuntime, Block, MockLLMClient

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required"
)


@pytest.fixture
def db():
    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        outer = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            yield session
        outer.rollback()
    engine.dispose()


def _new_simulation(db, *, status: str = "running") -> Simulation:
    user = User(
        id=uuid4(),
        username=str(uuid4()),
        display_name="mvp-tick",
        password_hash="x",
        roles=["USER"],
    )
    db.add(user)
    db.flush()
    simulation = Simulation(
        id=uuid4(), owner_id=user.id, name="mvp-tick", status=status
    )
    db.add(simulation)
    db.flush()
    seed_slice_zero(db, simulation.id)
    db.flush()
    return simulation


def _advance(db, simulation) -> None:
    runtime = AgentRuntime(MockLLMClient(), model="mvp-tick-policy")
    asyncio.run(advance_manual_tick(db, simulation, runtime=runtime))


# ---------------------------------------------------------------------------
# §4.2 야간 대기 불변식 + night skip
# ---------------------------------------------------------------------------
def test_evening_tick_sets_night_waiting_and_skip_transitions(db):
    simulation = _new_simulation(db)
    for _ in range(3):  # MORNING, AFTERNOON, EVENING
        _advance(db, simulation)

    db.refresh(simulation)
    assert simulation.current_tick == 3
    assert tick_position(3)[1] == Block.EVENING
    assert simulation.night_waiting is True
    assert simulation.current_day == 1

    outcome = skip_night(db, simulation)
    assert outcome.transitioned is True
    db.refresh(simulation)
    assert simulation.current_tick == 3  # 증가하지 않는다
    assert simulation.current_day == 2
    assert simulation.night_waiting is False

    # 멱등 재호출 — 상태 변경 없이 성공
    outcome2 = skip_night(db, simulation)
    assert outcome2.transitioned is False
    db.refresh(simulation)
    assert simulation.current_day == 2


def test_advance_after_evening_passes_through_night_transition(db):
    simulation = _new_simulation(db)
    for _ in range(3):
        _advance(db, simulation)
    db.refresh(simulation)
    assert simulation.night_waiting is True

    _advance(db, simulation)  # night_waiting 이면 야간 전환 후 MORNING Tick
    db.refresh(simulation)
    assert simulation.current_tick == 4
    assert simulation.current_day == 2
    assert simulation.night_waiting is False


def test_skip_night_conflicts_mid_day(db):
    simulation = _new_simulation(db)
    _advance(db, simulation)  # tick 1, MORNING
    db.refresh(simulation)
    assert simulation.night_waiting is False
    with pytest.raises(NightSkipConflictError):
        skip_night(db, simulation)


@pytest.mark.parametrize("status", ["ready", "completed", "failed"])
def test_skip_night_not_allowed_for_non_running_status(db, status):
    simulation = _new_simulation(db, status=status)
    with pytest.raises(NightSkipNotAllowedError):
        skip_night(db, simulation)


# ---------------------------------------------------------------------------
# §4.5 config_version 은 Tick 시작 시 고정된다
# ---------------------------------------------------------------------------
def test_tick_snapshot_pins_config_version_from_tick_start(db):
    simulation = _new_simulation(db)
    _advance(db, simulation)  # tick 1 -> config v1 자동 생성 + snapshot
    configs = SimulationConfigRepository()
    v1 = configs.latest(db, simulation.id)
    assert v1 is not None and v1.version == 1

    # 진행 중이 아닐 때 파라미터를 바꿔 새 버전을 만든다
    configs.create_version(
        db,
        simulation,
        event_frequency="high",
        event_impact="high",
        magic_enabled=simulation.magic_enabled,
        user_persona_settings={},
        policy_version=None,
        resolver_version=None,
    )
    db.flush()
    assert configs.latest(db, simulation.id).version == 2

    _advance(db, simulation)  # tick 2 -> v2 로 고정되어야 한다
    db.refresh(simulation)
    snapshot = SimulationSnapshotRepository().get_at_tick(
        db, simulation.id, simulation.current_tick
    )
    assert snapshot is not None
    assert snapshot.config_version == 2


# ---------------------------------------------------------------------------
# §4.3 빈도 파라미터 재구성
# ---------------------------------------------------------------------------
def test_build_event_parameters_without_config_is_inert(db):
    simulation = _new_simulation(db)
    params = build_event_parameters(
        db,
        simulation_id=simulation.id,
        current_tick=1,
        current_day=1,
        config=None,
    )
    assert params.frequency_seed is None


def test_build_event_parameters_seed_is_stable(db):
    simulation = _new_simulation(db)
    _advance(db, simulation)
    config = SimulationConfigRepository().latest(db, simulation.id)
    first = build_event_parameters(
        db, simulation_id=simulation.id, current_tick=2, current_day=1, config=config
    )
    second = build_event_parameters(
        db, simulation_id=simulation.id, current_tick=2, current_day=1, config=config
    )
    assert first.frequency_seed == second.frequency_seed
    assert first.frequency_seed == f"{simulation.id}:2:{config.version}"
