from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.memory_repository import MemoryCreateInput, MemoryRepository
from app.services.embedding_service import EmbeddingClient
from app.simulation.tick_engine import (
    MemoryCandidateItem,
    MemoryItem,
    MemoryRetrieverFn,
    MemoryStoreFn,
)


class MemoryAdapter:
    def __init__(
        self,
        session: Session,
        *,
        repository: MemoryRepository | None = None,
        embedding_client: EmbeddingClient,
    ) -> None:
        self._session = session
        self._repository = repository or MemoryRepository()
        self._embedding_client = embedding_client

    async def retrieve(
        self, agent_id: str, current_tick: int, query_text: str
    ) -> list[MemoryItem]:
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
        row = self._repository.create(
            self._session,
            MemoryCreateInput(
                agent_id=UUID(agent_id),
                event_id=None if event_id is None else UUID(event_id),
                content=candidate.content,
                memory_type=candidate.memory_type,
                importance=candidate.importance,
                created_tick=tick,
                occurred_at=datetime.now(UTC),
                embedding=embedding,
            ),
        )
        self._repository.enforce_cap(self._session, UUID(agent_id))
        return str(row.id)


def build_memory_retriever(
    session: Session,
    repo: MemoryRepository,
    embedding_client: EmbeddingClient,
) -> MemoryRetrieverFn:
    return MemoryAdapter(
        session, repository=repo, embedding_client=embedding_client
    ).retrieve


def build_memory_store(
    session: Session,
    repo: MemoryRepository,
    embedding_client: EmbeddingClient,
) -> MemoryStoreFn:
    return MemoryAdapter(
        session, repository=repo, embedding_client=embedding_client
    ).store
