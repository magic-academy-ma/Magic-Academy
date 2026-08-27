from copy import deepcopy
from enum import StrEnum
from typing import Any, Literal, Protocol, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


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


class SignalIntensity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RelationshipSignalType(StrEnum):
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


class StateSignalType(StrEnum):
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
    REFLECTION = "REFLECTION"
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


class BigFiveContext(StrictModel):
    openness: int = Field(ge=-50, le=50)
    conscientiousness: int = Field(ge=-50, le=50)
    extraversion: int = Field(ge=-50, le=50)
    agreeableness: int = Field(ge=-50, le=50)
    emotional_stability: int = Field(ge=-50, le=50)


class AgentStateContext(StrictModel):
    hunger: int = Field(ge=0, le=100)
    fatigue: int = Field(ge=0, le=100)
    stress: int = Field(ge=0, le=100)
    satisfaction: int = Field(ge=0, le=100)
    mood: int = Field(ge=-100, le=100)


class AgentContext(StrictModel):
    agent_id: UUID
    fixture_key: str
    agent_type: Literal["student", "professor"]
    name: str
    mbti: MBTI | None
    big_five: BigFiveContext
    state: AgentStateContext
    current_location_id: UUID | None
    active_status: bool = Field(strict=True)


class AgentSummary(StrictModel):
    agent_id: UUID
    name: str
    agent_type: Literal["student", "professor"]
    active_status: bool = Field(strict=True)
    current_location_id: UUID
    mood: int = Field(ge=-100, le=100)
    stress: int = Field(ge=0, le=100)
    fatigue: int = Field(ge=0, le=100)


class RelationshipSummary(StrictModel):
    source_agent_id: UUID
    target_agent_id: UUID
    affection: int
    closeness: int
    trust: int
    tension: int
    rivalry: int
    dependency: int


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
    seed: int = Field(default=0, ge=0)
    block: Block
    agent: AgentContext
    nearby_agents: list[AgentSummary]
    relationships: list[RelationshipSummary]
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
            if self.schedule.is_mandatory:
                raise ValueError("mandatory schedule event_id must be included in events")
            return self
        if scheduled_event.event_type != self.schedule.schedule_type:
            raise ValueError("schedule_type must match the linked event_type")
        if scheduled_event.location_id != self.schedule.location_id:
            raise ValueError("schedule location_id must match the linked event location_id")
        return self


class RelationshipSignal(StrictModel):
    signal_type: RelationshipSignalType
    intensity: SignalIntensity
    target_agent_id: UUID


class StateSignal(StrictModel):
    signal_type: StateSignalType
    intensity: SignalIntensity


class AgentReaction(StrictModel):
    valence: ReactionValence
    relationship_signals: list[RelationshipSignal] = Field(default_factory=list)
    state_signals: list[StateSignal] = Field(default_factory=list)


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
    """Inspector용 구조화 설명이며 모델의 내부 chain-of-thought가 아니다."""

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
    reaction: AgentReaction
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

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("idempotency_key must be non-blank without surrounding whitespace")
        return value

    @model_validator(mode="after")
    def validate_canonical_idempotency_key(self) -> "AgentRuntimeResult":
        expected = f"{self.run_id}:{self.tick_number}:{self.agent_id}"
        if self.idempotency_key != expected:
            raise ValueError("idempotency_key must match run_id:tick_number:agent_id")
        return self


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
    for signal in candidate.reaction.relationship_signals:
        if signal.target_agent_id not in runtime_input.valid_agent_ids:
            raise ValueError("relationship signal target_agent_id is not included in valid_agent_ids")
        if signal.target_agent_id == runtime_input.agent.agent_id:
            raise ValueError("relationship signal cannot target the acting agent")
    for memory in candidate.memory_candidates:
        if any(
            agent_id not in runtime_input.valid_agent_ids
            for agent_id in memory.related_agent_ids
        ):
            raise ValueError("memory candidate contains an invalid related_agent_id")
        if memory.related_event_id is not None and memory.related_event_id not in valid_event_ids:
            raise ValueError("memory candidate contains an invalid related_event_id")
    _validate_action_targets(candidate, runtime_input.agent.agent_id)
    return candidate


