from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Agent, Simulation, StudentProfile, UserPersonaConfig


def get_simulation_for_update(
    session: Session, simulation_id: UUID
) -> Simulation | None:
    return session.scalar(
        select(Simulation)
        .where(Simulation.id == simulation_id, Simulation.deleted_at.is_(None))
        .with_for_update()
    )


def get_student(
    session: Session, simulation_id: UUID, agent_id: UUID
) -> Agent | None:
    return session.scalar(
        select(Agent)
        .join(StudentProfile, StudentProfile.agent_id == Agent.id)
        .where(
            Agent.id == agent_id,
            Agent.simulation_id == simulation_id,
            Agent.agent_type == "student",
            Agent.deleted_at.is_(None),
        )
    )


def get_config(
    session: Session, simulation_id: UUID
) -> UserPersonaConfig | None:
    return session.get(UserPersonaConfig, simulation_id)


def upsert_config(
    session: Session,
    simulation_id: UUID,
    values: dict,
) -> UserPersonaConfig:
    config = session.get(UserPersonaConfig, simulation_id)
    if config is None:
        config = UserPersonaConfig(simulation_id=simulation_id, **values)
        session.add(config)
    else:
        for name, value in values.items():
            setattr(config, name, value)
    session.flush()
    return config
