from copy import deepcopy
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.simulation.agent_runtime import (
    AgentContext,
    AgentRuntimeInput,
    AgentRuntimeResult,
    EventSummary,
    MemoryType,
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
            name="아델",
            mbti="ISTJ",
            big_five={
                "openness": -25,
                "conscientiousness": 25,
                "extraversion": -25,
                "agreeableness": -20,
                "emotional_stability": 0,
            },
            state={
                "hunger": 25,
                "fatigue": 15,
                "stress": 20,
                "satisfaction": 60,
                "mood": 0,
            },
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
    assert candidate.reaction.state_signals[0].signal_type.value == "FATIGUE_UP"
    assert candidate.reaction.state_signals[0].intensity.value == "LOW"


def test_typed_relationship_signal_accepts_valid_other_agent(
    runtime_input: AgentRuntimeInput,
) -> None:
    response = valid_response(runtime_input)
    response["reaction"]["relationship_signals"] = [
        {
            "signal_type": "TRUST_UP",
            "intensity": "HIGH",
            "target_agent_id": str(STUDENT_IDS[1]),
        }
    ]

    candidate = validate_intent_candidate(response, runtime_input)

    signal = candidate.reaction.relationship_signals[0]
    assert signal.signal_type.value == "TRUST_UP"
    assert signal.intensity.value == "HIGH"
    assert signal.target_agent_id == STUDENT_IDS[1]


def test_relationship_signal_rejects_target_outside_valid_agents(
    runtime_input: AgentRuntimeInput,
) -> None:
    response = valid_response(runtime_input)
    response["reaction"]["relationship_signals"] = [
        {
            "signal_type": "TRUST_UP",
            "intensity": "LOW",
            "target_agent_id": "30000000-0000-0000-0000-000000000001",
        }
    ]

    with pytest.raises(ValueError, match="relationship signal target_agent_id"):
        validate_intent_candidate(response, runtime_input)


def test_relationship_signal_rejects_self_target(
    runtime_input: AgentRuntimeInput,
) -> None:
    response = valid_response(runtime_input)
    response["reaction"]["relationship_signals"] = [
        {
            "signal_type": "TRUST_UP",
            "intensity": "LOW",
            "target_agent_id": str(runtime_input.agent.agent_id),
        }
    ]

    with pytest.raises(ValueError, match="cannot target the acting agent"):
        validate_intent_candidate(response, runtime_input)


def test_reaction_rejects_legacy_common_intensity(
    runtime_input: AgentRuntimeInput,
) -> None:
    response = valid_response(runtime_input)
    response["reaction"]["intensity"] = "LOW"

    with pytest.raises(ValidationError, match="intensity"):
        validate_intent_candidate(response, runtime_input)


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


def test_reflection_memory_candidate_is_accepted(
    runtime_input: AgentRuntimeInput,
) -> None:
    response = valid_response(runtime_input)
    response["memory_candidates"][0]["memory_type"] = "REFLECTION"

    candidate = validate_intent_candidate(response, runtime_input)

    assert candidate.memory_candidates[0].memory_type is MemoryType.REFLECTION


@pytest.mark.parametrize(
    "memory_type",
    [MemoryType.OBSERVATION, MemoryType.CONVERSATION, MemoryType.PLAN],
)
def test_existing_memory_types_remain_valid(
    runtime_input: AgentRuntimeInput,
    memory_type: MemoryType,
) -> None:
    response = valid_response(runtime_input)
    response["memory_candidates"][0]["memory_type"] = memory_type.value

    candidate = validate_intent_candidate(response, runtime_input)

    assert candidate.memory_candidates[0].memory_type is memory_type


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


def test_study_without_target_is_valid(runtime_input: AgentRuntimeInput) -> None:
    response = valid_response(runtime_input)
    response["action_type"] = "STUDY"
    response["target_agent_id"] = None
    response["target_location_id"] = None
    response["related_event_id"] = None
    response["decision_explanation"]["alternatives"][0]["action_type"] = "STUDY"
    candidate = validate_intent_candidate(response, runtime_input)
    assert candidate.action_type.value == "STUDY"


@pytest.mark.parametrize("action_type", ["TALK", "HELP"])
def test_agent_action_with_other_target_is_valid(
    runtime_input: AgentRuntimeInput, action_type: str
) -> None:
    response = valid_response(runtime_input)
    response["action_type"] = action_type
    response["target_agent_id"] = str(STUDENT_IDS[1])
    response["target_location_id"] = None
    response["related_event_id"] = None
    response["decision_explanation"]["alternatives"][0]["action_type"] = action_type
    candidate = validate_intent_candidate(response, runtime_input)
    assert candidate.target_agent_id == STUDENT_IDS[1]


@pytest.mark.parametrize("action_type", ["TALK", "HELP"])
def test_agent_action_with_self_target_is_rejected(
    runtime_input: AgentRuntimeInput, action_type: str
) -> None:
    response = valid_response(runtime_input)
    response["action_type"] = action_type
    response["target_agent_id"] = str(runtime_input.agent.agent_id)
    response["target_location_id"] = None
    response["related_event_id"] = None
    response["decision_explanation"]["alternatives"][0]["action_type"] = action_type
    with pytest.raises(ValueError, match="cannot target the acting agent"):
        validate_intent_candidate(response, runtime_input)


@pytest.mark.parametrize("action_type", ["TALK", "HELP"])
def test_agent_action_without_target_is_rejected(
    runtime_input: AgentRuntimeInput, action_type: str
) -> None:
    response = valid_response(runtime_input)
    response["action_type"] = action_type
    response["target_agent_id"] = None
    response["target_location_id"] = None
    response["related_event_id"] = None
    response["decision_explanation"]["alternatives"][0]["action_type"] = action_type
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
    response = valid_response(runtime_input)
    response["reaction"]["relationship_signals"] = [
        {
            "signal_type": "TRUST_UP",
            "intensity": "MEDIUM",
            "target_agent_id": str(STUDENT_IDS[1]),
        }
    ]
    candidate = validate_intent_candidate(response, runtime_input)
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
    assert serialized["intent"]["reaction"] == {
        "valence": "NEUTRAL",
        "relationship_signals": [
            {
                "signal_type": "TRUST_UP",
                "intensity": "MEDIUM",
                "target_agent_id": str(STUDENT_IDS[1]),
            }
        ],
        "state_signals": [
            {"signal_type": "FATIGUE_UP", "intensity": "LOW"}
        ],
    }


@pytest.mark.parametrize("idempotency_key", ["", "   ", "\t\n", " key-with-spaces "])
def test_blank_idempotency_key_is_rejected(
    runtime_input: AgentRuntimeInput, idempotency_key: str
) -> None:
    candidate = validate_intent_candidate(valid_response(runtime_input), runtime_input)
    with pytest.raises(ValidationError, match="idempotency_key"):
        AgentRuntimeResult(
            run_id=runtime_input.run_id,
            tick_number=runtime_input.tick_number,
            agent_id=runtime_input.agent.agent_id,
            status=RuntimeStatus.PROPOSED,
            intent=candidate,
            retry_count=0,
            failure_reason=None,
            model="mock-llm",
            prompt_version="agent-runtime-10.1",
            idempotency_key=idempotency_key,
        )


def test_noncanonical_idempotency_key_is_rejected(
    runtime_input: AgentRuntimeInput,
) -> None:
    candidate = validate_intent_candidate(valid_response(runtime_input), runtime_input)

    with pytest.raises(ValidationError, match="run_id:tick_number:agent_id"):
        AgentRuntimeResult(
            run_id=runtime_input.run_id,
            tick_number=runtime_input.tick_number,
            agent_id=runtime_input.agent.agent_id,
            status=RuntimeStatus.PROPOSED,
            intent=candidate,
            retry_count=0,
            failure_reason=None,
            model="mock-llm",
            prompt_version="agent-runtime-10.1",
            idempotency_key="different:3:key",
        )


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
