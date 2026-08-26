from copy import deepcopy
from uuid import UUID

import pytest

from app.domain.models import Agent, AgentState, Event, EventParticipant, Relationship
from app.services.runtime_input_adapter import RuntimeInputAdapter
from app.services.runtime_orchestrator import RuntimeOrchestrator
from app.services.runtime_results import InMemoryRuntimeResultSink
from app.services.runtime_target_selection import RuntimeTargetSelector
from app.simulation.agent_runtime import (
    AgentRuntime,
    EventSummary,
    MockLLMClient,
    RuntimeStatus,
    ScheduleSummary,
)


STUDENT_ID = UUID("00000000-0000-0000-0000-000000000001")
PROFESSOR_ID = UUID("00000000-0000-0000-0000-000000000010")
LOCATION_IDS = [UUID(f"10000000-0000-0000-0000-{index:012d}") for index in range(1, 6)]
CLASS_EVENT_ID = UUID("20000000-0000-0000-0000-000000000001")
SECOND_EVENT_ID = UUID("20000000-0000-0000-0000-000000000002")
SIMULATION_ID = UUID("30000000-0000-0000-0000-000000000001")


def make_agent(
    agent_id: UUID = STUDENT_ID,
    *,
    agent_type: str = "student",
    active_status: str = "active",
) -> Agent:
    is_professor = agent_type == "professor"
    return Agent(
        id=agent_id,
        simulation_id=SIMULATION_ID,
        fixture_key="professor-01" if is_professor else "student-01",
        fixture_version="fixture-v1",
        agent_type=agent_type,
        name="에단" if is_professor else "아델",
        mbti_type="ISTJ",
        openness=-20 if is_professor else -25,
        conscientiousness=40 if is_professor else 25,
        extraversion=-25,
        agreeableness=10 if is_professor else -20,
        emotional_stability=35 if is_professor else 0,
        active_status=active_status,
    )


def make_state(agent_id: UUID = STUDENT_ID, *, location_id: UUID | None = None) -> AgentState:
    return AgentState(
        id=UUID(int=(agent_id.int + 100) % (1 << 128)),
        simulation_id=SIMULATION_ID,
        agent_id=agent_id,
        location_id=location_id or LOCATION_IDS[0],
        hunger=25,
        fatigue=15,
        stress=20,
        satisfaction=60,
        mood=0,
    )


def make_event(
    event_id: UUID = CLASS_EVENT_ID,
    *,
    event_type: str = "class",
) -> Event:
    return Event(
        id=event_id,
        simulation_id=SIMULATION_ID,
        location_id=LOCATION_IDS[0],
        event_type=event_type,
        title="통합마법학",
        description="기초 수업",
        status="scheduled",
        simulation_day=1,
        event_metadata={},
    )


def make_participant(event_id: UUID, agent_id: UUID) -> EventParticipant:
    return EventParticipant(
        id=UUID(int=(event_id.int + agent_id.int) % (1 << 128)),
        event_id=event_id,
        agent_id=agent_id,
        result={},
    )


def make_relationship(source_agent_id: UUID, target_agent_id: UUID) -> Relationship:
    return Relationship(
        id=UUID(int=(source_agent_id.int + target_agent_id.int + 200) % (1 << 128)),
        simulation_id=SIMULATION_ID,
        source_agent_id=source_agent_id,
        target_agent_id=target_agent_id,
        affection=1,
        closeness=2,
        trust=3,
        tension=4,
        rivalry=5,
        dependency=6,
    )


def make_schedule() -> ScheduleSummary:
    return ScheduleSummary(
        event_id=CLASS_EVENT_ID,
        schedule_type="class",
        is_mandatory=True,
        location_id=LOCATION_IDS[0],
        start_tick=3,
        end_tick=3,
    )


def orm_values(value: object) -> dict:
    return {
        key: deepcopy(item)
        for key, item in vars(value).items()
        if not key.startswith("_")
    }


def test_student_orm_values_are_mapped_to_agent_context() -> None:
    context = RuntimeInputAdapter.to_agent_context(make_agent(), make_state())

    assert context.agent_id == STUDENT_ID
    assert context.fixture_key == "student-01"
    assert context.agent_type == "student"
    assert context.name == "아델"
    assert context.mbti.value == "ISTJ"
    assert context.big_five.model_dump() == {
        "openness": -25,
        "conscientiousness": 25,
        "extraversion": -25,
        "agreeableness": -20,
        "emotional_stability": 0,
    }
    assert context.state.model_dump() == {
        "hunger": 25,
        "fatigue": 15,
        "stress": 20,
        "satisfaction": 60,
        "mood": 0,
    }
    assert context.current_location_id == LOCATION_IDS[0]
    assert context.active_status is True


