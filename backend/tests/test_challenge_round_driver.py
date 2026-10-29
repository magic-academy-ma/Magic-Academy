"""도전과제 모드 — 강제 Event 1개를 실제 DB/Agent Runtime으로 실행.

docs/04-feature-specs/challenge-mode-team-revival.md §5/§6. 이 파일의 모든
테스트는 TEST_DATABASE_URL이 필요하다 (다른 DB 연동 테스트와 동일한 skip 패턴,
test_event_magic_policy_integration.py 참고).
"""

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.domain.models import (
    Agent,
    AgentState,
    Event as DomainEvent,
    EventParticipant,
    Simulation,
    User,
)
from app.services.fixtures import seed_slice_zero
from app.simulation.agent_runtime import AgentRuntime, Block, MockLLMClient
from app.simulation.challenge import round_driver
from app.simulation.challenge.controller import build_round1_trigger_event
from app.simulation.challenge.festival_booth import BoothConcept, build_opening_event
from app.simulation.challenge.round_driver import run_forced_event_round


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


def _setup_simulation(db: Session):
    user = User(id=uuid4(), username=str(uuid4()), display_name="test", password_hash="test", roles=["USER"])
    db.add(user)
    db.flush()
    simulation = Simulation(id=uuid4(), owner_id=user.id, name="challenge round driver test")
    db.add(simulation)
    db.flush()
    seed_slice_zero(db, simulation.id)
    db.commit()
    return simulation.id


def test_run_forced_event_round_persists_event_and_applies_effects(db):
    simulation_id = _setup_simulation(db)
    agents_by_key = {
        agent.fixture_key: agent
        for agent in db.scalars(select(Agent).where(Agent.simulation_id == simulation_id))
    }
    agent_a = agents_by_key["student-01"]
    agent_b = agents_by_key["student-02"]

    state_a_before = db.scalar(select(AgentState).where(AgentState.agent_id == agent_a.id))
    state_b_before = db.scalar(select(AgentState).where(AgentState.agent_id == agent_b.id))
    fatigue_before = {agent_a.id: state_a_before.fatigue, agent_b.id: state_b_before.fatigue}
    stress_before = {agent_a.id: state_a_before.stress, agent_b.id: state_b_before.stress}
    location_id = str(state_a_before.location_id)

    event = build_round1_trigger_event(
        tick=1, agent_a_id=str(agent_a.id), agent_b_id=str(agent_b.id), location_id=location_id
    )

    result = run_forced_event_round(
        db,
        simulation_id=simulation_id,
        run_id=uuid4(),
        tick_number=1,
        simulation_day=1,
        block=Block.MORNING,
        event=event,
        runtime=AgentRuntime(MockLLMClient(), model="test-round-driver"),
    )

    assert {r.agent_id for r in result.runtime_results} == {agent_a.id, agent_b.id}

    db_event = db.scalar(
        select(DomainEvent).where(
            DomainEvent.simulation_id == simulation_id,
            DomainEvent.event_type == "group_project",
        )
    )
    assert db_event is not None
    assert db_event.title == "전술 연습 (의견 충돌)"
    participant_ids = {
        p.agent_id
        for p in db.scalars(select(EventParticipant).where(EventParticipant.event_id == db_event.id))
    }
    assert participant_ids == {agent_a.id, agent_b.id}

    for agent_id in (agent_a.id, agent_b.id):
        state = db.scalar(select(AgentState).where(AgentState.agent_id == agent_id))
        # GROUP_PROJECT 기본 효과(stress +3, event_policy.py) — MockLLMClient의
        # Reaction(FATIGUE_DOWN/LOW)과는 다른 경로이므로 합산되어 반영된다.
        assert state.stress == min(100, stress_before[agent_id] + 3)
        # MockLLMClient는 CLASS Event가 없으면 REST + FATIGUE_DOWN/LOW(-2)를 반환한다.
        assert state.fatigue == max(0, fatigue_before[agent_id] - 2)


def test_non_mandatory_agents_run_in_separate_batch_with_relaxed_schedule(monkeypatch):
    """CHAPTER 4 SUGGEST_REST: 지정 Agent만 is_mandatory=False 일정으로 실행되고,
    두 배치의 결과가 합쳐져 정책 적용에 한 번에 들어간다(DB 없이 경로만 검증)."""

    agent_ids = [uuid4() for _ in range(3)]
    location_id = uuid4()
    event = build_opening_event(
        concept=BoothConcept.FOOD,
        agent_ids=[str(agent_id) for agent_id in agent_ids],
        location_id=str(location_id),
    )
    db_event = SimpleNamespace(id=uuid4(), location_id=location_id)
    monkeypatch.setattr(
        round_driver, "_persist_forced_event", lambda db, **kwargs: (db_event, [])
    )
    monkeypatch.setattr(round_driver, "_apply_event_base_effects", lambda db, **kwargs: None)
    applied = {}
    monkeypatch.setattr(
        round_driver,
        "evaluate_and_apply_policy",
        lambda db, **kwargs: applied.update(results=kwargs["runtime_results"]),
    )
    calls = []

    def fake_run_runtime_phase(self, db, **kwargs):
        calls.append((tuple(kwargs["preselected_agent_ids"]), kwargs["schedule"].is_mandatory))
        return SimpleNamespace(results=tuple(kwargs["preselected_agent_ids"]))

    monkeypatch.setattr(round_driver.SimulationTickService, "run_runtime_phase", fake_run_runtime_phase)

    rested = sorted(agent_ids)[1]
    result = round_driver.run_forced_event_round(
        None,
        simulation_id=uuid4(),
        run_id=uuid4(),
        tick_number=9,
        simulation_day=3,
        block=Block.EVENING,
        event=event,
        runtime=AgentRuntime(MockLLMClient(), model="test-round-driver"),
        non_mandatory_agent_ids={rested},
    )

    mandatory = tuple(a for a in sorted(agent_ids) if a != rested)
    assert calls == [(mandatory, True), ((rested,), False)]
    assert set(result.runtime_results) == set(agent_ids)
    assert applied["results"] == result.runtime_results
