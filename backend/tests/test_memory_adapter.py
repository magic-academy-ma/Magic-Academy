from datetime import UTC
from types import SimpleNamespace
from uuid import uuid4

from app.services.memory_adapter import MemoryAdapter
from app.simulation.tick_engine import MemoryCandidateItem


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
    assert repository.created.embedding_model == "text-embedding-3-small"
    assert repository.created.embedding_version == "v1"
    assert repository.created.embedded_at.tzinfo is UTC
    assert repository.created.occurred_at.tzinfo is UTC
    assert repository.cap_agent_id == agent_id
    assert stored_id
