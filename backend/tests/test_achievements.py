import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.achievements import ACHIEVEMENTS, ACHIEVEMENTS_BY_ID, AchievementMode
from app.domain.models import User, UserAchievement
from app.main import app
from app.services.achievements import grant_achievements, list_achievements
from app.simulation.challenge.club_revival import ClubAchievement
from app.simulation.challenge.evaluation import TeamRevivalAchievement
from app.simulation.challenge.festival_booth import FestivalAchievement
from app.simulation.challenge.record import (
    INDECISIVE_THRESHOLD_SECONDS,
    InterventionRecord,
    chapter_achievements,
    ending_achievements,
)
from app.simulation.challenge.rumor import ACHIEVEMENTS as RUMOR_ACHIEVEMENTS

# ─── 카탈로그 ────────────────────────────────────────────────────────────────


def test_catalog_matches_spec_counts_and_unique_ids():
    assert len(ACHIEVEMENTS_BY_ID) == len(ACHIEVEMENTS)
    modes = [achievement.mode for achievement in ACHIEVEMENTS]
    assert modes.count(AchievementMode.STORY) == 24
    assert modes.count(AchievementMode.FREE) == 5
    assert all(len(achievement.id) <= 40 for achievement in ACHIEVEMENTS)


def test_catalog_contains_ids_already_judged_by_chapters():
    judged = {*RUMOR_ACHIEVEMENTS, *TeamRevivalAchievement, *FestivalAchievement}
    assert judged <= ACHIEVEMENTS_BY_ID.keys()


def test_every_story_achievement_has_a_judgement():
    slow = [InterventionRecord("1", "WATCH", INDECISIVE_THRESHOLD_SECONDS)]
    judged = {
        *RUMOR_ACHIEVEMENTS,
        *TeamRevivalAchievement,
        *ClubAchievement,
        *FestivalAchievement,
        *ending_achievements(cleared_chapters=4, semester_completed=True),
    }
    for chapter in range(1, 5):
        judged |= chapter_achievements(chapter=chapter, status="completed", interventions=slow)
    story = {a.id for a in ACHIEVEMENTS if a.mode == AchievementMode.STORY}
    assert judged == story


def test_grant_rejects_unknown_id_before_touching_db():
    with pytest.raises(ValueError):
        grant_achievements(None, None, ["NOT_AN_ACHIEVEMENT"])


# ─── 저장·조회 (실DB) ────────────────────────────────────────────────────────


@pytest.fixture
def db():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required")
    engine = create_engine(url)
    with engine.connect() as connection:
        outer = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            yield session
        outer.rollback()
    engine.dispose()


def _user(db: Session) -> User:
    user = User(
        id=uuid4(),
        username=str(uuid4()),
        display_name="achievement owner",
        password_hash="test",
        roles=["USER"],
    )
    db.add(user)
    db.commit()
    return user


def test_grant_stores_once_and_returns_only_new(db):
    owner = _user(db)
    assert grant_achievements(db, owner, ["CHAPTER1_CLEAR", "INDECISIVE"]) == {"CHAPTER1_CLEAR", "INDECISIVE"}
    db.commit()
    first = db.scalar(
        select(UserAchievement.achieved_at).where(
            UserAchievement.user_id == owner.id, UserAchievement.achievement_id == "CHAPTER1_CLEAR"
        )
    )

    assert grant_achievements(db, owner, ["CHAPTER1_CLEAR", "FIRST_SENTENCE"]) == {"FIRST_SENTENCE"}
    db.commit()

    rows = db.scalars(select(UserAchievement).where(UserAchievement.user_id == owner.id)).all()
    assert sorted(row.achievement_id for row in rows) == ["CHAPTER1_CLEAR", "FIRST_SENTENCE", "INDECISIVE"]
    assert next(row for row in rows if row.achievement_id == "CHAPTER1_CLEAR").achieved_at == first


def test_list_shows_catalog_order_and_only_own_achievements(db):
    owner, other = _user(db), _user(db)
    grant_achievements(db, owner, ["CURSE_LIFTED"])
    grant_achievements(db, other, ["CHAPTER1_CLEAR"])
    db.commit()

    items = list_achievements(db, owner)
    assert [item["id"] for item in items] == [achievement.id for achievement in ACHIEVEMENTS]
    achieved = {item["id"] for item in items if item["achieved"]}
    assert achieved == {"CURSE_LIFTED"}
    assert next(item for item in items if item["id"] == "CURSE_LIFTED")["achieved_at"]
    assert next(item for item in items if item["id"] == "CHAPTER1_CLEAR")["achieved_at"] is None


