from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("display_name")
    @classmethod
    def display_name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("display_name must not be blank")
        return value


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    username: str
    display_name: str
    roles: list[str]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class SimulationCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value


class SimulationStatusUpdateRequest(BaseModel):
    status: Literal["running", "paused", "completed", "failed"]


class SimulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    owner_id: UUID
    name: str
    status: str
    current_day: int
    current_tick: int
    magic_enabled: bool
    night_waiting: bool
    created_at: datetime
    # 최신 simulation_config 파라미터 (없으면 None — 별도 GET /parameters 를 만들지
    # 않고 기존 Simulation 조회 응답을 확장한다, simulation-parameters.md §10).
    event_frequency: str | None = None
    event_impact: str | None = None
    magic_layer_frequency: str | None = None
    magic_layer_impact: str | None = None
    magic_off_eligible: bool | None = None
    config_version: int | None = None


class SimulationConfigPutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_frequency: str
    event_impact: str
    magic_layer_frequency: str = "medium"
    magic_layer_impact: str = "medium"
    magic_enabled: StrictBool


class SimulationConfigPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_frequency: str
    event_impact: str


class RestoreSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: UUID


class EventCreateRequest(BaseModel):
    event_type: Literal[
        "class",
        "group_project",
        "exam",
        "meeting",
        "mt",
        "festival",
        "student_council",
        "random_incident",
    ]
    title: str = Field(min_length=1, max_length=100)
    description: str | None = None
    simulation_day: int = Field(ge=1)
    location_id: UUID | None = None

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    simulation_id: UUID
    location_id: UUID | None
    event_type: str
    title: str
    description: str | None
    status: str
    simulation_day: int
    created_at: datetime


class LatestEventResponse(EventResponse):
    # tick / importance 는 events 테이블 컬럼이 아니라 event engine 이
    # events.metadata(JSONB)에 남긴 값이다 (persist_event_batch). 수동 생성
    # Event 에는 없으므로 nullable 이다.
    tick: int | None
    importance: int | None
    # 참여(대상) Agent 는 event_participants 테이블에서 조회한다.
    target_agent_ids: list[UUID]


class EventRelatedMemoryResponse(BaseModel):
    # agent_memories 행 그대로. agent_memories.event_id FK 가 이 Event 를 가리키는 기억이다.
    id: UUID
    agent_id: UUID
    content: str
    memory_type: str
    importance: int
    created_tick: int
    occurred_at: datetime


class EventDetailResponse(EventResponse):
    # tick / importance / impact_level / source / event_subtype 는 events 테이블
    # 컬럼이 아니라 event engine(persist_event_batch)이 events.metadata(JSONB)에
    # 남긴 값이다. 수동 생성 Event 에는 없으므로 nullable 이다.
    tick: int | None
    importance: int | None
    impact_level: str | None
    source: str | None
    event_subtype: str | None
    # 참여(대상) Agent 는 event_participants 테이블에서 조회한다.
    target_agent_ids: list[UUID]
    # 이 Event 를 참조하는 agent_memories 행.
    related_memories: list[EventRelatedMemoryResponse]


class SimulationLogEntryResponse(BaseModel):
    # 통합 로그 타임라인 한 줄. 새 저장소 없이 기존에 영속화된 데이터만 모은다:
    #   - events 테이블 (엔진 Event + 수동 Event)
    #   - agent_memories 테이블 중 memory_type == 'conversation' (대화 기록)
    id: UUID
    # 엔진 Event 는 events.metadata(JSONB).tick, 대화 기록은 agent_memories.created_tick.
    # 수동 생성 Event 에는 tick 이 없어 None 이다.
    tick: int | None
    # system : Magic Layer 가 남긴 Event (events.metadata.source == 'magic_layer')
    # event  : 그 밖의 Event
    # dialogue : memory_type == 'conversation' 인 agent_memories 행
    type: Literal["system", "event", "dialogue"]
    # Event 는 title, 대화 기록은 content. 요약을 새로 생성하지 않고 원문을 그대로 쓴다.
    summary: str
    # Event 는 event_participants, 대화 기록은 해당 기억의 agent_id.
    target_agent_ids: list[UUID]
    # 엔진 Event 는 events.metadata.importance, 대화 기록은 agent_memories.importance.
    importance: int | None
    # Event Detail API 로 연결하기 위한 참조. Event 행은 자기 id, 대화 기록은
    # agent_memories.event_id FK (없으면 None). Dialogue 상세(dialogue_id)는
    # 아직 Dialogue 영속화가 없어 제공하지 않는다.
    event_id: UUID | None


