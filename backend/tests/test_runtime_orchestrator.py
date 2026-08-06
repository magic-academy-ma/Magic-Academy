from copy import deepcopy
from uuid import UUID

import pytest

from app.services.runtime_orchestrator import RuntimeOrchestrator
from app.services.runtime_results import (
    IdempotencyConflictError,
    InMemoryRuntimeResultSink,
)
from app.simulation.agent_runtime import (
    AgentRuntime,
    AgentRuntimeInput,
    AgentRuntimeResult,
    MockLLMClient,
    RuntimeStatus,
    validate_intent_candidate,
)


STUDENT_IDS = [UUID(f"00000000-0000-0000-0000-{index:012d}") for index in range(1, 6)]
LOCATION_IDS = [UUID(f"10000000-0000-0000-0000-{index:012d}") for index in range(1, 6)]
CLASS_EVENT_ID = UUID("20000000-0000-0000-0000-000000000001")


def make_input(agent_index: int = 0, *, active: bool = True) -> AgentRuntimeInput:
    return AgentRuntimeInput(
        run_id="slice-1-run",
        tick_number=3,
        block="MORNING",
        agent={
            "agent_id": STUDENT_IDS[agent_index],
            "fixture_key": f"student-{agent_index + 1:02d}",
            "agent_type": "student",
            "mbti": "ISTJ",
            "current_location_id": LOCATION_IDS[0],
            "active_status": active,
        },
        nearby_agents=[],
        relationships=[],
        memories=[],
        events=[
            {
                "event_id": CLASS_EVENT_ID,
                "event_type": "class",
                "location_id": LOCATION_IDS[0],
                "participant_agent_ids": [STUDENT_IDS[agent_index]],
            }
        ],
        schedule={
            "event_id": CLASS_EVENT_ID,
            "schedule_type": "class",
            "is_mandatory": True,
            "location_id": LOCATION_IDS[0],
            "start_tick": 3,
            "end_tick": 3,
        },
        valid_agent_ids=STUDENT_IDS,
        valid_location_ids=LOCATION_IDS,
    )


def make_result(
    runtime_input: AgentRuntimeInput,
    status: RuntimeStatus = RuntimeStatus.PROPOSED,
) -> AgentRuntimeResult:
    base_input = make_input()
    intent = validate_intent_candidate(
        MockLLMClient().generate(base_input), base_input
    ).model_copy(deep=True)
    return AgentRuntimeResult(
        run_id=runtime_input.run_id,
        tick_number=runtime_input.tick_number,
        agent_id=runtime_input.agent.agent_id,
        status=status,
        intent=intent,
        retry_count=1 if status == RuntimeStatus.FALLBACK else 0,
        failure_reason="validation failed" if status == RuntimeStatus.FALLBACK else None,
        model="fake-runtime",
        prompt_version="test",
        idempotency_key=(
            f"{runtime_input.run_id}:{runtime_input.tick_number}:"
            f"{runtime_input.agent.agent_id}"
        ),
    )


class SpyRuntime:
    def __init__(
        self,
        statuses: dict[UUID, RuntimeStatus] | None = None,
        failure_agent_id: UUID | None = None,
    ) -> None:
        self.statuses = statuses or {}
        self.failure_agent_id = failure_agent_id
        self.calls: list[AgentRuntimeInput] = []

    def run(self, runtime_input: AgentRuntimeInput) -> AgentRuntimeResult:
        self.calls.append(runtime_input)
        if runtime_input.agent.agent_id == self.failure_agent_id:
            raise RuntimeError("unexpected runtime failure")
        status = self.statuses.get(runtime_input.agent.agent_id, RuntimeStatus.PROPOSED)
        return make_result(runtime_input, status)


class SpySink:
    def __init__(self) -> None:
        self.delegate = InMemoryRuntimeResultSink()
        self.calls: list[tuple[AgentRuntimeResult, ...]] = []

    def save_batch(self, results):
        captured = tuple(result.model_copy(deep=True) for result in results)
        self.calls.append(captured)
        return self.delegate.save_batch(results)


def test_single_agent_executes_and_saves_result() -> None:
    runtime = SpyRuntime()
    sink = SpySink()
    batch = RuntimeOrchestrator(runtime, sink).run_batch([make_input()])
    assert len(batch.results) == 1
    assert batch.save_result.new_count == 1
    assert len(runtime.calls) == 1
    assert len(sink.calls) == 1