def test_http_lists_achievements_for_current_user(db):
    owner = _user(db)
    grant_achievements(db, owner, ["ENDING_CLEAR"])
    db.commit()

    def session():
        yield db

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[require_user_role] = lambda: owner
    try:
        with TestClient(app) as client:
            response = client.get("/v1/achievements")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == len(ACHIEVEMENTS)
    assert {item["id"] for item in data if item["achieved"]} == {"ENDING_CLEAR"}


# ─── 자유 모드 지급 요청 (실DB) ─────────────────────────────────────────────


def _free_simulation(db: Session):
    from app.domain.models import Agent, AgentState, Simulation
    from app.services.fixtures import seed_slice_zero

    owner = _user(db)
    simulation = Simulation(id=uuid4(), owner_id=owner.id, name="free mode")
    db.add(simulation)
    db.flush()
    seed_slice_zero(db, simulation.id)
    student = db.scalar(select(Agent).where(Agent.simulation_id == simulation.id, Agent.fixture_key == "student-01"))
    location_id = db.scalar(select(AgentState.location_id).where(AgentState.agent_id == student.id))
    db.commit()
    return owner, simulation, student, location_id


def _event(db: Session, simulation, location_id, event_type, agent):
    from app.domain.models import Event, EventParticipant

    event = Event(id=uuid4(), simulation_id=simulation.id, location_id=location_id, event_type=event_type,
                  title=event_type, status="completed", simulation_day=1)
    db.add(event)
    db.flush()
    db.add(EventParticipant(id=uuid4(), event_id=event.id, agent_id=agent.id))
    db.commit()
    return event


def _post(db: Session, owner: User, path: str, body: dict):
    def session():
        yield db

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[require_user_role] = lambda: owner
    try:
        with TestClient(app) as client:
            return client.post(path, json=body)
    finally:
        app.dependency_overrides.clear()


def test_inspecting_returned_student_grants_return_witness(db):
    owner, simulation, student, location_id = _free_simulation(db)
    body = {"simulation_id": str(simulation.id), "agent_id": str(student.id)}

    assert _post(db, owner, "/v1/achievements/free/inspector", body).json()["data"]["new_achievements"] == []

    _event(db, simulation, location_id, "student_missing", student)
    response = _post(db, owner, "/v1/achievements/free/inspector", body)
    assert response.status_code == 200
    assert response.json()["data"]["new_achievements"] == ["MISSING_STUDENT_RETURN"]


def test_opening_magical_discovery_event_grants_discovery_witness(db):
    owner, simulation, student, location_id = _free_simulation(db)
    other = _event(db, simulation, location_id, "curse_spread", student)
    discovery = _event(db, simulation, location_id, "magical_discovery", student)

    def post(event):
        return _post(db, owner, "/v1/achievements/free/event",
                     {"simulation_id": str(simulation.id), "event_id": str(event.id)})

    assert post(other).json()["data"]["new_achievements"] == []
    assert post(discovery).json()["data"]["new_achievements"] == ["MAGIC_DISCOVERY"]


def test_witness_request_rejects_other_users_simulation(db):
    _, simulation, student, _ = _free_simulation(db)
    stranger = _user(db)
    response = _post(db, stranger, "/v1/achievements/free/inspector",
                     {"simulation_id": str(simulation.id), "agent_id": str(student.id)})
    assert response.status_code == 403


def test_tick_grants_curse_achievements_to_simulation_owner(db):
    from app.services.achievements import grant_free_tick_achievements
    from app.simulation.free_mode_achievements import AgentStatus

    owner, simulation, student, _ = _free_simulation(db)
    before = {str(student.id): AgentStatus("inactive_temporary", False), "b": AgentStatus("active", False)}
    after = [
        {"agent_id": str(student.id), "active_status": "active", "cursed_until_tick": 7},
        {"agent_id": "b", "active_status": "active", "cursed_until_tick": None},
    ]
    assert grant_free_tick_achievements(db, simulation, before, after) == {"CURSE_TRIGGERED"}
    db.commit()
    achieved = {item["id"] for item in list_achievements(db, owner) if item["achieved"]}
    assert achieved == {"CURSE_TRIGGERED"}
