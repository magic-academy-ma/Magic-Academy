from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import SimulationLogEntryResponse
from app.domain.models import Agent, AgentMemory, Event, EventParticipant


def _metadata_int(metadata: dict, key: str) -> int | None:
    """events.metadata(JSONB) 의 숫자 값을 안전하게 읽는다 (app/api/events.py 와 동일)."""
    value = metadata.get(key)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def list_simulation_logs(
    db: Session, simulation_id: UUID
) -> list[SimulationLogEntryResponse]:
    """요청한 Simulation 의 통합 로그 타임라인.

    새 Log 저장소를 만들지 않고, 이미 영속화된 두 소스만 합친다.

    * ``events`` — 엔진(persist_event_batch)이 남긴 Event 와 수동 생성 Event.
      ``metadata.source == 'magic_layer'`` 이면 ``system``, 아니면 ``event``.
    * ``agent_memories`` 중 ``memory_type == 'conversation'`` — ``dialogue``.
      agent_memories 에는 simulation_id 컬럼이 없어 agents 를 통해 범위를 좁힌다.

    정렬은 기존 도메인 규칙을 재사용한다: tick 오름차순(수동 Event 처럼 tick 이
    없으면 시뮬레이션 이전의 준비 기록으로 보고 맨 앞), 같은 tick 안에서는 행 id
    (uuid7 — 생성 시각 순) 오름차순. 새 우선순위 규칙(importance 우선 등)은
    도입하지 않는다.
    """
    events = list(
        db.scalars(select(Event).where(Event.simulation_id == simulation_id))
    )

    participants: dict[UUID, list[UUID]] = {}
    if events:
        rows = db.execute(
            select(EventParticipant.event_id, EventParticipant.agent_id)
            .where(EventParticipant.event_id.in_([event.id for event in events]))
            .order_by(EventParticipant.event_id, EventParticipant.agent_id)
        )
        for event_id, agent_id in rows:
            participants.setdefault(event_id, []).append(agent_id)

    conversations = list(
        db.scalars(
            select(AgentMemory)
            .join(Agent, Agent.id == AgentMemory.agent_id)
            .where(
                Agent.simulation_id == simulation_id,
                AgentMemory.memory_type == "conversation",
            )
        )
    )

    entries: list[tuple[int, UUID, SimulationLogEntryResponse]] = []
    for event in events:
        metadata = event.event_metadata or {}
        tick = _metadata_int(metadata, "tick")
        entries.append(
            (
                tick if tick is not None else 0,
                event.id,
                SimulationLogEntryResponse(
                    id=event.id,
                    tick=tick,
                    type="system"
                    if metadata.get("source") == "magic_layer"
                    else "event",
                    summary=event.title,
                    target_agent_ids=participants.get(event.id, []),
                    importance=_metadata_int(metadata, "importance"),
                    event_id=event.id,
                ),
            )
        )
    for memory in conversations:
        entries.append(
            (
                memory.created_tick,
                memory.id,
                SimulationLogEntryResponse(
                    id=memory.id,
                    tick=memory.created_tick,
                    type="dialogue",
                    summary=memory.content,
                    target_agent_ids=[memory.agent_id],
                    importance=memory.importance,
                    event_id=memory.event_id,
                ),
            )
        )

    entries.sort(key=lambda item: (item[0], item[1]))
    return [entry for _, _, entry in entries]
