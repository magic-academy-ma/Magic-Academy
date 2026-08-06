from copy import deepcopy
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.simulation.agent_runtime import (
    AgentContext,
    AgentRuntimeInput,
    AgentRuntimeResult,
    EventSummary,
    MockLLMClient,
    RuntimeStatus,
    ScheduleSummary,
    validate_intent_candidate,
)


STUDENT_IDS = [UUID(f"00000000-0000-0000-0000-{index:012d}") for index in range(1, 6)]
LOCATION_IDS = [UUID(f"10000000-0000-0000-0000-{index:012d}") for index in range(1, 6)]
CLASS_EVENT_ID = UUID("20000000-0000-0000-0000-000000000001")


@pytest.fixture()
def runtime_input() -> AgentRuntimeInput:
    return AgentRuntimeInput(
        run_id="slice-1-run",
        tick_number=3,
        block="MORNING",
        agent=AgentContext(
            agent_id=STUDENT_IDS[0],
            fixture_key="student-01",
            agent_type="student",
            mbti="ISTJ",
            current_location_id=LOCATION_IDS[0],
            active_status=True,
        ),
        nearby_agents=[],
        relationships=[],
        memories=[],
        events=[
            EventSummary(
                event_id=CLASS_EVENT_ID,
                event_type="class",
                location_id=LOCATION_IDS[0],
                participant_agent_ids=[STUDENT_IDS[0]],
                title="통합마법학",
            )
        ],
        schedule=ScheduleSummary(
            event_id=CLASS_EVENT_ID,
            schedule_type="class",
            is_mandatory=True,
            location_id=LOCATION_IDS[0],
            start_tick=3,
            end_tick=3,
        ),
        valid_agent_ids=STUDENT_IDS,
        valid_location_ids=LOCATION_IDS,
    )


def valid_response(runtime_input: AgentRuntimeInput) -> dict:
    return MockLLMClient().generate(runtime_input)


def test_valid_attend_class_response(runtime_input: AgentRuntimeInput) -> None:
    candidate = validate_intent_candidate(valid_response(runtime_input), runtime_input)
    assert candidate.action_type.value == "ATTEND_CLASS"
    assert candidate.target_agent_id is None
    assert candidate.target_location_id == LOCATION_IDS[0]
    assert candidate.related_event_id == CLASS_EVENT_ID


def test_output_must_be_one_intent_object(runtime_input: AgentRuntimeInput) -> None:
    with pytest.raises(ValidationError):
        validate_intent_candidate([valid_response(runtime_input)], runtime_input)


def test_missing_required_field_is_rejected(runtime_input: AgentRuntimeInput) -> None:
    response = valid_response(runtime_input)
    del response["motivation_summary"]
    with pytest.raises(ValidationError):
        validate_intent_candidate(response, runtime_input)


def test_unknown_action_type_is_rejected(runtime_input: AgentRuntimeInput) -> None:
    response = valid_response(runtime_input)
    response["action_type"] = "FLY"
    with pytest.raises(ValidationError):
        validate_intent_candidate(response, runtime_input)


def test_action_not_allowed_for_role_is_rejected(runtime_input: AgentRuntimeInput) -> None:
    response = valid_response(runtime_input)
    response["action_type"] = "TEACH_CLASS"
    response["decision_explanation"]["alternatives"][0]["action_type"] = "TEACH_CLASS"
    with pytest.raises(ValueError, match="not allowed for student"):
        validate_intent_candidate(response, runtime_input)


def test_invalid_agent_reference_is_rejected(runtime_input: AgentRuntimeInput) -> None:
    response = valid_response(runtime_input)
    response["action_type"] = "TALK"
    response["target_agent_id"] = "30000000-0000-0000-0000-000000000001"
    response["target_location_id"] = None
    response["related_event_id"] = None
    response["decision_explanation"]["alternatives"][0]["action_type"] = "TALK"
    with pytest.raises(ValueError, match="target_agent_id"):
        validate_intent_candidate(response, runtime_input)


def test_invalid_location_reference_is_rejected(runtime_input: AgentRuntimeInput) -> None:
    response = valid_response(runtime_input)
    response["target_location_id"] = "30000000-0000-0000-0000-000000000002"
    with pytest.raises(ValueError, match="target_location_id"):
        validate_intent_candidate(response, runtime_input)


def test_event_not_in_input_is_rejected(runtime_input: AgentRuntimeInput) -> None:
    response = valid_response(runtime_input)
    response["related_event_id"] = "30000000-0000-0000-0000-000000000003"
    with pytest.raises(ValueError, match="related_event_id"):
        validate_intent_candidate(response, runtime_input)


def test_malformed_uuid_is_rejected(runtime_input: AgentRuntimeInput) -> None:
    response = valid_response(runtime_input)
    response["target_location_id"] = "not-a-uuid"
    with pytest.raises(ValidationError):
        validate_intent_candidate(response, runtime_input)


