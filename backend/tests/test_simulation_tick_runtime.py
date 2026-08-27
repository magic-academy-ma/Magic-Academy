import os
from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.domain.models import Agent, AgentState, Event, EventParticipant, Location, Simulation, User
from app.services.fixtures import seed_slice_zero
from app.services.runtime_input_adapter import RuntimeInputAdapter
from app.services.runtime_orchestrator import RuntimeOrchestrator
from app.services.runtime_results import InMemoryRuntimeResultSink
from app.services.simulation_tick import RuntimeSnapshotError, SimulationTickService
from app.simulation.agent_runtime import AgentRuntime, MockLLMClient, RuntimeStatus, ScheduleSummary


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")
CLASS_EVENT_ID = UUID("20000000-0000-0000-0000-000000000001")
RUN_ID = UUID("30000000-0000-0000-0000-000000000001")


@pytest.fixture()
def runtime_db():
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE users, simulations, locations, agents, agent_states "
                "RESTART IDENTITY CASCADE"
            )
        )
    with session_factory() as db:
        user = User(
            id=uuid4(),
            username="tick-owner",
            display_name="Tick Owner",
            password_hash="hash",
            roles=["USER"],
        )
        db.add(user)
        db.flush()
        simulation = Simulation(id=uuid4(), owner_id=user.id, name="Runtime Tick")
        other_simulation = Simulation(id=uuid4(), owner_id=user.id, name="Other")
        db.add_all([simulation, other_simulation])
        db.flush()
        seed_slice_zero(db, simulation.id)
        seed_slice_zero(db, other_simulation.id)
        # seed_slice_zero already creates the 6 MVP locations (fixtures.LOCATIONS);
        # reuse the seeded "library" as the extra active location instead of
        # inserting a duplicate that violates uq_locations_simulation_code.
        extra_location = db.scalar(
            select(Location).where(
                Location.simulation_id == simulation.id,
                Location.code == "library",
            )
        )
        inactive_location = Location(
            id=uuid4(),
            simulation_id=simulation.id,
            code="closed_tower",
            name="폐쇄된 탑",
            is_active=False,
        )
        db.add(inactive_location)
        db.commit()
        yield db, simulation, other_simulation, extra_location, inactive_location


def make_schedule(location_id: UUID) -> ScheduleSummary:
    return ScheduleSummary(
        event_id=CLASS_EVENT_ID,
        schedule_type="class",
        is_mandatory=True,
        location_id=location_id,
        start_tick=3,
        end_tick=3,
    )


def make_event(simulation_id: UUID, location_id: UUID) -> Event:
    return Event(
        id=CLASS_EVENT_ID,
        simulation_id=simulation_id,
        location_id=location_id,
        event_type="class",
        title="통합마법학",
        description="수업",
        status="scheduled",
        simulation_day=1,
        event_metadata={},
    )


class SpyAdapter:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.result = object()

    def run(self, **values):
        self.calls.append(values)
        return self.result


def run_phase(service, db, simulation, event, participants, schedule, **overrides):
    slice_one_student_id = db.scalar(
        select(Agent.id).where(
            Agent.simulation_id == simulation.id,
            Agent.fixture_key == "student-01",
        )
    )
    values = {
        "simulation_id": simulation.id,
        "run_id": RUN_ID,
        "tick_number": 3,
        "block": "MORNING",
        "preselected_agent_ids": [slice_one_student_id],
        "schedule": schedule,
        "events": [event],
        "event_participants": {event.id: participants},
    }
    values.update(overrides)
    return service.run_runtime_phase(db, **values)


