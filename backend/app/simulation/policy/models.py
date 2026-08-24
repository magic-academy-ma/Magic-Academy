from dataclasses import dataclass, field
from enum import Enum

from app.domain.relationship_metrics import RELATIONSHIP_METRIC_RANGES
from app.simulation.agent_runtime import AgentRuntimeResult

METRIC_RANGE: dict[str, tuple[int, int]] = {
    **RELATIONSHIP_METRIC_RANGES,
    "mood": (-100, 100),
    "hunger": (0, 100),
    "fatigue": (0, 100),
    "stress": (0, 100),
    "satisfaction": (0, 100),
}


class PolicyStatus(str, Enum):
    EVALUATED = "EVALUATED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"


class EffectTargetType(str, Enum):
    RELATIONSHIP = "RELATIONSHIP"
    AGENT_STATE = "AGENT_STATE"


@dataclass
class AgentSnapshot:
    agent_id: str
    hunger: int
    fatigue: int
    stress: int
    satisfaction: int
    mood: int = 0


@dataclass
class RelationshipSnapshot:
    source_agent_id: str
    target_agent_id: str
    trust: int
    tension: int
    affection: int = 0
    closeness: int = 0
    rivalry: int = 0
    dependency: int = 0


@dataclass
class PolicyEvaluationInput:
    run_id: str
    tick_number: int
    policy_version: str
    agent_snapshots: dict[str, AgentSnapshot]
    relationship_snapshots: list[RelationshipSnapshot]
    runtime_results: list[AgentRuntimeResult]
    valid_agent_ids: set[str]


@dataclass
class EffectCandidate:
    effect_id: str
    target_type: EffectTargetType
    source_agent_id: str
    target_agent_id: str | None
    metric: str
    delta: int
    before: int
    after_preview: int
    rule_id: str
    reason: str
    effect_ids: tuple[str, ...] = ()


@dataclass
class PolicyEvaluationResult:
    run_id: str
    tick_number: int
    policy_version: str
    status: PolicyStatus
    effect_candidates: list[EffectCandidate] = field(default_factory=list)
    rejected_effects: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
