from copy import deepcopy
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.simulation.agent_context_assembler import AgentContextAssembler
from app.simulation.agent_runtime import (
    AgentRuntime,
    BigFiveContext,
    EventSummary,
    MockLLMClient,
    RuntimeStatus,
    ScheduleSummary,
    AgentStateContext,
)


STUDENT_IDS = [UUID(f"00000000-0000-0000-0000-{index:012d}") for index in range(1, 6)]
LOCATION_IDS = [UUID(f"10000000-0000-0000-0000-{index:012d}") for index in range(1, 6)]
CLASS_EVENT_ID = UUID("20000000-0000-0000-0000-000000000001")


def make_inputs() -> dict:
    return {
        "run_id": "slice-1-run",
        "tick_number": 3,
        "block": "MORNING",
        "agent_id": STUDENT_IDS[0],
        "fixture_key": "student-01",
        "agent_type": "student",
        "name": "아델",
        "mbti": "ISTJ",
        "big_five": BigFiveContext(
            openness=-25,
            conscientiousness=25,
            extraversion=-25,
            agreeableness=-20,
            emotional_stability=0,
        ),
        "state": AgentStateContext(
            hunger=25,
            fatigue=15,
            stress=20,
            satisfaction=60,
            mood=0,
        ),
        "current_location_id": LOCATION_IDS[0],
        "active_status": True,
        "events": [
            EventSummary(
                event_id=CLASS_EVENT_ID,
                event_type="class",
                location_id=LOCATION_IDS[0],
                participant_agent_ids=[STUDENT_IDS[0]],
                title="통합마법학",
            )
        ],
        "schedule": ScheduleSummary(
            event_id=CLASS_EVENT_ID,
            schedule_type="class",
            is_mandatory=True,
            location_id=LOCATION_IDS[0],
            start_tick=3,
            end_tick=3,
        ),
        "valid_agent_ids": STUDENT_IDS.copy(),
        "valid_location_ids": LOCATION_IDS.copy(),
    }


def test_assembles_slice_one_student_class_context() -> None:
    runtime_input = AgentContextAssembler().assemble(**make_inputs())

    assert runtime_input.agent.name == "아델"
    assert runtime_input.agent.mbti.value == "ISTJ"
    assert runtime_input.agent.big_five.conscientiousness == 25
    assert runtime_input.agent.state.satisfaction == 60
    assert runtime_input.agent.current_location_id == LOCATION_IDS[0]
    assert runtime_input.agent.active_status is True
    assert runtime_input.agent.agent_id == STUDENT_IDS[0]
    assert runtime_input.events[0].event_id == CLASS_EVENT_ID
    assert runtime_input.valid_agent_ids == STUDENT_IDS
    assert runtime_input.valid_location_ids == LOCATION_IDS
    assert runtime_input.relationships == []
    assert runtime_input.memories == []
    assert runtime_input.nearby_agents == []
    assert runtime_input.model_dump(mode="json")["events"][0]["event_type"] == "class"


def test_preserves_collection_order_without_mutating_inputs() -> None:
    inputs = make_inputs()
    inputs["valid_agent_ids"] = list(reversed(STUDENT_IDS))
    inputs["valid_location_ids"] = list(reversed(LOCATION_IDS))
    original = deepcopy(inputs)

    runtime_input = AgentContextAssembler().assemble(**inputs)

    assert runtime_input.valid_agent_ids == list(reversed(STUDENT_IDS))
    assert runtime_input.valid_location_ids == list(reversed(LOCATION_IDS))
    assert inputs == original


def test_same_input_produces_equal_runtime_input() -> None:
    inputs = make_inputs()
    assembler = AgentContextAssembler()

    assert assembler.assemble(**inputs) == assembler.assemble(**inputs)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("agent_id", "not-a-uuid"),
        ("current_location_id", "not-a-uuid"),
    ],
)
def test_invalid_normalized_input_uses_existing_schema_validation(
    field_name: str, invalid_value: str
) -> None:
    inputs = make_inputs()
    inputs[field_name] = invalid_value

    with pytest.raises(ValidationError):
        AgentContextAssembler().assemble(**inputs)


def test_active_status_rejects_string_coercion() -> None:
    inputs = make_inputs()
    inputs["active_status"] = "true"

    with pytest.raises(ValidationError):
        AgentContextAssembler().assemble(**inputs)


@pytest.mark.parametrize(
    ("context_type", "field_name", "invalid_value"),
    [
        (BigFiveContext, "openness", -51),
        (BigFiveContext, "emotional_stability", 51),
        (AgentStateContext, "hunger", -1),
        (AgentStateContext, "fatigue", 101),
        (AgentStateContext, "stress", 101),
        (AgentStateContext, "satisfaction", -1),
        (AgentStateContext, "mood", -101),
        (AgentStateContext, "mood", 101),
    ],
)
def test_personality_and_state_ranges_are_enforced(
    context_type: type, field_name: str, invalid_value: int
) -> None:
    values = (
        {
            "openness": 0,
            "conscientiousness": 0,
            "extraversion": 0,
            "agreeableness": 0,
            "emotional_stability": 0,
        }
        if context_type is BigFiveContext
        else {
            "hunger": 0,
            "fatigue": 0,
            "stress": 0,
            "satisfaction": 0,
            "mood": 0,
        }
    )
    values[field_name] = invalid_value

    with pytest.raises(ValidationError):
        context_type(**values)


def test_assembled_input_runs_with_existing_runtime_and_mock_client() -> None:
    runtime_input = AgentContextAssembler().assemble(**make_inputs())

    result = AgentRuntime(MockLLMClient()).run(runtime_input)

    assert result.status == RuntimeStatus.PROPOSED
    assert result.agent_id == STUDENT_IDS[0]
