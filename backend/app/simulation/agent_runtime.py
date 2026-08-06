from copy import deepcopy
from enum import StrEnum
from typing import Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ActionType(StrEnum):
    ATTEND_CLASS = "ATTEND_CLASS"
    TEACH_CLASS = "TEACH_CLASS"
    STUDY = "STUDY"
    TALK = "TALK"
    EAT = "EAT"
    MOVE = "MOVE"
    REST = "REST"
    PARTICIPATE_EVENT = "PARTICIPATE_EVENT"
    HELP = "HELP"
    AVOID = "AVOID"
    WAIT = "WAIT"


class RuntimeStatus(StrEnum):
    PROPOSED = "PROPOSED"
    FALLBACK = "FALLBACK"
    SKIPPED = "SKIPPED"


class Block(StrEnum):
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    EVENING = "EVENING"


class MBTI(StrEnum):
    ISTJ = "ISTJ"
    ESTP = "ESTP"
    INFP = "INFP"
    ENTJ = "ENTJ"
    ESFJ = "ESFJ"


class EventType(StrEnum):
    CLASS = "class"
    GROUP_PROJECT = "group_project"
    EXAM = "exam"
    MEETING = "meeting"
    MT = "mt"
    FESTIVAL = "festival"
    STUDENT_COUNCIL = "student_council"
    RANDOM_INCIDENT = "random_incident"


