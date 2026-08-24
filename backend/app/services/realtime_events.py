from collections import defaultdict
from typing import Any, Literal
from uuid import UUID

from fastapi import WebSocket
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Event, Relationship
from app.services.manual_tick import ManualTickResult


class RealtimeEvent(BaseModel):
    type: Literal[
        "TICK_UPDATED",
        "AGENT_ACTION_UPDATED",
        "EVENT_CREATED",
        "RELATIONSHIP_UPDATED",
        "SIMULATION_STATUS_UPDATED",
    ]
    data: dict[str, Any]


class SimulationConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)

    def connect(self, simulation_id: UUID, websocket: WebSocket) -> None:
        self._connections[simulation_id].add(websocket)

    def disconnect(self, simulation_id: UUID, websocket: WebSocket) -> None:
        connections = self._connections.get(simulation_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(simulation_id, None)

    async def broadcast(self, simulation_id: UUID, events: list[RealtimeEvent]) -> None:
        stale: list[WebSocket] = []
        for websocket in tuple(self._connections.get(simulation_id, ())):
            try:
                for event in events:
                    await websocket.send_json(event.model_dump(mode="json"))
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(simulation_id, websocket)


connection_manager = SimulationConnectionManager()


def build_event_created_event(event: Event) -> RealtimeEvent:
    return RealtimeEvent(
        type="EVENT_CREATED",
        data={
            "event_id": event.id,
            "simulation_id": event.simulation_id,
            "event_type": event.event_type,
            "title": event.title,
            "status": event.status,
            "simulation_day": event.simulation_day,
            "location_id": event.location_id,
        },
    )


def build_simulation_status_event(
    simulation_id: UUID,
    status: str,
) -> RealtimeEvent:
    return RealtimeEvent(
        type="SIMULATION_STATUS_UPDATED",
        data={"simulation_id": simulation_id, "status": status},
    )


def build_tick_events(
    db: Session,
    simulation_id: UUID,
    result: ManualTickResult,
) -> list[RealtimeEvent]:
    events = [
        RealtimeEvent(
            type="TICK_UPDATED",
            data={
                "simulation_id": simulation_id,
                "current_day": result.current_day,
                "tick_number": result.current_tick,
            },
        )
    ]
    events.extend(
        RealtimeEvent(
            type="AGENT_ACTION_UPDATED",
            data={
                "agent_id": runtime_result.agent_id,
                "action": runtime_result.intent.action_type,
                "location": runtime_result.intent.target_location_id,
            },
        )
        for runtime_result in result.runtime_results
    )

    changes_by_pair: dict[tuple[UUID, UUID], dict[str, int]] = defaultdict(dict)
    for effect in result.policy_result.relationship_effects:
        if effect.target_agent_id is not None:
            changes_by_pair[
                (UUID(effect.source_agent_id), UUID(effect.target_agent_id))
            ][effect.metric] = effect.after_preview - effect.before

    if changes_by_pair:
        relationships = db.scalars(
            select(Relationship).where(
                Relationship.simulation_id == simulation_id,
            )
        ).all()
        relationships_by_pair = {
            (item.source_agent_id, item.target_agent_id): item for item in relationships
        }
        for pair, changes in changes_by_pair.items():
            relationship = relationships_by_pair.get(pair)
            if relationship is None:
                continue
            events.append(
                RealtimeEvent(
                    type="RELATIONSHIP_UPDATED",
                    data={
                        "relationship_id": relationship.id,
                        "source_agent_id": pair[0],
                        "target_agent_id": pair[1],
                        "changes": changes,
                        "values": {
                            metric: getattr(relationship, metric) for metric in changes
                        },
                    },
                )
            )
    return events
