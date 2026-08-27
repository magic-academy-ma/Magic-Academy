"""Slice 5 Task 1 — Event/Magic -> Policy/Resolver integration tests (Issue #101)."""

import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.domain.event_persistence import EventBatch, EventWrite, StateDelta
from app.domain.models import Agent, AgentState, Simulation, User
from app.services.event_persistence import persist_event_batch
from app.services.fixtures import seed_slice_zero
from app.simulation.event_master import (
    AgentSummary,
    Event,
    EventMaster,
    ImpactLevel,
    ScheduledEventInput,
)
from app.simulation.magic_layer import (
    MagicLayer,
    SpecialEvent,
    STUDENT_MISSING,
    STUDENT_MISSING_STREAK_TICKS,
)
from app.simulation.magic_layer import AgentSnapshot as MagicAgentSnapshot
from app.simulation.policy.conflict import resolve_conflicts
from app.simulation.policy.models import AgentSnapshot as PolicyAgentSnapshot, EffectTargetType
from app.simulation.policy.registries.event_policy import (
    build_event_effect_candidates,
    build_magic_effect_candidates,
)
from app.services.event_magic_phase import run_event_and_magic_phase


def _snapshot(agent_id: str, **overrides) -> PolicyAgentSnapshot:
    base = dict(agent_id=agent_id, hunger=50, fatigue=10, stress=10, satisfaction=50, mood=0)
    base.update(overrides)
    return PolicyAgentSnapshot(**base)


# ---------------------------------------------------------------------------
# 15. Event 기본 effect candidate 생성
# ---------------------------------------------------------------------------
def test_event_base_effect_candidates_use_registered_deltas():
    event = Event(
        event_key="k1",
        event_type="EXAM",
        participant_agent_ids=("s1",),
        location_id="classroom",
        tick=1,
        impact_level=ImpactLevel.HIGH,
        importance=80,
        title="기말고사",
        description="",
    )
    candidates = build_event_effect_candidates(
        event, run_id="run-1", agent_snapshots={"s1": _snapshot("s1", stress=10, fatigue=10)}
    )
    by_metric = {c.metric: c for c in candidates}
    assert by_metric["stress"].delta == 8
    assert by_metric["fatigue"].delta == 5
    assert all(c.target_type == EffectTargetType.AGENT_STATE for c in candidates)


# ---------------------------------------------------------------------------
# 16. Magic signal -> 기존 Policy delta 변환
# ---------------------------------------------------------------------------
def test_magic_signal_uses_existing_signal_policy_delta():
    special = SpecialEvent(
        event_subtype=STUDENT_MISSING,
        participant_agent_ids=("m1",),
        location_id="dormitory",
        tick=1,
        title="학생 실종",
        missing_agent_ids=("m1",),
        affected_agent_ids=("neighbor1",),
    )
    candidates = build_magic_effect_candidates(
        [special], run_id="run-1", agent_snapshots={"neighbor1": _snapshot("neighbor1", stress=20)}
    )
    assert len(candidates) == 1
    # STRESS_UP/MEDIUM -> signal_policy.get_state_delta 값(=+5)과 동일해야 한다.
    assert candidates[0].delta == 5
    assert candidates[0].metric == "stress"
    assert candidates[0].source_agent_id == "neighbor1"


# ---------------------------------------------------------------------------
# 17. 관계 변화가 Event 기본 효과에서 직접 생성되지 않음
# ---------------------------------------------------------------------------
def test_event_base_effects_never_produce_relationship_candidates():
    event = Event(
        event_key="k1",
        event_type="MT",
        participant_agent_ids=("s1", "s2"),
        location_id="resort",
        tick=1,
        impact_level=ImpactLevel.MEDIUM,
        importance=50,
        title="MT",
        description="",
    )
    candidates = build_event_effect_candidates(
        event,
        run_id="run-1",
        agent_snapshots={"s1": _snapshot("s1"), "s2": _snapshot("s2")},
    )
    assert all(c.target_type == EffectTargetType.AGENT_STATE for c in candidates)
    assert all(c.target_agent_id is None for c in candidates)


