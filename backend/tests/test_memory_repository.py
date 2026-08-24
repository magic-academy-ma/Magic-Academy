import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.domain.models import Agent, AgentMemory, Event, Simulation, User
from app.repositories.memory_repository import MemoryCreateInput, MemoryRepository

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")


def vector(first: float, second: float = 0.0) -> list[float]:
    return [first, second, *([0.0] * 1534)]


@pytest.fixture()
def memory_context():
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE agent_memories, agents, simulations, users "
                "RESTART IDENTITY CASCADE"
            )
        )

    user_id = uuid4()
    simulation_id = uuid4()
    agent_id = uuid4()
    other_agent_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            User(
                id=user_id,
                username="memory-owner",
                display_name="Memory Owner",
                password_hash="not-a-real-password-hash",
                roles=["USER"],
            )
        )
        session.flush()
        session.add(
            Simulation(id=simulation_id, owner_id=user_id, name="Memory Test")
        )
        session.flush()
        for identifier, key in ((agent_id, "student-01"), (other_agent_id, "student-02")):
            session.add(
                Agent(
                    id=identifier,
                    simulation_id=simulation_id,
                    fixture_key=key,
                    fixture_version="student-fixture-v0.2",
                    agent_type="student",
                    name=key,
                    mbti_type="ISTJ",
                )
            )
    try:
        yield session_factory, agent_id, other_agent_id
    finally:
        engine.dispose()


def create_memory(
    repository: MemoryRepository,
    session,
    agent_id,
    *,
    tick: int,
    importance: int = 50,
    embedding: list[float] | None = None,
):
    embedded_at = datetime(2026, 8, 14, tzinfo=UTC) + timedelta(minutes=tick)
    return repository.create(
        session,
        MemoryCreateInput(
            agent_id=agent_id,
            content=f"memory-{tick}",
            memory_type="observation",
            importance=importance,
            created_tick=tick,
            occurred_at=datetime(2026, 8, 14, tzinfo=UTC) + timedelta(minutes=tick),
            embedding=embedding,
            embedding_model=None if embedding is None else "test-model",
            embedding_version=None if embedding is None else "v1",
            embedded_at=None if embedding is None else embedded_at,
        ),
    )


def test_create_flushes_without_committing(memory_context) -> None:
    session_factory, agent_id, _ = memory_context
    repository = MemoryRepository()
    with session_factory() as session:
        created = create_memory(repository, session, agent_id, tick=1, embedding=vector(1.0))
        assert created.id.version == 7
        assert created.embedding == vector(1.0)
        assert session.get(AgentMemory, created.id) is not None
        session.rollback()
    with session_factory() as session:
        assert session.get(AgentMemory, created.id) is None


def test_create_rejects_event_from_another_simulation(memory_context) -> None:
    session_factory, agent_id, _ = memory_context
    repository = MemoryRepository()
    with session_factory() as session:
        simulation = session.scalar(select(Simulation).limit(1))
        other_simulation = Simulation(
            id=uuid4(), owner_id=simulation.owner_id, name="Other Simulation"
        )
        session.add(other_simulation)
        session.flush()
        other_event = Event(
            id=uuid4(),
            simulation_id=other_simulation.id,
            event_type="class",
            title="Other Class",
            status="scheduled",
            simulation_day=1,
        )
        session.add(other_event)
        session.flush()

        with pytest.raises(IntegrityError):
            repository.create(
                session,
                MemoryCreateInput(
                    agent_id=agent_id,
                    event_id=other_event.id,
                    content="invalid cross-simulation memory",
                    memory_type="observation",
                    importance=50,
                    created_tick=1,
                    occurred_at=datetime.now(UTC),
                ),
            )


def test_create_rejects_partial_embedding_metadata(memory_context) -> None:
    session_factory, agent_id, _ = memory_context
    with session_factory() as session, pytest.raises(IntegrityError):
        MemoryRepository().create(
            session,
            MemoryCreateInput(
                agent_id=agent_id,
                content="partial embedding",
                memory_type="observation",
                importance=50,
                created_tick=1,
                occurred_at=datetime.now(UTC),
                embedding=vector(1.0),
            ),
        )


def test_retrieve_returns_latest_two_then_similarity_three_without_duplicates(
    memory_context,
) -> None:
    session_factory, agent_id, other_agent_id = memory_context
    repository = MemoryRepository()
    with session_factory.begin() as session:
        similar = [
            create_memory(repository, session, agent_id, tick=1, embedding=vector(1.0, 0.0)),
            create_memory(repository, session, agent_id, tick=2, embedding=vector(0.9, 0.1)),
            create_memory(repository, session, agent_id, tick=3, embedding=vector(0.8, 0.2)),
        ]
        latest = [
            create_memory(repository, session, agent_id, tick=9),
            create_memory(repository, session, agent_id, tick=10),
        ]
        create_memory(repository, session, agent_id, tick=11, embedding=vector(1.0))
        create_memory(repository, session, other_agent_id, tick=8, embedding=vector(1.0))

    with session_factory() as session:
        rows = repository.retrieve_for_runtime(session, agent_id, 10, vector(1.0))

    assert [row.id for row in rows[:2]] == [latest[1].id, latest[0].id]
    assert [row.id for row in rows[2:]] == [item.id for item in similar]
    assert len({row.id for row in rows}) == 5


