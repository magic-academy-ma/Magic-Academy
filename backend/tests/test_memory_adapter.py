"""Slice 3 Task 5: MemoryRepository + EmbeddingClient를 TickEngine 콜백으로 감싸는 어댑터 테스트"""
import os
import threading
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.domain.models import Agent, AgentMemory, Simulation, User
from app.repositories.memory_repository import MemoryRepository, MemoryRow
from app.services.memory_adapter import MemoryAdapter, build_memory_retriever, build_memory_store
from app.simulation.tick_engine import MemoryCandidateItem

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

AGENT_ID = uuid4()
EVENT_ID = uuid4()


def make_row(**overrides):
    defaults = dict(
        id=uuid4(),
        agent_id=AGENT_ID,
        event_id=None,
        content="기억 내용",
        memory_type="observation",
        importance=50,
        created_tick=1,
        occurred_at=datetime.now(UTC),
        embedding=[0.1] * 1536,
    )
    defaults.update(overrides)
    return MemoryRow(**defaults)


async def test_memory_retriever_embeds_query_then_maps_rows_to_memory_items():
    embedding_client = MagicMock()
    embedding_client.embed = AsyncMock(return_value=[0.2] * 1536)
    repo = MagicMock()
    row = make_row()
    repo.retrieve_for_runtime = MagicMock(return_value=[row])
    session = MagicMock()

    retriever = build_memory_retriever(session=session, repo=repo, embedding_client=embedding_client)
    memories = await retriever(str(AGENT_ID), 5, "class")

    embedding_client.embed.assert_awaited_once_with("class")
    repo.retrieve_for_runtime.assert_called_once_with(session, AGENT_ID, 5, [0.2] * 1536)
    assert len(memories) == 1
    assert memories[0].id == str(row.id)
    assert memories[0].content == "기억 내용"
    assert memories[0].importance == 50


async def test_memory_retriever_returns_empty_when_no_rows():
    embedding_client = MagicMock()
    embedding_client.embed = AsyncMock(return_value=[0.0] * 1536)
    repo = MagicMock()
    repo.retrieve_for_runtime = MagicMock(return_value=[])
    session = MagicMock()

    retriever = build_memory_retriever(session=session, repo=repo, embedding_client=embedding_client)
    memories = await retriever(str(AGENT_ID), 1, "class")

    assert memories == []


async def test_memory_store_embeds_content_creates_row_then_enforces_cap():
    embedding_client = MagicMock()
    embedding_client.embed = AsyncMock(return_value=[0.3] * 1536)
    repo = MagicMock()
    created_row = make_row(event_id=EVENT_ID)
    repo.create = MagicMock(return_value=created_row)
    repo.enforce_cap = MagicMock(return_value=0)
    session = MagicMock()

    store = build_memory_store(session=session, repo=repo, embedding_client=embedding_client)
    candidate = MemoryCandidateItem(content="협력 기억", memory_type="observation", importance=50)
    memory_id = await store(str(AGENT_ID), str(EVENT_ID), candidate, 3)

    embedding_client.embed.assert_awaited_once_with("협력 기억")
    repo.create.assert_called_once()
    create_call_item = repo.create.call_args.args[1]
    assert create_call_item.agent_id == AGENT_ID
    assert create_call_item.event_id == EVENT_ID
    assert create_call_item.content == "협력 기억"
    assert create_call_item.importance == 50
    assert create_call_item.created_tick == 3
    assert create_call_item.embedding == [0.3] * 1536

    repo.enforce_cap.assert_called_once_with(session, AGENT_ID)
    assert memory_id == str(created_row.id)


async def test_memory_store_handles_none_event_id():
    embedding_client = MagicMock()
    embedding_client.embed = AsyncMock(return_value=[0.1] * 1536)
    repo = MagicMock()
    repo.create = MagicMock(return_value=make_row())
    repo.enforce_cap = MagicMock(return_value=0)
    session = MagicMock()

    store = build_memory_store(session=session, repo=repo, embedding_client=embedding_client)
    candidate = MemoryCandidateItem(content="독립 기억", memory_type="reflection", importance=30)
    await store(str(AGENT_ID), None, candidate, 1)

    create_call_item = repo.create.call_args.args[1]
    assert create_call_item.event_id is None