# ---------------------------------------------------------------------------
# 18. canonical effect_id dedup과 기존 Task2 resolver 호환
# ---------------------------------------------------------------------------
def test_duplicate_event_candidates_are_deduplicated_by_resolver():
    event = Event(
        event_key="k1",
        event_type="CLASS",
        participant_agent_ids=("s1",),
        location_id="classroom",
        tick=1,
        impact_level=ImpactLevel.MEDIUM,
        importance=50,
        title="수업",
        description="",
    )
    candidates = build_event_effect_candidates(
        event, run_id="run-1", agent_snapshots={"s1": _snapshot("s1", stress=10)}
    )
    resolved = resolve_conflicts([*candidates, *candidates])  # 같은 후보가 두 경로에서 온 상황 시뮬레이션
    assert len(resolved) == 1
    assert resolved[0].delta == 1  # 중복 제거되어 두 배로 합산되지 않음


# ---------------------------------------------------------------------------
# 19. 동일 effect_id conflicting payload 거부 유지
# ---------------------------------------------------------------------------
def test_conflicting_payload_for_same_effect_id_is_rejected():
    event = Event(
        event_key="k1",
        event_type="CLASS",
        participant_agent_ids=("s1",),
        location_id="classroom",
        tick=1,
        impact_level=ImpactLevel.MEDIUM,
        importance=50,
        title="수업",
        description="",
    )
    candidates = build_event_effect_candidates(
        event, run_id="run-1", agent_snapshots={"s1": _snapshot("s1", stress=10)}
    )
    conflicting = build_event_effect_candidates(
        event, run_id="run-1", agent_snapshots={"s1": _snapshot("s1", stress=99)}
    )
    import pytest
    from app.simulation.policy.conflict import ConflictingEffectIdError

    with pytest.raises(ConflictingEffectIdError):
        resolve_conflicts([*candidates, *conflicting])


# ---------------------------------------------------------------------------
# 20. Event Master -> Magic -> Policy 실제 호출 경로
# ---------------------------------------------------------------------------
def test_run_event_and_magic_phase_full_pipeline():
    agent_summaries = [
        AgentSummary(
            agent_id="s1", name="아델", role="student", major_id="방어 마법", year=1,
            active_status=True, current_location_id="classroom", mood=0, stress=10, fatigue=10,
        )
    ]
    scheduled = [
        ScheduledEventInput(
            event_id="evt-1", event_type="CLASS", location_id="classroom",
            participant_agent_ids=("s1",),
        )
    ]
    result = run_event_and_magic_phase(
        run_id="run-1",
        tick=1,
        agent_summaries=agent_summaries,
        agent_state_snapshots={"s1": _snapshot("s1", stress=10)},
        magic_agent_snapshots=[
            MagicAgentSnapshot(
                agent_id="s1", agent_type="student", active_status=True,
                current_location_id="classroom", fatigue=10, is_cursed=False,
            )
        ],
        scheduled_events=scheduled,
    )
    assert len(result.events) == 1
    assert result.events[0].event_type == "CLASS"
    assert len(result.resolved_effects) == 1
    assert result.resolved_effects[0].metric == "stress"
    assert result.resolved_effects[0].delta == 1


# ---------------------------------------------------------------------------
# 21. Task 3 EventBatch/persistence 입력으로 변환 가능한 결과 계약
# ---------------------------------------------------------------------------
def test_event_master_output_is_convertible_to_task3_event_write():
    event = EventMaster().generate(
        tick=1,
        agent_summaries=[
            AgentSummary(
                agent_id="s1", name="아델", role="student", major_id=None, year=1,
                active_status=True, current_location_id="c1", mood=0, stress=0, fatigue=0,
            )
        ],
        scheduled_events=[
            ScheduledEventInput(
                event_id="evt-1", event_type="CLASS", location_id="c1",
                participant_agent_ids=("s1",), title="수업",
            )
        ],
    )[0]

    # Task 5가 실제 저장 시 수행할 변환과 동일한 필드 매핑이 예외 없이 성립해야 한다.
    write = EventWrite(
        id=uuid4(),
        event_type=event.event_type,
        event_subtype=event.event_subtype,
        title=event.title,
        description=event.description or "-",
        participant_agent_ids=(uuid4(),),
        location_id=uuid4(),
        source=event.source,
        impact_level=event.impact_level.value,
        importance=event.importance,
        expected_effects=event.expected_effects,
    )
    assert write.event_type == "CLASS"

    delta = StateDelta(
        source_agent_id=uuid4(), metric="stress", before=10, requested_total=1,
        applied_delta=1, after=11, effect_ids=("k1",),
    )
    batch = EventBatch(
        simulation_id=uuid4(), run_id="run-1", tick_number=1,
        policy_version="policy-mvp-0.1", resolver_version="resolver-mvp-0.1",
        resolution_id="run-1:1", events=(write,), resolved_effects=(delta,),
    )
    assert batch.events[0].event_type == "CLASS"


