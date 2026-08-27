import os
from uuid import uuid4

import pytest
from app.domain.models import Agent, Relationship, Simulation, User
from app.repositories.relationships import (
    InvalidRelationshipDeltaError,
    RelationshipDelta,
    StaleRelationshipValueError,
    apply_deltas,
    get_pair,
)
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required"
)


@pytest.fixture()
def relationship_db():
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE users, simulations, agents, relationships "
                "RESTART IDENTITY CASCADE"
            )
        )

    user_id = uuid4()
    simulation_id = uuid4()
    source_agent_id = uuid4()
    target_agent_id = uuid4()
    relationship_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            User(
                id=user_id,
                username="relationship-owner",
                display_name="Relationship Owner",
                password_hash="not-used-in-this-test",
                roles=["USER"],
            )
        )
        session.flush()
        session.add(
            Simulation(id=simulation_id, owner_id=user_id, name="Relationship Test")
        )
        session.flush()
        session.add_all(
            [
                Agent(
                    id=source_agent_id,
                    simulation_id=simulation_id,
                    fixture_key="student-01",
                    fixture_version="relationship-test-v1",
                    agent_type="student",
                    name="Source",
                    gender="unspecified",
                    mbti_type="ISTJ",
                ),
                Agent(
                    id=target_agent_id,
                    simulation_id=simulation_id,
                    fixture_key="student-02",
                    fixture_version="relationship-test-v1",
                    agent_type="student",
                    name="Target",
                    gender="unspecified",
                    mbti_type="ESTP",
                ),
            ]
        )
        session.flush()
        session.add(
            Relationship(
                id=relationship_id,
                simulation_id=simulation_id,
                source_agent_id=source_agent_id,
                target_agent_id=target_agent_id,
                affection=10,
                closeness=0,
                trust=20,
                tension=5,
                rivalry=0,
                dependency=0,
            )
        )

    yield session_factory, simulation_id, source_agent_id, target_agent_id
    engine.dispose()


def make_delta(source_agent_id, target_agent_id, **overrides) -> RelationshipDelta:
    values = {
        "source_agent_id": source_agent_id,
        "target_agent_id": target_agent_id,
        "metric": "trust",
        "before": 20,
        "requested_total": 5,
        "applied_delta": 5,
        "after": 25,
        "effect_ids": ("effect-1",),
        "policy_version": "policy-mvp-0.1",
        "resolver_version": "resolver-mvp-0.1",
        "resolution_id": "resolution-1",
    }
    values.update(overrides)
    return RelationshipDelta(**values)


def test_get_pair_is_directional(relationship_db) -> None:
    session_factory, _, source_agent_id, target_agent_id = relationship_db
    with session_factory() as session:
        assert get_pair(session, source_agent_id, target_agent_id) is not None
        assert get_pair(session, target_agent_id, source_agent_id) is None


def test_apply_deltas_flushes_without_committing(relationship_db) -> None:
    session_factory, _, source_agent_id, target_agent_id = relationship_db
    with session_factory() as session:
        apply_deltas(session, [make_delta(source_agent_id, target_agent_id)])
        assert get_pair(session, source_agent_id, target_agent_id).trust == 25
        session.rollback()

    with session_factory() as session:
        assert get_pair(session, source_agent_id, target_agent_id).trust == 20


def test_friend_entry_is_directional_and_uses_final_numeric_values(
    relationship_db,
) -> None:
    session_factory, _, source_agent_id, target_agent_id = relationship_db
    with session_factory.begin() as session:
        relationship = get_pair(session, source_agent_id, target_agent_id)
        relationship.trust = 49
        relationship.affection = 51
        relationship.closeness = 50

    delta = make_delta(
        source_agent_id,
        target_agent_id,
        before=49,
        requested_total=1,
        applied_delta=1,
        after=50,
    )
    with session_factory.begin() as session:
        apply_deltas(session, [delta])

    with session_factory() as session:
        relationship = get_pair(session, source_agent_id, target_agent_id)
        assert relationship.relationship_type == "friend"
        assert get_pair(session, target_agent_id, source_agent_id) is None


