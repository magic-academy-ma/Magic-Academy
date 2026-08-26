import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from uuid6 import uuid7

from app.domain.models import (
    Agent,
    Event,
    RuntimeResult,
    Simulation,
    SimulationSnapshot,
)
from app.services.simulation_snapshots import SimulationSnapshotService
from app.simulation.instrumentation import get_counts, reset_counters


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required"
)


@pytest.fixture()
def api_context():
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
        yield client, session_factory, app
    app.dependency_overrides.clear()
    engine.dispose()


def _register(client: TestClient, username: str) -> dict[str, str]:
    password = "Slice6-password!"
    response = client.post(
        "/v1/auth/register",
        json={"username": username, "display_name": username, "password": password},
    )
    assert response.status_code == 201
    login = client.post(
        "/v1/auth/login", json={"username": username, "password": password}
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_simulation(client: TestClient, headers: dict[str, str], name: str) -> UUID:
    response = client.post("/v1/simulations", headers=headers, json={"name": name})
    assert response.status_code == 201
    return UUID(response.json()["id"])


def _persist_runtime_and_snapshot(
    session_factory,
    simulation_id: UUID,
    *,
    tick_number: int,
    run_id: str,
    fixture_keys: tuple[str, ...] = ("student-01",),
) -> tuple[list[UUID], UUID]:
    result_ids = []
    with session_factory.begin() as session:
        simulation = session.get(Simulation, simulation_id)
        simulation.current_tick = tick_number
        for sequence, fixture_key in enumerate(fixture_keys):
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
                    run_id=run_id,
                    tick_number=tick_number,
                    agent_id=agent_id,
                    status="PROPOSED",
                    action_type="IDLE",
                    intent={"sequence": sequence},
                    retry_count=0,
                    model="test-model",
                    prompt_version="test-prompt-v1",
                    idempotency_key=f"{run_id}:{tick_number}:{fixture_key}",
                    result_fingerprint=(str(sequence + 1) * 64)[:64],
                )
            )
        session.flush()
        snapshot = SimulationSnapshotService().create_snapshot(session, simulation)
        snapshot_id = snapshot.id
    return result_ids, snapshot_id