def test_snapshot_queries_all_living_agents_and_active_locations(runtime_db) -> None:
    db, simulation, other_simulation, extra_location, inactive_location = runtime_db
    agents = db.scalars(
        select(Agent).where(Agent.simulation_id == simulation.id).order_by(Agent.fixture_key)
    ).all()
    agents[1].active_status = "inactive_temporary"
    agents[2].agent_type = "user_persona"
    agents[-1].deleted_at = datetime.now(UTC)
    location_id = db.scalar(
        select(Location.id).where(
            Location.simulation_id == simulation.id,
            Location.code == "classroom",
        )
    )
    db.commit()
    event = make_event(simulation.id, location_id)
    adapter = SpyAdapter()

    result = run_phase(
        SimulationTickService(adapter),
        db,
        simulation,
        event,
        [],
        make_schedule(location_id),
    )

    assert result is adapter.result
    call = adapter.calls[0]
    assert [agent.fixture_key for agent in call["agents"]] == [
        "professor-01",
        "student-01",
        "student-02",
        "student-03",
        "student-04",
    ]
    assert call["agents"][1].active_status == "inactive_temporary"
    assert call["agents"][2].agent_type == "user_persona"
    assert all(agent.simulation_id == simulation.id for agent in call["agents"])
    assert call["valid_agent_ids"] == [agent.id for agent in call["agents"]]
    assert extra_location.id in call["valid_location_ids"]
    assert inactive_location.id not in call["valid_location_ids"]
    assert call["valid_location_ids"] == sorted(call["valid_location_ids"], key=str)
    assert len(call["valid_location_ids"]) > 1
    assert other_simulation.id != simulation.id


def test_runtime_phase_preserves_caller_inputs_and_does_not_mutate_orm(runtime_db) -> None:
    db, simulation, _, _, _ = runtime_db
    agent = db.scalar(
        select(Agent).where(
            Agent.simulation_id == simulation.id,
            Agent.fixture_key == "student-01",
        )
    )
    state = db.scalar(select(AgentState).where(AgentState.agent_id == agent.id))
    location_id = db.scalar(
        select(Location.id).where(
            Location.simulation_id == simulation.id,
            Location.code == "classroom",
        )
    )
    event = make_event(simulation.id, location_id)
    participant = EventParticipant(
        id=uuid4(),
        event_id=event.id,
        agent_id=db.scalar(
            select(Agent.id).where(
                Agent.simulation_id == simulation.id,
                Agent.fixture_key == "student-01",
            )
        ),
        result={},
    )
    events = [event]
    participants = {event.id: [participant]}
    schedule = make_schedule(location_id)
    before = (
        simulation.current_tick,
        simulation.current_day,
        agent.active_status,
        agent.inactive_until_tick,
        state.location_id,
        state.hunger,
        deepcopy(events),
        deepcopy(participants),
    )
    adapter = SpyAdapter()

    run_phase(
        SimulationTickService(adapter),
        db,
        simulation,
        event,
        [participant],
        schedule,
        events=events,
        event_participants=participants,
    )

    call = adapter.calls[0]
    assert call["run_id"] == str(RUN_ID)
    assert call["tick_number"] == 3
    assert call["block"] == "MORNING"
    assert call["schedule"] is schedule
    assert call["preselected_agent_ids"] == [agent.id]
    assert call["events"] is events
    assert call["event_participants"] is participants
    assert (
        simulation.current_tick,
        simulation.current_day,
        agent.active_status,
        agent.inactive_until_tick,
        state.location_id,
        state.hunger,
    ) == before[:6]
    assert events[0].id == before[6][0].id
    assert participants[event.id][0].agent_id == before[7][event.id][0].agent_id


def test_missing_state_stops_before_adapter(runtime_db) -> None:
    db, simulation, _, _, _ = runtime_db
    agent_id = db.scalar(
        select(Agent.id).where(
            Agent.simulation_id == simulation.id,
            Agent.fixture_key == "student-01",
        )
    )
    state = db.scalar(select(AgentState).where(AgentState.agent_id == agent_id))
    db.delete(state)
    db.flush()
    adapter = SpyAdapter()

    with pytest.raises(RuntimeSnapshotError, match="missing AgentState"):
        SimulationTickService(adapter).run_runtime_phase(
            db,
            simulation_id=simulation.id,
            run_id=RUN_ID,
            tick_number=3,
            block="MORNING",
            preselected_agent_ids=[],
            schedule=make_schedule(uuid4()),
            events=[],
            event_participants={},
        )

    assert adapter.calls == []


