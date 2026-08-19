# TODO(kan-44): 가윤님 PR 머지 후 이 파일 삭제하고 tick_engine에서 import로 교체
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.simulation.tick_engine import MemoryCandidateItem


class RelationshipSignalType(str, Enum):
    TRUST_UP = "TRUST_UP"
    TRUST_DOWN = "TRUST_DOWN"
    TENSION_UP = "TENSION_UP"
    TENSION_DOWN = "TENSION_DOWN"
    AFFECTION_UP = "AFFECTION_UP"
    AFFECTION_DOWN = "AFFECTION_DOWN"
    CLOSENESS_UP = "CLOSENESS_UP"
    CLOSENESS_DOWN = "CLOSENESS_DOWN"
    RIVALRY_UP = "RIVALRY_UP"
    RIVALRY_DOWN = "RIVALRY_DOWN"
    DEPENDENCY_UP = "DEPENDENCY_UP"
    DEPENDENCY_DOWN = "DEPENDENCY_DOWN"


class StateSignalType(str, Enum):
    HUNGER_UP = "HUNGER_UP"
    HUNGER_DOWN = "HUNGER_DOWN"
    FATIGUE_UP = "FATIGUE_UP"
    FATIGUE_DOWN = "FATIGUE_DOWN"
    STRESS_UP = "STRESS_UP"
    STRESS_DOWN = "STRESS_DOWN"
    SATISFACTION_UP = "SATISFACTION_UP"
    SATISFACTION_DOWN = "SATISFACTION_DOWN"
    MOOD_UP = "MOOD_UP"
    MOOD_DOWN = "MOOD_DOWN"


class SignalIntensity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class RelationshipSignal:
    signal_type: RelationshipSignalType
    intensity: SignalIntensity
    target_agent_id: str


@dataclass
class StateSignal:
    signal_type: StateSignalType
    intensity: SignalIntensity


@dataclass
class AgentReaction:
    valence: str
    relationship_signals: list[RelationshipSignal] = field(default_factory=list)
    state_signals: list[StateSignal] = field(default_factory=list)


@dataclass
class AgentRuntimeResult:
    agent_id: str
    action_type: str
    target_agent_id: str | None = None
    reaction: AgentReaction | None = None
    memory_candidate: MemoryCandidateItem | None = None  # Slice 3 추가
