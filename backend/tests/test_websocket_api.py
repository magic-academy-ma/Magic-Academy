import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from starlette.websockets import WebSocketDisconnect

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")


@pytest.fixture()
def client():
    from app.core.database import get_db
    from app.main import app
    from app.services.runtime_dependency import get_agent_runtime
    from app.simulation.agent_runtime import AgentRuntime, MockLLMClient

    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE users, simulations RESTART IDENTITY CASCADE"))

    def override_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_agent_runtime] = lambda: AgentRuntime(
        MockLLMClient(), model="websocket-test-runtime"
    )
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_login_and_create(client: TestClient, username: str) -> tuple[str, str]:
    password = "WebSocket-password!"
    assert client.post(
        "/v1/auth/register",
        json={"username": username, "display_name": username, "password": password},
    ).status_code == 201
    login = client.post(
        "/v1/auth/login", json={"username": username, "password": password}
    )
    token = login.json()["access_token"]
    simulation = client.post(
        "/v1/simulations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": username},
    )
    return token, simulation.json()["id"]


def test_websocket_requires_valid_first_frame(client: TestClient) -> None:
    with client.websocket_connect(f"/v1/ws/simulations/{uuid4()}") as websocket:
        websocket.send_json({"type": "NOT_AUTH", "token": "forged"})
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()
    assert closed.value.code == 1008


def test_websocket_accepts_owner_and_rejects_other_user(client: TestClient) -> None:
    owner_token, simulation_id = register_login_and_create(client, "ws-owner")
    other_token, _ = register_login_and_create(client, "ws-other")

    with client.websocket_connect(f"/v1/ws/simulations/{simulation_id}") as websocket:
        websocket.send_json({"type": "AUTH", "token": owner_token})
        assert websocket.receive_json() == {
            "type": "AUTHENTICATED",
            "data": {"simulation_id": simulation_id},
        }

    with client.websocket_connect(f"/v1/ws/simulations/{simulation_id}") as websocket:
        websocket.send_json({"type": "AUTH", "token": other_token})
        with pytest.raises(WebSocketDisconnect) as closed:
            websocket.receive_json()
    assert closed.value.code == 1008
    assert UUID(simulation_id)


def test_tick_broadcasts_committed_relationship_matching_rest(
    client: TestClient, monkeypatch
) -> None:
    from app.simulation.agent_runtime import MockLLMClient

    token, simulation_id = register_login_and_create(client, "ws-tick-owner")
    headers = {"Authorization": f"Bearer {token}"}
    original_generate = MockLLMClient.generate

    def generate_relationship_signal(self, runtime_input):
        response = original_generate(self, runtime_input)
        # Task 2 Context 분리로 events[0].participant_agent_ids는 관찰 가능한
        # 대상만 남는다 — 실제로 관찰 가능한(nearby) 상대에게만 반응할 수 있다.
        if (
            runtime_input.agent.agent_id not in runtime_input.events[0].participant_agent_ids
            or not runtime_input.nearby_agents
        ):
            return response
        target_agent_id = runtime_input.nearby_agents[0].agent_id
        response["reaction"]["relationship_signals"] = [
            {
                "signal_type": "TRUST_UP",
                "intensity": "MEDIUM",
                "target_agent_id": str(target_agent_id),
            }
        ]
        return response

    monkeypatch.setattr(MockLLMClient, "generate", generate_relationship_signal)

    with client.websocket_connect(f"/v1/ws/simulations/{simulation_id}") as websocket:
        websocket.send_json({"type": "AUTH", "token": token})
        assert websocket.receive_json()["type"] == "AUTHENTICATED"

        response = client.post(
            f"/v1/simulations/{simulation_id}/ticks/advance", headers=headers
        )
        assert response.status_code == 200, response.text

        tick_event = websocket.receive_json()
        assert tick_event == {
            "type": "TICK_UPDATED",
            "data": {
                "simulation_id": simulation_id,
                "current_day": 1,
                "tick_number": 1,
            },
        }
        # 예정 CLASS Event가 있으면 EVENT_CREATED가 먼저 오고,
        # 이어서 All 5 Students + the conditional Professor의 AGENT_ACTION_UPDATED,
        # 마지막으로 RELATIONSHIP_UPDATED 2건이 온다.
        action_events = []
        while len(action_events) < 6:
            event = websocket.receive_json()
            if event["type"] == "EVENT_CREATED":
                continue
            action_events.append(event)
        assert {event["type"] for event in action_events} == {
            "AGENT_ACTION_UPDATED"
        }
        # Task 2 Context 분리로 nearby_agents가 있는 쪽만 반응하므로 1건만 발생한다.
        relationship_events = [websocket.receive_json()]

        for event in relationship_events:
            assert event["type"] == "RELATIONSHIP_UPDATED"
            relationships = client.get(
                f"/v1/agents/{event['data']['source_agent_id']}/relationships",
                headers=headers,
            )
            assert relationships.status_code == 200, relationships.text
            relationship = next(
                item
                for item in relationships.json()
                if item["target_agent_id"] == event["data"]["target_agent_id"]
            )
            assert relationship["trust"] == event["data"]["values"]["trust"]


