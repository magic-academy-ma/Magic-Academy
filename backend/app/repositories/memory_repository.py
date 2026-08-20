from dataclasses import dataclass
from datetime import datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import AgentMemory


@dataclass(frozen=True)
class MemoryCreateInput:
    agent_id: UUID
    content: str
    memory_type: str
    importance: int
    created_tick: int
    occurred_at: datetime
    embedding: Sequence[float] | None = None
    event_id: UUID | None = None


@dataclass(frozen=True)
class MemoryRow:
    id: UUID
    agent_id: UUID
    event_id: UUID | None
    content: str
    memory_type: str
    importance: int
    created_tick: int
    occurred_at: datetime
    embedding: list[float] | None


class MemoryRepository:
    @staticmethod
    def _to_row(memory: AgentMemory) -> MemoryRow:
        embedding = None if memory.embedding is None else list(memory.embedding)
        return MemoryRow(
            id=memory.id,
            agent_id=memory.agent_id,
            event_id=memory.event_id,
            content=memory.content,
            memory_type=memory.memory_type,
            importance=memory.importance,
            created_tick=memory.created_tick,
            occurred_at=memory.occurred_at,
            embedding=embedding,
        )

    def create(self, session: Session, item: MemoryCreateInput) -> MemoryRow:
        memory = AgentMemory(
            id=uuid7(),
            agent_id=item.agent_id,
            event_id=item.event_id,
            content=item.content,
            memory_type=item.memory_type,
            importance=item.importance,
            created_tick=item.created_tick,
            occurred_at=item.occurred_at,
            embedding=None if item.embedding is None else list(item.embedding),
        )
        session.add(memory)
        session.flush()
        return self._to_row(memory)

    def retrieve_for_runtime(
        self,
        session: Session,
        agent_id: UUID,
        current_tick: int,
        query_embedding: Sequence[float],
    ) -> list[MemoryRow]:
        eligible = (
            AgentMemory.agent_id == agent_id,
            AgentMemory.created_tick <= current_tick,
        )
        latest = session.scalars(
            select(AgentMemory)
            .where(*eligible)
            .order_by(
                AgentMemory.created_tick.desc(),
                AgentMemory.occurred_at.desc(),
                AgentMemory.id.desc(),
            )
            .limit(2)
        ).all()
        similar = session.scalars(
            select(AgentMemory)
            .where(*eligible, AgentMemory.embedding.is_not(None))
            .order_by(
                AgentMemory.embedding.cosine_distance(list(query_embedding)),
                AgentMemory.id.asc(),
            )
            .limit(3)
        ).all()

        deduplicated: list[AgentMemory] = []
        seen: set[UUID] = set()
        for memory in (*latest, *similar):
            if memory.id not in seen:
                seen.add(memory.id)
                deduplicated.append(memory)
        return [self._to_row(memory) for memory in deduplicated[:5]]

    def enforce_cap(
        self,
        session: Session,
        agent_id: UUID,
        max_active: int = 10,
    ) -> int:
        if max_active < 0:
            raise ValueError("max_active must be non-negative")

        memory_count = session.scalar(
            select(func.count())
            .select_from(AgentMemory)
            .where(AgentMemory.agent_id == agent_id)
        )
        excess_count = max((memory_count or 0) - max_active, 0)
        if excess_count == 0:
            return 0

        ids_to_delete = session.scalars(
            select(AgentMemory.id)
            .where(AgentMemory.agent_id == agent_id)
            .order_by(
                AgentMemory.importance.asc(),
                AgentMemory.created_tick.asc(),
                AgentMemory.id.asc(),
            )
            .limit(excess_count)
        ).all()
        session.execute(delete(AgentMemory).where(AgentMemory.id.in_(ids_to_delete)))
        session.flush()
        return len(ids_to_delete)
