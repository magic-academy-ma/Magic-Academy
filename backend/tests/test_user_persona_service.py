import os

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from uuid6 import uuid7

from app.domain.models import Agent, Simulation, User, UserPersonaConfig
from app.services.fixtures import seed_slice_zero
from app.services.user_persona import (
    InvalidPersonaAgentError,
    InvalidPersonalityConfigurationError,
    PersonaChangeConflictError,
    PersonaInput,
    PersonaRequiredError,
    UserPersonaService,
)


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required"
)


@pytest.fixture()
def persona_context():
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE users, simulations RESTART IDENTITY CASCADE"))

    owner_id = uuid7()
    simulation_id = uuid7()
    with session_factory.begin() as session:
        session.add(
            User(
                id=owner_id,
                username="slice4-persona-owner",
                display_name="Slice 4 Persona Owner",
                password_hash="not-a-real-password-hash",
                roles=["USER"],
            )
        )
        session.flush()
        session.add(
            Simulation(id=simulation_id, owner_id=owner_id, name="Slice 4")
        )
        session.flush()
        seed_slice_zero(session, simulation_id)
    try:
        yield session_factory, owner_id, simulation_id
    finally:
        engine.dispose()


def persona_input(agent_id, *, mbti_type="INFP") -> PersonaInput:
    return PersonaInput(
        agent_id=agent_id,
        mbti_type=mbti_type,
        personality_rule_version="mbti-big-five-v0.1",
        openness=25,
        conscientiousness=-25,
        extraversion=-25,
        agreeableness=20,
        emotional_stability=0,
    )


def test_persona_can_change_before_start_without_mutating_previous_student(
    persona_context,
) -> None:
    session_factory, _, simulation_id = persona_context
    service = UserPersonaService()
    with session_factory.begin() as session:
        students = list(
            session.scalars(
                select(Agent)
                .where(
                    Agent.simulation_id == simulation_id,
                    Agent.agent_type == "student",
                )
                .order_by(Agent.fixture_key)
            )
        )
        original_first_mbti = students[0].mbti_type
        first = service.set_persona(
            session, simulation_id, persona_input(students[0].id)
        )
        assert first.agent_id == students[0].id
        second = service.set_persona(
            session,
            simulation_id,
            PersonaInput(
                agent_id=students[1].id,
                mbti_type="ESTP",
                personality_rule_version="mbti-big-five-v0.1",
                openness=-25,
                conscientiousness=-25,
                extraversion=25,
                agreeableness=-20,
                emotional_stability=0,
            ),
        )
        assert second.agent_id == students[1].id
        assert students[0].mbti_type == original_first_mbti
        assert session.query(UserPersonaConfig).count() == 1


def test_persona_rejects_professor_and_cross_simulation_student(
    persona_context,
) -> None:
    session_factory, owner_id, simulation_id = persona_context
    service = UserPersonaService()
    with session_factory.begin() as session:
        professor_id = session.scalar(
            select(Agent.id).where(
                Agent.simulation_id == simulation_id,
                Agent.agent_type == "professor",
            )
        )
        with pytest.raises(InvalidPersonaAgentError):
            service.set_persona(
                session, simulation_id, persona_input(professor_id)
            )

        other_simulation_id = uuid7()
        session.add(
            Simulation(
                id=other_simulation_id,
                owner_id=owner_id,
                name="Other Slice 4",
            )
        )
        session.flush()
        seed_slice_zero(session, other_simulation_id)
        other_student_id = session.scalar(
            select(Agent.id).where(
                Agent.simulation_id == other_simulation_id,
                Agent.fixture_key == "student-01",
            )
        )
        with pytest.raises(InvalidPersonaAgentError):
            service.set_persona(
                session, simulation_id, persona_input(other_student_id)
            )


def test_personality_rule_range_and_step_are_validated(persona_context) -> None:
    session_factory, _, simulation_id = persona_context
    service = UserPersonaService()
    with session_factory() as session:
        student_id = session.scalar(
            select(Agent.id).where(
                Agent.simulation_id == simulation_id,
                Agent.agent_type == "student",
            )
        )
        invalid = persona_input(student_id)
        invalid = PersonaInput(**{**invalid.__dict__, "extraversion": 10})
        with pytest.raises(InvalidPersonalityConfigurationError):
            service.set_persona(session, simulation_id, invalid)


def test_start_applies_and_locks_persona_atomically(persona_context) -> None:
    session_factory, _, simulation_id = persona_context
    service = UserPersonaService()
    with session_factory.begin() as session:
        student = session.scalar(
            select(Agent).where(
                Agent.simulation_id == simulation_id,
                Agent.fixture_key == "student-03",
            )
        )
        service.set_persona(session, simulation_id, persona_input(student.id))
        simulation = service.start(session, simulation_id)
        assert simulation.status == "running"
        assert simulation.started_at is not None
        assert student.persona_locked_at is not None
        assert student.agent_type == "student"
        assert student.mbti_type == "INFP"
        assert student.openness == 25

        with pytest.raises(PersonaChangeConflictError):
            service.set_persona(session, simulation_id, persona_input(student.id))


def test_start_requires_persona(persona_context) -> None:
    session_factory, _, simulation_id = persona_context
    with session_factory() as session:
        with pytest.raises(PersonaRequiredError):
            UserPersonaService().start(session, simulation_id)


def test_start_and_persona_lock_roll_back_together(persona_context) -> None:
    session_factory, _, simulation_id = persona_context
    service = UserPersonaService()
    with session_factory() as session:
        student = session.scalar(
            select(Agent).where(
                Agent.simulation_id == simulation_id,
                Agent.fixture_key == "student-03",
            )
        )
        original_openness = student.openness
        with pytest.raises(RuntimeError, match="start failed"):
            with session.begin_nested():
                service.set_persona(session, simulation_id, persona_input(student.id))
                service.start(session, simulation_id)
                raise RuntimeError("start failed")
        session.rollback()

    with session_factory() as session:
        simulation = session.get(Simulation, simulation_id)
        student = session.scalar(
            select(Agent).where(
                Agent.simulation_id == simulation_id,
                Agent.fixture_key == "student-03",
            )
        )
        assert simulation.status == "ready"
        assert simulation.started_at is None
        assert student.persona_locked_at is None
        assert student.openness == original_openness