def test_retrieve_deduplicates_latest_and_similarity(memory_context) -> None:
    session_factory, agent_id, _ = memory_context
    repository = MemoryRepository()
    with session_factory.begin() as session:
        for tick in range(1, 5):
            create_memory(repository, session, agent_id, tick=tick, embedding=vector(1.0, tick / 10))

    with session_factory() as session:
        rows = repository.retrieve_for_runtime(session, agent_id, 10, vector(1.0))

    assert len(rows) <= 5
    assert len({row.id for row in rows}) == len(rows)


def test_retrieve_fills_three_distinct_similarity_slots_when_latest_overlap(
    memory_context,
) -> None:
    session_factory, agent_id, _ = memory_context
    repository = MemoryRepository()
    with session_factory.begin() as session:
        older = [
            create_memory(
                repository,
                session,
                agent_id,
                tick=tick,
                embedding=vector(1.0, tick / 100),
            )
            for tick in range(1, 4)
        ]
        latest = [
            create_memory(
                repository,
                session,
                agent_id,
                tick=tick,
                embedding=vector(1.0),
            )
            for tick in (9, 10)
        ]

    with session_factory() as session:
        rows = repository.retrieve_for_runtime(session, agent_id, 10, vector(1.0))

    assert [row.id for row in rows[:2]] == [latest[1].id, latest[0].id]
    assert {row.id for row in rows[2:]} == {row.id for row in older}
    assert len(rows) == 5


def test_enforce_cap_deletes_lowest_importance_then_oldest_tick(memory_context) -> None:
    session_factory, agent_id, _ = memory_context
    repository = MemoryRepository()
    with session_factory.begin() as session:
        low_old = create_memory(repository, session, agent_id, tick=1, importance=10)
        low_new = create_memory(repository, session, agent_id, tick=2, importance=10)
        for tick in range(3, 13):
            create_memory(repository, session, agent_id, tick=tick, importance=50 + tick)

    with session_factory() as session:
        assert repository.enforce_cap(session, agent_id) == 2
        remaining_ids = set(
            session.scalars(
                select(AgentMemory.id).where(AgentMemory.agent_id == agent_id)
            ).all()
        )
        assert low_old.id not in remaining_ids
        assert low_new.id not in remaining_ids
        assert len(remaining_ids) == 10
        session.rollback()

    with session_factory() as session:
        assert len(
            session.scalars(
                select(AgentMemory.id).where(AgentMemory.agent_id == agent_id)
            ).all()
        ) == 12


def test_enforce_cap_uses_erd_priority_without_type_or_recency_exceptions(memory_context) -> None:
    session_factory, agent_id, _ = memory_context
    repository = MemoryRepository()
    with session_factory.begin() as session:
        old_reflection = repository.create(
            session,
            MemoryCreateInput(
                agent_id=agent_id,
                content="important reflection",
                memory_type="reflection",
                importance=0,
                created_tick=1,
                occurred_at=datetime(2026, 8, 14, tzinfo=UTC),
            ),
        )
        observations = [
            create_memory(repository, session, agent_id, tick=tick, importance=tick)
            for tick in range(2, 13)
        ]
        latest_low_importance = [
            create_memory(repository, session, agent_id, tick=tick, importance=0)
            for tick in (13, 14)
        ]

    with session_factory.begin() as session:
        assert repository.enforce_cap(session, agent_id) == 4

    with session_factory() as session:
        remaining_ids = set(
            session.scalars(
                select(AgentMemory.id).where(AgentMemory.agent_id == agent_id)
            )
        )

    assert old_reflection.id not in remaining_ids
    assert {memory.id for memory in latest_low_importance}.isdisjoint(remaining_ids)
    assert {memory.id for memory in observations[-10:]} == remaining_ids


def test_enforce_cap_rejects_negative_limit(memory_context) -> None:
    session_factory, agent_id, _ = memory_context
    with session_factory() as session, pytest.raises(ValueError, match="non-negative"):
        MemoryRepository().enforce_cap(session, agent_id, max_active=-1)


def test_enforce_cap_rejects_missing_agent(memory_context) -> None:
    session_factory, _, _ = memory_context
    with session_factory() as session, pytest.raises(
        ValueError, match="agent does not exist"
    ):
        MemoryRepository().enforce_cap(session, uuid4())


def test_enforce_cap_zero_removes_all_memories(memory_context) -> None:
    session_factory, agent_id, _ = memory_context
    repository = MemoryRepository()
    with session_factory.begin() as session:
        create_memory(repository, session, agent_id, tick=1)
        create_memory(repository, session, agent_id, tick=2)

    with session_factory.begin() as session:
        assert repository.enforce_cap(session, agent_id, max_active=0) == 2

    with session_factory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(AgentMemory)
            .where(AgentMemory.agent_id == agent_id)
        ) == 0