# ---------------------------------------------------------------------------
# 22. STUDENT_MISSING 상태가 Task1과 Task3에서 이중 적용되지 않음
# ---------------------------------------------------------------------------
def test_student_missing_produces_no_active_status_effect_candidate():
    snapshots = [
        MagicAgentSnapshot(
            agent_id="m1", agent_type="student", active_status=True,
            current_location_id="dormitory", fatigue=10, is_cursed=False,
            recent_stress=tuple([95] * 10),
        ),
        MagicAgentSnapshot(
            agent_id="neighbor1", agent_type="student", active_status=True,
            current_location_id="dormitory", fatigue=10, is_cursed=False,
        ),
    ]
    magic_result = MagicLayer().evaluate(tick=11, regular_events=[], agent_snapshots=snapshots)
    special = magic_result.special_events[0]
    assert special.event_subtype == STUDENT_MISSING
    assert special.missing_agent_ids == ("m1",)

    candidates = build_magic_effect_candidates(
        magic_result.special_events,
        run_id="run-1",
        agent_snapshots={"m1": _snapshot("m1"), "neighbor1": _snapshot("neighbor1")},
    )
    # EffectCandidate는 AGENT_STATE(hunger/fatigue/stress/satisfaction/mood)와
    # RELATIONSHIP만 표현할 수 있다 — active_status 전이는 여기서 만들어질 수
    # 없고, missing_agent_ids로만 Task 3(#103)에 전달된다.
    assert all(c.source_agent_id != "m1" for c in candidates)
    assert {c.source_agent_id for c in candidates} == {"neighbor1"}


# ---------------------------------------------------------------------------
# Task 3 handoff: Magic Layer STUDENT_MISSING candidate -> 실제
# persist_event_batch() 호출 -> INACTIVE_TEMPORARY -> ACTIVE+CURSED -> 해제.
# Task1은 이 전이를 직접 mutation하지 않고, Task3(#103)의 실제 서비스가
# Task1의 산출물(missing_agent_ids)을 그대로 받아 처리함을 증명한다.
# ---------------------------------------------------------------------------
@pytest.fixture
def db():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required")
    engine = create_engine(url)
    with engine.connect() as connection:
        outer = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            yield session
        outer.rollback()
    engine.dispose()


def _setup_simulation(db):
    user = User(id=uuid4(), username=str(uuid4()), display_name="test", password_hash="test", roles=["USER"])
    db.add(user)
    db.flush()
    simulation = Simulation(id=uuid4(), owner_id=user.id, name="Task1-Task3 handoff")
    db.add(simulation)
    db.flush()
    seed_slice_zero(db, simulation.id)
    db.commit()
    return simulation.id