class DialogueMessageResponse(BaseModel):
    # 한 발화. order 는 dialogue 내 안정적 순서(0부터)이며 실제 turn-taking 이
    # 아니라 Runtime 배치 선정 순서를 따른다. Runtime 이 발화를 비우면 utterance 는 None.
    speaker: UUID
    utterance: str | None
    order: int


class DialogueDetailResponse(BaseModel):
    # 같은 tick 안에서 성립한 mutual TALK pair 하나 = dialogue 하나.
    dialogue_id: UUID
    simulation_id: UUID
    tick: int
    participants: list[UUID]
    messages: list[DialogueMessageResponse]


class SimulationShareCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visibility: Literal["private", "unlisted", "public"] = "private"
    title: str = Field(default="", max_length=200)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("title")
    @classmethod
    def title_must_be_trimmed(cls, value: str) -> str:
        return value.strip()


class SimulationShareSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    simulation_id: UUID
    owner_id: UUID
    title: str
    description: str | None
    visibility: str
    export_schema_version: str
    created_at: datetime
    updated_at: datetime


class SimulationShareDetailResponse(SimulationShareSummaryResponse):
    export_payload: dict[str, object]


class AgentProfileResponse(BaseModel):
    openness: int
    conscientiousness: int
    extraversion: int
    agreeableness: int
    emotional_stability: int


class AgentStateResponse(BaseModel):
    hunger: int
    fatigue: int
    stress: int
    satisfaction: int
    mood: int
    current_action: str | None


class LocationResponse(BaseModel):
    id: UUID
    code: str
    name: str


class StudentProfileResponse(BaseModel):
    grade: int
    interest_field: str


class ProfessorProfileResponse(BaseModel):
    academic_rank: str
    specialty: str


class AgentResponse(BaseModel):
    id: UUID
    fixture_key: str
    fixture_version: str
    name: str
    agent_type: str
    active_status: str
    mbti_type: str
    profile: AgentProfileResponse
    student_profile: StudentProfileResponse | None
    professor_profile: ProfessorProfileResponse | None
    state: AgentStateResponse
    location: LocationResponse


class OrganizationResponse(BaseModel):
    id: UUID
    organization_type: str
    name: str
    membership_role: str | None


class AgentDetailResponse(AgentResponse):
    organizations: list[OrganizationResponse]


class AgentStateDetailResponse(AgentStateResponse):
    current_location: LocationResponse
    updated_at: datetime


class MemoryResponse(BaseModel):
    id: UUID
    content: str
    memory_type: str
    importance: int
    created_tick: int
    occurred_at: datetime
    event_id: UUID | None


class RelationshipResponse(BaseModel):
    target_agent_id: UUID
    target_agent_name: str
    affection: int
    closeness: int
    trust: int
    tension: int
    rivalry: int
    dependency: int
    relationship_type: str | None
    updated_at: datetime


class DecisionAlternativeResponse(BaseModel):
    action_type: str
    description: str
    relative_priority: str
    selected: bool


class InfluencingFactorResponse(BaseModel):
    source: str
    description: str
    direction: str


class DecisionExplanationDetailResponse(BaseModel):
    agent_id: UUID
    tick: int
    alternatives: list[DecisionAlternativeResponse]
    influencing_factors: list[InfluencingFactorResponse]