def test_null_state_location_stops_before_adapter(runtime_db) -> None:
    db, simulation, _, _, _ = runtime_db
    state = db.scalar(
        select(AgentState)
        .join(Agent, Agent.id == AgentState.agent_id)
        .where(Agent.simulation_id == simulation.id)
    )
    state.location_id = None
    db.flush()
    adapter = SpyAdapter()

    with pytest.raises(RuntimeSnapshotError, match="location_id"):
        SimulationTickService(adapter).run_runtime_phase(
            db,
            simulation_id=simulation.id,
            run_id=RUN_ID,
            tick_number=3,
            block="MORNING",
            preselected_agent_ids=[],
            schedule=make_schedule(uuid4()),
            events=[],
            event_participants={},
        )

    assert adapter.calls == []


@pytest.mark.parametrize("failure", ["duplicate_state", "mismatched_state", "duplicate_agent"])
def test_invalid_snapshot_rows_stop_before_adapter(runtime_db, monkeypatch, failure) -> None:
    db, simulation, _, _, _ = runtime_db
    from app.services import simulation_tick

    agents = simulation_tick.list_runtime_agents(db, simulation.id)
    states = simulation_tick.list_runtime_agent_states(db, [agent.id for agent in agents])
    if failure == "duplicate_state":
        monkeypatch.setattr(
            simulation_tick,
            "list_runtime_agent_states",
            lambda *_: [*states, states[0]],
        )
    elif failure == "mismatched_state":
        mismatched = deepcopy(states[0])
        mismatched.agent_id = uuid4()
        monkeypatch.setattr(
            simulation_tick,
            "list_runtime_agent_states",
            lambda *_: [mismatched, *states[1:]],
        )
    else:
        monkeypatch.setattr(simulation_tick, "list_runtime_agents", lambda *_: [*agents, agents[0]])
    adapter = SpyAdapter()

    with pytest.raises(RuntimeSnapshotError):
        SimulationTickService(adapter).run_runtime_phase(
            db,
            simulation_id=simulation.id,
            run_id=RUN_ID,
            tick_number=3,
            block="MORNING",
            preselected_agent_ids=[],
            schedule=make_schedule(uuid4()),
            events=[],
            event_participants={},
        )

    assert adapter.calls == []


def test_event_from_other_simulation_stops_before_adapter(runtime_db) -> None:
    db, simulation, other_simulation, _, _ = runtime_db
    other_location_id = db.scalar(
        select(Location.id).where(
            Location.simulation_id == other_simulation.id,
            Location.code == "classroom",
        )
    )
    event = make_event(other_simulation.id, other_location_id)
    adapter = SpyAdapter()

    with pytest.raises(RuntimeSnapshotError, match="does not belong"):
        run_phase(
            SimulationTickService(adapter),
            db,
            simulation,
            event,
            [],
            make_schedule(other_location_id),
        )

    assert adapter.calls == []


def test_participant_from_other_simulation_stops_before_adapter(runtime_db) -> None:
    db, simulation, other_simulation, _, _ = runtime_db
    location_id = db.scalar(
        select(Location.id).where(
            Location.simulation_id == simulation.id,
            Location.code == "classroom",
        )
    )
    other_agent_id = db.scalar(
        select(Agent.id).where(
            Agent.simulation_id == other_simulation.id,
            Agent.fixture_key == "student-01",
        )
    )
    event = make_event(simulation.id, location_id)
    participant = EventParticipant(
        id=uuid4(), event_id=event.id, agent_id=other_agent_id, result={}
    )
    adapter = SpyAdapter()

    with pytest.raises(RuntimeSnapshotError, match="is not valid"):
        run_phase(
            SimulationTickService(adapter),
            db,
            simulation,
            event,
            [participant],
            make_schedule(location_id),
        )

    assert adapter.calls == []


