from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import Agent, AgentState, Location


@dataclass(frozen=True)
class AgentFixture:
    key: str
    version: str
    name: str
    agent_type: str
    mbti_type: str
    grade: int | None
    location_code: str


AGENT_FIXTURES = (
    AgentFixture("student-01", "student-fixture-v0.2", "아델", "student", "ISTJ", 1, "dormitory"),
    AgentFixture("student-02", "student-fixture-v0.2", "레오", "student", "ESTP", 2, "dormitory"),
    AgentFixture("student-03", "student-fixture-v0.2", "리아", "student", "INFP", 1, "dormitory"),
    AgentFixture("student-04", "student-fixture-v0.2", "카이", "student", "ENTJ", 3, "dormitory"),
    AgentFixture("student-05", "student-fixture-v0.2", "세라", "student", "ESFJ", 4, "dormitory"),
    AgentFixture("professor-01", "professor-fixture-v0.2", "에단", "professor", "ISTJ", None, "classroom"),
)

LOCATIONS = {"dormitory": "기숙사", "classroom": "교실"}


def seed_slice_zero(db: Session, simulation_id: UUID) -> None:
    location_ids: dict[str, UUID] = {}
    for code, name in LOCATIONS.items():
        statement = (
            insert(Location)
            .values(id=uuid7(), simulation_id=simulation_id, code=code, name=name, is_active=True)
            .on_conflict_do_update(
                constraint="uq_locations_simulation_code",
                set_={"name": name, "is_active": True},
            )
            .returning(Location.id)
        )
        location_ids[code] = db.execute(statement).scalar_one()

    for fixture in AGENT_FIXTURES:
        agent_statement = (
            insert(Agent)
            .values(
                id=uuid7(),
                simulation_id=simulation_id,
                fixture_key=fixture.key,
                fixture_version=fixture.version,
                name=fixture.name,
                agent_type=fixture.agent_type,
                mbti_type=fixture.mbti_type,
                grade=fixture.grade,
                openness=50,
                conscientiousness=50,
                extraversion=50,
                agreeableness=50,
                emotional_stability=50,
                active_status="active",
            )
            .on_conflict_do_update(
                constraint="uq_agents_simulation_fixture_key",
                set_={
                    "fixture_version": fixture.version,
                    "name": fixture.name,
                    "agent_type": fixture.agent_type,
                    "mbti_type": fixture.mbti_type,
                    "grade": fixture.grade,
                    "deleted_at": None,
                },
            )
            .returning(Agent.id)
        )
        agent_id = db.execute(agent_statement).scalar_one()
        state_statement = (
            insert(AgentState)
            .values(
                id=uuid7(),
                simulation_id=simulation_id,
                agent_id=agent_id,
                location_id=location_ids[fixture.location_code],
                hunger=50,
                fatigue=0,
                stress=0,
                satisfaction=50,
                mood=0,
            )
            .on_conflict_do_update(
                constraint="uq_agent_states_agent_id",
                set_={
                    "simulation_id": simulation_id,
                    "location_id": location_ids[fixture.location_code],
                },
            )
        )
        db.execute(state_statement)