def test_student_missing_candidate_drives_real_task3_transition_cycle(db):
    """Tick N: Task1 STUDENT_MISSING 후보 -> Task3 실제 서비스로 전체 사이클 검증."""
    simulation_id = _setup_simulation(db)
    agents = list(
        db.scalars(select(Agent).where(Agent.simulation_id == simulation_id).order_by(Agent.fixture_key))
    )
    target = next(a for a in agents if a.fixture_key == "student-02")
    others = [a for a in agents if a.id != target.id]
    states_by_agent = {
        state.agent_id: state
        for state in db.scalars(select(AgentState).where(AgentState.simulation_id == simulation_id))
    }
    location_id = states_by_agent[target.id].location_id

    # Task1: Magic Layer가 실제로 STUDENT_MISSING 후보를 판정한다 (10/10 스트릭).
    magic_snapshots = [
        MagicAgentSnapshot(
            agent_id=str(target.id), agent_type="student", active_status=True,
            current_location_id=str(location_id), fatigue=10, is_cursed=False,
            recent_stress=tuple([95] * 10),
        )
    ]
    magic_result = MagicLayer().evaluate(tick=1, regular_events=[], agent_snapshots=magic_snapshots)
    special = magic_result.special_events[0]
    assert special.event_subtype == STUDENT_MISSING
    assert special.missing_agent_ids == (str(target.id),)

    # Task1 -> Task3 계약 변환: Magic 후보를 EventWrite/EventBatch로 감싸기만 한다
    # (Task1은 여기서 active_status/inactive_until_tick을 직접 건드리지 않는다).
    missing_write = EventWrite(
        id=uuid4(), event_type=special.event_subtype, title="학생 실종",
        description="Magic Layer STUDENT_MISSING 후보", participant_agent_ids=(target.id,),
        location_id=location_id, source="magic_layer", impact_level="high", importance=80,
    )
    tick_1 = EventBatch(
        simulation_id=simulation_id, run_id="run-1", tick_number=1,
        policy_version="policy-mvp-0.1", resolver_version="resolver-mvp-0.1",
        resolution_id="run-1:1", events=(missing_write,),
        missing_agent_ids=tuple(UUID(agent_id) for agent_id in special.missing_agent_ids),
    )

    # Task1 코드는 여기까지만 관여한다 — 이후는 전부 Task3의 실제 서비스 호출.
    persist_event_batch(db, tick_1)
    db.flush()
    assert (target.active_status, target.inactive_until_tick) == ("inactive_temporary", 4)

    for tick in range(2, 8):
        db.get(Simulation, simulation_id).current_tick = tick - 1
        db.flush()
        empty = EventBatch(
            simulation_id=simulation_id, run_id="run-1", tick_number=tick,
            policy_version="policy-mvp-0.1", resolver_version="resolver-mvp-0.1",
            resolution_id=f"run-1:{tick}",
        )
        persist_event_batch(db, empty)
        if tick == 3:
            assert target.active_status == "inactive_temporary"
        if tick == 4:
            assert target.active_status == "active"
            assert target.cursed_until_tick == 7
        if tick == 7:
            assert target.cursed_until_tick is None

    # Task1은 다른 Agent의 state를 이중 mutation하지 않았다 (Task1은 DB에
    # 아무것도 쓰지 않으므로, 전이 결과는 오직 Task3 persist_event_batch에서만 나온다).
    for agent in others:
        assert agent.cursed_until_tick is None
        assert agent.inactive_until_tick is None


# ---------------------------------------------------------------------------
# production STUDENT_MISSING 발생 가능성: 새 history 저장소 없이 기존
# RuntimeResult 기록에서 최근 10 Tick stress를 역산 가능함을 확인한다.
# ---------------------------------------------------------------------------
def _make_runtime_result_row(*, agent_id, tick_number, run_id, stress_signal=None):
    from app.domain.models import RuntimeResult

    state_signals = []
    if stress_signal is not None:
        signal_type, intensity = stress_signal
        state_signals.append({"signal_type": signal_type, "intensity": intensity})
    intent = {
        "action_type": "WAIT",
        "target_agent_id": None,
        "target_location_id": None,
        "related_event_id": None,
        "utterance": None,
        "motivation_summary": "test",
        "reaction": {"valence": "NEUTRAL", "relationship_signals": [], "state_signals": state_signals},
        "decision_explanation": {"alternatives": [], "influencing_factors": []},
        "memory_candidates": [],
    }
    return RuntimeResult(
        id=uuid4(), run_id=run_id, tick_number=tick_number, agent_id=agent_id,
        status="PROPOSED", action_type="WAIT", intent=intent, retry_count=0,
        failure_reason=None, model="test-model", prompt_version="test-prompt",
        idempotency_key=f"{run_id}:{tick_number}:{agent_id}",
        result_fingerprint=f"fp-{run_id}-{tick_number}-{agent_id}",
    )


def test_reconstruct_recent_stress_from_existing_runtime_results(db):
    """새 history 모델/migration 없이 기존 RuntimeResult로 10 Tick stress를 역산한다."""
    from app.services.manual_tick import _reconstruct_recent_stress

    simulation_id = _setup_simulation(db)
    agent = next(
        db.scalars(
            select(Agent).where(Agent.simulation_id == simulation_id, Agent.fixture_key == "student-01")
        )
    )
    state = db.scalar(select(AgentState).where(AgentState.agent_id == agent.id))
    state.stress = 90  # tick 10(현재 직전 tick)까지의 최종 stress.
    db.flush()

    # tick 2~10 각각에 STRESS_UP/HIGH(+8) Reaction을 기록해, tick 10(=current)의
    # 90에서 9번 역산하면 tick 1의 18까지 총 10개 연속 tick 값이 나오게 구성한다.
    for tick in range(2, 11):
        db.add(
            _make_runtime_result_row(
                agent_id=agent.id, tick_number=tick, run_id="run-hist",
                stress_signal=("STRESS_UP", "HIGH"),
            )
        )
    db.flush()

    history = _reconstruct_recent_stress(
        db,
        agent_ids=[agent.id],
        current_tick=11,
        current_stress_by_agent={agent.id: state.stress},
    )
    assert history[agent.id] == (18, 26, 34, 42, 50, 58, 66, 74, 82, 90)
    assert len(history[agent.id]) == 10


