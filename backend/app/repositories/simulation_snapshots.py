from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, inspect, select
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
    RuntimeResult,
    Simulation,
    SimulationConfig,
    SimulationSnapshot,
    StudentProfile,
)


class SnapshotAlreadyExistsError(RuntimeError):
    pass


def _json_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return list(value)
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def _serialize(row: Any, sequence: int) -> dict[str, Any]:
    data = {
        attribute.key: _json_value(getattr(row, attribute.key))
        for attribute in inspect(type(row)).column_attrs
    }
    data["sequence"] = sequence
    return data


class SimulationConfigRepository:
    def latest(self, session: Session, simulation_id: UUID) -> SimulationConfig | None:
        return session.scalar(
            select(SimulationConfig)
            .where(SimulationConfig.simulation_id == simulation_id)
            .order_by(SimulationConfig.version.desc())
            .limit(1)
        )

    def create_version(
        self,
        session: Session,
        simulation: Simulation,
        *,
        event_frequency: str,
        event_impact: str,
        magic_enabled: bool,
        user_persona_settings: dict[str, Any],
        policy_version: str | None,
        resolver_version: str | None,
    ) -> SimulationConfig:
        session.execute(
            select(Simulation.id).where(Simulation.id == simulation.id).with_for_update()
        )
        version = (
            session.scalar(
                select(func.max(SimulationConfig.version)).where(
                    SimulationConfig.simulation_id == simulation.id
                )
            )
            or 0
        ) + 1
        config = SimulationConfig(
            id=uuid7(),
            simulation_id=simulation.id,
            version=version,
            event_frequency=event_frequency,
            event_impact=event_impact,
            magic_enabled=magic_enabled,
            policy_version=policy_version,
            resolver_version=resolver_version,
            user_persona_settings=dict(user_persona_settings),
        )
        session.add(config)
        session.flush()
        return config


class SimulationSnapshotRepository:
    def get(self, session: Session, snapshot_id: UUID) -> SimulationSnapshot | None:
        return session.get(SimulationSnapshot, snapshot_id)

    def get_at_tick(
        self, session: Session, simulation_id: UUID, tick_number: int
    ) -> SimulationSnapshot | None:
        return session.scalar(
            select(SimulationSnapshot).where(
                SimulationSnapshot.simulation_id == simulation_id,
                SimulationSnapshot.tick_number == tick_number,
            )
        )

    def create(
        self,
        session: Session,
        simulation: Simulation,
        config: SimulationConfig,
    ) -> SimulationSnapshot:
        if self.get_at_tick(session, simulation.id, simulation.current_tick) is not None:
            raise SnapshotAlreadyExistsError(
                f"snapshot already exists for tick {simulation.current_tick}"
            )
        payload = self._capture(session, simulation, config)
        snapshot = SimulationSnapshot(
            id=uuid7(),
            simulation_id=simulation.id,
            tick_number=simulation.current_tick,
            config_version=config.version,
            payload=payload,
        )
        session.add(snapshot)
        session.flush()
        return snapshot

    def _capture(
        self,
        session: Session,
        simulation: Simulation,
        config: SimulationConfig,
    ) -> dict[str, Any]:
        agents = list(session.scalars(select(Agent).where(Agent.simulation_id == simulation.id).order_by(Agent.id)))
        agent_ids = [agent.id for agent in agents]
        events = list(session.scalars(select(Event).where(Event.simulation_id == simulation.id).order_by(Event.created_at, Event.id)))
        event_ids = [event.id for event in events]

        def rows(model: Any, condition: Any, *order_by: Any) -> list[Any]:
            query = select(model).where(condition)
            if order_by:
                query = query.order_by(*order_by)
            return list(session.scalars(query))

        collections: dict[str, list[Any]] = {
            "locations": rows(Location, Location.simulation_id == simulation.id, Location.id),
            "agents": agents,
            "student_profiles": rows(StudentProfile, StudentProfile.agent_id.in_(agent_ids), StudentProfile.agent_id),
            "professor_profiles": rows(ProfessorProfile, ProfessorProfile.agent_id.in_(agent_ids), ProfessorProfile.agent_id),
            "agent_states": rows(AgentState, AgentState.simulation_id == simulation.id, AgentState.agent_id),
            "organizations": rows(Organization, Organization.simulation_id == simulation.id, Organization.id),
            "organization_memberships": rows(OrganizationMembership, OrganizationMembership.simulation_id == simulation.id, OrganizationMembership.id),
            "events": events,
            "event_participants": rows(EventParticipant, EventParticipant.event_id.in_(event_ids), EventParticipant.created_at, EventParticipant.id),
            "runtime_results": rows(RuntimeResult, RuntimeResult.agent_id.in_(agent_ids), RuntimeResult.tick_number, RuntimeResult.created_at, RuntimeResult.id),
            "relationships": rows(Relationship, Relationship.simulation_id == simulation.id, Relationship.source_agent_id, Relationship.target_agent_id),
            "agent_memories": rows(AgentMemory, AgentMemory.agent_id.in_(agent_ids), AgentMemory.created_tick, AgentMemory.id),
        }
        return {
            "schema_version": "slice6-snapshot-v1",
            "simulation": _serialize(simulation, 0),
            "config": _serialize(config, 0),
            **{
                name: [_serialize(row, sequence) for sequence, row in enumerate(values)]
                for name, values in collections.items()
            },
        }
