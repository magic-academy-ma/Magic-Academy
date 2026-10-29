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
from app.simulation.challenge.evaluation import TeamRevivalAchievement
from app.simulation.challenge.festival_booth import FestivalAchievement
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
