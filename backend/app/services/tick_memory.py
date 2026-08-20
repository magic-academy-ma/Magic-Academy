from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.memory_repository import MemoryCreateInput, MemoryRepository, MemoryRow
from app.simulation.tick_engine import MemoryCandidateItem, MemoryItem


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> Sequence[float]: ...


class TickMemoryService:
    def __init__(
        self,
        repository: MemoryRepository,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._repository = repository
        self._embedding_provider = embedding_provider

    def retrieve(
        self,
        session: Session,
        agent_id: str,
        current_tick: int,
        query_text: str,
    ) -> list[MemoryItem]:
        repository_agent_id = self._parse_uuid(agent_id, "agent_id")
        query_embedding = self._embed(query_text)
        rows = self._repository.retrieve_for_runtime(
            session,
            repository_agent_id,
            current_tick,
            query_embedding,
        )
        return [self._to_item(row) for row in rows]

    def store(
        self,
        session: Session,
        agent_id: str,
        event_id: str | None,
        candidate: MemoryCandidateItem,
        current_tick: int,
    ) -> str:
        repository_agent_id = self._parse_uuid(agent_id, "agent_id")
        repository_event_id = (
            None if event_id is None else self._parse_uuid(event_id, "event_id")
        )
        row = self._repository.create(
            session,
            MemoryCreateInput(
                agent_id=repository_agent_id,
                event_id=repository_event_id,
                content=candidate.content,
                memory_type=candidate.memory_type,
                importance=candidate.importance,
                created_tick=current_tick,
                occurred_at=datetime.now(UTC),
                embedding=self._embed(candidate.content),
            ),
        )
        self._repository.enforce_cap(session, repository_agent_id, max_active=10)
        return str(row.id)

    def _embed(self, text: str) -> list[float]:
        embedding = list(self._embedding_provider.embed(text))
        if len(embedding) != 1536:
            raise ValueError("embedding must contain exactly 1536 values")
        return embedding

    @staticmethod
    def _parse_uuid(value: str, field_name: str) -> UUID:
        try:
            return UUID(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be a UUID") from None

    @staticmethod
    def _to_item(row: MemoryRow) -> MemoryItem:
        return MemoryItem(
            id=str(row.id),
            content=row.content,
            memory_type=row.memory_type,
            importance=row.importance,
            created_tick=row.created_tick,
            event_id=None if row.event_id is None else str(row.event_id),
        )
