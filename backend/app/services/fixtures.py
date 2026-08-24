from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import (
    Agent,
    AgentState,
    Event,
    EventParticipant,
    Location,
    ProfessorProfile,
    StudentProfile,
)


@dataclass(frozen=True)
class AgentFixture:
    key: str
    version: str
    name: str
    agent_type: str
    mbti_type: str
    gender: str
    location_code: str
    openness: int
    conscientiousness: int
    extraversion: int
    agreeableness: int
    emotional_stability: int
    hunger: int
    fatigue: int
    stress: int
    satisfaction: int
    mood: int
    grade: int | None = None
    interest_field: str | None = None
    academic_rank: str | None = None
    specialty: str | None = None


AGENT_FIXTURES = (
    AgentFixture("student-01", "student-fixture-v0.2", "아델", "student", "ISTJ", "female", "dormitory", -25, 25, -25, -20, 0, 25, 15, 20, 60, 0, 1, "방어 마법"),
    AgentFixture("student-02", "student-fixture-v0.2", "레오", "student", "ESTP", "male", "dormitory", -25, -25, 25, -20, 0, 35, 20, 15, 65, 10, 2, "마법 생물"),
    AgentFixture("student-03", "student-fixture-v0.2", "리아", "student", "INFP", "female", "dormitory", 25, -25, -25, 20, 0, 20, 15, 20, 55, 0, 1, "고대 마법"),
    AgentFixture("student-04", "student-fixture-v0.2", "카이", "student", "ENTJ", "male", "dormitory", 25, 25, 25, -20, 0, 25, 10, 25, 60, 5, 3, "마법 도구 제작"),
    AgentFixture("student-05", "student-fixture-v0.2", "세라", "student", "ESFJ", "female", "dormitory", -25, 25, 25, 20, 0, 30, 20, 15, 65, 10, 4, "마법약"),
    AgentFixture("professor-01", "professor-fixture-v0.2", "에단", "professor", "ISTJ", "male", "classroom", -20, 40, -25, 10, 35, 20, 15, 20, 70, 20, academic_rank="통합 교수", specialty="통합마법학과 수업·시험·학생 지도"),
)

LOCATIONS = {"dormitory": "기숙사", "classroom": "교실"}
SLICE_ONE_CLASS_TITLE = "통합마법학 개론"


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
                gender=fixture.gender,
                openness=fixture.openness,
                conscientiousness=fixture.conscientiousness,
                extraversion=fixture.extraversion,
                agreeableness=fixture.agreeableness,
                emotional_stability=fixture.emotional_stability,
                active_status="active",
            )
            .on_conflict_do_update(
                constraint="uq_agents_simulation_fixture_key",
                set_={
                    "fixture_version": fixture.version,
                    "name": fixture.name,
                    "agent_type": fixture.agent_type,
                    "mbti_type": fixture.mbti_type,
                    "gender": fixture.gender,
                    "openness": fixture.openness,
                    "conscientiousness": fixture.conscientiousness,
                    "extraversion": fixture.extraversion,
                    "agreeableness": fixture.agreeableness,
                    "emotional_stability": fixture.emotional_stability,
                    "deleted_at": None,
                },
            )
            .returning(Agent.id)
        )
        agent_id = db.execute(agent_statement).scalar_one()
        if fixture.agent_type == "student":
            profile_statement = (
                insert(StudentProfile)
                .values(
                    agent_id=agent_id,
                    grade=fixture.grade,
                    interest_field=fixture.interest_field,
                )
                .on_conflict_do_update(
                    index_elements=[StudentProfile.agent_id],
                    set_={
                        "grade": fixture.grade,
                        "interest_field": fixture.interest_field,
                    },
                )
            )
        else:
            profile_statement = (
                insert(ProfessorProfile)
                .values(
                    agent_id=agent_id,
                    academic_rank=fixture.academic_rank,
                    specialty=fixture.specialty,
                )
                .on_conflict_do_update(
                    index_elements=[ProfessorProfile.agent_id],
                    set_={
                        "academic_rank": fixture.academic_rank,
                        "specialty": fixture.specialty,
                    },
                )
            )
        db.execute(profile_statement)
        state_statement = (
            insert(AgentState)
            .values(
                id=uuid7(),
                simulation_id=simulation_id,
                agent_id=agent_id,
                location_id=location_ids[fixture.location_code],
                hunger=fixture.hunger,
                fatigue=fixture.fatigue,
                stress=fixture.stress,
                satisfaction=fixture.satisfaction,
                mood=fixture.mood,
                current_action=None,
            )
            .on_conflict_do_update(
                constraint="uq_agent_states_agent_id",
                set_={
                    "simulation_id": simulation_id,
                    "location_id": location_ids[fixture.location_code],
                    "hunger": fixture.hunger,
                    "fatigue": fixture.fatigue,
                    "stress": fixture.stress,
                    "satisfaction": fixture.satisfaction,
                    "mood": fixture.mood,
                    "current_action": None,
                },
            )
        )
        db.execute(state_statement)

    seed_slice_one_class_event(db, simulation_id, location_ids["classroom"])


def seed_slice_one_class_event(
    db: Session, simulation_id: UUID, classroom_id: UUID
) -> None:
    event = db.scalar(
        select(Event).where(
            Event.simulation_id == simulation_id,
            Event.event_type == "class",
            Event.title == SLICE_ONE_CLASS_TITLE,
        )
    )
    if event is None:
        event = Event(
            id=uuid7(),
            simulation_id=simulation_id,
            location_id=classroom_id,
            event_type="class",
            title=SLICE_ONE_CLASS_TITLE,
            description="아델과 에단 교수가 참여하는 Slice 1 수업",
            status="scheduled",
            simulation_day=1,
            event_metadata={"fixture_key": "slice-1-class-01"},
        )
        db.add(event)
        db.flush()

    participant_ids = set(
        db.scalars(
            select(Agent.id).where(
                Agent.simulation_id == simulation_id,
                Agent.fixture_key.in_(("student-01", "professor-01")),
            )
        )
    )
    existing_ids = set(
        db.scalars(
            select(EventParticipant.agent_id).where(
                EventParticipant.event_id == event.id
            )
        )
    )
    for agent_id in participant_ids - existing_ids:
        db.add(
            EventParticipant(
                id=uuid7(),
                event_id=event.id,
                agent_id=agent_id,
                participant_role="participant",
                result={},
            )
        )
