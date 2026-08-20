from datetime import UTC
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from app.repositories.memory_repository import MemoryRow
from app.services.tick_memory import TickMemoryService
from app.simulation.tick_engine import MemoryCandidateItem


AGENT_ID = UUID("00000000-0000-0000-0000-000000000001")
EVENT_ID = UUID("00000000-0000-0000-0000-000000000002")
MEMORY_ID = UUID("00000000-0000-0000-0000-000000000003")
EMBEDDING = [0.1] * 1536


class FakeEmbeddingProvider:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.texts.append(text)
        return EMBEDDING


class FakeMemoryRepository:
    def __init__(self) -> None:
        self.retrieve_calls: list[tuple] = []
        self.created = None
        self.cap_calls: list[tuple] = []

    def retrieve_for_runtime(self, session, agent_id, current_tick, query_embedding):
        self.retrieve_calls.append((session, agent_id, current_tick, query_embedding))
        return [
            MemoryRow(
                id=MEMORY_ID,
                agent_id=AGENT_ID,
                event_id=EVENT_ID,
                content="이전 수업 기억",
                memory_type="observation",
                importance=70,
                created_tick=2,
                occurred_at=MagicMock(),
                embedding=EMBEDDING,
            )
        ]

    def create(self, session, item):
        self.created = (session, item)
        return MemoryRow(
            id=MEMORY_ID,
            agent_id=item.agent_id,
            event_id=item.event_id,
            content=item.content,
            memory_type=item.memory_type,
            importance=item.importance,
            created_tick=item.created_tick,
            occurred_at=item.occurred_at,
            embedding=list(item.embedding),
        )

    def enforce_cap(self, session, agent_id, max_active=10):
        self.cap_calls.append((session, agent_id, max_active))
        return 0


def test_retrieve_converts_uuid_rows_to_tick_memory_items() -> None:
    session = MagicMock()
    repository = FakeMemoryRepository()
    embedding_provider = FakeEmbeddingProvider()
    service = TickMemoryService(repository, embedding_provider)

    items = service.retrieve(session, str(AGENT_ID), 3, "class")

    assert embedding_provider.texts == ["class"]
    assert repository.retrieve_calls == [(session, AGENT_ID, 3, EMBEDDING)]
    assert items[0].id == str(MEMORY_ID)
    assert items[0].event_id == str(EVENT_ID)
    assert items[0].content == "이전 수업 기억"


def test_store_converts_tick_candidate_and_applies_cap_without_commit() -> None:
    session = MagicMock()
    repository = FakeMemoryRepository()
    embedding_provider = FakeEmbeddingProvider()
    service = TickMemoryService(repository, embedding_provider)
    candidate = MemoryCandidateItem(
        content="새 주문을 익혔다",
        memory_type="observation",
        importance=60,
    )

    memory_id = service.store(
        session,
        str(AGENT_ID),
        str(EVENT_ID),
        candidate,
        current_tick=3,
    )

    _, created = repository.created
    assert created.agent_id == AGENT_ID
    assert created.event_id == EVENT_ID
    assert created.embedding == EMBEDDING
    assert created.occurred_at.tzinfo is UTC
    assert repository.cap_calls == [(session, AGENT_ID, 10)]
    assert memory_id == str(MEMORY_ID)
    session.commit.assert_not_called()


def test_invalid_agent_id_is_rejected_before_repository_call() -> None:
    repository = FakeMemoryRepository()
    service = TickMemoryService(repository, FakeEmbeddingProvider())

    with pytest.raises(ValueError, match="agent_id must be a UUID"):
        service.retrieve(MagicMock(), "not-a-uuid", 3, "class")

    assert repository.retrieve_calls == []


def test_invalid_embedding_dimension_is_rejected() -> None:
    provider = FakeEmbeddingProvider()
    provider.embed = MagicMock(return_value=[0.1])
    service = TickMemoryService(FakeMemoryRepository(), provider)

    with pytest.raises(ValueError, match="1536"):
        service.retrieve(MagicMock(), str(AGENT_ID), 3, "class")
