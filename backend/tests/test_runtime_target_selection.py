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


def test_preselected_ids_control_execution_and_preserve_caller_order() -> None:
    candidates = [
        make_agent(STUDENT_IDS[0]),
        make_agent(STUDENT_IDS[1]),
        make_agent(PROFESSOR_ID, agent_type="professor"),
    ]

    selected = RuntimeTargetSelector().select(
        candidates,
        preselected_agent_ids=[PROFESSOR_ID, STUDENT_IDS[0]],
    )

    assert [agent.agent_id for agent in selected] == [PROFESSOR_ID, STUDENT_IDS[0]]


def test_inactive_preselected_agent_is_not_filtered() -> None:
    inactive_student = make_agent(STUDENT_IDS[0], active=False)

    selected = RuntimeTargetSelector().select(
        [inactive_student],
        preselected_agent_ids=[inactive_student.agent_id],
    )

    assert selected == (inactive_student,)


def test_non_preselected_students_are_not_returned() -> None:
    candidates = [make_agent(agent_id) for agent_id in STUDENT_IDS]

    selected = RuntimeTargetSelector().select(
        candidates,
        preselected_agent_ids=[STUDENT_IDS[0]],
    )

    assert [agent.agent_id for agent in selected] == [STUDENT_IDS[0]]


def test_conflicting_duplicate_agent_is_rejected() -> None:
    first = make_agent(STUDENT_IDS[0])
    conflicting = make_agent(STUDENT_IDS[0], name="다른 이름")

    with pytest.raises(ValueError, match="conflicting agent candidates"):
        RuntimeTargetSelector().select(
            [first, conflicting],
            preselected_agent_ids=[first.agent_id],
        )


def test_selection_is_deterministic_and_does_not_mutate_inputs() -> None:
    candidates = [make_agent(STUDENT_IDS[2]), make_agent(STUDENT_IDS[0])]
    original_candidates = deepcopy(candidates)
    selected_ids = [STUDENT_IDS[0], STUDENT_IDS[2]]
    selector = RuntimeTargetSelector()

    first = selector.select(candidates, preselected_agent_ids=selected_ids)
    second = selector.select(candidates, preselected_agent_ids=selected_ids)

    assert first == second
    assert [agent.agent_id for agent in first] == [STUDENT_IDS[0], STUDENT_IDS[2]]
    assert candidates == original_candidates


def test_duplicate_preselected_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not contain duplicates"):
        RuntimeTargetSelector().select(
            [make_agent(STUDENT_IDS[0])],
            preselected_agent_ids=[STUDENT_IDS[0], STUDENT_IDS[0]],
        )


def test_preselected_id_missing_from_snapshot_is_rejected() -> None:
    with pytest.raises(ValueError, match="is not a runtime candidate"):
        RuntimeTargetSelector().select([], preselected_agent_ids=[STUDENT_IDS[0]])


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


def test_orchestrator_assembles_and_runs_preselected_batch_in_caller_order() -> None:
    candidates = [make_agent(STUDENT_IDS[2]), make_agent(STUDENT_IDS[0])]
    events = [make_event(participants=[STUDENT_IDS[2], STUDENT_IDS[0]])]
    valid_agent_ids = list(reversed(STUDENT_IDS)) + [PROFESSOR_ID]
    valid_location_ids = list(reversed(LOCATION_IDS))
    assembler = RecordingAssembler()
    runtime = RecordingRuntime()
    sink = InMemoryRuntimeResultSink()

    batch = RuntimeOrchestrator(runtime, sink, context_assembler=assembler).run_preselected(
        run_id="slice-1-run",
        tick_number=3,
        block="MORNING",
        agent_candidates=candidates,
        preselected_agent_ids=[STUDENT_IDS[0], STUDENT_IDS[2]],
        schedule=make_schedule(),
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
        orchestrator.run_preselected(
            run_id="slice-1-run",
            tick_number=3,
            block="MORNING",
            agent_candidates=[make_agent(STUDENT_IDS[0])],
            preselected_agent_ids=[STUDENT_IDS[0]],
            schedule=make_schedule(),
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
    ).run_preselected(
        run_id="slice-1-run",
        tick_number=3,
        block="MORNING",
        agent_candidates=[professor, student],
        preselected_agent_ids=[student.agent_id, professor.agent_id],
        schedule=make_schedule(),
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
