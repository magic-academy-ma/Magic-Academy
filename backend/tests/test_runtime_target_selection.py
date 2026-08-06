from copy import deepcopy
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.services.runtime_orchestrator import RuntimeOrchestrator
from app.services.runtime_results import InMemoryRuntimeResultSink
from app.services.runtime_target_selection import RuntimeTargetSelector
from app.simulation.agent_context_assembler import AgentContextAssembler
from app.simulation.agent_runtime import (
    AgentContext,
    AgentRuntime,
    AgentRuntimeInput,
    AgentRuntimeResult,
    EventSummary,
    MockLLMClient,
    RuntimeStatus,
    ScheduleSummary,
    validate_intent_candidate,
)


STUDENT_IDS = [UUID(f"00000000-0000-0000-0000-{index:012d}") for index in range(1, 6)]
PROFESSOR_ID = UUID("00000000-0000-0000-0000-000000000010")
LOCATION_IDS = [UUID(f"10000000-0000-0000-0000-{index:012d}") for index in range(1, 6)]
CLASS_EVENT_ID = UUID("20000000-0000-0000-0000-000000000001")


def make_agent(
    agent_id: UUID,
    *,
    agent_type: str = "student",
    active: bool = True,
    name: str | None = None,
) -> AgentContext:
    return AgentContext(
        agent_id=agent_id,
        fixture_key=("professor-01" if agent_type == "professor" else "student-01"),
        agent_type=agent_type,
        name=name or ("에단" if agent_type == "professor" else "아델"),
        mbti="ISTJ",
        big_five={
            "openness": 0,
            "conscientiousness": 0,
            "extraversion": 0,
            "agreeableness": 0,
            "emotional_stability": 0,
        },
        state={
            "hunger": 0,
            "fatigue": 0,
            "stress": 0,
            "satisfaction": 0,
            "mood": 0,
        },
        current_location_id=LOCATION_IDS[0],
        active_status=active,
    )


