"""Slice 6 사용자 관점 HTTP 인수 테스트."""

import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from uuid6 import uuid7

from app.domain.models import Agent, Event, RuntimeResult, Simulation, SimulationSnapshot
from app.services.simulation_snapshots import SimulationSnapshotService
from app.simulation.instrumentation import get_counts, reset_counters


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required"
)


@pytest.fixture()
def acceptance_context():
    from app.core.database import get_db
    from app.main import app

    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE users, simulations RESTART IDENTITY CASCADE"))

    def override_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, session_factory
    app.dependency_overrides.clear()
    engine.dispose()


def _register(client: TestClient, username: str) -> dict[str, str]:
    password = "Slice6-acceptance!"
    response = client.post(
        "/v1/auth/register",
        json={"username": username, "display_name": username, "password": password},
    )
    assert response.status_code == 201
    response = client.post(
        "/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_simulation(
    client: TestClient, headers: dict[str, str], name: str
) -> UUID:
    response = client.post("/v1/simulations", headers=headers, json={"name": name})
    assert response.status_code == 201
    return UUID(response.json()["id"])


def _database_state(session_factory, simulation_id: UUID) -> dict[str, int]:
    with session_factory() as session:
        return {
            "simulations": session.scalar(select(func.count()).select_from(Simulation)),
            "runtime_results": session.scalar(
                select(func.count()).select_from(RuntimeResult)
            ),
            "snapshots": session.scalar(
                select(func.count()).select_from(SimulationSnapshot)
            ),
            "events": session.scalar(select(func.count()).select_from(Event)),
            "current_tick": session.get(Simulation, simulation_id).current_tick,
        }


def _persist_recorded_tick(
    session_factory, simulation_id: UUID
) -> tuple[list[UUID], UUID]:
    result_ids: list[UUID] = []
    with session_factory.begin() as session:
        simulation = session.get(Simulation, simulation_id)
        simulation.current_tick = 1
        for sequence, fixture_key in enumerate(("student-02", "student-01")):
            agent_id = session.scalar(
                select(Agent.id).where(
                    Agent.simulation_id == simulation_id,
                    Agent.fixture_key == fixture_key,
                )
            )
            result_id = uuid7()
            result_ids.append(result_id)
            session.add(
                RuntimeResult(
                    id=result_id,
                    run_id=f"slice6-acceptance-run:{simulation_id}",
                    tick_number=1,
                    agent_id=agent_id,
                    status="PROPOSED",
                    action_type="IDLE",
                    intent={"recorded_sequence": sequence},
                    retry_count=0,
                    model="acceptance-model",
                    prompt_version="acceptance-v1",
                    idempotency_key=f"slice6-acceptance:{simulation_id}:1:{fixture_key}",
                    result_fingerprint=(str(sequence + 1) * 64)[:64],
                )
            )
        session.flush()
        snapshot = SimulationSnapshotService().create_snapshot(session, simulation)
        snapshot_id = snapshot.id
    return result_ids, snapshot_id