def test_professor_orm_values_are_mapped_to_agent_context() -> None:
    context = RuntimeInputAdapter.to_agent_context(
        make_agent(PROFESSOR_ID, agent_type="professor"),
        make_state(PROFESSOR_ID),
    )

    assert context.agent_id == PROFESSOR_ID
    assert context.agent_type == "professor"
    assert context.name == "에단"
    assert context.big_five.conscientiousness == 40


def test_user_persona_is_normalized_to_student_and_selected() -> None:
    context = RuntimeInputAdapter.to_agent_context(
        make_agent(agent_type="user_persona"),
        make_state(),
    )

    selected = RuntimeTargetSelector().select(
        [context],
        preselected_agent_ids=[context.agent_id],
    )

    assert context.agent_type == "student"
    assert selected == (context,)


@pytest.mark.parametrize(
    ("stored_status", "expected"),
    [("active", True), ("inactive_temporary", False)],
)
def test_official_active_status_is_mapped(stored_status: str, expected: bool) -> None:
    context = RuntimeInputAdapter.to_agent_context(
        make_agent(active_status=stored_status),
        make_state(),
    )

    assert context.active_status is expected


@pytest.mark.parametrize(
    "stored_status",
    ["ACTIVE", "INACTIVE_TEMPORARY", "inactive", "unknown", "", None],
)
def test_unknown_active_status_is_rejected(stored_status: str | None) -> None:
    with pytest.raises(ValueError, match="unknown active_status"):
        RuntimeInputAdapter.to_agent_context(
            make_agent(active_status=stored_status),
            make_state(),
        )


def test_unknown_agent_role_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown agent_type"):
        RuntimeInputAdapter.to_agent_context(
            make_agent(agent_type="event_master"),
            make_state(),
        )


def test_mismatched_agent_state_is_rejected() -> None:
    with pytest.raises(ValueError, match="AgentState.agent_id"):
        RuntimeInputAdapter.to_agent_context(
            make_agent(STUDENT_ID),
            make_state(PROFESSOR_ID),
        )


def test_event_and_participant_order_are_preserved() -> None:
    events = [make_event(SECOND_EVENT_ID, event_type="exam"), make_event()]
    first_participants = [
        make_participant(SECOND_EVENT_ID, PROFESSOR_ID),
        make_participant(SECOND_EVENT_ID, STUDENT_ID),
    ]

    summaries = RuntimeInputAdapter.to_event_summaries(
        events,
        {SECOND_EVENT_ID: first_participants},
    )

    assert [summary.event_id for summary in summaries] == [SECOND_EVENT_ID, CLASS_EVENT_ID]
    assert summaries[0].participant_agent_ids == [PROFESSOR_ID, STUDENT_ID]
    assert summaries[1].participant_agent_ids == []
    assert summaries[0].event_type.value == "exam"
    assert summaries[0].title == "통합마법학"
    assert summaries[0].description == "기초 수업"


def test_participant_event_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="EventParticipant.event_id"):
        RuntimeInputAdapter.to_event_summaries(
            [make_event()],
            {CLASS_EVENT_ID: [make_participant(SECOND_EVENT_ID, STUDENT_ID)]},
        )


def test_directional_relationship_is_mapped_to_typed_summary() -> None:
    summary = RuntimeInputAdapter.to_relationship_summaries(
        [make_relationship(STUDENT_ID, PROFESSOR_ID)]
    )[0]

    assert summary.source_agent_id == STUDENT_ID
    assert summary.target_agent_id == PROFESSOR_ID
    assert summary.model_dump()["trust"] == 3


class SpyOrchestrator:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.result = object()

    def run_preselected(self, **values):
        self.calls.append(deepcopy(values))
        return self.result


