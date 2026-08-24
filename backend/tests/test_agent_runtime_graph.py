from copy import deepcopy
from uuid import UUID

import pytest

from app.simulation.agent_runtime import (
    AgentRuntime,
    AgentRuntimeInput,
    LLMInvocationError,
    MockLLMClient,
    RuntimeStatus,
)


STUDENT_IDS = [UUID(f"00000000-0000-0000-0000-{index:012d}") for index in range(1, 6)]
LOCATION_IDS = [UUID(f"10000000-0000-0000-0000-{index:012d}") for index in range(1, 6)]
CLASS_EVENT_ID = UUID("20000000-0000-0000-0000-000000000001")


def make_runtime_input(*, active: bool = True) -> AgentRuntimeInput:
    return AgentRuntimeInput(
        run_id="slice-1-run",
        tick_number=3,
        block="MORNING",
        agent={
            "agent_id": STUDENT_IDS[0],
            "fixture_key": "student-01",
            "agent_type": "student",
            "name": "아델",
            "mbti": "ISTJ",
            "big_five": {
                "openness": 0,
                "conscientiousness": 0,
                "extraversion": 0,
                "agreeableness": 0,
                "emotional_stability": 0,
            },
            "state": {
                "hunger": 0,
                "fatigue": 0,
                "stress": 0,
                "satisfaction": 0,
                "mood": 0,
            },
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
                "participant_agent_ids": [STUDENT_IDS[0]],
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


class SequenceLLMClient:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.call_count = 0
        self.runtime_inputs: list[AgentRuntimeInput] = []

    def generate(self, runtime_input: AgentRuntimeInput) -> object:
        self.runtime_inputs.append(runtime_input)
        outcome = self.outcomes[self.call_count]
        self.call_count += 1
        if isinstance(outcome, Exception):
            raise outcome
        return deepcopy(outcome)


def valid_response(runtime_input: AgentRuntimeInput) -> object:
    return MockLLMClient().generate(runtime_input)


def invalid_response(runtime_input: AgentRuntimeInput) -> dict:
    response = deepcopy(valid_response(runtime_input))
    del response["motivation_summary"]
    return response


def self_target_response(runtime_input: AgentRuntimeInput) -> dict:
    response = deepcopy(valid_response(runtime_input))
    response["action_type"] = "TALK"
    response["target_agent_id"] = str(runtime_input.agent.agent_id)
    response["target_location_id"] = None
    response["related_event_id"] = None
    response["decision_explanation"]["alternatives"][0]["action_type"] = "TALK"
    return response


def test_first_call_success_returns_proposed() -> None:
    runtime_input = make_runtime_input()
    client = SequenceLLMClient([valid_response(runtime_input)])
    result = AgentRuntime(client, model="mock", prompt_version="10.1").run(runtime_input)
    assert result.status == RuntimeStatus.PROPOSED
    assert result.retry_count == 0
    assert result.failure_reason is None
    assert client.call_count == 1


def test_validation_failure_then_retry_success() -> None:
    runtime_input = make_runtime_input()
    client = SequenceLLMClient([invalid_response(runtime_input), valid_response(runtime_input)])
    result = AgentRuntime(client).run(runtime_input)
    assert result.status == RuntimeStatus.PROPOSED
    assert result.retry_count == 1
    assert result.failure_reason is None
    assert client.call_count == 2
    assert client.runtime_inputs == [runtime_input, runtime_input]


def test_two_validation_failures_return_wait_fallback() -> None:
    runtime_input = make_runtime_input()
    client = SequenceLLMClient([invalid_response(runtime_input), invalid_response(runtime_input)])
    result = AgentRuntime(client).run(runtime_input)
    assert result.status == RuntimeStatus.FALLBACK
    assert result.intent.action_type.value == "WAIT"
    assert result.retry_count == 1
    assert "motivation_summary" in result.failure_reason
    assert client.call_count == 2


def test_retryable_llm_failure_then_success() -> None:
    runtime_input = make_runtime_input()
    client = SequenceLLMClient(
        [LLMInvocationError("temporary failure"), valid_response(runtime_input)]
    )
    result = AgentRuntime(client).run(runtime_input)
    assert result.status == RuntimeStatus.PROPOSED
    assert result.retry_count == 1
    assert result.failure_reason is None
    assert client.call_count == 2


def test_two_retryable_llm_failures_return_wait_fallback() -> None:
    runtime_input = make_runtime_input()
    client = SequenceLLMClient(
        [LLMInvocationError("first failure"), LLMInvocationError("final failure")]
    )
    result = AgentRuntime(client).run(runtime_input)
    assert result.status == RuntimeStatus.FALLBACK
    assert result.intent.action_type.value == "WAIT"
    assert result.retry_count == 1
    assert result.failure_reason == "LLMInvocationError: final failure"


def test_llm_is_never_called_more_than_twice() -> None:
    runtime_input = make_runtime_input()
    client = SequenceLLMClient(
        [
            LLMInvocationError("first"),
            LLMInvocationError("second"),
            valid_response(runtime_input),
        ]
    )
    AgentRuntime(client).run(runtime_input)
    assert client.call_count == 2


def test_unhandled_graph_exception_propagates() -> None:
    runtime_input = make_runtime_input()
    client = SequenceLLMClient([RuntimeError("programming error")])
    with pytest.raises(RuntimeError, match="programming error"):
        AgentRuntime(client).run(runtime_input)


def test_inactive_agent_is_skipped_without_llm_call() -> None:
    runtime_input = make_runtime_input(active=False)
    client = SequenceLLMClient([valid_response(runtime_input)])
    result = AgentRuntime(client).run(runtime_input)
    assert result.status == RuntimeStatus.SKIPPED
    assert result.intent.action_type.value == "WAIT"
    assert result.retry_count == 0
    assert result.failure_reason is None
    assert client.call_count == 0


def test_graph_state_tracks_attempts_failure_and_final_result() -> None:
    runtime_input = make_runtime_input()
    client = SequenceLLMClient([invalid_response(runtime_input), invalid_response(runtime_input)])
    state = AgentRuntime(client).run_state(runtime_input)
    assert state["attempt_count"] == 2
    assert state["last_validation_failure"] is not None
    assert state["final_result"].retry_count == 1


def test_self_target_validation_failure_uses_existing_retry_flow() -> None:
    runtime_input = make_runtime_input()
    invalid = self_target_response(runtime_input)
    client = SequenceLLMClient([invalid, invalid])
    result = AgentRuntime(client).run(runtime_input)
    assert client.call_count == 2
    assert result.status == RuntimeStatus.FALLBACK
    assert result.retry_count == 1
    assert "cannot target the acting agent" in result.failure_reason
