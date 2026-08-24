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


def test_tick_broadcasts_only_after_successful_commit(client: TestClient) -> None:
    token, simulation_id = register_login_and_create(client, "ws-tick-owner")
    headers = {"Authorization": f"Bearer {token}"}

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
        action_events = [websocket.receive_json(), websocket.receive_json()]
        assert {event["type"] for event in action_events} == {
            "AGENT_ACTION_UPDATED"
        }