def test_commit_failure_does_not_broadcast(client: TestClient, monkeypatch) -> None:
    from sqlalchemy.orm import Session

    from app.services.realtime_events import connection_manager

    token, simulation_id = register_login_and_create(client, "ws-rollback-owner")
    broadcasts = []

    async def record_broadcast(*args):
        broadcasts.append(args)

    def fail_commit(self):
        raise RuntimeError("forced commit failure")

    monkeypatch.setattr(connection_manager, "broadcast", record_broadcast)
    monkeypatch.setattr(Session, "commit", fail_commit)

    response = client.post(
        f"/v1/simulations/{simulation_id}/ticks/advance",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 500
    assert broadcasts == []
    simulation = client.get(
        f"/v1/simulations/{simulation_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert simulation.status_code == 200, simulation.text
    assert simulation.json()["current_tick"] == 0



def test_simulation_status_broadcast_matches_rest(client: TestClient) -> None:
    token, simulation_id = register_login_and_create(client, "ws-status-owner")
    headers = {"Authorization": f"Bearer {token}"}

    with client.websocket_connect(f"/v1/ws/simulations/{simulation_id}") as websocket:
        websocket.send_json({"type": "AUTH", "token": token})
        assert websocket.receive_json()["type"] == "AUTHENTICATED"

        updated = client.patch(
            f"/v1/simulations/{simulation_id}/status",
            headers=headers,
            json={"status": "running"},
        )
        assert updated.status_code == 200, updated.text
        event = websocket.receive_json()

    current = client.get(f"/v1/simulations/{simulation_id}", headers=headers)
    assert current.status_code == 200, current.text
    assert event == {
        "type": "SIMULATION_STATUS_UPDATED",
        "data": {"simulation_id": simulation_id, "status": "running"},
    }
    assert current.json()["status"] == event["data"]["status"]


def test_simulation_status_rejects_invalid_transition_and_other_owner(
    client: TestClient,
) -> None:
    owner_token, simulation_id = register_login_and_create(client, "status-owner")
    other_token, _ = register_login_and_create(client, "status-other")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    forbidden = client.patch(
        f"/v1/simulations/{simulation_id}/status",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"status": "running"},
    )
    assert forbidden.status_code == 403

    assert client.patch(
        f"/v1/simulations/{simulation_id}/status",
        headers=owner_headers,
        json={"status": "running"},
    ).status_code == 200
    assert client.patch(
        f"/v1/simulations/{simulation_id}/status",
        headers=owner_headers,
        json={"status": "completed"},
    ).status_code == 200
    invalid = client.patch(
        f"/v1/simulations/{simulation_id}/status",
        headers=owner_headers,
        json={"status": "running"},
    )
    assert invalid.status_code == 409
    assert invalid.json()["detail"] == "Invalid simulation status transition"


def test_simulation_status_commit_failure_rolls_back_without_broadcast(
    client: TestClient, monkeypatch
) -> None:
    from sqlalchemy.orm import Session

    from app.services.realtime_events import connection_manager

    token, simulation_id = register_login_and_create(client, "status-rollback-owner")
    headers = {"Authorization": f"Bearer {token}"}
    broadcasts = []

    async def record_broadcast(*args):
        broadcasts.append(args)

    def fail_commit(self):
        raise RuntimeError("forced commit failure")

    monkeypatch.setattr(connection_manager, "broadcast", record_broadcast)
    monkeypatch.setattr(Session, "commit", fail_commit)

    response = client.patch(
        f"/v1/simulations/{simulation_id}/status",
        headers=headers,
        json={"status": "running"},
    )

    assert response.status_code == 500
    assert broadcasts == []
    current = client.get(f"/v1/simulations/{simulation_id}", headers=headers)
    assert current.status_code == 200, current.text
    assert current.json()["status"] == "ready"


def test_created_event_broadcast_matches_rest(client: TestClient) -> None:
    token, simulation_id = register_login_and_create(client, "ws-event-owner")
    headers = {"Authorization": f"Bearer {token}"}
    agents = client.get(
        f"/v1/simulations/{simulation_id}/agents", headers=headers
    ).json()
    location_id = agents[0]["location"]["id"]

    with client.websocket_connect(f"/v1/ws/simulations/{simulation_id}") as websocket:
        websocket.send_json({"type": "AUTH", "token": token})
        assert websocket.receive_json()["type"] == "AUTHENTICATED"

        created = client.post(
            f"/v1/simulations/{simulation_id}/events",
            headers=headers,
            json={
                "event_type": "random_incident",
                "title": "마법 폭주",
                "description": "복도에서 마법이 폭주했다.",
                "simulation_day": 1,
                "location_id": location_id,
            },
        )
        assert created.status_code == 201, created.text
        event = websocket.receive_json()

    listed = client.get(
        f"/v1/simulations/{simulation_id}/events", headers=headers
    )
    assert listed.status_code == 200, listed.text
    stored = next(item for item in listed.json() if item["id"] == created.json()["id"])
    assert event == {
        "type": "EVENT_CREATED",
        "data": {
            "event_id": stored["id"],
            "simulation_id": simulation_id,
            "event_type": stored["event_type"],
            "title": stored["title"],
            "status": stored["status"],
            "simulation_day": stored["simulation_day"],
            "location_id": stored["location_id"],
        },
    }


def test_event_api_rejects_other_owner_and_foreign_location(client: TestClient) -> None:
    owner_token, simulation_id = register_login_and_create(client, "event-owner")
    other_token, other_simulation_id = register_login_and_create(client, "event-other")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    other_headers = {"Authorization": f"Bearer {other_token}"}
    foreign_agents = client.get(
        f"/v1/simulations/{other_simulation_id}/agents", headers=other_headers
    ).json()
    payload = {
        "event_type": "meeting",
        "title": "회의",
        "simulation_day": 1,
        "location_id": foreign_agents[0]["location"]["id"],
    }

    forbidden_create = client.post(
        f"/v1/simulations/{simulation_id}/events",
        headers=other_headers,
        json=payload,
    )
    forbidden_list = client.get(
        f"/v1/simulations/{simulation_id}/events", headers=other_headers
    )
    invalid_location = client.post(
        f"/v1/simulations/{simulation_id}/events",
        headers=owner_headers,
        json=payload,
    )

    assert forbidden_create.status_code == 403
    assert forbidden_list.status_code == 403
    assert invalid_location.status_code == 422
    assert invalid_location.json()["detail"] == "Location does not belong to simulation"


def test_event_commit_failure_rolls_back_without_broadcast(
    client: TestClient, monkeypatch
) -> None:
    from sqlalchemy.orm import Session

    from app.services.realtime_events import connection_manager

    token, simulation_id = register_login_and_create(client, "event-rollback-owner")
    headers = {"Authorization": f"Bearer {token}"}
    broadcasts = []

    async def record_broadcast(*args):
        broadcasts.append(args)

    def fail_commit(self):
        raise RuntimeError("forced commit failure")

    monkeypatch.setattr(connection_manager, "broadcast", record_broadcast)
    monkeypatch.setattr(Session, "commit", fail_commit)

    response = client.post(
        f"/v1/simulations/{simulation_id}/events",
        headers=headers,
        json={
            "event_type": "exam",
            "title": "마법 시험",
            "simulation_day": 1,
        },
    )

    assert response.status_code == 500
    assert broadcasts == []
    listed = client.get(
        f"/v1/simulations/{simulation_id}/events", headers=headers
    )
    assert listed.status_code == 200, listed.text
    assert all(item["title"] != "마법 시험" for item in listed.json())