@pytest.mark.parametrize(
    ("container", "field_name", "value"),
    [
        ("reaction", "relationship_delta", {"trust": 3}),
        ("reaction", "state_delta", {"fatigue": 2}),
        (None, "effects", {"fatigue": "UP"}),
    ],
)
def test_unknown_effect_or_numeric_delta_rejects_entire_output(
    runtime_input: AgentRuntimeInput, container: str | None, field_name: str, value: object
) -> None:
    response = valid_response(runtime_input)
    target = response if container is None else response[container]
    target[field_name] = value
    with pytest.raises(ValidationError):
        validate_intent_candidate(response, runtime_input)


def test_runtime_management_field_from_llm_is_rejected(runtime_input: AgentRuntimeInput) -> None:
    response = valid_response(runtime_input)
    response["status"] = "PROPOSED"
    with pytest.raises(ValidationError):
        validate_intent_candidate(response, runtime_input)


@pytest.mark.parametrize("importance", [0, 11])
def test_memory_importance_must_be_between_one_and_ten(
    runtime_input: AgentRuntimeInput, importance: int
) -> None:
    response = valid_response(runtime_input)
    response["memory_candidates"][0]["importance"] = importance
    with pytest.raises(ValidationError):
        validate_intent_candidate(response, runtime_input)


def test_decision_explanation_structure_is_validated(runtime_input: AgentRuntimeInput) -> None:
    response = valid_response(runtime_input)
    response["decision_explanation"]["alternatives"][0]["relative_priority"] = "URGENT"
    with pytest.raises(ValidationError):
        validate_intent_candidate(response, runtime_input)


def test_selected_alternative_must_match_action(runtime_input: AgentRuntimeInput) -> None:
    response = valid_response(runtime_input)
    response["decision_explanation"]["alternatives"][0]["action_type"] = "STUDY"
    with pytest.raises(ValidationError, match="selected alternative"):
        validate_intent_candidate(response, runtime_input)


def test_action_requiring_agent_target_rejects_null(runtime_input: AgentRuntimeInput) -> None:
    response = valid_response(runtime_input)
    response["action_type"] = "TALK"
    response["target_location_id"] = None
    response["related_event_id"] = None
    response["decision_explanation"]["alternatives"][0]["action_type"] = "TALK"
    with pytest.raises(ValueError, match="requires target_agent_id"):
        validate_intent_candidate(response, runtime_input)


def test_mock_client_default_response_matches_section_10_1(
    runtime_input: AgentRuntimeInput,
) -> None:
    response = MockLLMClient().generate(runtime_input)
    candidate = validate_intent_candidate(response, runtime_input)
    assert candidate.action_type.value == "ATTEND_CLASS"
    assert "relationship_delta" not in response
    assert "state_delta" not in response


def test_mock_client_accepts_injected_response(runtime_input: AgentRuntimeInput) -> None:
    injected = deepcopy(valid_response(runtime_input))
    del injected["utterance"]
    response = MockLLMClient(injected).generate(runtime_input)
    with pytest.raises(ValidationError):
        validate_intent_candidate(response, runtime_input)


def test_runtime_result_serializes_uuid_as_json_string(runtime_input: AgentRuntimeInput) -> None:
    candidate = validate_intent_candidate(valid_response(runtime_input), runtime_input)
    result = AgentRuntimeResult(
        run_id=runtime_input.run_id,
        tick_number=runtime_input.tick_number,
        agent_id=runtime_input.agent.agent_id,
        status=RuntimeStatus.PROPOSED,
        intent=candidate,
        retry_count=0,
        failure_reason=None,
        model="mock-llm",
        prompt_version="agent-runtime-10.1",
        idempotency_key=(
            f"{runtime_input.run_id}:{runtime_input.tick_number}:"
            f"{runtime_input.agent.agent_id}"
        ),
    )
    serialized = result.model_dump(mode="json")
    assert serialized["agent_id"] == str(STUDENT_IDS[0])
    assert serialized["intent"]["related_event_id"] == str(CLASS_EVENT_ID)


def test_runtime_input_rejects_schedule_event_type_mismatch() -> None:
    with pytest.raises(ValidationError, match="schedule_type"):
        AgentRuntimeInput(
            run_id="slice-1-run",
            tick_number=3,
            block="MORNING",
            agent={
                "agent_id": STUDENT_IDS[0],
                "fixture_key": "student-01",
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
                    "participant_agent_ids": [STUDENT_IDS[0]],
                }
            ],
            schedule={
                "event_id": CLASS_EVENT_ID,
                "schedule_type": "exam",
                "is_mandatory": True,
                "location_id": LOCATION_IDS[0],
                "start_tick": 3,
                "end_tick": 3,
            },
            valid_agent_ids=STUDENT_IDS,
            valid_location_ids=LOCATION_IDS,
        )