def test_adapter_preserves_inputs_and_delegates_to_preselected_batch() -> None:
    agent = make_agent()
    state = make_state()
    event = make_event()
    participant = make_participant(CLASS_EVENT_ID, STUDENT_ID)
    agents = [agent]
    states = {STUDENT_ID: state}
    events = [event]
    participants = {CLASS_EVENT_ID: [participant]}
    valid_agent_ids = [PROFESSOR_ID, STUDENT_ID, STUDENT_ID]
    valid_location_ids = list(reversed(LOCATION_IDS))
    original_values = tuple(
        orm_values(value)
        for value in (agent, state, event, participant)
    )
    original_collections = (
        agents.copy(),
        states.copy(),
        events.copy(),
        {key: value.copy() for key, value in participants.items()},
        valid_agent_ids.copy(),
        valid_location_ids.copy(),
    )
    orchestrator = SpyOrchestrator()
    adapter = RuntimeInputAdapter(orchestrator)

    first = adapter.run(
        run_id="slice-1-run",
        tick_number=3,
        block="MORNING",
        agents=agents,
        preselected_agent_ids=[STUDENT_ID],
        agent_states=states,
        schedule=make_schedule(),
        events=events,
        event_participants=participants,
        valid_agent_ids=valid_agent_ids,
        valid_location_ids=valid_location_ids,
    )
    second = adapter.run(
        run_id="slice-1-run",
        tick_number=3,
        block="MORNING",
        agents=agents,
        preselected_agent_ids=[STUDENT_ID],
        agent_states=states,
        schedule=make_schedule(),
        events=events,
        event_participants=participants,
        valid_agent_ids=valid_agent_ids,
        valid_location_ids=valid_location_ids,
    )

    assert first is orchestrator.result
    assert second is orchestrator.result
    assert orchestrator.calls[0] == orchestrator.calls[1]
    assert orchestrator.calls[0]["valid_agent_ids"] == valid_agent_ids
    assert orchestrator.calls[0]["valid_location_ids"] == valid_location_ids
    assert orchestrator.calls[0]["schedule"] == make_schedule()
    assert orchestrator.calls[0]["preselected_agent_ids"] == [STUDENT_ID]
    assert orchestrator.calls[0]["events"][0].event_id == CLASS_EVENT_ID
    assert tuple(
        orm_values(value)
        for value in (agent, state, event, participant)
    ) == original_values
    assert (
        agents,
        states,
        events,
        participants,
        valid_agent_ids,
        valid_location_ids,
    ) == original_collections


def test_adapter_preserves_candidate_order_without_selecting_or_sorting() -> None:
    professor = make_agent(PROFESSOR_ID, agent_type="professor")
    student = make_agent()
    orchestrator = SpyOrchestrator()

    RuntimeInputAdapter(orchestrator).run(
        run_id="slice-1-run",
        tick_number=3,
        block="MORNING",
        agents=[professor, student],
        preselected_agent_ids=[STUDENT_ID],
        agent_states={PROFESSOR_ID: make_state(PROFESSOR_ID), STUDENT_ID: make_state()},
        schedule=make_schedule(),
        events=[make_event()],
        event_participants={},
        valid_agent_ids=[STUDENT_ID, PROFESSOR_ID],
        valid_location_ids=LOCATION_IDS,
    )

    assert [
        candidate.agent_id
        for candidate in orchestrator.calls[0]["agent_candidates"]
    ] == [PROFESSOR_ID, STUDENT_ID]


@pytest.mark.parametrize("invalid_value", [1, "student-01", None])
def test_preselected_agent_ids_require_uuids(invalid_value: object) -> None:
    with pytest.raises(TypeError, match="preselected_agent_ids"):
        RuntimeInputAdapter(SpyOrchestrator()).run(
            run_id="slice-1-run",
            tick_number=3,
            block="MORNING",
            agents=[],
            preselected_agent_ids=[invalid_value],
            agent_states={},
            schedule=make_schedule(),
            events=[],
            event_participants={},
            valid_agent_ids=[],
            valid_location_ids=[],
        )


class CountingSink(InMemoryRuntimeResultSink):
    def __init__(self) -> None:
        super().__init__()
        self.call_count = 0

    def save_batch(self, results):
        self.call_count += 1
        return super().save_batch(results)


def test_adapter_to_runtime_integration_proposes_student_and_skips_professor() -> None:
    student = make_agent()
    professor = make_agent(
        PROFESSOR_ID,
        agent_type="professor",
        active_status="inactive_temporary",
    )
    event = make_event()
    sink = CountingSink()
    adapter = RuntimeInputAdapter(
        RuntimeOrchestrator(AgentRuntime(MockLLMClient()), sink)
    )

    batch = adapter.run(
        run_id="slice-1-run",
        tick_number=3,
        block="MORNING",
        agents=[professor, student],
        preselected_agent_ids=[STUDENT_ID, PROFESSOR_ID],
        agent_states={STUDENT_ID: make_state(), PROFESSOR_ID: make_state(PROFESSOR_ID)},
        schedule=make_schedule(),
        events=[event],
        event_participants={
            CLASS_EVENT_ID: [
                make_participant(CLASS_EVENT_ID, STUDENT_ID),
                make_participant(CLASS_EVENT_ID, PROFESSOR_ID),
            ]
        },
        valid_agent_ids=[STUDENT_ID, PROFESSOR_ID],
        valid_location_ids=LOCATION_IDS,
    )

    assert [result.agent_id for result in batch.results] == [STUDENT_ID, PROFESSOR_ID]
    assert [result.status for result in batch.results] == [
        RuntimeStatus.PROPOSED,
        RuntimeStatus.SKIPPED,
    ]
    assert sink.call_count == 1
