from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import (
    Agent,
    AgentState,
    Location,
    ProfessorProfile,
    Relationship,
    Simulation,
    StudentProfile,
)


def get_simulation(db: Session, simulation_id: UUID) -> Simulation | None:
    return db.scalar(
        select(Simulation).where(Simulation.id == simulation_id, Simulation.deleted_at.is_(None))
    )


def list_simulation_locations(db: Session, simulation_id: UUID) -> list[Location]:
    return list(
        db.scalars(
            select(Location)
            .where(Location.simulation_id == simulation_id)
            .order_by(Location.code.asc())
        ).all()
    )


def list_agents_with_state(db: Session, simulation_id: UUID):
    return db.execute(
        select(Agent, AgentState, Location, StudentProfile, ProfessorProfile)
        .join(AgentState, AgentState.agent_id == Agent.id)
        .join(Location, Location.id == AgentState.location_id)
        .outerjoin(StudentProfile, StudentProfile.agent_id == Agent.id)
        .outerjoin(ProfessorProfile, ProfessorProfile.agent_id == Agent.id)
        .where(
            Agent.simulation_id == simulation_id,
            Agent.deleted_at.is_(None),
        )
        .order_by(Agent.fixture_key.asc())
    ).all()


def list_runtime_agents(db: Session, simulation_id: UUID) -> list[Agent]:
    return list(
        db.scalars(
            select(Agent)
            .where(
                Agent.simulation_id == simulation_id,
                Agent.deleted_at.is_(None),
                Agent.agent_type.in_(("student", "professor", "user_persona")),
            )
            .order_by(Agent.fixture_key.asc())
        ).all()
    )


def list_runtime_agent_states(
    db: Session,
    agent_ids: list[UUID],
) -> list[AgentState]:
    if not agent_ids:
        return []
    return list(
        db.scalars(
            select(AgentState)
            .where(AgentState.agent_id.in_(agent_ids))
            .order_by(AgentState.agent_id.asc())
        ).all()
    )


def list_active_runtime_location_ids(db: Session, simulation_id: UUID) -> list[UUID]:
    return list(
        db.scalars(
            select(Location.id)
            .where(
                Location.simulation_id == simulation_id,
                Location.is_active.is_(True),
            )
            .order_by(Location.id.asc())
        ).all()
    )


def list_runtime_relationships(db: Session, simulation_id: UUID) -> list[Relationship]:
    return list(
        db.scalars(
            select(Relationship)
            .where(Relationship.simulation_id == simulation_id)
            .order_by(
                Relationship.source_agent_id.asc(),
                Relationship.target_agent_id.asc(),
            )
        ).all()
    )
