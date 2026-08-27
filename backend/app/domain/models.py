from datetime import datetime
from typing import Any
from uuid import UUID as PythonUUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", name="uq_users_username"),)

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    roles: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default=text("'[\"USER\"]'::jsonb"))


class Simulation(TimestampMixin, Base):
    __tablename__ = "simulations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ready', 'running', 'paused', 'completed', 'failed')",
            name="ck_simulations_status",
        ),
        CheckConstraint("current_day >= 1", name="ck_simulations_current_day"),
        CheckConstraint("current_tick >= 0", name="ck_simulations_current_tick"),
        Index("idx_simulations_owner_created", "owner_id", text("created_at DESC")),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    owner_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ready")
    current_day: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    current_tick: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    magic_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
class SimulationConfig(TimestampMixin, Base):
    __tablename__ = "simulation_configs"
    __table_args__ = (
        UniqueConstraint("simulation_id", "version", name="uq_simulation_configs_version"),
        CheckConstraint("version >= 1", name="ck_simulation_configs_version"),
        CheckConstraint(
            "event_frequency IN ('low', 'medium', 'high')",
            name="ck_simulation_configs_event_frequency",
        ),
        CheckConstraint(
            "event_impact IN ('low', 'medium', 'high')",
            name="ck_simulation_configs_event_impact",
        ),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    simulation_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulations.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    event_frequency: Mapped[str] = mapped_column(String(10), nullable=False)
    event_impact: Mapped[str] = mapped_column(String(10), nullable=False)
    magic_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_version: Mapped[str | None] = mapped_column(String(100))
    resolver_version: Mapped[str | None] = mapped_column(String(100))
    user_persona_settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class SimulationSnapshot(TimestampMixin, Base):
    __tablename__ = "simulation_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["simulation_id", "config_version"],
            ["simulation_configs.simulation_id", "simulation_configs.version"],
            name="fk_simulation_snapshots_config",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("simulation_id", "tick_number", name="uq_simulation_snapshots_tick"),
        CheckConstraint("tick_number >= 0", name="ck_simulation_snapshots_tick"),
        CheckConstraint("config_version >= 1", name="ck_simulation_snapshots_config_version"),
        Index("idx_simulation_snapshots_timeline", "simulation_id", "tick_number"),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    simulation_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulations.id", ondelete="RESTRICT"), nullable=False
    )
    tick_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class SimulationShare(TimestampMixin, Base):
    __tablename__ = "simulation_shares"
    __table_args__ = (
        CheckConstraint("visibility IN ('private', 'unlisted', 'public')", name="ck_simulation_shares_visibility"),
        Index(
            "uq_simulation_shares_active_simulation",
            "simulation_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index(
            "idx_simulation_shares_public_listing",
            "visibility",
            "created_at",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    simulation_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulations.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    owner_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    description: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, server_default="private")
    export_schema_version: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="slice7-share-v1"
    )
    export_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Location(TimestampMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("simulation_id", "code", name="uq_locations_simulation_code"),
        UniqueConstraint("simulation_id", "id", name="uq_locations_simulation_id_id"),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    simulation_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulations.id", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class Agent(TimestampMixin, Base):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("simulation_id", "id", name="uq_agents_simulation_id_id"),
        UniqueConstraint("simulation_id", "fixture_key", name="uq_agents_simulation_fixture_key"),
        CheckConstraint("agent_type IN ('student', 'professor', 'user_persona')", name="ck_agents_agent_type"),
        CheckConstraint("gender IS NULL OR gender IN ('male', 'female', 'non_binary', 'unspecified')", name="ck_agents_gender"),
        CheckConstraint("mbti_type IN ('ISTJ', 'ESTP', 'INFP', 'ENTJ', 'ESFJ')", name="ck_agents_mbti_type"),
        CheckConstraint("openness BETWEEN -50 AND 50 AND openness % 5 = 0", name="ck_agents_openness"),
        CheckConstraint("conscientiousness BETWEEN -50 AND 50 AND conscientiousness % 5 = 0", name="ck_agents_conscientiousness"),
        CheckConstraint("extraversion BETWEEN -50 AND 50 AND extraversion % 5 = 0", name="ck_agents_extraversion"),
        CheckConstraint("agreeableness BETWEEN -50 AND 50 AND agreeableness % 5 = 0", name="ck_agents_agreeableness"),
        CheckConstraint("emotional_stability BETWEEN -50 AND 50 AND emotional_stability % 5 = 0", name="ck_agents_emotional_stability"),
        CheckConstraint("inactive_until_tick IS NULL OR inactive_until_tick >= 0", name="ck_agents_inactive_until_tick"),
        Index("uq_agents_active_user_persona", "simulation_id", unique=True, postgresql_where=text("agent_type = 'user_persona' AND deleted_at IS NULL")),
        Index("idx_agents_simulation_id", "simulation_id", "id"),
        Index("idx_agents_runtime_active", "simulation_id", "active_status", "inactive_until_tick"),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    simulation_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulations.id", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False)
    fixture_key: Mapped[str] = mapped_column(String(50), nullable=False)
    fixture_version: Mapped[str] = mapped_column(String(50), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(20))
    personality_type: Mapped[str | None] = mapped_column(String(30))
    mbti_type: Mapped[str] = mapped_column(String(4), nullable=False)
    openness: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    conscientiousness: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    extraversion: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    agreeableness: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    emotional_stability: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    role_description: Mapped[str | None] = mapped_column(Text)
    active_status: Mapped[str] = mapped_column(String(30), nullable=False, server_default="active")
    inactive_until_tick: Mapped[int | None] = mapped_column(BigInteger)
    persona_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserPersonaConfig(TimestampMixin, Base):
    __tablename__ = "user_persona_configs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["simulation_id", "agent_id"],
            ["agents.simulation_id", "agents.id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
            name="fk_user_persona_configs_agent",
        ),
        CheckConstraint(
            "openness BETWEEN -50 AND 50 AND openness % 5 = 0",
            name="ck_user_persona_configs_openness",
        ),
        CheckConstraint(
            "conscientiousness BETWEEN -50 AND 50 AND conscientiousness % 5 = 0",
            name="ck_user_persona_configs_conscientiousness",
        ),
        CheckConstraint(
            "extraversion BETWEEN -50 AND 50 AND extraversion % 5 = 0",
            name="ck_user_persona_configs_extraversion",
        ),
        CheckConstraint(
            "agreeableness BETWEEN -50 AND 50 AND agreeableness % 5 = 0",
            name="ck_user_persona_configs_agreeableness",
        ),
        CheckConstraint(
            "emotional_stability BETWEEN -50 AND 50 AND emotional_stability % 5 = 0",
            name="ck_user_persona_configs_emotional_stability",
        ),
    )

    simulation_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulations.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        primary_key=True,
    )
    agent_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    mbti_type: Mapped[str] = mapped_column(String(4), nullable=False)
    personality_rule_version: Mapped[str] = mapped_column(String(50), nullable=False)
    openness: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    conscientiousness: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    extraversion: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    agreeableness: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    emotional_stability: Mapped[int] = mapped_column(SmallInteger, nullable=False)


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    __table_args__ = (CheckConstraint("grade BETWEEN 1 AND 4", name="ck_student_profiles_grade"),)

    agent_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        primary_key=True,
    )
    grade: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    interest_field: Mapped[str] = mapped_column(String(100), nullable=False)