def test_friend_entry_rolls_back_with_relationship_delta(relationship_db) -> None:
    session_factory, _, source_agent_id, target_agent_id = relationship_db
    with session_factory.begin() as session:
        relationship = get_pair(session, source_agent_id, target_agent_id)
        relationship.trust = 49
        relationship.affection = 50
        relationship.closeness = 50

    with session_factory() as session:
        apply_deltas(
            session,
            [
                make_delta(
                    source_agent_id,
                    target_agent_id,
                    before=49,
                    requested_total=1,
                    applied_delta=1,
                    after=50,
                )
            ],
        )
        assert get_pair(session, source_agent_id, target_agent_id).relationship_type == "friend"
        session.rollback()

    with session_factory() as session:
        relationship = get_pair(session, source_agent_id, target_agent_id)
        assert relationship.trust == 49
        assert relationship.relationship_type is None


def test_apply_deltas_accepts_negative_closeness(relationship_db) -> None:
    session_factory, _, source_agent_id, target_agent_id = relationship_db
    delta = make_delta(
        source_agent_id,
        target_agent_id,
        metric="closeness",
        before=0,
        requested_total=-3,
        applied_delta=-3,
        after=-3,
    )
    with session_factory.begin() as session:
        apply_deltas(session, [delta])

    with session_factory() as session:
        assert get_pair(session, source_agent_id, target_agent_id).closeness == -3


def test_stale_delta_causes_caller_rollback_of_entire_batch(relationship_db) -> None:
    session_factory, _, source_agent_id, target_agent_id = relationship_db
    valid = make_delta(source_agent_id, target_agent_id)
    stale = make_delta(
        source_agent_id,
        target_agent_id,
        metric="affection",
        before=999,
        requested_total=-899,
        applied_delta=-899,
        after=100,
        resolution_id="resolution-2",
    )

    with pytest.raises(StaleRelationshipValueError), session_factory.begin() as session:
        apply_deltas(session, [valid, stale])

    with session_factory() as session:
        relationship = session.scalar(select(Relationship))
        assert relationship.trust == 20
        assert relationship.affection == 10


def test_apply_deltas_creates_missing_directional_pair(relationship_db) -> None:
    session_factory, simulation_id, source_agent_id, target_agent_id = relationship_db
    with session_factory.begin() as session:
        session.execute(text("DELETE FROM relationships"))

    delta = make_delta(
        source_agent_id,
        target_agent_id,
        before=0,
        requested_total=3,
        applied_delta=3,
        after=3,
    )
    with session_factory.begin() as session:
        apply_deltas(session, [delta])

    with session_factory() as session:
        relationship = get_pair(session, source_agent_id, target_agent_id)
        assert relationship is not None
        assert relationship.id.version == 7
        assert relationship.simulation_id == simulation_id
        assert relationship.trust == 3
        assert get_pair(session, target_agent_id, source_agent_id) is None


def test_apply_deltas_rejects_delta_exceeding_requested_total(relationship_db) -> None:
    session_factory, _, source_agent_id, target_agent_id = relationship_db
    invalid = make_delta(
        source_agent_id,
        target_agent_id,
        requested_total=5,
        applied_delta=6,
        after=26,
    )
    with session_factory() as session, pytest.raises(InvalidRelationshipDeltaError):
        apply_deltas(session, [invalid])


def test_apply_deltas_rejects_after_value_inconsistent_with_applied_delta(
    relationship_db,
) -> None:
    session_factory, _, source_agent_id, target_agent_id = relationship_db
    invalid = make_delta(
        source_agent_id,
        target_agent_id,
        requested_total=5,
        applied_delta=5,
        after=27,
    )
    with session_factory() as session, pytest.raises(
        InvalidRelationshipDeltaError,
        match="after = before \\+ applied_delta",
    ):
        apply_deltas(session, [invalid])


def test_apply_deltas_loads_agent_simulations_in_one_query(relationship_db) -> None:
    session_factory, _, source_agent_id, target_agent_id = relationship_db
    statements: list[str] = []

    def record_statement(
        _conn, _cursor, statement, _parameters, _context, _executemany
    ):
        statements.append(statement)

    engine = session_factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", record_statement)
    try:
        with session_factory() as session:
            apply_deltas(
                session,
                [
                    make_delta(source_agent_id, target_agent_id),
                    make_delta(
                        source_agent_id,
                        target_agent_id,
                        metric="affection",
                        before=10,
                        requested_total=2,
                        applied_delta=2,
                        after=12,
                        resolution_id="resolution-2",
                    ),
                ],
            )
            session.rollback()
    finally:
        event.remove(engine, "before_cursor_execute", record_statement)

    agent_queries = [
        statement
        for statement in statements
        if "FROM agents" in statement and "agents.simulation_id" in statement
    ]
    assert len(agent_queries) == 1
