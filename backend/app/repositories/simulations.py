from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Agent, AgentState, Location, Simulation


def get_simulation(db: Session, simulation_id: UUID) -> Simulation | None:
    return db.scalar(
        select(Simulation).where(Simulation.id == simulation_id, Simulation.deleted_at.is_(None))
    )


def list_agents_with_state(db: Session, simulation_id: UUID):
    return db.execute(
        select(Agent, AgentState, Location)
        .join(AgentState, AgentState.agent_id == Agent.id)
        .join(Location, Location.id == AgentState.location_id)
        .where(
            Agent.simulation_id == simulation_id,
            Agent.deleted_at.is_(None),
        )
        .order_by(Agent.fixture_key.asc())
    ).all()