class ProfessorProfile(Base):
    __tablename__ = "professor_profiles"

    agent_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        primary_key=True,
    )
    academic_rank: Mapped[str] = mapped_column(String(50), nullable=False)
    specialty: Mapped[str] = mapped_column(String(200), nullable=False)


class AgentState(TimestampMixin, Base):
    __tablename__ = "agent_states"
    __table_args__ = (
        ForeignKeyConstraint(["simulation_id", "agent_id"], ["agents.simulation_id", "agents.id"], ondelete="RESTRICT", onupdate="RESTRICT", name="fk_agent_states_agent"),
        ForeignKeyConstraint(["simulation_id", "location_id"], ["locations.simulation_id", "locations.id"], ondelete="RESTRICT", onupdate="RESTRICT", name="fk_agent_states_location"),
        UniqueConstraint("agent_id", name="uq_agent_states_agent_id"),
        CheckConstraint("hunger BETWEEN 0 AND 100 AND fatigue BETWEEN 0 AND 100 AND stress BETWEEN 0 AND 100 AND satisfaction BETWEEN 0 AND 100 AND mood BETWEEN -100 AND 100", name="ck_agent_states_bounded_scores"),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    simulation_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulations.id", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False)
    agent_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    location_id: Mapped[PythonUUID | None] = mapped_column(UUID(as_uuid=True))
    hunger: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="50")
    fatigue: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    stress: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    satisfaction: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="50")
    mood: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    current_action: Mapped[str | None] = mapped_column(String(50))


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("simulation_id", "organization_type", "name", name="uq_organizations_simulation_type_name"),
        UniqueConstraint("simulation_id", "id", name="uq_organizations_simulation_id_id"),
        CheckConstraint("organization_type IN ('major', 'club', 'dormitory')", name="ck_organizations_type"),
        Index("idx_organizations_simulation_id", "simulation_id", "id"),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    simulation_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulations.id", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False)
    organization_type: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrganizationMembership(TimestampMixin, Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        ForeignKeyConstraint(["simulation_id", "organization_id"], ["organizations.simulation_id", "organizations.id"], ondelete="RESTRICT", onupdate="RESTRICT", name="fk_memberships_organization"),
        ForeignKeyConstraint(["simulation_id", "agent_id"], ["agents.simulation_id", "agents.id"], ondelete="RESTRICT", onupdate="RESTRICT", name="fk_memberships_agent"),
        CheckConstraint("membership_role IS NULL OR membership_role IN ('member', 'leader', 'professor', 'resident')", name="ck_memberships_role"),
        Index("uq_organization_memberships_active", "organization_id", "agent_id", unique=True, postgresql_where=text("left_at IS NULL")),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    simulation_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulations.id", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False)
    organization_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agent_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    membership_role: Mapped[str | None] = mapped_column(String(30))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Event(TimestampMixin, Base):
    __tablename__ = "events"
    __table_args__ = (
        ForeignKeyConstraint(["simulation_id", "location_id"], ["locations.simulation_id", "locations.id"], ondelete="SET NULL (location_id)", onupdate="RESTRICT", name="fk_events_location"),
        CheckConstraint("event_type IN ('class', 'group_project', 'exam', 'meeting', 'mt', 'festival', 'student_council', 'random_incident')", name="ck_events_type"),
        CheckConstraint("status IN ('scheduled', 'ongoing', 'completed', 'cancelled')", name="ck_events_status"),
        CheckConstraint("simulation_day >= 1", name="ck_events_simulation_day"),
        Index("idx_events_simulation_started", "simulation_id", text("started_at DESC"), text("id DESC")),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    simulation_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulations.id", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False)
    location_id: Mapped[PythonUUID | None] = mapped_column(UUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="scheduled")
    simulation_day: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class EventParticipant(TimestampMixin, Base):
    __tablename__ = "event_participants"
    __table_args__ = (UniqueConstraint("event_id", "agent_id", name="uq_event_participants_event_agent"),)

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    event_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False)
    agent_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False)
    participant_role: Mapped[str | None] = mapped_column(String(30))
    action_taken: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class RuntimeResult(TimestampMixin, Base):
    __tablename__ = "runtime_results"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_runtime_results_idempotency_key"),
        UniqueConstraint(
            "run_id",
            "tick_number",
            "agent_id",
            name="uq_runtime_results_run_tick_agent",
        ),
        CheckConstraint("tick_number >= 0", name="ck_runtime_results_tick_number"),
        CheckConstraint("retry_count >= 0", name="ck_runtime_results_retry_count"),
        CheckConstraint(
            "status IN ('PROPOSED', 'FALLBACK', 'SKIPPED')",
            name="ck_runtime_results_status",
        ),
        Index("idx_runtime_results_run_tick", "run_id", "tick_number", "agent_id"),
        Index(
            "idx_runtime_results_run_failures",
            "run_id",
            "tick_number",
            postgresql_where=text("failure_reason IS NOT NULL"),
        ),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(100), nullable=False)
    tick_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    agent_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    intent: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failure_reason: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    result_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class RuntimeExecution(TimestampMixin, Base):
    __tablename__ = "runtime_executions"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_runtime_executions_run_id"),
        UniqueConstraint(
            "simulation_id",
            "tick_number",
            name="uq_runtime_executions_simulation_tick",
        ),
        CheckConstraint(
            "tick_number >= 0", name="ck_runtime_executions_tick_number"
        ),
        CheckConstraint("seed >= 0", name="ck_runtime_executions_seed"),
        Index(
            "idx_runtime_executions_simulation_tick",
            "simulation_id",
            text("tick_number DESC"),
        ),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    simulation_id: Mapped[PythonUUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulations.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    run_id: Mapped[str] = mapped_column(String(100), nullable=False)
    tick_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_version: Mapped[str | None] = mapped_column(String(100))


class Relationship(TimestampMixin, Base):
    __tablename__ = "relationships"
    __table_args__ = (
        ForeignKeyConstraint(["simulation_id", "source_agent_id"], ["agents.simulation_id", "agents.id"], ondelete="RESTRICT", onupdate="RESTRICT", name="fk_relationships_source_agent"),
        ForeignKeyConstraint(["simulation_id", "target_agent_id"], ["agents.simulation_id", "agents.id"], ondelete="RESTRICT", onupdate="RESTRICT", name="fk_relationships_target_agent"),
        UniqueConstraint("simulation_id", "source_agent_id", "target_agent_id", name="uq_relationships_pair"),
        CheckConstraint("source_agent_id <> target_agent_id", name="ck_relationships_distinct_agents"),
        CheckConstraint("affection BETWEEN -100 AND 100", name="ck_relationships_affection"),
        CheckConstraint("closeness BETWEEN -100 AND 100", name="ck_relationships_closeness"),
        CheckConstraint("trust BETWEEN -100 AND 100", name="ck_relationships_trust"),
        CheckConstraint("tension BETWEEN 0 AND 100", name="ck_relationships_tension"),
        CheckConstraint("rivalry BETWEEN 0 AND 100", name="ck_relationships_rivalry"),
        CheckConstraint("dependency BETWEEN 0 AND 100", name="ck_relationships_dependency"),
        CheckConstraint("relationship_type IS NULL OR relationship_type IN ('friend', 'rival', 'senior_junior', 'confession', 'betrayal', 'reconciliation')", name="ck_relationships_type"),
        Index("idx_relationships_source_updated", "source_agent_id", text("updated_at DESC"), text("id DESC")),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    simulation_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("simulations.id", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False)
    source_agent_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_agent_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    affection: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    closeness: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    trust: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    tension: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    rivalry: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    dependency: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    relationship_type: Mapped[str | None] = mapped_column(String(30))


class AgentMemory(TimestampMixin, Base):
    __tablename__ = "agent_memories"
    __table_args__ = (
        CheckConstraint("memory_type IN ('observation', 'conversation', 'reflection', 'plan')", name="ck_agent_memories_type"),
        CheckConstraint("importance BETWEEN 0 AND 100", name="ck_agent_memories_importance"),
        CheckConstraint("created_tick >= 0", name="ck_agent_memories_created_tick"),
        Index("idx_agent_memories_agent_occurred", "agent_id", text("occurred_at DESC"), text("id DESC")),
        Index("idx_agent_memories_cleanup", "agent_id", "importance", "created_tick"),
        Index(
            "idx_agent_memories_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
    )

    id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    agent_id: Mapped[PythonUUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="RESTRICT", onupdate="RESTRICT"), nullable=False)
    event_id: Mapped[PythonUUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL", onupdate="RESTRICT"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[str] = mapped_column(String(20), nullable=False, server_default="observation")
    importance: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="0")
    created_tick: Mapped[int] = mapped_column(BigInteger, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