def test_multiple_results_preserve_input_order() -> None:
    inputs = [make_input(2), make_input(0), make_input(1)]
    batch = RuntimeOrchestrator(SpyRuntime(), SpySink()).run_batch(inputs)
    assert [result.agent_id for result in batch.results] == [
        runtime_input.agent.agent_id for runtime_input in inputs
    ]


def test_multiple_results_are_sent_with_one_save_batch_call() -> None:
    sink = SpySink()
    RuntimeOrchestrator(SpyRuntime(), sink).run_batch([make_input(0), make_input(1)])
    assert len(sink.calls) == 1
    assert len(sink.calls[0]) == 2


def test_proposed_fallback_and_skipped_are_saved_together() -> None:
    inputs = [make_input(0), make_input(1), make_input(2, active=False)]
    statuses = {
        STUDENT_IDS[0]: RuntimeStatus.PROPOSED,
        STUDENT_IDS[1]: RuntimeStatus.FALLBACK,
        STUDENT_IDS[2]: RuntimeStatus.SKIPPED,
    }
    batch = RuntimeOrchestrator(SpyRuntime(statuses), SpySink()).run_batch(inputs)
    assert [result.status for result in batch.results] == list(statuses.values())
    assert batch.save_result.new_count == 3


def test_inactive_agent_does_not_stop_batch_storage() -> None:
    inputs = [make_input(0), make_input(1, active=False)]
    statuses = {STUDENT_IDS[1]: RuntimeStatus.SKIPPED}
    batch = RuntimeOrchestrator(SpyRuntime(statuses), SpySink()).run_batch(inputs)
    assert len(batch.results) == 2
    assert batch.save_result.new_count == 2


def test_unhandled_runtime_exception_prevents_sink_call_and_propagates() -> None:
    inputs = [make_input(0), make_input(1), make_input(2)]
    runtime = SpyRuntime(failure_agent_id=STUDENT_IDS[1])
    sink = SpySink()
    with pytest.raises(RuntimeError, match="unexpected runtime failure"):
        RuntimeOrchestrator(runtime, sink).run_batch(inputs)
    assert len(runtime.calls) == 2
    assert sink.calls == []
    assert sink.delegate.list_results() == []


def test_sink_idempotency_conflict_propagates_without_partial_save() -> None:
    sink = InMemoryRuntimeResultSink()
    existing_input = make_input(0)
    existing = make_result(existing_input)
    sink.save_batch([existing])

    runtime = SpyRuntime()
    original_run = runtime.run

    def conflicting_run(runtime_input: AgentRuntimeInput) -> AgentRuntimeResult:
        result = original_run(runtime_input)
        if runtime_input.agent.agent_id == existing.agent_id:
            result.intent.motivation_summary = "conflicting result"
        return result

    runtime.run = conflicting_run
    new_input = make_input(1)
    with pytest.raises(IdempotencyConflictError):
        RuntimeOrchestrator(runtime, sink).run_batch([new_input, existing_input])
    assert sink.get(make_result(new_input).idempotency_key) is None
    assert sink.get(existing.idempotency_key) == existing


def test_same_batch_rerun_reports_duplicates() -> None:
    sink = InMemoryRuntimeResultSink()
    orchestrator = RuntimeOrchestrator(SpyRuntime(), sink)
    inputs = [make_input(0), make_input(1)]
    first = orchestrator.run_batch(inputs)
    second = orchestrator.run_batch(inputs)
    assert first.save_result.new_count == 2
    assert second.save_result.new_count == 0
    assert second.save_result.duplicate_count == 2


def test_empty_batch_calls_sink_once_and_returns_empty_results() -> None:
    runtime = SpyRuntime()
    sink = SpySink()
    batch = RuntimeOrchestrator(runtime, sink).run_batch([])
    assert batch.results == ()
    assert batch.save_result.new_count == 0
    assert batch.save_result.duplicate_count == 0
    assert runtime.calls == []
    assert sink.calls == [()]


def test_actual_graph_to_in_memory_sink_integration() -> None:
    runtime_input = make_input()
    sink = InMemoryRuntimeResultSink()
    batch = RuntimeOrchestrator(
        AgentRuntime(MockLLMClient()), sink
    ).run_batch([runtime_input])
    assert batch.results[0].status == RuntimeStatus.PROPOSED
    assert batch.save_result.new_count == 1
    assert sink.get(batch.results[0].idempotency_key) == batch.results[0]