class ReactionValence(StrEnum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


class Intensity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RelationshipSignal(StrEnum):
    TRUST_UP = "TRUST_UP"
    TRUST_DOWN = "TRUST_DOWN"
    AFFECTION_UP = "AFFECTION_UP"
    AFFECTION_DOWN = "AFFECTION_DOWN"
    CLOSENESS_UP = "CLOSENESS_UP"
    CLOSENESS_DOWN = "CLOSENESS_DOWN"
    TENSION_UP = "TENSION_UP"
    TENSION_DOWN = "TENSION_DOWN"
    RIVALRY_UP = "RIVALRY_UP"
    RIVALRY_DOWN = "RIVALRY_DOWN"
    DEPENDENCY_UP = "DEPENDENCY_UP"
    DEPENDENCY_DOWN = "DEPENDENCY_DOWN"


class StateSignal(StrEnum):
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


class MemoryType(StrEnum):
    OBSERVATION = "OBSERVATION"
    CONVERSATION = "CONVERSATION"
    PLAN = "PLAN"


class RelativePriority(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class InfluencingSource(StrEnum):
    STATE = "STATE"
    PERSONALITY = "PERSONALITY"
    RELATIONSHIP = "RELATIONSHIP"
    MEMORY = "MEMORY"
    SCHEDULE = "SCHEDULE"
    LOCATION = "LOCATION"
    EVENT = "EVENT"


class InfluenceDirection(StrEnum):
    SUPPORT = "SUPPORT"
    OPPOSE = "OPPOSE"


class AgentContext(StrictModel):
    agent_id: UUID
    fixture_key: str
    agent_type: Literal["student", "professor"]
    mbti: MBTI | None
    current_location_id: UUID | None
    active_status: bool


class EventSummary(StrictModel):
    event_id: UUID
    event_type: EventType
    location_id: UUID
    participant_agent_ids: list[UUID]
    title: str | None = None
    description: str | None = None


class ScheduleSummary(StrictModel):
    event_id: UUID
    schedule_type: EventType
    is_mandatory: bool
    location_id: UUID
    start_tick: int = Field(ge=0)
    end_tick: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_tick_range(self) -> "ScheduleSummary":
        if self.end_tick < self.start_tick:
            raise ValueError("end_tick must be greater than or equal to start_tick")
        return self


class AgentRuntimeInput(StrictModel):
    run_id: str
    tick_number: int = Field(ge=0)
    block: Block
    agent: AgentContext
    nearby_agents: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    memories: list[dict[str, Any]]
    events: list[EventSummary]
    schedule: ScheduleSummary
    valid_agent_ids: list[UUID]
    valid_location_ids: list[UUID]

    @model_validator(mode="after")
    def validate_references(self) -> "AgentRuntimeInput":
        events_by_id = {event.event_id: event for event in self.events}
        scheduled_event = events_by_id.get(self.schedule.event_id)
        if scheduled_event is None:
            raise ValueError("schedule event_id must be included in events")
        if scheduled_event.event_type != self.schedule.schedule_type:
            raise ValueError("schedule_type must match the linked event_type")
        if scheduled_event.location_id != self.schedule.location_id:
            raise ValueError("schedule location_id must match the linked event location_id")
        return self


class Reaction(StrictModel):
    valence: ReactionValence
    intensity: Intensity
    relationship_signals: list[RelationshipSignal]
    state_signals: list[StateSignal]


class ActionAlternative(StrictModel):
    action_type: ActionType
    description: str
    relative_priority: RelativePriority
    selected: bool


class InfluencingFactor(StrictModel):
    source: InfluencingSource
    description: str
    direction: InfluenceDirection


class DecisionExplanation(StrictModel):
    alternatives: list[ActionAlternative] = Field(min_length=1, max_length=3)
    influencing_factors: list[InfluencingFactor]


class MemoryCandidate(StrictModel):
    memory_type: MemoryType
    content: str
    importance: int = Field(ge=1, le=10)
    related_agent_ids: list[UUID]
    related_event_id: UUID | None


class IntentCandidate(StrictModel):
    action_type: ActionType
    target_agent_id: UUID | None
    target_location_id: UUID | None
    related_event_id: UUID | None
    utterance: str | None
    motivation_summary: str
    reaction: Reaction
    decision_explanation: DecisionExplanation
    memory_candidates: list[MemoryCandidate]

    @model_validator(mode="after")
    def validate_selected_alternative(self) -> "IntentCandidate":
        selected = [item for item in self.decision_explanation.alternatives if item.selected]
        if len(selected) != 1 or selected[0].action_type != self.action_type:
            raise ValueError("exactly one selected alternative must match the selected action_type")
        return self


class AgentRuntimeResult(StrictModel):
    run_id: str
    tick_number: int = Field(ge=0)
    agent_id: UUID
    status: RuntimeStatus
    intent: IntentCandidate
    retry_count: int = Field(ge=0)
    failure_reason: str | None
    model: str
    prompt_version: str
    idempotency_key: str


STUDENT_ACTIONS = set(ActionType) - {ActionType.TEACH_CLASS}
PROFESSOR_ACTIONS = set(ActionType) - {ActionType.ATTEND_CLASS}


def validate_intent_candidate(
    raw_output: object, runtime_input: AgentRuntimeInput
) -> IntentCandidate:
    candidate = IntentCandidate.model_validate(raw_output)
    allowed_actions = (
        STUDENT_ACTIONS if runtime_input.agent.agent_type == "student" else PROFESSOR_ACTIONS
    )
    if candidate.action_type not in allowed_actions:
        raise ValueError(
            f"action {candidate.action_type} is not allowed for {runtime_input.agent.agent_type}"
        )
    if (
        candidate.target_agent_id is not None
        and candidate.target_agent_id not in runtime_input.valid_agent_ids
    ):
        raise ValueError("target_agent_id is not included in valid_agent_ids")
    if (
        candidate.target_location_id is not None
        and candidate.target_location_id not in runtime_input.valid_location_ids
    ):
        raise ValueError("target_location_id is not included in valid_location_ids")
    valid_event_ids = {event.event_id for event in runtime_input.events}
    if candidate.related_event_id is not None and candidate.related_event_id not in valid_event_ids:
        raise ValueError("related_event_id is not included in runtime events")
    for memory in candidate.memory_candidates:
        if any(
            agent_id not in runtime_input.valid_agent_ids
            for agent_id in memory.related_agent_ids
        ):
            raise ValueError("memory candidate contains an invalid related_agent_id")
        if memory.related_event_id is not None and memory.related_event_id not in valid_event_ids:
            raise ValueError("memory candidate contains an invalid related_event_id")
    _validate_action_targets(candidate)
    return candidate


def _validate_action_targets(candidate: IntentCandidate) -> None:
    if candidate.action_type in {ActionType.TALK, ActionType.HELP}:
        if candidate.target_agent_id is None:
            raise ValueError(f"{candidate.action_type} requires target_agent_id")
    if candidate.action_type in {ActionType.EAT, ActionType.MOVE, ActionType.REST}:
        if candidate.target_location_id is None:
            raise ValueError(f"{candidate.action_type} requires target_location_id")
    if candidate.action_type in {
        ActionType.ATTEND_CLASS,
        ActionType.TEACH_CLASS,
        ActionType.PARTICIPATE_EVENT,
    }:
        if candidate.related_event_id is None:
            raise ValueError(f"{candidate.action_type} requires related_event_id")
    if candidate.action_type in {ActionType.ATTEND_CLASS, ActionType.TEACH_CLASS}:
        if candidate.target_location_id is None:
            raise ValueError(f"{candidate.action_type} requires target_location_id")
    if candidate.action_type == ActionType.AVOID:
        if candidate.target_agent_id is None and candidate.related_event_id is None:
            raise ValueError("AVOID requires target_agent_id or related_event_id")
    if candidate.action_type == ActionType.WAIT:
        if any(
            value is not None
            for value in (
                candidate.target_agent_id,
                candidate.target_location_id,
                candidate.related_event_id,
            )
        ):
            raise ValueError("WAIT does not accept a target or related event")


class LLMClient(Protocol):
    def generate(self, runtime_input: AgentRuntimeInput) -> object: ...


class MockLLMClient:
    def __init__(self, response: object | None = None) -> None:
        self._response = response

    def generate(self, runtime_input: AgentRuntimeInput) -> object:
        if self._response is not None:
            return deepcopy(self._response)
        if runtime_input.agent.fixture_key != "student-01":
            raise ValueError("default mock response is only defined for student-01")
        class_event = next(
            event for event in runtime_input.events if event.event_type == EventType.CLASS
        )
        response = {
            "action_type": "ATTEND_CLASS",
            "target_agent_id": None,
            "target_location_id": str(class_event.location_id),
            "related_event_id": str(class_event.event_id),
            "utterance": None,
            "motivation_summary": (
                "아델은 책임감 있게 예정된 수업에 참석하려 한다."
            ),
            "reaction": {
                "valence": "NEUTRAL",
                "intensity": "LOW",
                "relationship_signals": [],
                "state_signals": ["FATIGUE_UP"],
            },
            "decision_explanation": {
                "alternatives": [
                    {
                        "action_type": "ATTEND_CLASS",
                        "description": "예정된 수업에 참석한다.",
                        "relative_priority": "HIGH",
                        "selected": True,
                    },
                    {
                        "action_type": "STUDY",
                        "description": "개인 학습을 진행한다.",
                        "relative_priority": "LOW",
                        "selected": False,
                    },
                ],
                "influencing_factors": [
                    {
                        "source": "SCHEDULE",
                        "description": "현재 일정에 수업 참석 의무가 있다.",
                        "direction": "SUPPORT",
                    },
                    {
                        "source": "PERSONALITY",
                        "description": "ISTJ 성향은 규칙과 책임을 중시한다.",
                        "direction": "SUPPORT",
                    },
                    {
                        "source": "EVENT",
                        "description": "현재 인식 가능한 수업 사건이 진행 중이다.",
                        "direction": "SUPPORT",
                    },
                ],
            },
            "memory_candidates": [
                {
                    "memory_type": "OBSERVATION",
                    "content": "예정된 수업에 참석했다.",
                    "importance": 3,
                    "related_agent_ids": [],
                    "related_event_id": str(class_event.event_id),
                }
            ],
        }
        return response
