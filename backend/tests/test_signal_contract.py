from typing import get_type_hints
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.simulation.tick_engine import (
    AgentReaction,
    AgentRuntimeResult,
    PolicyInput,
    RelationshipSignal,
    RelationshipSignalType,
    SignalIntensity,
    StateSignal,
    StateSignalType,
)


AGENT_ID = UUID("00000000-0000-0000-0000-000000000001")
TARGET_AGENT_ID = UUID("00000000-0000-0000-0000-000000000002")


def test_signal_enum_contract_is_frozen() -> None:
    assert {item.value for item in SignalIntensity} == {"LOW", "MEDIUM", "HIGH"}
    assert {item.value for item in RelationshipSignalType} == {
        "TRUST_UP",
        "TRUST_DOWN",
        "AFFECTION_UP",
        "AFFECTION_DOWN",
        "CLOSENESS_UP",
        "CLOSENESS_DOWN",
        "TENSION_UP",
        "TENSION_DOWN",
        "RIVALRY_UP",
        "RIVALRY_DOWN",
        "DEPENDENCY_UP",
        "DEPENDENCY_DOWN",
    }
    assert {item.value for item in StateSignalType} == {
        "HUNGER_UP",
        "HUNGER_DOWN",
        "FATIGUE_UP",
        "FATIGUE_DOWN",
        "STRESS_UP",
        "STRESS_DOWN",
        "SATISFACTION_UP",
        "SATISFACTION_DOWN",
        "MOOD_UP",
        "MOOD_DOWN",
    }


def test_signal_models_have_per_signal_intensity_and_required_target() -> None:
    relationship_signal = RelationshipSignal(
        signal_type="TRUST_UP",
        intensity="HIGH",
        target_agent_id=TARGET_AGENT_ID,
    )
    state_signal = StateSignal(signal_type="FATIGUE_UP", intensity="LOW")

    assert relationship_signal.intensity is SignalIntensity.HIGH
    assert relationship_signal.target_agent_id == TARGET_AGENT_ID
    assert state_signal.intensity is SignalIntensity.LOW

    with pytest.raises(ValidationError, match="target_agent_id"):
        RelationshipSignal(signal_type="TRUST_UP", intensity="LOW")


def test_agent_reaction_defaults_to_empty_signal_lists() -> None:
    reaction = AgentReaction(valence="NEUTRAL")

    assert reaction.relationship_signals == []
    assert reaction.state_signals == []


def test_agent_reaction_rejects_legacy_numeric_delta() -> None:
    with pytest.raises(ValidationError, match="relationship_delta"):
        AgentReaction(valence="POSITIVE", relationship_delta={"trust": 5})


def test_policy_input_uses_agent_runtime_result_contract() -> None:
    assert get_type_hints(PolicyInput)["runtime_result"] is AgentRuntimeResult