def test_participant_event_mismatch_stops_before_adapter(runtime_db) -> None:
    db, simulation, _, _, _ = runtime_db
    location_id = db.scalar(
        select(Location.id).where(
            Location.simulation_id == simulation.id,
            Location.code == "classroom",
        )
    )
    event = make_event(simulation.id, location_id)
    participant = EventParticipant(
        id=uuid4(), event_id=uuid4(), agent_id=uuid4(), result={}
    )
    adapter = SpyAdapter()

    with pytest.raises(RuntimeSnapshotError, match="event_id does not match"):
        run_phase(
            SimulationTickService(adapter),
            db,
            simulation,
            event,
            [participant],
            make_schedule(location_id),
        )

    assert adapter.calls == []


def test_unknown_participant_mapping_key_stops_before_adapter(runtime_db) -> None:
    db, simulation, _, _, _ = runtime_db
    location_id = db.scalar(
        select(Location.id).where(
            Location.simulation_id == simulation.id,
            Location.code == "classroom",
        )
    )
    event = make_event(simulation.id, location_id)
    adapter = SpyAdapter()

    with pytest.raises(RuntimeSnapshotError, match="unknown Event"):
        run_phase(
            SimulationTickService(adapter),
            db,
            simulation,
            event,
            [],
            make_schedule(location_id),
            event_participants={uuid4(): []},
        )

    assert adapter.calls == []


def test_duplicate_event_id_stops_before_adapter(runtime_db) -> None:
    db, simulation, _, _, _ = runtime_db
    location_id = db.scalar(
        select(Location.id).where(
            Location.simulation_id == simulation.id,
            Location.code == "classroom",
        )
    )
    event = make_event(simulation.id, location_id)
    adapter = SpyAdapter()

    with pytest.raises(RuntimeSnapshotError, match="duplicate Event.id"):
        run_phase(
            SimulationTickService(adapter),
            db,
            simulation,
            event,
            [],
            make_schedule(location_id),
            events=[event, deepcopy(event)],
        )

    assert adapter.calls == []


@pytest.mark.parametrize("location_kind", ["other_simulation", "inactive", "missing"])
def test_invalid_event_location_stops_before_adapter(runtime_db, location_kind) -> None:
    db, simulation, other_simulation, _, inactive_location = runtime_db
    if location_kind == "other_simulation":
        location_id = db.scalar(
            select(Location.id).where(
                Location.simulation_id == other_simulation.id,
                Location.code == "classroom",
            )
        )
    elif location_kind == "inactive":
        location_id = inactive_location.id
    else:
        location_id = None
    event = make_event(simulation.id, location_id)
    adapter = SpyAdapter()

    with pytest.raises(RuntimeSnapshotError, match="invalid runtime Location"):
        run_phase(
            SimulationTickService(adapter),
            db,
            simulation,
            event,
            [],
            make_schedule(location_id or uuid4()),
        )

    assert adapter.calls == []


class CountingSink(InMemoryRuntimeResultSink):
    def __init__(self) -> None:
        super().__init__()
        self.call_count = 0

    def save_batch(self, results):
        self.call_count += 1
        return super().save_batch(results)


class RecordingMockLLMClient(MockLLMClient):
    def __init__(self, response: dict) -> None:
        super().__init__(response)
        self.agent_ids: list[UUID] = []

    def generate(self, runtime_input):
        self.agent_ids.append(runtime_input.agent.agent_id)
        return super().generate(runtime_input)