async def test_memory_store_uses_session_on_caller_thread():
    caller_thread_id = threading.get_ident()
    repository_thread_ids = []
    embedding_client = MagicMock()
    embedding_client.embed = AsyncMock(return_value=[0.1] * 1536)
    repo = MagicMock()
    repo.create.side_effect = lambda _session, _item: (
        repository_thread_ids.append(threading.get_ident()) or make_row()
    )
    repo.enforce_cap.side_effect = lambda _session, _agent_id: repository_thread_ids.append(
        threading.get_ident()
    )
    session = MagicMock()

    store = build_memory_store(session=session, repo=repo, embedding_client=embedding_client)
    candidate = MemoryCandidateItem(content="동일 스레드 기억", memory_type="observation", importance=40)
    await store(str(AGENT_ID), None, candidate, 2)

    assert repository_thread_ids == [caller_thread_id, caller_thread_id]


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")
async def test_memory_store_enforces_cap_end_to_end_via_real_db() -> None:
    """11번째 저장 시 최신 2개를 보존하고 나머지 최저 중요도를 제거한다."""
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(
            text("TRUNCATE agent_memories, agents, simulations, users RESTART IDENTITY CASCADE")
        )

    user_id = uuid4()
    simulation_id = uuid4()
    agent_id = uuid4()
    with session_factory.begin() as session:
        session.add(
            User(
                id=user_id,
                username="adapter-owner",
                display_name="Adapter Owner",
                password_hash="not-a-real-password-hash",
                roles=["USER"],
            )
        )
        session.flush()
        session.add(Simulation(id=simulation_id, owner_id=user_id, name="Adapter Test"))
        session.flush()
        session.add(
            Agent(
                id=agent_id,
                simulation_id=simulation_id,
                fixture_key="student-01",
                fixture_version="student-fixture-v0.2",
                agent_type="student",
                name="student-01",
                mbti_type="ISTJ",
            )
        )

    repo = MemoryRepository()
    embedding_client = MagicMock()
    embedding_client.embed = AsyncMock(return_value=[0.0] * 1536)

    try:
        with session_factory() as session:
            store = build_memory_store(session=session, repo=repo, embedding_client=embedding_client)
            for tick in range(1, 11):
                await store(str(agent_id), None, MemoryCandidateItem(
                    content=f"memory-{tick}", memory_type="observation", importance=10 + tick,
                ), tick)
            session.commit()

        with session_factory() as session:
            assert len(
                session.scalars(
                    select(AgentMemory.id).where(AgentMemory.agent_id == agent_id)
                ).all()
            ) == 10

        with session_factory() as session:
            store = build_memory_store(session=session, repo=repo, embedding_client=embedding_client)
            await store(str(agent_id), None, MemoryCandidateItem(
                content="memory-lowest-importance", memory_type="observation", importance=1,
            ), 11)
            session.commit()

        with session_factory() as session:
            rows = session.scalars(
                select(AgentMemory).where(AgentMemory.agent_id == agent_id)
            ).all()
            contents = {row.content for row in rows}
            assert len(rows) == 10
            assert "memory-lowest-importance" in contents
            assert "memory-1" not in contents
    finally:
        engine.dispose()
class FakeRepository:
    def __init__(self):
        self.created = None
        self.cap_agent_id = None

    def retrieve_for_runtime(self, session, agent_id, current_tick, query_embedding):
        return [SimpleNamespace(
            id=uuid4(), content="기억", memory_type="observation", importance=50,
            created_tick=1, event_id=None,
        )]

    def create(self, session, item):
        self.created = item
        return SimpleNamespace(id=uuid4())

    def enforce_cap(self, session, agent_id, max_active=10):
        self.cap_agent_id = agent_id


class FakeEmbeddingClient:
    async def embed(self, text):
        return [0.1] * 1536


async def test_memory_adapter_retrieves_and_stores_with_embedding():
    repository = FakeRepository()
    adapter = MemoryAdapter(object(), repository=repository, embedding_client=FakeEmbeddingClient())
    agent_id, event_id = uuid4(), uuid4()

    memories = await adapter.retrieve(str(agent_id), 2, "class")
    stored_id = await adapter.store(
        str(agent_id), str(event_id),
        MemoryCandidateItem(content="새 기억", memory_type="observation", importance=60), 2,
    )

    assert memories[0].content == "기억"
    assert repository.created.embedding == [0.1] * 1536
    assert repository.created.occurred_at.tzinfo is UTC
    assert repository.cap_agent_id == agent_id
    assert stored_id