def _validate_action_targets(candidate: IntentCandidate, acting_agent_id: UUID) -> None:
    if candidate.action_type in {ActionType.TALK, ActionType.HELP}:
        if candidate.target_agent_id is None:
            raise ValueError(f"{candidate.action_type} requires target_agent_id")
        if candidate.target_agent_id == acting_agent_id:
            raise ValueError(f"{candidate.action_type} cannot target the acting agent")
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
        class_event = next(
            event for event in runtime_input.events if event.event_type == EventType.CLASS
        )
        is_professor = runtime_input.agent.agent_type == "professor"
        action_type = "TEACH_CLASS" if is_professor else "ATTEND_CLASS"
        response = {
            "action_type": action_type,
            "target_agent_id": None,
            "target_location_id": str(class_event.location_id),
            "related_event_id": str(class_event.event_id),
            "utterance": None,
            "motivation_summary": (
                f"{runtime_input.agent.name}은 예정된 수업에 "
                f"{'진행' if is_professor else '참석'}하려 한다."
            ),
            "reaction": {
                "valence": "NEUTRAL",
                "relationship_signals": [],
                "state_signals": [
                    {"signal_type": "FATIGUE_UP", "intensity": "LOW"}
                ],
            },
            "decision_explanation": {
                "alternatives": [
                    {
                        "action_type": action_type,
                        "description": "예정된 수업을 진행한다."
                        if is_professor
                        else "예정된 수업에 참석한다.",
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


class LLMInvocationError(Exception):
    """An expected LLM invocation failure that may be retried."""


class RuntimeGraphState(TypedDict):
    runtime_input: AgentRuntimeInput
    current_llm_response: object | None
    attempt_count: int
    last_validation_failure: str | None
    candidate: IntentCandidate | None
    final_result: AgentRuntimeResult | None


class AgentRuntime:
    def __init__(
        self,
        llm_client: LLMClient,
        *,
        model: str = "mock-llm",
        prompt_version: str = "agent-runtime-10.1",
    ) -> None:
        self._llm_client = llm_client
        self._model = model
        self._prompt_version = prompt_version
        self._graph = self._build_graph()

    def run(self, runtime_input: AgentRuntimeInput) -> AgentRuntimeResult:
        state = self.run_state(runtime_input)
        result = state["final_result"]
        if result is None:
            raise RuntimeError("runtime graph completed without a final result")
        return result

    def run_state(self, runtime_input: AgentRuntimeInput) -> RuntimeGraphState:
        initial_state: RuntimeGraphState = {
            "runtime_input": runtime_input,
            "current_llm_response": None,
            "attempt_count": 0,
            "last_validation_failure": None,
            "candidate": None,
            "final_result": None,
        }
        return self._graph.invoke(initial_state)

    def _build_graph(self):
        graph = StateGraph(RuntimeGraphState)
        graph.add_node("decide", self._decide)
        graph.add_node("validate", self._validate)
        graph.add_node("success", self._assemble_success)
        graph.add_node("fallback", self._assemble_fallback)
        graph.add_node("skipped", self._assemble_skipped)
        graph.add_conditional_edges(
            START,
            self._route_start,
            {"decide": "decide", "skipped": "skipped"},
        )
        graph.add_edge("decide", "validate")
        graph.add_conditional_edges(
            "validate",
            self._route_after_validation,
            {"success": "success", "retry": "decide", "fallback": "fallback"},
        )
        graph.add_edge("success", END)
        graph.add_edge("fallback", END)
        graph.add_edge("skipped", END)
        return graph.compile()

    @staticmethod
    def _route_start(state: RuntimeGraphState) -> str:
        if state["runtime_input"].agent.active_status:
            return "decide"
        return "skipped"

    def _decide(self, state: RuntimeGraphState) -> dict[str, object]:
        attempt_count = state["attempt_count"] + 1
        try:
            # Block LLM invocation during replay mode and instrument the call
            from app.simulation.replay_guard import assert_not_replay
            from app.simulation.instrumentation import increment_llm

            assert_not_replay("LLM generation attempted during replay")
            increment_llm()
            response = self._llm_client.generate(state["runtime_input"])
        except LLMInvocationError as exc:
            return {
                "attempt_count": attempt_count,
                "current_llm_response": None,
                "candidate": None,
                "last_validation_failure": _failure_reason(exc),
            }
        return {
            "attempt_count": attempt_count,
            "current_llm_response": response,
            "candidate": None,
            "last_validation_failure": None,
        }

    @staticmethod
    def _validate(state: RuntimeGraphState) -> dict[str, object]:
        if state["current_llm_response"] is None:
            return {"candidate": None}
        try:
            candidate = validate_intent_candidate(
                state["current_llm_response"], state["runtime_input"]
            )
        except (ValidationError, ValueError) as exc:
            return {
                "candidate": None,
                "last_validation_failure": _failure_reason(exc),
            }
        return {"candidate": candidate, "last_validation_failure": None}

    @staticmethod
    def _route_after_validation(state: RuntimeGraphState) -> str:
        if state["candidate"] is not None:
            return "success"
        if state["attempt_count"] < 2:
            return "retry"
        return "fallback"

    def _assemble_success(self, state: RuntimeGraphState) -> dict[str, object]:
        candidate = state["candidate"]
        if candidate is None:
            raise RuntimeError("success node requires a validated candidate")
        return {
            "final_result": self._result(
                state,
                status=RuntimeStatus.PROPOSED,
                intent=candidate,
                retry_count=state["attempt_count"] - 1,
                failure_reason=None,
            )
        }

    def _assemble_fallback(self, state: RuntimeGraphState) -> dict[str, object]:
        failure_reason = state["last_validation_failure"]
        if failure_reason is None:
            raise RuntimeError("fallback node requires a failure reason")
        return {
            "final_result": self._result(
                state,
                status=RuntimeStatus.FALLBACK,
                intent=_wait_intent("유효한 행동을 결정하지 못해 대기한다."),
                retry_count=1,
                failure_reason=failure_reason,
            )
        }

    def _assemble_skipped(self, state: RuntimeGraphState) -> dict[str, object]:
        return {
            "final_result": self._result(
                state,
                status=RuntimeStatus.SKIPPED,
                intent=_wait_intent(
                    "비활성 Agent이므로 이번 행동 결정을 건너뛴다."
                ),
                retry_count=0,
                failure_reason=None,
            )
        }

    def _result(
        self,
        state: RuntimeGraphState,
        *,
        status: RuntimeStatus,
        intent: IntentCandidate,
        retry_count: int,
        failure_reason: str | None,
    ) -> AgentRuntimeResult:
        runtime_input = state["runtime_input"]
        return AgentRuntimeResult(
            run_id=runtime_input.run_id,
            tick_number=runtime_input.tick_number,
            agent_id=runtime_input.agent.agent_id,
            status=status,
            intent=intent,
            retry_count=retry_count,
            failure_reason=failure_reason,
            model=self._model,
            prompt_version=self._prompt_version,
            idempotency_key=(
                f"{runtime_input.run_id}:{runtime_input.tick_number}:"
                f"{runtime_input.agent.agent_id}"
            ),
        )


def _wait_intent(motivation_summary: str) -> IntentCandidate:
    return IntentCandidate(
        action_type=ActionType.WAIT,
        target_agent_id=None,
        target_location_id=None,
        related_event_id=None,
        utterance=None,
        motivation_summary=motivation_summary,
        reaction=AgentReaction(
            valence=ReactionValence.NEUTRAL,
            relationship_signals=[],
            state_signals=[],
        ),
        decision_explanation=DecisionExplanation(
            alternatives=[
                ActionAlternative(
                    action_type=ActionType.WAIT,
                    description="현재 위치에서 대기한다.",
                    relative_priority=RelativePriority.HIGH,
                    selected=True,
                )
            ],
            influencing_factors=[],
        ),
        memory_candidates=[],
    )


def _failure_reason(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"
