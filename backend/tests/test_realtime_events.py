from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.services.realtime_events import RealtimeEvent, SimulationConnectionManager


class FakeWebSocket:
    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails
        self.messages: list[dict] = []

    async def send_json(self, message: dict) -> None:
        if self.fails:
            raise RuntimeError("disconnected")
        self.messages.append(message)


@pytest.mark.parametrize(
    "event_type",
    [
        "TICK_UPDATED",
        "AGENT_ACTION_UPDATED",
        "RELATIONSHIP_UPDATED",
    ],
)
def test_realtime_event_supports_documented_message_types(event_type: str) -> None:
    assert RealtimeEvent(type=event_type, data={}).type == event_type


def test_realtime_event_rejects_unknown_message_type() -> None:
    with pytest.raises(ValidationError):
        RealtimeEvent(type="UNKNOWN", data={})


@pytest.mark.asyncio
async def test_connection_manager_isolates_simulations_and_removes_stale_connections() -> None:
    manager = SimulationConnectionManager()
    simulation_a = uuid4()
    simulation_b = uuid4()
    receiver_a = FakeWebSocket()
    receiver_b = FakeWebSocket()
    stale = FakeWebSocket(fails=True)
    manager.connect(simulation_a, receiver_a)
    manager.connect(simulation_b, receiver_b)
    manager.connect(simulation_a, stale)

    event = RealtimeEvent(type="TICK_UPDATED", data={"tick_number": 1})
    await manager.broadcast(simulation_a, [event])
    await manager.broadcast(simulation_a, [event])

    assert receiver_a.messages == [
        {"type": "TICK_UPDATED", "data": {"tick_number": 1}},
        {"type": "TICK_UPDATED", "data": {"tick_number": 1}},
    ]
    assert receiver_b.messages == []
    assert stale not in manager._connections[simulation_a]


@pytest.mark.asyncio
async def test_authenticated_frame_failure_removes_registered_connection(monkeypatch) -> None:
    from app.api import websockets

    simulation_id = uuid4()
    websocket = FakeWebSocket(fails=True)
    websocket.accept = lambda: _completed_awaitable()
    websocket.receive_json = lambda: _completed_awaitable(
        {"type": "AUTH", "token": "valid-token"}
    )
    monkeypatch.setattr(websockets, "authenticate_access_token", lambda db, token: object())
    monkeypatch.setattr(
        websockets,
        "require_owned_simulation",
        lambda db, requested_id, user: object(),
    )

    with pytest.raises(RuntimeError, match="disconnected"):
        await websockets.simulation_events(websocket, simulation_id, db=object())

    assert simulation_id not in websockets.connection_manager._connections


async def _completed_awaitable(value=None):
    return value
