import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.domain.models import Agent, ClubChallengeRun, Simulation, User
from app.services.club_challenge import (
    ClubChallengeChoiceError,
    advance_club_challenge,
    club_chapter_record,
    start_club_challenge,
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
        display_name="challenge owner",
        password_hash="test",
        roles=["USER"],
    )
    db.add(user)
    db.commit()
    return user


def test_full_club_challenge_is_persisted_and_completed(db: Session, owner: User):
    simulation, run = start_club_challenge(db, owner)
    assert run.member_count == 2
    assert run.reputation == 40
    assert len(run.initial_member_affections) == 2
    runtime = AgentRuntime(MockLLMClient(), model="club-challenge-test")
    choices = {3: "REASSIGN_ROLES", 6: "PROFESSOR_REFERRAL", 9: "SAFE_OPERATION"}

    agents_by_id = {
        agent.id: agent
        for agent in db.scalars(
            select(Agent).where(Agent.simulation_id == simulation.id)
        )
    }
    run, first_tick = advance_club_challenge(
        db,
        run_id=run.id,
        owner=owner,
        runtime=runtime,
        choice=None,
    )
    assert {
        agents_by_id[item.agent_id].fixture_key for item in first_tick.runtime_results
    } == {"student-01", "student-02"}

    tick_three_result = None
    for tick in range(2, 10):
        run, result = advance_club_challenge(
            db,
            run_id=run.id,
            owner=owner,
            runtime=runtime,
            choice=choices.get(tick),
        )
        if tick == 3:
            tick_three_result = result

    db.expire_all()
    stored = db.scalar(select(ClubChallengeRun).where(ClubChallengeRun.id == run.id))
    stored_simulation = db.get(Simulation, simulation.id)
    assert stored.current_tick == 9
    assert stored.member_count == 3
    assert stored.reputation == 80
    assert stored.status == "completed"
    assert stored.ending == "CONDITIONAL"
    assert [(item["point"], item["choice"]) for item in stored.interventions] == [
        ("3", "REASSIGN_ROLES"),
        ("6", "PROFESSOR_REFERRAL"),
        ("9", "SAFE_OPERATION"),
    ]
    record = club_chapter_record(stored)
    assert record.chapter == 3
    assert record.grade == "MIXED"
    assert len(record.interventions) == 3
    assert stored_simulation.current_tick == 9
    assert stored_simulation.status == "completed"
    assert len(tick_three_result.runtime_results) == 2


def test_choice_is_required_at_intervention_tick(db: Session, owner: User):
    _, run = start_club_challenge(db, owner)
    runtime = AgentRuntime(MockLLMClient(), model="club-challenge-test")
    for _ in range(2):
        run, _ = advance_club_challenge(
            db,
            run_id=run.id,
            owner=owner,
            runtime=runtime,
            choice=None,
        )
    with pytest.raises(ClubChallengeChoiceError):
        advance_club_challenge(
            db,
            run_id=run.id,
            owner=owner,
            runtime=runtime,
            choice=None,
        )
