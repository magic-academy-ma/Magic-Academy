from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.api.schemas import (
    AgentProfileResponse,
    AgentResponse,
    AgentStateResponse,
    LocationResponse,
    ProfessorProfileResponse,
    StudentProfileResponse,
)
from app.domain.models import Simulation, User
from app.repositories.simulations import get_simulation, list_agents_with_state
from app.services.fixtures import seed_slice_zero
from app.services.simulation_snapshots import SimulationSnapshotService


def create_simulation(db: Session, owner: User, name: str) -> Simulation:
    simulation = Simulation(id=uuid7(), owner_id=owner.id, name=name.strip())
    db.add(simulation)
    try:
        db.flush()
        seed_slice_zero(db, simulation.id)
        SimulationSnapshotService().create_snapshot(db, simulation)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(simulation)
    return simulation


def require_owned_simulation(db: Session, simulation_id: UUID, owner: User) -> Simulation:
    simulation = get_simulation(db, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    if simulation.owner_id != owner.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Simulation access denied")
    return simulation


def get_agent_responses(db: Session, simulation_id: UUID, owner: User) -> list[AgentResponse]:
    require_owned_simulation(db, simulation_id, owner)
    responses = []
    for agent, state, location, student_profile, professor_profile in list_agents_with_state(
        db, simulation_id
    ):
        responses.append(
            AgentResponse(
                id=agent.id,
                fixture_key=agent.fixture_key,
                fixture_version=agent.fixture_version,
                name=agent.name,
                agent_type=agent.agent_type,
                mbti_type=agent.mbti_type,
                profile=AgentProfileResponse(
                    openness=agent.openness,
                    conscientiousness=agent.conscientiousness,
                    extraversion=agent.extraversion,
                    agreeableness=agent.agreeableness,
                    emotional_stability=agent.emotional_stability,
                ),
                student_profile=(
                    StudentProfileResponse(
                        grade=student_profile.grade,
                        interest_field=student_profile.interest_field,
                    )
                    if student_profile
                    else None
                ),
                professor_profile=(
                    ProfessorProfileResponse(
                        academic_rank=professor_profile.academic_rank,
                        specialty=professor_profile.specialty,
                    )
                    if professor_profile
                    else None
                ),
                state=AgentStateResponse(
                    hunger=state.hunger,
                    fatigue=state.fatigue,
                    stress=state.stress,
                    satisfaction=state.satisfaction,
                    mood=state.mood,
                    current_action=state.current_action,
                ),
                location=LocationResponse(id=location.id, code=location.code, name=location.name),
            )
        )
    return responses
