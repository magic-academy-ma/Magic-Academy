from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (
    AgentDetailResponse,
    AgentProfileResponse,
    AgentResponse,
    AgentStateDetailResponse,
    AgentStateResponse,
    DecisionExplanationDetailResponse,
    LocationResponse,
    MemoryResponse,
    OrganizationResponse,
    ProfessorProfileResponse,
    RelationshipResponse,
    StudentProfileResponse,
)
from app.domain.models import (
    Agent,
    AgentMemory,
    AgentState,
    Location,
    Organization,
    OrganizationMembership,
    ProfessorProfile,
    Relationship,
    RuntimeResult,
    Simulation,
    StudentProfile,
    User,
)


def _require_owned_agent(db: Session, agent_id: UUID, owner: User) -> Agent:
    agent = db.get(Agent, agent_id)
    if agent is None or agent.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    simulation = db.get(Simulation, agent.simulation_id)
    if simulation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if simulation.owner_id != owner.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent access denied")
    return agent


def _agent_response(db: Session, agent: Agent) -> AgentResponse:
    state = db.scalar(select(AgentState).where(AgentState.agent_id == agent.id))
    if state is None or state.location_id is None:
        raise HTTPException(status_code=500, detail="Agent state is incomplete")
    location = db.get(Location, state.location_id)
    if location is None:
        raise HTTPException(status_code=500, detail="Agent location is missing")
    student = db.get(StudentProfile, agent.id)
    professor = db.get(ProfessorProfile, agent.id)
    return AgentResponse(
        id=agent.id,
        fixture_key=agent.fixture_key,
        fixture_version=agent.fixture_version,
        name=agent.name,
        agent_type=agent.agent_type,
        active_status=agent.active_status,
        mbti_type=agent.mbti_type,
        profile=AgentProfileResponse(
            openness=agent.openness,
            conscientiousness=agent.conscientiousness,
            extraversion=agent.extraversion,
            agreeableness=agent.agreeableness,
            emotional_stability=agent.emotional_stability,
        ),
        student_profile=(
            StudentProfileResponse(grade=student.grade, interest_field=student.interest_field)
            if student else None
        ),
        professor_profile=(
            ProfessorProfileResponse(academic_rank=professor.academic_rank, specialty=professor.specialty)
            if professor else None
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


def get_agent_detail(db: Session, agent_id: UUID, owner: User) -> AgentDetailResponse:
    agent = _require_owned_agent(db, agent_id, owner)
    base = _agent_response(db, agent)
    memberships = db.execute(
        select(OrganizationMembership, Organization)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .where(OrganizationMembership.agent_id == agent.id, OrganizationMembership.left_at.is_(None))
        .order_by(Organization.organization_type, Organization.id)
    ).all()
    return AgentDetailResponse(
        **base.model_dump(),
        organizations=[
            OrganizationResponse(
                id=organization.id,
                organization_type=organization.organization_type,
                name=organization.name,
                membership_role=membership.membership_role,
            )
            for membership, organization in memberships
        ],
    )


def get_agent_state(db: Session, agent_id: UUID, owner: User) -> AgentStateDetailResponse:
    agent = _require_owned_agent(db, agent_id, owner)
    state = db.scalar(select(AgentState).where(AgentState.agent_id == agent.id))
    if state is None or state.location_id is None:
        raise HTTPException(status_code=500, detail="Agent state is incomplete")
    location = db.get(Location, state.location_id)
    if location is None:
        raise HTTPException(status_code=500, detail="Agent location is missing")
    return AgentStateDetailResponse(
        hunger=state.hunger,
        fatigue=state.fatigue,
        stress=state.stress,
        satisfaction=state.satisfaction,
        mood=state.mood,
        current_action=state.current_action,
        current_location=LocationResponse(id=location.id, code=location.code, name=location.name),
        updated_at=state.updated_at,
    )


def list_agent_memories(db: Session, agent_id: UUID, owner: User, limit: int) -> list[MemoryResponse]:
    _require_owned_agent(db, agent_id, owner)
    memories = db.scalars(
        select(AgentMemory)
        .where(AgentMemory.agent_id == agent_id)
        .order_by(AgentMemory.occurred_at.desc(), AgentMemory.id.desc())
        .limit(limit)
    ).all()
    return [
        MemoryResponse(
            id=item.id,
            content=item.content,
            memory_type=item.memory_type,
            importance=item.importance,
            created_tick=item.created_tick,
            occurred_at=item.occurred_at,
            event_id=item.event_id,
        )
        for item in memories
    ]


def list_agent_relationships(db: Session, agent_id: UUID, owner: User) -> list[RelationshipResponse]:
    _require_owned_agent(db, agent_id, owner)
    rows = db.execute(
        select(Relationship, Agent)
        .join(Agent, Agent.id == Relationship.target_agent_id)
        .where(Relationship.source_agent_id == agent_id)
        .order_by(Relationship.updated_at.desc(), Relationship.id.desc())
    ).all()
    return [
        RelationshipResponse(
            target_agent_id=target.id,
            target_agent_name=target.name,
            affection=relationship.affection,
            closeness=relationship.closeness,
            trust=relationship.trust,
            tension=relationship.tension,
            rivalry=relationship.rivalry,
            dependency=relationship.dependency,
            relationship_type=relationship.relationship_type,
            updated_at=relationship.updated_at,
        )
        for relationship, target in rows
    ]


def get_decision_explanation(
    db: Session, agent_id: UUID, owner: User, tick: int
) -> DecisionExplanationDetailResponse:
    _require_owned_agent(db, agent_id, owner)
    result = db.scalar(
        select(RuntimeResult)
        .where(RuntimeResult.agent_id == agent_id, RuntimeResult.tick_number == tick)
        .order_by(RuntimeResult.created_at.desc(), RuntimeResult.id.desc())
        .limit(1)
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision explanation not found")
    explanation = result.intent.get("decision_explanation", {})
    return DecisionExplanationDetailResponse(
        agent_id=agent_id,
        tick=tick,
        alternatives=explanation.get("alternatives", []),
        influencing_factors=explanation.get("influencing_factors", []),
    )