def valid_intent_response(event_id: UUID, location_id: UUID) -> dict:
    return {
        "action_type": "ATTEND_CLASS",
        "target_agent_id": None,
        "target_location_id": str(location_id),
        "related_event_id": str(event_id),
        "utterance": None,
        "motivation_summary": "예정된 수업에 참석한다.",
        "reaction": {
            "valence": "NEUTRAL",
            "relationship_signals": [],
            "state_signals": [],
        },
        "decision_explanation": {
            "alternatives": [
                {
                    "action_type": "ATTEND_CLASS",
                    "description": "수업에 참석한다.",
                    "relative_priority": "HIGH",
                    "selected": True,
                }
            ],
            "influencing_factors": [],
        },
        "memory_candidates": [],
    }


def test_runtime_phase_integrates_runtime_and_sink_once(runtime_db) -> None:
    db, simulation, _, _, _ = runtime_db
    agents = db.scalars(
        select(Agent).where(Agent.simulation_id == simulation.id).order_by(Agent.fixture_key)
    ).all()
    professor = next(agent for agent in agents if agent.agent_type == "professor")
    professor.active_status = "inactive_temporary"
    location_id = db.scalar(
        select(Location.id).where(
            Location.simulation_id == simulation.id,
            Location.code == "classroom",
        )
    )
    event = make_event(simulation.id, location_id)
    participants = [
        EventParticipant(
            id=uuid4(),
            event_id=event.id,
            agent_id=professor.id,
            result={},
        )
    ]
    sink = CountingSink()
    llm_client = RecordingMockLLMClient(valid_intent_response(event.id, location_id))
    service = SimulationTickService(
        RuntimeInputAdapter(
            RuntimeOrchestrator(
                AgentRuntime(llm_client),
                sink,
            )
        )
    )

    batch = run_phase(
        service,
        db,
        simulation,
        event,
        participants,
        make_schedule(location_id),
        preselected_agent_ids=[
            next(agent.id for agent in agents if agent.fixture_key == "student-01"),
            professor.id,
        ],
    )

    statuses_by_agent = {result.agent_id: result.status for result in batch.results}
    assert statuses_by_agent[professor.id] == RuntimeStatus.SKIPPED
    assert sum(status == RuntimeStatus.PROPOSED for status in statuses_by_agent.values()) == 1
    assert professor.id not in llm_client.agent_ids
    assert len(llm_client.agent_ids) == 1
    assert sink.call_count == 1


def test_inactive_slice_one_student_is_skipped_without_llm_and_saved(runtime_db) -> None:
    db, simulation, _, _, _ = runtime_db
    student = db.scalar(
        select(Agent).where(
            Agent.simulation_id == simulation.id,
            Agent.fixture_key == "student-01",
        )
    )
    student.active_status = "inactive_temporary"
    location_id = db.scalar(
        select(Location.id).where(
            Location.simulation_id == simulation.id,
            Location.code == "classroom",
        )
    )
    db.commit()
    event = make_event(simulation.id, location_id)
    sink = CountingSink()
    llm_client = RecordingMockLLMClient(valid_intent_response(event.id, location_id))
    service = SimulationTickService(
        RuntimeInputAdapter(RuntimeOrchestrator(AgentRuntime(llm_client), sink))
    )

    batch = run_phase(
        service,
        db,
        simulation,
        event,
        [],
        make_schedule(location_id),
    )

    assert len(batch.results) == 1
    assert batch.results[0].agent_id == student.id
    assert batch.results[0].status == RuntimeStatus.SKIPPED
    assert llm_client.agent_ids == []
    assert sink.call_count == 1
    assert sink.list_results() == [batch.results[0]]


# ── Slice 4 Task 2: preselected_agent_ids 자동 편성 ───────────────────────────


def _runtime_agent_ids_by_fixture_key(db, simulation_id) -> dict[str, UUID]:
    rows = db.execute(
        select(Agent.fixture_key, Agent.id).where(Agent.simulation_id == simulation_id)
    ).all()
    return {fixture_key: agent_id for fixture_key, agent_id in rows}