def test_settings_snapshot_replay_restore_http_golden_path(acceptance_context) -> None:
    client, session_factory = acceptance_context
    owner_headers = _register(client, "slice6-acceptance-owner")
    other_headers = _register(client, "slice6-acceptance-other")
    simulation_id = _create_simulation(client, owner_headers, "Slice 6 Golden Path")

    saved = client.put(
        f"/v1/simulations/{simulation_id}/parameters",
        headers=owner_headers,
        json={
            "event_frequency": "high",
            "event_impact": "low",
            # magic_enabled=false 는 magic_layer_impact=high 에서만 허용된다.
            "magic_layer_impact": "high",
            "magic_enabled": False,
        },
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["config_version"] == 2

    invalid = client.patch(
        f"/v1/simulations/{simulation_id}/parameters",
        headers=owner_headers,
        json={"event_frequency": "invalid", "event_impact": "medium"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_REPLAY_REQUEST"

    with session_factory.begin() as session:
        session.get(Simulation, simulation_id).status = "running"
    locked = client.put(
        f"/v1/simulations/{simulation_id}/parameters",
        headers=owner_headers,
        json={
            "event_frequency": "medium",
            "event_impact": "medium",
            "magic_enabled": True,
        },
    )
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "INITIAL_SETTINGS_LOCKED"

    runtime_result_ids, snapshot_id = _persist_recorded_tick(
        session_factory, simulation_id
    )
    state_before = _database_state(session_factory, simulation_id)

    snapshot = client.get(
        f"/v1/simulations/{simulation_id}/snapshots/1", headers=owner_headers
    )
    assert snapshot.status_code == 200
    snapshot_data = snapshot.json()["data"]
    assert snapshot_data["snapshot_id"] == str(snapshot_id)
    assert snapshot_data["tick_number"] == 1
    assert snapshot_data["config"]["event_frequency"] == "high"
    assert snapshot_data["config"]["event_impact"] == "low"
    assert snapshot_data["config"]["magic_enabled"] is False

    missing_snapshot = client.get(
        f"/v1/simulations/{simulation_id}/snapshots/999", headers=owner_headers
    )
    assert missing_snapshot.status_code == 404
    denied_snapshot = client.get(
        f"/v1/simulations/{simulation_id}/snapshots/1", headers=other_headers
    )
    assert denied_snapshot.status_code == 403

    reset_counters()
    replay_list = client.get(
        f"/v1/simulations/{simulation_id}/replay", headers=owner_headers
    )
    assert replay_list.status_code == 200
    assert [row["tick_number"] for row in replay_list.json()["data"]] == [0, 1]

    replay_detail = client.get(
        f"/v1/simulations/{simulation_id}/replay/1", headers=owner_headers
    )
    assert replay_detail.status_code == 200
    replay_data = replay_detail.json()["data"]
    assert replay_data["snapshot_id"] == str(snapshot_id)
    assert replay_data["tick_number"] == 1
    assert [row["id"] for row in replay_data["runtime_results"]] == [
        str(result_id) for result_id in runtime_result_ids
    ]
    assert [row["run_id"] for row in replay_data["runtime_results"]] == [
        f"slice6-acceptance-run:{simulation_id}",
        f"slice6-acceptance-run:{simulation_id}",
    ]
    assert [row["tick_number"] for row in replay_data["runtime_results"]] == [1, 1]
    assert len({row["agent_id"] for row in replay_data["runtime_results"]}) == 2
    assert get_counts() == {"tick_calls": 0, "runtime_calls": 0, "llm_calls": 0}

    restored = client.post(
        f"/v1/simulations/{simulation_id}/restore",
        headers=owner_headers,
        json={"snapshot_id": str(snapshot_id)},
    )
    assert restored.status_code == 200
    assert restored.json()["data"]["simulation"]["id"] == str(simulation_id)
    assert _database_state(session_factory, simulation_id) == state_before


def test_http_auth_ownership_and_restore_errors(acceptance_context) -> None:
    client, session_factory = acceptance_context
    owner_headers = _register(client, "slice6-errors-owner")
    other_headers = _register(client, "slice6-errors-other")
    simulation_id = _create_simulation(client, owner_headers, "Error source")
    other_simulation_id = _create_simulation(client, owner_headers, "Mismatch source")
    _, snapshot_id = _persist_recorded_tick(session_factory, simulation_id)
    _, other_snapshot_id = _persist_recorded_tick(session_factory, other_simulation_id)

    unauthenticated = client.get(f"/v1/simulations/{simulation_id}/replay")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    denied = client.get(
        f"/v1/simulations/{simulation_id}/replay", headers=other_headers
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "SIMULATION_ACCESS_DENIED"

    missing = client.get(
        f"/v1/simulations/{uuid4()}/replay", headers=owner_headers
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "REPLAY_RESOURCE_NOT_FOUND"

    mismatch = client.post(
        f"/v1/simulations/{simulation_id}/restore",
        headers=owner_headers,
        json={"snapshot_id": str(other_snapshot_id)},
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "SNAPSHOT_MISMATCH"

    state_before = _database_state(session_factory, simulation_id)
    with session_factory.begin() as session:
        stored = session.get(SimulationSnapshot, snapshot_id)
        stored.payload = {**stored.payload, "schema_version": "unsupported"}
    state_after_fixture_change = _database_state(session_factory, simulation_id)
    unsupported = client.post(
        f"/v1/simulations/{simulation_id}/restore",
        headers=owner_headers,
        json={"snapshot_id": str(snapshot_id)},
    )
    assert unsupported.status_code == 409
    assert unsupported.json()["error"]["code"] == "UNSUPPORTED_SNAPSHOT_SCHEMA"
    assert _database_state(session_factory, simulation_id) == state_after_fixture_change
    assert state_after_fixture_change == state_before