def test_reconstruct_recent_stress_stops_at_gap_and_stays_conservative(db):
    """RuntimeResult 연속성이 끊기면 그 이전은 추정하지 않고 짧은 결과를 반환한다."""
    from app.services.manual_tick import _reconstruct_recent_stress

    simulation_id = _setup_simulation(db)
    agent = next(
        db.scalars(
            select(Agent).where(Agent.simulation_id == simulation_id, Agent.fixture_key == "student-01")
        )
    )
    state = db.scalar(select(AgentState).where(AgentState.agent_id == agent.id))
    state.stress = 95
    db.flush()
    # tick 9,8,7은 연속으로 존재하지만 tick 6은 비어 있어 그 지점에서 끊긴 상황.
    for tick in (9, 8, 7):
        db.add(
            _make_runtime_result_row(
                agent_id=agent.id, tick_number=tick, run_id="run-hist",
                stress_signal=("STRESS_UP", "MEDIUM"),
            )
        )
    db.flush()

    history = _reconstruct_recent_stress(
        db,
        agent_ids=[agent.id],
        current_tick=10,
        current_stress_by_agent={agent.id: state.stress},
    )
    # tick 7~10(4개)까지만 역산되고, tick 6 기록이 없어 그 이전은 추정하지 않고 멈춘다.
    assert history[agent.id] == (80, 85, 90, 95)
    assert len(history[agent.id]) < STUDENT_MISSING_STREAK_TICKS


def test_production_wiring_actually_fires_student_missing(db):
    """`_run_event_and_magic_phase`(실제 manual_tick.py wiring)가 충분한
    RuntimeResult 이력이 있으면 STUDENT_MISSING을 실제로 발생시킴을 증명한다."""
    from app.services.manual_tick import _run_event_and_magic_phase

    simulation_id = _setup_simulation(db)
    agents = list(
        db.scalars(select(Agent).where(Agent.simulation_id == simulation_id).order_by(Agent.fixture_key))
    )
    target = next(a for a in agents if a.fixture_key == "student-01")
    state = db.scalar(select(AgentState).where(AgentState.agent_id == target.id))
    state.stress = 95
    db.flush()
    for tick in range(2, 11):
        db.add(
            _make_runtime_result_row(
                agent_id=target.id, tick_number=tick, run_id="run-hist",
                stress_signal=None,  # 신호 없음 -> delta 0, stress가 95로 유지됨
            )
        )
    db.flush()

    result = _run_event_and_magic_phase(
        db, simulation_id=simulation_id, run_id=uuid4(), tick=11, agents=agents,
    )
    assert [e.event_subtype for e in result.special_events] == [STUDENT_MISSING]