def test_default_selection_runs_five_students_without_professor(runtime_db) -> None:
    """preselected_agent_ids를 생략하면 Student 5명만 자동 편성된다."""
    db, simulation, _, _, _ = runtime_db
    location_id = db.scalar(
        select(Location.id).where(
            Location.simulation_id == simulation.id,
            Location.code == "classroom",
        )
    )
    event = make_event(simulation.id, location_id)
    ids_by_fixture_key = _runtime_agent_ids_by_fixture_key(db, simulation.id)
    adapter = SpyAdapter()

    run_phase(
        SimulationTickService(adapter),
        db,
        simulation,
        event,
        [],
        make_schedule(location_id),
        preselected_agent_ids=None,
    )

    assert adapter.calls[0]["preselected_agent_ids"] == tuple(
        ids_by_fixture_key[f"student-{index:02d}"] for index in range(1, 6)
    )


def test_default_selection_adds_professor_when_event_participant(runtime_db) -> None:
    """Professor가 Event 참여자면 자동 편성 결과에 6명이 포함된다."""
    db, simulation, _, _, _ = runtime_db
    location_id = db.scalar(
        select(Location.id).where(
            Location.simulation_id == simulation.id,
            Location.code == "classroom",
        )
    )
    event = make_event(simulation.id, location_id)
    ids_by_fixture_key = _runtime_agent_ids_by_fixture_key(db, simulation.id)
    professor_id = ids_by_fixture_key["professor-01"]
    participant = EventParticipant(
        id=uuid4(), event_id=event.id, agent_id=professor_id, result={}
    )
    adapter = SpyAdapter()

    run_phase(
        SimulationTickService(adapter),
        db,
        simulation,
        event,
        [participant],
        make_schedule(location_id),
        preselected_agent_ids=None,
    )

    assert adapter.calls[0]["preselected_agent_ids"] == (
        *(ids_by_fixture_key[f"student-{index:02d}"] for index in range(1, 6)),
        professor_id,
    )


def test_default_selection_adds_professor_when_schedule_requires(runtime_db) -> None:
    """schedule_requires_professor=True면 Event 미참여 Professor도 자동 편성에 포함된다."""
    db, simulation, _, _, _ = runtime_db
    location_id = db.scalar(
        select(Location.id).where(
            Location.simulation_id == simulation.id,
            Location.code == "classroom",
        )
    )
    event = make_event(simulation.id, location_id)
    ids_by_fixture_key = _runtime_agent_ids_by_fixture_key(db, simulation.id)
    adapter = SpyAdapter()

    run_phase(
        SimulationTickService(adapter),
        db,
        simulation,
        event,
        [],
        make_schedule(location_id),
        preselected_agent_ids=None,
        schedule_requires_professor=True,
    )

    assert adapter.calls[0]["preselected_agent_ids"] == (
        *(ids_by_fixture_key[f"student-{index:02d}"] for index in range(1, 6)),
        ids_by_fixture_key["professor-01"],
    )


def test_explicit_preselected_agent_ids_bypasses_automatic_selection(runtime_db) -> None:
    """preselected_agent_ids를 명시하면 자동 편성 대신 그대로 사용된다."""
    db, simulation, _, _, _ = runtime_db
    location_id = db.scalar(
        select(Location.id).where(
            Location.simulation_id == simulation.id,
            Location.code == "classroom",
        )
    )
    event = make_event(simulation.id, location_id)
    ids_by_fixture_key = _runtime_agent_ids_by_fixture_key(db, simulation.id)
    only_student = ids_by_fixture_key["student-02"]
    adapter = SpyAdapter()

    run_phase(
        SimulationTickService(adapter),
        db,
        simulation,
        event,
        [],
        make_schedule(location_id),
        preselected_agent_ids=[only_student],
        schedule_requires_professor=True,
    )

    assert adapter.calls[0]["preselected_agent_ids"] == [only_student]
