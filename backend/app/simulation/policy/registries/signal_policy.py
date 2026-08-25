from app.simulation.agent_runtime import (
    RelationshipSignalType,
    SignalIntensity,
    StateSignalType,
)

INTENSITY_TO_RELATIONSHIP_BASE: dict[SignalIntensity, int] = {
    SignalIntensity.LOW: 1,
    SignalIntensity.MEDIUM: 3,
    SignalIntensity.HIGH: 5,
}

INTENSITY_TO_STATE_BASE: dict[SignalIntensity, int] = {
    SignalIntensity.LOW: 2,
    SignalIntensity.MEDIUM: 5,
    SignalIntensity.HIGH: 8,
}

_RELATIONSHIP_SIGN: dict[RelationshipSignalType, int] = {
    RelationshipSignalType.TRUST_UP: 1,
    RelationshipSignalType.TRUST_DOWN: -1,
    RelationshipSignalType.TENSION_UP: 1,
    RelationshipSignalType.TENSION_DOWN: -1,
    RelationshipSignalType.AFFECTION_UP: 1,
    RelationshipSignalType.AFFECTION_DOWN: -1,
    RelationshipSignalType.CLOSENESS_UP: 1,
    RelationshipSignalType.CLOSENESS_DOWN: -1,
    RelationshipSignalType.RIVALRY_UP: 1,
    RelationshipSignalType.RIVALRY_DOWN: -1,
    RelationshipSignalType.DEPENDENCY_UP: 1,
    RelationshipSignalType.DEPENDENCY_DOWN: -1,
}

_STATE_SIGN: dict[StateSignalType, int] = {
    StateSignalType.HUNGER_UP: 1,
    StateSignalType.HUNGER_DOWN: -1,
    StateSignalType.FATIGUE_UP: 1,
    StateSignalType.FATIGUE_DOWN: -1,
    StateSignalType.STRESS_UP: 1,
    StateSignalType.STRESS_DOWN: -1,
    StateSignalType.SATISFACTION_UP: 1,
    StateSignalType.SATISFACTION_DOWN: -1,
    StateSignalType.MOOD_UP: 1,
    StateSignalType.MOOD_DOWN: -1,
}


def get_relationship_delta(
    signal_type: RelationshipSignalType, intensity: SignalIntensity
) -> int:
    return _RELATIONSHIP_SIGN[signal_type] * INTENSITY_TO_RELATIONSHIP_BASE[intensity]


def get_state_delta(signal_type: StateSignalType, intensity: SignalIntensity) -> int:
    return _STATE_SIGN[signal_type] * INTENSITY_TO_STATE_BASE[intensity]
