from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import (
    Agent,
    AgentMemory,
    AgentState,
    Event,
    EventParticipant,
    Location,
    Organization,
    OrganizationMembership,
    ProfessorProfile,
    Relationship,
    Simulation,
    SimulationSnapshot,
    StudentProfile,
)
from app.repositories.simulation_snapshots import (
    SimulationConfigRepository,
    SimulationSnapshotRepository,
)


class InvalidSimulationConfigError(ValueError):
    pass


class SnapshotAccessDeniedError(PermissionError):
    pass


class SnapshotNotFoundError(LookupError):
    pass


ALLOWED_LEVELS = {"low", "medium", "high"}
CONFIGURABLE_STATUSES = {"ready", "running", "paused"}


def _timestamp(value: str | datetime | None) -> datetime | None:
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value


@dataclass(frozen=True)
class SimulationConfigInput:
    event_frequency: str
    event_impact: str
    magic_enabled: bool
    user_persona_settings: dict[str, Any]
    policy_version: str | None = None
    resolver_version: str | None = None


class SimulationSnapshotService:
    def __init__(self) -> None:
        self.configs = SimulationConfigRepository()
        self.snapshots = SimulationSnapshotRepository()

    def save_config(
        self,
        session: Session,
        simulation: Simulation,
        config_input: SimulationConfigInput,
    ):
        if simulation.status not in CONFIGURABLE_STATUSES:
            raise InvalidSimulationConfigError(
                f"settings are locked while simulation status is {simulation.status}"
            )
        if config_input.event_frequency not in ALLOWED_LEVELS:
            raise InvalidSimulationConfigError("invalid event_frequency")
        if config_input.event_impact not in ALLOWED_LEVELS:
            raise InvalidSimulationConfigError("invalid event_impact")
        return self.configs.create_version(
            session,
            simulation,
            event_frequency=config_input.event_frequency,
            event_impact=config_input.event_impact,
            magic_enabled=config_input.magic_enabled,
            user_persona_settings=config_input.user_persona_settings,
            policy_version=config_input.policy_version,
            resolver_version=config_input.resolver_version,
        )

    def create_snapshot(
        self, session: Session, simulation: Simulation
    ) -> SimulationSnapshot:
        config = self.configs.latest(session, simulation.id)
        if config is None:
            config = self.save_config(
                session,
                simulation,
                SimulationConfigInput(
                    event_frequency="medium",
                    event_impact="medium",
                    magic_enabled=simulation.magic_enabled,
                    user_persona_settings={},
                ),
            )
        return self.snapshots.create(session, simulation, config)

    def restore_as_branch(
        self,
        session: Session,
        snapshot_id: UUID,
        *,
        owner_id: UUID,
        name: str,
    ) -> Simulation:
        snapshot = self.snapshots.get(session, snapshot_id)
        if snapshot is None:
            raise SnapshotNotFoundError(str(snapshot_id))
        source = session.get(Simulation, snapshot.simulation_id)
        if source is None:
            raise SnapshotNotFoundError(str(snapshot.simulation_id))
        if source.owner_id != owner_id:
            raise SnapshotAccessDeniedError(str(snapshot_id))

        payload = snapshot.payload
        if payload.get("schema_version") != "slice6-snapshot-v1":
            raise SnapshotNotFoundError("unsupported snapshot schema")
        simulation_data = payload["simulation"]
        restored = Simulation(
            id=uuid7(),
            owner_id=owner_id,
            name=name.strip(),
            status=simulation_data["status"],
            current_day=simulation_data["current_day"],
            current_tick=simulation_data["current_tick"],
            magic_enabled=simulation_data["magic_enabled"],
            origin_simulation_id=source.id,
            origin_snapshot_id=snapshot.id,
        )
        session.add(restored)
        session.flush()
        self._restore_state(session, restored, payload)

        config = payload["config"]
        self.configs.create_version(
            session,
            restored,
            event_frequency=config["event_frequency"],
            event_impact=config["event_impact"],
            magic_enabled=config["magic_enabled"],
            user_persona_settings=config["user_persona_settings"],
            policy_version=config["policy_version"],
            resolver_version=config["resolver_version"],
        )
        session.flush()
        return restored

    def _restore_state(
        self, session: Session, restored: Simulation, payload: dict[str, Any]
    ) -> None:
        location_ids = {row["id"]: uuid7() for row in payload["locations"]}
        agent_ids = {row["id"]: uuid7() for row in payload["agents"]}
        organization_ids = {row["id"]: uuid7() for row in payload["organizations"]}
        event_ids = {row["id"]: uuid7() for row in payload["events"]}

        for row in payload["locations"]:
            session.add(Location(id=location_ids[row["id"]], simulation_id=restored.id, code=row["code"], name=row["name"], is_active=row["is_active"]))
        for row in payload["agents"]:
            session.add(Agent(
                id=agent_ids[row["id"]], simulation_id=restored.id,
                fixture_key=row["fixture_key"], fixture_version=row["fixture_version"],
                agent_type=row["agent_type"], name=row["name"], gender=row["gender"],
                personality_type=row["personality_type"], mbti_type=row["mbti_type"],
                openness=row["openness"], conscientiousness=row["conscientiousness"],
                extraversion=row["extraversion"], agreeableness=row["agreeableness"],
                emotional_stability=row["emotional_stability"], role_description=row["role_description"],
                active_status=row["active_status"], inactive_until_tick=row["inactive_until_tick"],
                persona_locked_at=_timestamp(row["persona_locked_at"]), deleted_at=_timestamp(row["deleted_at"]),
            ))
        session.flush()
        for row in payload["student_profiles"]:
            session.add(StudentProfile(agent_id=agent_ids[row["agent_id"]], grade=row["grade"], interest_field=row["interest_field"]))
        for row in payload["professor_profiles"]:
            session.add(ProfessorProfile(agent_id=agent_ids[row["agent_id"]], academic_rank=row["academic_rank"], specialty=row["specialty"]))
        for row in payload["agent_states"]:
            session.add(AgentState(
                id=uuid7(), simulation_id=restored.id, agent_id=agent_ids[row["agent_id"]],
                location_id=location_ids.get(row["location_id"]), hunger=row["hunger"],
                fatigue=row["fatigue"], stress=row["stress"], satisfaction=row["satisfaction"],
                mood=row["mood"], current_action=row["current_action"],
            ))
        for row in payload["organizations"]:
            session.add(Organization(
                id=organization_ids[row["id"]], simulation_id=restored.id,
                organization_type=row["organization_type"], name=row["name"],
                description=row["description"], is_active=row["is_active"],
                deleted_at=_timestamp(row["deleted_at"]),
            ))
        session.flush()
        for row in payload["organization_memberships"]:
            session.add(OrganizationMembership(
                id=uuid7(), simulation_id=restored.id,
                organization_id=organization_ids[row["organization_id"]],
                agent_id=agent_ids[row["agent_id"]], membership_role=row["membership_role"],
                joined_at=_timestamp(row["joined_at"]), left_at=_timestamp(row["left_at"]),
            ))
        for row in payload["events"]:
            session.add(Event(
                id=event_ids[row["id"]], simulation_id=restored.id,
                location_id=location_ids.get(row["location_id"]), event_type=row["event_type"],
                title=row["title"], description=row["description"], status=row["status"],
                simulation_day=row["simulation_day"], started_at=_timestamp(row["started_at"]),
                ended_at=_timestamp(row["ended_at"]), event_metadata=row["event_metadata"],
            ))
        session.flush()
        for row in payload["event_participants"]:
            session.add(EventParticipant(
                id=uuid7(), event_id=event_ids[row["event_id"]], agent_id=agent_ids[row["agent_id"]],
                participant_role=row["participant_role"], action_taken=row["action_taken"], result=row["result"],
            ))
        for row in payload["relationships"]:
            session.add(Relationship(
                id=uuid7(), simulation_id=restored.id,
                source_agent_id=agent_ids[row["source_agent_id"]], target_agent_id=agent_ids[row["target_agent_id"]],
                affection=row["affection"], closeness=row["closeness"], trust=row["trust"],
                tension=row["tension"], rivalry=row["rivalry"], dependency=row["dependency"],
                relationship_type=row["relationship_type"],
            ))
        for row in payload["agent_memories"]:
            session.add(AgentMemory(
                id=uuid7(), agent_id=agent_ids[row["agent_id"]],
                event_id=event_ids.get(row["event_id"]), content=row["content"],
                memory_type=row["memory_type"], importance=row["importance"],
                created_tick=row["created_tick"], occurred_at=_timestamp(row["occurred_at"]),
                last_accessed_at=_timestamp(row["last_accessed_at"]), embedding=row["embedding"],
            ))
