from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    created_at: datetime


class SimulationConfigPutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_frequency: str
    event_impact: str
    magic_enabled: bool


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


class SimulationShareCreateRequest(BaseModel):
    visibility: str = Field(default="private", pattern=r"^(private|unlisted|public)$")
    export_payload: dict[str, object] | None = None


class SimulationShareResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    simulation_id: UUID
    owner_id: UUID
    visibility: str
    export_schema_version: str
    export_payload: dict[str, object]
    created_at: datetime
    updated_at: datetime


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