def test_parameters_routes_and_error_contract(api_context) -> None:
    client, session_factory, _ = api_context
    owner_headers = _register(client, "slice6-api-owner")
    other_headers = _register(client, "slice6-api-other")
    simulation_id = _create_simulation(client, owner_headers, "Parameters")

    put = client.put(
        f"/v1/simulations/{simulation_id}/parameters",
        headers=owner_headers,
        json={
            "event_frequency": "high",
            "event_impact": "low",
            "magic_enabled": False,
        },
    )
    assert put.status_code == 200
    put_data = put.json()["data"]
    assert {
        key: value for key, value in put_data.items() if key != "changed_at"
    } == {
        "event_frequency": "high",
        "event_impact": "low",
        "magic_enabled": False,
        "config_version": 2,
    }
    assert put_data["changed_at"]

    with session_factory.begin() as session:
        simulation = session.get(Simulation, simulation_id)
        simulation.status = "running"

    patch = client.patch(
        f"/v1/simulations/{simulation_id}/parameters",
        headers=owner_headers,
        json={"event_frequency": "low", "event_impact": "medium"},
    )
    assert patch.status_code == 200
    assert patch.json()["data"]["config_version"] == 3
    assert patch.json()["data"]["magic_enabled"] is False

    locked_initial = client.put(
        f"/v1/simulations/{simulation_id}/parameters",
        headers=owner_headers,
        json={
            "event_frequency": "low",
            "event_impact": "medium",
            "magic_enabled": True,
        },
    )
    assert locked_initial.status_code == 409
    assert locked_initial.json()["error"]["code"] == "INITIAL_SETTINGS_LOCKED"

    invalid = client.patch(
        f"/v1/simulations/{simulation_id}/parameters",
        headers=owner_headers,
        json={"event_frequency": "extreme", "event_impact": "medium"},
    )
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_REPLAY_REQUEST"

    with session_factory.begin() as session:
        session.get(Simulation, simulation_id).status = "completed"
    locked = client.patch(
        f"/v1/simulations/{simulation_id}/parameters",
        headers=owner_headers,
        json={"event_frequency": "low", "event_impact": "medium"},
    )
    assert locked.status_code == 409
    assert locked.json()["error"]["code"] == "SIMULATION_SETTINGS_LOCKED"

    denied = client.patch(
        f"/v1/simulations/{simulation_id}/parameters",
        headers=other_headers,
        json={"event_frequency": "low", "event_impact": "medium"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "SIMULATION_ACCESS_DENIED"

    unauthenticated = client.patch(
        f"/v1/simulations/{simulation_id}/parameters",
        json={"event_frequency": "low", "event_impact": "medium"},
    )
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"

    missing = client.patch(
        f"/v1/simulations/{uuid4()}/parameters",
        headers=owner_headers,
        json={"event_frequency": "low", "event_impact": "medium"},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "REPLAY_RESOURCE_NOT_FOUND"


def test_snapshot_restore_and_mismatch_are_read_only(api_context) -> None:
    client, session_factory, _ = api_context
    owner_headers = _register(client, "slice6-snapshot-owner")
    other_headers = _register(client, "slice6-snapshot-other")
    simulation_id = _create_simulation(client, owner_headers, "Snapshots")
    other_simulation_id = _create_simulation(client, owner_headers, "Other source")
    foreign_simulation_id = _create_simulation(client, other_headers, "Foreign")

    with session_factory() as session:
        snapshot = session.scalar(
            select(SimulationSnapshot).where(
                SimulationSnapshot.simulation_id == simulation_id
            )
        )
        other_snapshot = session.scalar(
            select(SimulationSnapshot).where(
                SimulationSnapshot.simulation_id == other_simulation_id
            )
        )
        foreign_snapshot = session.scalar(
            select(SimulationSnapshot).where(
                SimulationSnapshot.simulation_id == foreign_simulation_id
            )
        )
        before = (
            session.scalar(select(func.count()).select_from(Simulation)),
            session.scalar(select(func.count()).select_from(RuntimeResult)),
            session.scalar(select(func.count()).select_from(SimulationSnapshot)),
            session.scalar(select(func.count()).select_from(Event)),
        )

    get_response = client.get(
        f"/v1/simulations/{simulation_id}/snapshots/0", headers=owner_headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["data"]["snapshot_id"] == str(snapshot.id)
    assert get_response.json()["data"]["tick_number"] == 0

    denied_get = client.get(
        f"/v1/simulations/{simulation_id}/snapshots/0", headers=other_headers
    )
    assert denied_get.status_code == 403

    missing = client.get(
        f"/v1/simulations/{simulation_id}/snapshots/99", headers=owner_headers
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "REPLAY_RESOURCE_NOT_FOUND"

    restored = client.post(
        f"/v1/simulations/{simulation_id}/restore",
        headers=owner_headers,
        json={"snapshot_id": str(snapshot.id)},
    )
    assert restored.status_code == 200
    assert restored.json()["data"]["simulation"]["id"] == str(simulation_id)

    missing_restore = client.post(
        f"/v1/simulations/{simulation_id}/restore",
        headers=owner_headers,
        json={"snapshot_id": str(uuid4())},
    )
    assert missing_restore.status_code == 404

    mismatch = client.post(
        f"/v1/simulations/{simulation_id}/restore",
        headers=owner_headers,
        json={"snapshot_id": str(other_snapshot.id)},
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "SNAPSHOT_MISMATCH"

    denied = client.post(
        f"/v1/simulations/{simulation_id}/restore",
        headers=owner_headers,
        json={"snapshot_id": str(foreign_snapshot.id)},
    )
    assert denied.status_code == 403

    with session_factory.begin() as session:
        stored = session.get(SimulationSnapshot, snapshot.id)
        stored.payload = {**stored.payload, "schema_version": "unsupported"}
    unsupported = client.post(
        f"/v1/simulations/{simulation_id}/restore",
        headers=owner_headers,
        json={"snapshot_id": str(snapshot.id)},
    )
    assert unsupported.status_code == 409
    assert unsupported.json()["error"]["code"] == "UNSUPPORTED_SNAPSHOT_SCHEMA"

    with session_factory() as session:
        after = (
            session.scalar(select(func.count()).select_from(Simulation)),
            session.scalar(select(func.count()).select_from(RuntimeResult)),
            session.scalar(select(func.count()).select_from(SimulationSnapshot)),
            session.scalar(select(func.count()).select_from(Event)),
        )
    assert after == before


def test_replay_routes_preserve_order_paginate_and_never_run_or_write(api_context) -> None:
    client, session_factory, app = api_context
    headers = _register(client, "slice6-replay-owner")
    simulation_id = _create_simulation(client, headers, "Replay")
    other_simulation_id = _create_simulation(client, headers, "Isolated")
    result_ids, _ = _persist_runtime_and_snapshot(
        session_factory,
        simulation_id,
        tick_number=1,
        run_id="slice6-api-run",
        fixture_keys=("student-02", "student-01"),
    )
    _persist_runtime_and_snapshot(
        session_factory,
        other_simulation_id,
        tick_number=2,
        run_id="other-run",
    )

    openapi_paths = app.openapi()["paths"]
    route_paths = set(openapi_paths)
    assert "/v1/simulations/{simulation_id}/parameters" in route_paths
    assert set(openapi_paths["/v1/simulations/{simulation_id}/parameters"]) == {
        "put",
        "patch",
    }
    assert "/v1/simulations/{simulation_id}/snapshots/{tick_number}" in route_paths
    assert "/v1/simulations/{simulation_id}/restore" in route_paths
    assert "/v1/simulations/{simulation_id}/replay" in route_paths
    assert "/v1/simulations/{simulation_id}/replay/{tick_number}" in route_paths

    with session_factory() as session:
        before = {
            "runtime": session.scalar(select(func.count()).select_from(RuntimeResult)),
            "snapshots": session.scalar(
                select(func.count()).select_from(SimulationSnapshot)
            ),
            "events": session.scalar(select(func.count()).select_from(Event)),
            "tick": session.get(Simulation, simulation_id).current_tick,
        }

    reset_counters()
    first_page = client.get(
        f"/v1/simulations/{simulation_id}/replay?limit=1", headers=headers
    )
    assert first_page.status_code == 200
    assert [item["tick_number"] for item in first_page.json()["data"]] == [0]
    assert first_page.json()["meta"] == {"next_cursor": "0", "has_more": True}

    second_page = client.get(
        f"/v1/simulations/{simulation_id}/replay?limit=1&cursor=0",
        headers=headers,
    )
    assert [item["tick_number"] for item in second_page.json()["data"]] == [1]
    assert all(item["tick_number"] != 2 for item in second_page.json()["data"])

    detail = client.get(
        f"/v1/simulations/{simulation_id}/replay/1", headers=headers
    )
    assert detail.status_code == 200
    replay_results = detail.json()["data"]["runtime_results"]
    assert [row["id"] for row in replay_results] == [str(value) for value in result_ids]
    assert [row["tick_number"] for row in replay_results] == [1, 1]
    assert [row["run_id"] for row in replay_results] == [
        "slice6-api-run",
        "slice6-api-run",
    ]
    assert len({row["agent_id"] for row in replay_results}) == 2
    assert get_counts() == {"tick_calls": 0, "runtime_calls": 0, "llm_calls": 0}

    missing_runtime = client.get(
        f"/v1/simulations/{simulation_id}/replay/0", headers=headers
    )
    assert missing_runtime.status_code == 404
    assert missing_runtime.json()["error"]["code"] == "REPLAY_RESOURCE_NOT_FOUND"

    with session_factory() as session:
        after = {
            "runtime": session.scalar(select(func.count()).select_from(RuntimeResult)),
            "snapshots": session.scalar(
                select(func.count()).select_from(SimulationSnapshot)
            ),
            "events": session.scalar(select(func.count()).select_from(Event)),
            "tick": session.get(Simulation, simulation_id).current_tick,
        }
    assert after == before


def test_replay_detail_reports_missing_snapshot_and_mismatch(api_context) -> None:
    client, session_factory, _ = api_context
    headers = _register(client, "slice6-replay-errors")
    simulation_id = _create_simulation(client, headers, "Replay errors")

    with session_factory.begin() as session:
        simulation = session.get(Simulation, simulation_id)
        simulation.current_tick = 3
        agent_id = session.scalar(
            select(Agent.id).where(Agent.simulation_id == simulation_id)
        )
        session.add(
            RuntimeResult(
                id=uuid7(),
                run_id="missing-snapshot",
                tick_number=3,
                agent_id=agent_id,
                status="PROPOSED",
                action_type="IDLE",
                intent={},
                retry_count=0,
                model="test-model",
                prompt_version="test-prompt-v1",
                idempotency_key="missing-snapshot:3",
                result_fingerprint="f" * 64,
            )
        )
    missing = client.get(
        f"/v1/simulations/{simulation_id}/replay/3", headers=headers
    )
    assert missing.status_code == 404

    _, snapshot_id = _persist_runtime_and_snapshot(
        session_factory,
        simulation_id,
        tick_number=4,
        run_id="mismatch-run",
    )
    with session_factory.begin() as session:
        snapshot = session.get(SimulationSnapshot, snapshot_id)
        snapshot.payload = {**snapshot.payload, "runtime_results": []}
    mismatch = client.get(
        f"/v1/simulations/{simulation_id}/replay/4", headers=headers
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["error"]["code"] == "SNAPSHOT_MISMATCH"
