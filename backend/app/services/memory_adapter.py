from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.repositories.memory_repository import MemoryCreateInput, MemoryRepository
from app.simulation.tick_engine import MemoryCandidateItem, MemoryItem


class EmbeddingClient(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class OpenAIEmbeddingClient:
    def __init__(self, api_key: str) -> None:
        self._client = AsyncOpenAI(api_key=api_key)

    async def embed(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding


class MemoryAdapter:
    def __init__(
        self,
        session: Session,
        *,
        repository: MemoryRepository | None = None,
        embedding_client: EmbeddingClient,
        embedding_model: str = "text-embedding-3-small",
        embedding_version: str = "v1",
    ) -> None:
        self._session = session
        self._repository = repository or MemoryRepository()
        self._embedding_client = embedding_client
        self._embedding_model = embedding_model
        self._embedding_version = embedding_version

    async def retrieve(self, agent_id: str, current_tick: int, query_text: str) -> list[MemoryItem]:
        embedding = await self._embedding_client.embed(query_text)
        rows = self._repository.retrieve_for_runtime(
            self._session, UUID(agent_id), current_tick, embedding
        )
        return [
            MemoryItem(
                id=str(row.id),
                content=row.content,
                memory_type=row.memory_type,
                importance=row.importance,
                created_tick=row.created_tick,
                event_id=None if row.event_id is None else str(row.event_id),
            )
            for row in rows
        ]

    async def store(
        self,
        agent_id: str,
        event_id: str | None,
        candidate: MemoryCandidateItem,
        tick: int,
    ) -> str:
        embedding = await self._embedding_client.embed(candidate.content)
        embedded_at = datetime.now(UTC)
        row = self._repository.create(
            self._session,
            MemoryCreateInput(
                agent_id=UUID(agent_id),
                event_id=None if event_id is None else UUID(event_id),
                content=candidate.content,
                memory_type=candidate.memory_type,
                importance=candidate.importance,
                created_tick=tick,
                occurred_at=embedded_at,
                embedding=embedding,
                embedding_model=self._embedding_model,
                embedding_version=self._embedding_version,
                embedded_at=embedded_at,
            ),
        )
        self._repository.enforce_cap(self._session, UUID(agent_id))
        return str(row.id)
