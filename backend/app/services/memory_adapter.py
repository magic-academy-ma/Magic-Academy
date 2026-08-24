"""Slice 3 Task 5: MemoryRepository + EmbeddingClient를 TickEngine의
MemoryRetrieverFn / MemoryStoreFn 콜백 시그니처로 감싸는 어댑터.

TickEngine은 (agent_id: str, tick: int, query_text: str) -> list[MemoryItem]과
(agent_id: str, event_id: str | None, candidate: MemoryCandidateItem, tick: int) -> str
형태의 async 콜백만 알면 되고, DB/embedding 구현 세부사항은 이 모듈에 캡슐화한다.
"""
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


def build_memory_retriever(
    session: Session,
    repo: MemoryRepository,
    embedding_client: EmbeddingClient,
) -> MemoryRetrieverFn:
    async def retrieve(agent_id: str, current_tick: int, query_text: str) -> list[MemoryItem]:
        query_embedding = await embedding_client.embed(query_text)
        rows = repo.retrieve_for_runtime(session, UUID(agent_id), current_tick, query_embedding)
        return [
            MemoryItem(
                id=str(row.id),
                content=row.content,
                memory_type=row.memory_type,
                importance=row.importance,
                created_tick=row.created_tick,
                event_id=str(row.event_id) if row.event_id else None,
            )
            for row in rows
        ]

    return retrieve


def build_memory_store(
    session: Session,
    repo: MemoryRepository,
    embedding_client: EmbeddingClient,
) -> MemoryStoreFn:
    async def store(
        agent_id: str,
        event_id: str | None,
        candidate: MemoryCandidateItem,
        tick: int,
    ) -> str:
        embedding = await embedding_client.embed(candidate.content)
        item = MemoryCreateInput(
            agent_id=UUID(agent_id),
            event_id=UUID(event_id) if event_id else None,
            content=candidate.content,
            memory_type=candidate.memory_type,
            importance=candidate.importance,
            created_tick=tick,
            occurred_at=datetime.now(UTC),
            embedding=embedding,
        )
        row = repo.create(session, item)
        repo.enforce_cap(session, UUID(agent_id))
        return str(row.id)

    return store