def make_event(
    *,
    event_type: str = "class",
    participants: list[UUID] | None = None,
    event_id: UUID = CLASS_EVENT_ID,
) -> EventSummary:
    return EventSummary(
        event_id=event_id,
        event_type=event_type,
        location_id=LOCATION_IDS[0],
        participant_agent_ids=participants or [],
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


def test_active_students_are_selected_without_events() -> None:
    candidates = [
        make_agent(STUDENT_IDS[2]),
        make_agent(STUDENT_IDS[0]),
        make_agent(STUDENT_IDS[1]),
        make_agent(STUDENT_IDS[3], active=False),
    ]

    selected = RuntimeTargetSelector().select(
        candidates,
        schedule_requires_professor=False,
        events=[],
    )

    assert [agent.agent_id for agent in selected] == STUDENT_IDS[:3]


def test_schedule_requirement_selects_professor() -> None:
    professor = make_agent(PROFESSOR_ID, agent_type="professor")

    selected = RuntimeTargetSelector().select(
        [professor],
        schedule_requires_professor=True,
        events=[],
    )

    assert selected == (professor,)


@pytest.mark.parametrize("event_type", ["class", "exam", "random_incident"])
@pytest.mark.parametrize("position", [0, 1, 2])
def test_event_participation_selects_professor_regardless_of_type_or_position(
    event_type: str, position: int
) -> None:
    professor = make_agent(PROFESSOR_ID, agent_type="professor")
    participants = [STUDENT_IDS[0], STUDENT_IDS[1]]
    participants.insert(position, PROFESSOR_ID)

    selected = RuntimeTargetSelector().select(
        [professor],
        schedule_requires_professor=False,
        events=[make_event(event_type=event_type, participants=participants)],
    )

    assert selected == (professor,)


def test_professor_without_schedule_or_event_condition_is_excluded() -> None:
    professor = make_agent(PROFESSOR_ID, agent_type="professor")

    selected = RuntimeTargetSelector().select(
        [professor],
        schedule_requires_professor=False,
        events=[make_event(participants=[])],
    )

    assert selected == ()


def test_duplicate_selection_paths_and_events_select_professor_once() -> None:
    professor = make_agent(PROFESSOR_ID, agent_type="professor")
    second_event_id = UUID("20000000-0000-0000-0000-000000000002")

    selected = RuntimeTargetSelector().select(
        [professor, professor.model_copy(deep=True)],
        schedule_requires_professor=True,
        events=[
            make_event(participants=[PROFESSOR_ID]),
            make_event(event_id=second_event_id, participants=[PROFESSOR_ID]),
        ],
    )

    assert selected == (professor,)


def test_conflicting_duplicate_agent_is_rejected() -> None:
    first = make_agent(STUDENT_IDS[0])
    conflicting = make_agent(STUDENT_IDS[0], name="다른 이름")

    with pytest.raises(ValueError, match="conflicting agent candidates"):
        RuntimeTargetSelector().select(
            [first, conflicting],
            schedule_requires_professor=False,
            events=[],
        )


def test_selection_is_sorted_deterministic_and_does_not_mutate_inputs() -> None:
    candidates = [make_agent(STUDENT_IDS[2]), make_agent(STUDENT_IDS[0])]
    events = [make_event(participants=[STUDENT_IDS[2], STUDENT_IDS[0]])]
    original_candidates = deepcopy(candidates)
    original_events = deepcopy(events)
    selector = RuntimeTargetSelector()

    first = selector.select(candidates, schedule_requires_professor=False, events=events)
    second = selector.select(candidates, schedule_requires_professor=False, events=events)

    assert first == second
    assert [agent.agent_id for agent in first] == [STUDENT_IDS[0], STUDENT_IDS[2]]
    assert candidates == original_candidates
    assert events == original_events


def test_schedule_requires_professor_rejects_truthy_string() -> None:
    with pytest.raises(TypeError, match="schedule_requires_professor"):
        RuntimeTargetSelector().select(
            [make_agent(PROFESSOR_ID, agent_type="professor")],
            schedule_requires_professor="true",
            events=[],
        )


class RecordingAssembler:
    def __init__(self) -> None:
        self.delegate = AgentContextAssembler()
        self.calls: list[dict] = []

    def assemble(self, **values) -> AgentRuntimeInput:
        self.calls.append(deepcopy(values))
        return self.delegate.assemble(**values)


class RecordingRuntime:
    def __init__(self) -> None:
        self.calls: list[AgentRuntimeInput] = []

    def run(self, runtime_input: AgentRuntimeInput) -> AgentRuntimeResult:
        self.calls.append(runtime_input)
        intent = validate_intent_candidate(MockLLMClient().generate(runtime_input), runtime_input)
        agent_id = runtime_input.agent.agent_id
        return AgentRuntimeResult(
            run_id=runtime_input.run_id,
            tick_number=runtime_input.tick_number,
            agent_id=agent_id,
            status=RuntimeStatus.PROPOSED,
            intent=intent,
            retry_count=0,
            failure_reason=None,
            model="recording-runtime",
            prompt_version="test",
            idempotency_key=f"{runtime_input.run_id}:{runtime_input.tick_number}:{agent_id}",
        )


class RecordingMockLLMClient(MockLLMClient):
    def __init__(self) -> None:
        super().__init__()
        self.agent_ids: list[UUID] = []

    def generate(self, runtime_input: AgentRuntimeInput) -> object:
        self.agent_ids.append(runtime_input.agent.agent_id)
        return super().generate(runtime_input)


def test_orchestrator_selects_assembles_and_runs_in_sorted_order() -> None:
    candidates = [make_agent(STUDENT_IDS[2]), make_agent(STUDENT_IDS[0])]
    events = [make_event(participants=[STUDENT_IDS[2], STUDENT_IDS[0]])]
    valid_agent_ids = list(reversed(STUDENT_IDS)) + [PROFESSOR_ID]
    valid_location_ids = list(reversed(LOCATION_IDS))
    assembler = RecordingAssembler()
    runtime = RecordingRuntime()
    sink = InMemoryRuntimeResultSink()

    batch = RuntimeOrchestrator(runtime, sink, context_assembler=assembler).select_and_run(
        run_id="slice-1-run",
        tick_number=3,
        block="MORNING",
        agent_candidates=candidates,
        schedule=make_schedule(),
        schedule_requires_professor=False,
        events=events,
        valid_agent_ids=valid_agent_ids,
        valid_location_ids=valid_location_ids,
    )

    expected_ids = [STUDENT_IDS[0], STUDENT_IDS[2]]
    assert [result.agent_id for result in batch.results] == expected_ids
    assert [item.agent.agent_id for item in runtime.calls] == expected_ids
    assert len(assembler.calls) == 2
    assert all(call["run_id"] == "slice-1-run" for call in assembler.calls)
    assert all(call["tick_number"] == 3 for call in assembler.calls)
    assert all(call["block"] == "MORNING" for call in assembler.calls)
    assert all(call["events"] == events for call in assembler.calls)
    assert all(call["valid_agent_ids"] == valid_agent_ids for call in assembler.calls)
    assert all(call["valid_location_ids"] == valid_location_ids for call in assembler.calls)
    assert batch.save_result.new_count == 2


def test_execution_with_missing_schedule_event_propagates_validation_error() -> None:
    orchestrator = RuntimeOrchestrator(
        RecordingRuntime(),
        InMemoryRuntimeResultSink(),
    )

    with pytest.raises(ValidationError, match="schedule event_id"):
        orchestrator.select_and_run(
            run_id="slice-1-run",
            tick_number=3,
            block="MORNING",
            agent_candidates=[make_agent(STUDENT_IDS[0])],
            schedule=make_schedule(),
            schedule_requires_professor=False,
            events=[],
            valid_agent_ids=STUDENT_IDS,
            valid_location_ids=LOCATION_IDS,
        )


def test_inactive_participating_professor_is_skipped_and_saved() -> None:
    student = make_agent(STUDENT_IDS[0])
    professor = make_agent(PROFESSOR_ID, agent_type="professor", active=False)
    event = make_event(participants=[student.agent_id, professor.agent_id])
    sink = InMemoryRuntimeResultSink()
    llm_client = RecordingMockLLMClient()

    batch = RuntimeOrchestrator(
        AgentRuntime(llm_client),
        sink,
    ).select_and_run(
        run_id="slice-1-run",
        tick_number=3,
        block="MORNING",
        agent_candidates=[professor, student],
        schedule=make_schedule(),
        schedule_requires_professor=False,
        events=[event],
        valid_agent_ids=[student.agent_id, professor.agent_id],
        valid_location_ids=LOCATION_IDS,
    )

    assert [result.agent_id for result in batch.results] == [student.agent_id, professor.agent_id]
    assert [result.status for result in batch.results] == [
        RuntimeStatus.PROPOSED,
        RuntimeStatus.SKIPPED,
    ]
    assert llm_client.agent_ids == [student.agent_id]
    assert batch.save_result.new_count == 2
    assert len(sink.list_results()) == 2