# ---------------------------------------------------------------------------
# DB에 저장된 CLASS scheduled Event가 실제 advance_manual_tick() 경로를 통해
# Event Master -> Magic Layer -> Policy까지 연결되는지 검증한다 (synthetic
# run_event_and_magic_phase() 직접 호출이 아니라 real production adapter 사용).
# ---------------------------------------------------------------------------
def test_advance_manual_tick_wires_db_class_event_into_event_master(db):
    import asyncio

    from app.domain.models import Event as DomainEvent, EventParticipant
    from app.services.manual_tick import advance_manual_tick
    from app.simulation.agent_runtime import AgentRuntime, MockLLMClient

    simulation_id = _setup_simulation(db)
    simulation = db.get(Simulation, simulation_id)

    class_event = db.scalar(
        select(DomainEvent).where(
            DomainEvent.simulation_id == simulation_id, DomainEvent.event_type == "class"
        )
    )
    db_participant_ids = {
        p.agent_id
        for p in db.scalars(
            select(EventParticipant).where(EventParticipant.event_id == class_event.id)
        )
    }
    assert db_participant_ids  # fixture 전제: student-01 + professor-01

    runtime = AgentRuntime(MockLLMClient(), model="test-event-master-wiring")
    result = asyncio.run(advance_manual_tick(db, simulation, runtime=runtime))

    event_and_magic = result.event_and_magic_result
    class_events = [e for e in event_and_magic.events if e.event_type == "CLASS"]
    assert len(class_events) == 1
    wired_event = class_events[0]

    # DB의 실제 EventParticipant와 정확히 일치해야 한다 (inactive 제외 규칙 유지 —
    # 이 fixture는 전원 active이므로 그대로 전원 포함되어야 한다).
    assert {UUID(agent_id) for agent_id in wired_event.participant_agent_ids} == db_participant_ids

    # CLASS 기본 효과(stress +1)가 참여자 전원에 대해 resolved_effects까지 연결된다.
    stress_effects = {
        UUID(effect.source_agent_id): effect
        for effect in event_and_magic.resolved_effects
        if effect.metric == "stress"
    }
    assert set(stress_effects) == db_participant_ids
    assert all(effect.delta == 1 for effect in stress_effects.values())

    # Magic Layer로도 정상 전달된다 (converted_events에 동일 CLASS Event가 포함).
    assert any(e.event_type == "CLASS" for e in event_and_magic.events)

    # Task 5 production commit 경계가 Task 3 저장 계약까지 실제로 연결된다.
    saved = result.event_batch_result
    assert saved["simulation_id"] == str(simulation_id)
    assert saved["tick_number"] == 1
    assert any(event["event_type"] == "CLASS" for event in saved["events"])
    assert db.get(Simulation, simulation_id).current_tick == 1


def test_advance_manual_tick_rolls_back_all_tick_writes_after_event_batch_failure(
    db, monkeypatch
):
    """A fatal failure after Task 3 flush leaves the complete Tick unchanged."""
    import asyncio

    from sqlalchemy import func

    from app.domain.models import (
        Event as DomainEvent,
        EventBatchResult,
        Relationship,
        RuntimeResult,
    )
    from app.services import manual_tick
    from app.simulation.agent_runtime import AgentRuntime, MockLLMClient

    simulation_id = _setup_simulation(db)
    simulation = db.get(Simulation, simulation_id)
    participants = list(
        db.scalars(
            select(Agent)
            .where(
                Agent.simulation_id == simulation_id,
                Agent.fixture_key.in_(("student-01", "professor-01")),
            )
            .order_by(Agent.fixture_key)
        )
    )
    relationship = Relationship(
        id=uuid4(),
        simulation_id=simulation_id,
        source_agent_id=participants[0].id,
        target_agent_id=participants[1].id,
        trust=7,
    )
    db.add(relationship)
    db.commit()

    state_before = {
        state.agent_id: (state.hunger, state.fatigue, state.stress, state.satisfaction, state.mood)
        for state in db.scalars(
            select(AgentState).where(AgentState.simulation_id == simulation_id)
        )
    }
    event_count_before = db.scalar(
        select(func.count()).select_from(DomainEvent).where(
            DomainEvent.simulation_id == simulation_id
        )
    )
    original_persist = manual_tick.persist_event_batch

    def fail_after_event_batch_flush(session, batch):
        original_persist(session, batch)
        relationship.trust = 10
        session.flush()
        raise RuntimeError("injected downstream failure")

    monkeypatch.setattr(manual_tick, "persist_event_batch", fail_after_event_batch_flush)
    with pytest.raises(RuntimeError, match="injected downstream"):
        asyncio.run(
            manual_tick.advance_manual_tick(
                db,
                simulation,
                runtime=AgentRuntime(MockLLMClient(), model="rollback-test"),
            )
        )
    db.rollback()

    assert db.get(Simulation, simulation_id).current_tick == 0
    assert db.get(Relationship, relationship.id).trust == 7
    assert db.scalar(
        select(func.count()).select_from(DomainEvent).where(
            DomainEvent.simulation_id == simulation_id
        )
    ) == event_count_before
    assert db.scalar(
        select(func.count()).select_from(EventBatchResult).where(
            EventBatchResult.simulation_id == simulation_id
        )
    ) == 0
    assert db.scalar(
        select(func.count()).select_from(RuntimeResult).join(
            Agent, Agent.id == RuntimeResult.agent_id
        ).where(Agent.simulation_id == simulation_id)
    ) == 0
    assert {
        state.agent_id: (state.hunger, state.fatigue, state.stress, state.satisfaction, state.mood)
        for state in db.scalars(
            select(AgentState).where(AgentState.simulation_id == simulation_id)
        )
    } == state_before
