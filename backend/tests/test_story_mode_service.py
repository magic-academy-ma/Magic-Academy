import os
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.domain.models import Relationship, StoryChapterRun, User, UserAchievement
from app.services.festival_booth_chapter import (
    advance_festival_booth,
    festival_booth_achievements,
    festival_booth_record,
    start_festival_booth,
)
from app.services.story_chapter_common import StoryChapterChoiceError
from app.services.story_mode import (
    complete_current_chapter,
    start_current_chapter,
    start_story,
)
from app.services.team_revival_chapter import (
    advance_team_revival,
    start_team_revival,
    team_revival_achievements,
    team_revival_record,
)
from app.simulation.agent_runtime import AgentRuntime, MockLLMClient


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


@pytest.fixture
def owner(db: Session) -> User:
    user = User(
        id=uuid4(),
        username=str(uuid4()),
        display_name="story owner",
        password_hash="test",
        roles=["USER"],
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def runtime() -> AgentRuntime:
    return AgentRuntime(MockLLMClient(), model="story-mode-test")


def _play_team_revival(db, owner, runtime, run_id):
    choices = {2: "MEDIATE", 5: "PERSUADE_LEAVER"}
    run = None
    for tick in range(1, 10):
        run = advance_team_revival(
            db, run_id=run_id, owner=owner, runtime=runtime, choice=choices.get(tick)
        )
    return run


def _play_festival_booth(db, owner, runtime, run, roles=True):
    agent_ids = run.state["agent_ids"]
    role_cycle = ["COUNTER", "COUNTER", "PRODUCTION", "SUPPLY", "PROMOTION"]
    for tick in range(1, 10):
        kwargs = {}
        if tick == 2:
            kwargs = {
                "concept": "FOOD",
                "roles": dict(zip(agent_ids, role_cycle, strict=True)) if roles else None,
            }
        elif tick == 6:
            kwargs = {"choice": "SEND_HELP", "help_agent_id": agent_ids[0]}
        elif tick == 9:
            kwargs = {"choice": "SWAP_ROLES"}
        run = advance_festival_booth(db, run_id=run.id, owner=owner, runtime=runtime, **kwargs)
    return run


def test_team_revival_runs_nine_ticks_and_leaves_a_chapter_two_record(db, owner, runtime):
    run = start_team_revival(db, owner)
    roster = run.state["roster"]
    leader_to_member = db.scalar(
        select(Relationship).where(
            Relationship.simulation_id == run.simulation_id,
            Relationship.source_agent_id == UUID(roster["leader"]),
            Relationship.target_agent_id == UUID(roster["ignored_member"]),
        )
    )
    assert leader_to_member.affection < 0
    assert len(run.state["initial_affections"]) == 20

    run = _play_team_revival(db, owner, runtime, run.id)

    assert run.status == "completed"
    assert run.current_tick == 9
    assert run.ending in {"UNITED", "PARTIAL", "DISBANDED"}
    assert [(item["point"], item["choice"]) for item in run.interventions] == [
        ("ROUND1", "MEDIATE"),
        ("ROUND2", "PERSUADE_LEAVER"),
    ]
    record = team_revival_record(run)
    assert record.chapter == 2


def test_team_revival_requires_choice_at_intervention_tick(db, owner, runtime):
    run = start_team_revival(db, owner)
    advance_team_revival(db, run_id=run.id, owner=owner, runtime=runtime, choice=None)
    with pytest.raises(StoryChapterChoiceError):
        advance_team_revival(db, run_id=run.id, owner=owner, runtime=runtime, choice=None)


def test_festival_booth_runs_nine_ticks_and_records_staffing(db, owner, runtime):
    run = start_festival_booth(db, owner)
    run = _play_festival_booth(db, owner, runtime, run)

    assert run.status == "completed"
    assert run.ending in {"POPULAR", "COMPLETED", "HALTED"}
    assert [record["tick"] for record in run.state["staffing"]] == [4, 6, 7, 9]
    assert [item["choice"] for item in run.interventions] == [
        "ASSIGN_ROLES",
        "SEND_HELP",
        "SWAP_ROLES",
    ]
    assert festival_booth_record(run).chapter == 4


def test_festival_booth_without_roles_records_watch(db, owner, runtime):
    run = start_festival_booth(db, owner)
    advance_festival_booth(db, run_id=run.id, owner=owner, runtime=runtime)
    run = advance_festival_booth(
        db, run_id=run.id, owner=owner, runtime=runtime, concept="EXHIBITION", roles=None
    )
    assert run.interventions[0]["choice"] == "WATCH"
    assert run.state["incident_subtype"] in {"RIVAL_BOOTH_ISSUE", "INGREDIENT_SHORTAGE"}


def test_story_moves_through_chapters_in_order_and_ends_with_final(db, owner, runtime):
    story = start_story(db, owner)
    assert story.chapter == 1

    story = start_current_chapter(db, owner, story.id)
    first_run_id = story.chapter_run_ids["1"]
    assert start_current_chapter(db, owner, story.id).chapter_run_ids["1"] == first_run_id
    with pytest.raises(HTTPException) as unfinished:
        complete_current_chapter(db, owner, story.id)
    assert unfinished.value.status_code == 409

    # CHAPTER 1·3 진행은 각 챕터 서비스 테스트가 맡는다. 여기서는 기록만 채우고 넘어간다.
    good = {"ending": "-", "grade": "GOOD", "interventions": []}
    story.records = {"1": {**good, "chapter": 1}}
    story.chapter = 2
    db.commit()

    story = start_current_chapter(db, owner, story.id)
    team_run = _play_team_revival(db, owner, runtime, UUID(story.chapter_run_ids["2"]))
    story, granted = complete_current_chapter(db, owner, story.id)
    assert story.chapter == 3
    assert story.records["2"]["chapter"] == 2
    assert "CHAPTER2_CLEAR" in granted
    assert granted == team_revival_achievements(db, team_run)

    story.records = {**story.records, "3": {**good, "chapter": 3}}
    story.chapter = 4
    db.commit()

    story = start_current_chapter(db, owner, story.id)
    chapter_four = db.get(StoryChapterRun, UUID(story.chapter_run_ids["4"]))
    chapter_four = _play_festival_booth(db, owner, runtime, chapter_four)
    story, granted = complete_current_chapter(db, owner, story.id)
    assert {"CHAPTER4_CLEAR", "ENDING_UNLOCKED", "ENDING_CLEAR"} <= granted
    assert granted - {"ENDING_UNLOCKED", "ENDING_CLEAR"} <= festival_booth_achievements(chapter_four)
    stored = set(
        db.scalars(select(UserAchievement.achievement_id).where(UserAchievement.user_id == owner.id))
    )
    assert {"CHAPTER2_CLEAR", "CHAPTER4_CLEAR", "ENDING_CLEAR"} <= stored
    # FINAL 이후에는 다시 완료해도 아무것도 지급하지 않는다.
    assert complete_current_chapter(db, owner, story.id)[1] == frozenset()

    assert story.chapter == 5
    assert story.status == "completed"
    assert story.final_ending in {"BEST", "NORMAL", "BAD"}
    if {story.records["2"]["grade"], story.records["4"]["grade"]} != {"GOOD"}:
        assert story.final_ending == "NORMAL"
