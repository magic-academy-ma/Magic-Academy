from uuid import UUID

import pytest

from app.services.runtime_results import (
    IdempotencyConflictError,
    InMemoryRuntimeResultSink,
)
from app.simulation.agent_runtime import (
    AgentRuntimeInput,
    AgentRuntimeResult,
    MockLLMClient,
    RuntimeStatus,
    validate_intent_candidate,
)


STUDENT_IDS = [UUID(f"00000000-0000-0000-0000-{index:012d}") for index in range(1, 6)]
LOCATION_IDS = [UUID(f"10000000-0000-0000-0000-{index:012d}") for index in range(1, 6)]
CLASS_EVENT_ID = UUID("20000000-0000-0000-0000-000000000001")


def make_runtime_input(*, agent_index: int = 0) -> AgentRuntimeInput:
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
            "active_status": True,
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
    *, agent_index: int = 0, status: RuntimeStatus = RuntimeStatus.PROPOSED
) -> AgentRuntimeResult:
    runtime_input = make_runtime_input(agent_index=agent_index)
    intent = validate_intent_candidate(
        MockLLMClient().generate(make_runtime_input()), make_runtime_input()
    )
    agent_id = runtime_input.agent.agent_id
    return AgentRuntimeResult(
        run_id=runtime_input.run_id,
        tick_number=runtime_input.tick_number,
        agent_id=agent_id,
        status=status,
        intent=intent,
        retry_count=1 if status == RuntimeStatus.FALLBACK else 0,
        failure_reason="validation failed" if status == RuntimeStatus.FALLBACK else None,
        model="mock-llm",
        prompt_version="agent-runtime-10.1",
        idempotency_key=f"{runtime_input.run_id}:{runtime_input.tick_number}:{agent_id}",
    )


@pytest.mark.parametrize(
    "status",
    [RuntimeStatus.PROPOSED, RuntimeStatus.FALLBACK, RuntimeStatus.SKIPPED],
)
def test_stores_each_final_runtime_status(status: RuntimeStatus) -> None:
    sink = InMemoryRuntimeResultSink()
    result = make_result(status=status)
    saved = sink.save_batch([result])
    assert saved.new_count == 1
    assert saved.duplicate_count == 0
    assert sink.get(result.idempotency_key).status == status


def test_stores_multiple_results_as_one_batch() -> None:
    sink = InMemoryRuntimeResultSink()
    results = [make_result(agent_index=0), make_result(agent_index=1)]
    saved = sink.save_batch(results)
    assert saved.new_count == 2
    assert saved.duplicate_count == 0
    assert len(sink.list_results()) == 2


def test_same_key_and_same_result_is_successful_noop() -> None:
    sink = InMemoryRuntimeResultSink()
    result = make_result()
    sink.save_batch([result])
    saved = sink.save_batch([result.model_copy(deep=True)])
    assert saved.new_count == 0
    assert saved.duplicate_count == 1
    assert len(sink.list_results()) == 1


def test_same_key_and_different_result_raises_conflict() -> None:
    sink = InMemoryRuntimeResultSink()
    result = make_result()
    sink.save_batch([result])
    changed = result.model_copy(deep=True)
    changed.intent.motivation_summary = "서로 다른 결과"
    with pytest.raises(IdempotencyConflictError, match=result.idempotency_key):
        sink.save_batch([changed])


def test_same_result_repeated_inside_batch_counts_as_duplicate() -> None:
    sink = InMemoryRuntimeResultSink()
    result = make_result()
    saved = sink.save_batch([result, result.model_copy(deep=True)])
    assert saved.new_count == 1
    assert saved.duplicate_count == 1
    assert len(sink.list_results()) == 1


def test_different_results_with_same_key_inside_batch_conflict() -> None:
    sink = InMemoryRuntimeResultSink()
    result = make_result()
    changed = result.model_copy(deep=True)
    changed.intent.motivation_summary = "서로 다른 결과"
    with pytest.raises(IdempotencyConflictError):
        sink.save_batch([result, changed])
    assert sink.list_results() == []


def test_conflict_with_stored_value_keeps_entire_batch_atomic() -> None:
    sink = InMemoryRuntimeResultSink()
    stored = make_result(agent_index=0)
    new_result = make_result(agent_index=1)
    sink.save_batch([stored])
    conflict = stored.model_copy(deep=True)
    conflict.intent.motivation_summary = "충돌 결과"
    with pytest.raises(IdempotencyConflictError):
        sink.save_batch([new_result, conflict])
    assert sink.get(new_result.idempotency_key) is None
    assert sink.get(stored.idempotency_key) == stored


def test_internal_conflict_does_not_partially_save_other_result() -> None:
    sink = InMemoryRuntimeResultSink()
    first = make_result(agent_index=0)
    conflict = first.model_copy(deep=True)
    conflict.intent.motivation_summary = "충돌 결과"
    other = make_result(agent_index=1)
    with pytest.raises(IdempotencyConflictError):
        sink.save_batch([other, first, conflict])
    assert sink.list_results() == []


def test_empty_batch_is_successful() -> None:
    saved = InMemoryRuntimeResultSink().save_batch([])
    assert saved.new_count == 0
    assert saved.duplicate_count == 0


def test_batch_result_reports_new_and_duplicate_counts() -> None:
    sink = InMemoryRuntimeResultSink()
    existing = make_result(agent_index=0)
    new_result = make_result(agent_index=1)
    sink.save_batch([existing])
    saved = sink.save_batch([existing.model_copy(deep=True), new_result])
    assert saved.new_count == 1
    assert saved.duplicate_count == 1


def test_stored_result_is_isolated_from_caller_mutation() -> None:
    sink = InMemoryRuntimeResultSink()
    result = make_result()
    original_summary = result.intent.motivation_summary
    sink.save_batch([result])
    result.intent.motivation_summary = "호출자가 변경한 값"
    assert sink.get(result.idempotency_key).intent.motivation_summary == original_summary


def test_sink_contract_contains_no_raw_llm_response() -> None:
    sink = InMemoryRuntimeResultSink()
    result = make_result()
    sink.save_batch([result])
    stored = sink.get(result.idempotency_key).model_dump(mode="json")
    assert "current_llm_response" not in stored
    assert "raw_response" not in stored
