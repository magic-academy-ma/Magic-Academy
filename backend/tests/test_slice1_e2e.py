import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event as ThreadEvent
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
if os.getenv("CI") == "true" and not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL is required in CI")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required"
)


@pytest.fixture()
def client():
    from app.core.database import get_db
    from app.main import app
    from app.services.runtime_dependency import get_agent_runtime
    from app.simulation.agent_runtime import AgentRuntime, MockLLMClient

    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE runtime_results, event_participants, events, users, "
                "simulations, locations, agents RESTART IDENTITY CASCADE"
            )
        )

    def override_db():
        with session_factory() as session:
            yield session

    runtime = AgentRuntime(MockLLMClient(), model="test-runtime-override")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_agent_runtime] = lambda: runtime
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client, session_factory
    app.dependency_overrides.clear()
    engine.dispose()


def register_login_create(test_client):
    credentials = {
        "username": "slice-one-owner",
        "display_name": "Slice One",
        "password": "Slice1-password!",
    }
    assert test_client.post("/v1/auth/register", json=credentials).status_code == 201
    login = test_client.post(
        "/v1/auth/login",
        json={"username": credentials["username"], "password": credentials["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    created = test_client.post(
        "/v1/simulations", headers=headers, json={"name": "Slice 1 E2E"}
    )
    assert created.status_code == 201
    return created.json()["id"], headers


def test_slice_one_full_vertical_flow(client):
    from app.domain.models import (
        Agent,
        AgentState,
        Event,
        EventParticipant,
        Relationship,
        RuntimeResult,
        Simulation,
    )

    test_client, session_factory = client
    simulation_id, headers = register_login_create(test_client)

    assert (
        test_client.post(f"/v1/simulations/{simulation_id}/ticks/advance").status_code
        == 401
    )

    response = test_client.post(
        f"/v1/simulations/{simulation_id}/ticks/advance", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["simulation_id"] == simulation_id
    assert (body["previous_tick"], body["current_tick"], body["current_day"]) == (
        0,
        1,
        1,
    )
    assert body["status"] == "COMPLETED"
    assert body["retrieved_memories"] == []
    assert "runtime_outputs" not in body
    assert "participant_ids" not in body
    assert {result["runtime_status"] for result in body["agent_results"]} <= {
        "PROPOSED",
        "FALLBACK",
        "SKIPPED",
    }
    assert body["relationship_deltas"] == []

    with session_factory() as db:
        simulation_uuid = UUID(simulation_id)
        agents = list(
            db.scalars(select(Agent).where(Agent.simulation_id == simulation_uuid))
        )
        assert len(agents) == 6
        class_event = db.scalar(
            select(Event).where(
                Event.simulation_id == simulation_uuid, Event.event_type == "class"
            )
        )
        participant_ids = set(
            db.scalars(
                select(EventParticipant.agent_id).where(
                    EventParticipant.event_id == class_event.id
                )
            )
        )
        fixtures_by_id = {agent.id: agent.fixture_key for agent in agents}
        assert {fixtures_by_id[agent_id] for agent_id in participant_ids} == {
            "student-01",
            "professor-01",
        }
        stored = list(
            db.scalars(select(RuntimeResult).order_by(RuntimeResult.agent_id))
        )
        assert {fixtures_by_id[result.agent_id] for result in stored} == {
            "student-01",
            "professor-01",
        }
        run_ids = {result.run_id for result in stored}
        assert len(run_ids) == 1
        stored_run_id = run_ids.pop()
        assert stored_run_id != simulation_id
        assert UUID(stored_run_id).version == 7
        assert all(
            result.idempotency_key
            == f"{result.run_id}:{result.tick_number}:{result.agent_id}"
            for result in stored
        )
        assert {result.model for result in stored} == {"test-runtime-override"}
        api_by_id = {result["agent_id"]: result for result in body["agent_results"]}
        assert set(api_by_id) == {str(result.agent_id) for result in stored}
        for result in stored:
            api_result = api_by_id[str(result.agent_id)]
            assert api_result["runtime_status"] == result.status
            assert api_result["action_type"] == result.action_type
        simulation = db.get(Simulation, simulation_uuid)
        assert (simulation.current_tick, simulation.current_day) == (1, 1)
        assert db.scalar(select(func.count()).select_from(RuntimeResult)) == 2
        assert len(body["state_deltas"]) == 2
        assert {
            (delta["metric"], delta["delta"], delta["after"])
            for delta in body["state_deltas"]
        } == {("fatigue", 2, 17)}
        states = list(
            db.scalars(
                select(AgentState).where(AgentState.agent_id.in_(participant_ids))
            )
        )
        assert {state.fatigue for state in states} == {17}
        assert db.scalar(select(func.count()).select_from(Relationship)) == 0


def test_slice_two_policy_applies_directional_relationship_delta(client, monkeypatch):
    from app.domain.models import Agent, Relationship
    from app.simulation.agent_runtime import MockLLMClient

    test_client, session_factory = client
    simulation_id, headers = register_login_create(test_client)
    original_generate = MockLLMClient.generate

    def generate_relationship_signal(self, runtime_input):
        response = original_generate(self, runtime_input)
        target_agent_id = next(
            agent_id
            for agent_id in runtime_input.events[0].participant_agent_ids
            if agent_id != runtime_input.agent.agent_id
        )
        response["reaction"]["relationship_signals"] = [
            {
                "signal_type": "TRUST_UP",
                "intensity": "MEDIUM",
                "target_agent_id": str(target_agent_id),
            }
        ]
        return response

    monkeypatch.setattr(MockLLMClient, "generate", generate_relationship_signal)
    response = test_client.post(
        f"/v1/simulations/{simulation_id}/ticks/advance", headers=headers
    )

    assert response.status_code == 200, response.text
    deltas = response.json()["relationship_deltas"]
    assert len(deltas) == 2
    assert {(delta["metric"], delta["delta"]) for delta in deltas} == {("trust", 3)}

    with session_factory() as db:
        agents = list(
            db.scalars(select(Agent).where(Agent.simulation_id == UUID(simulation_id)))
        )
        participants = {
            agent.id
            for agent in agents
            if agent.fixture_key in {"student-01", "professor-01"}
        }
        relationships = list(db.scalars(select(Relationship)))
        assert len(relationships) == 2
        assert {
            (
                relationship.source_agent_id,
                relationship.target_agent_id,
                relationship.trust,
            )
            for relationship in relationships
        } == {
            (source, target, 3)
            for source in participants
            for target in participants
            if source != target
        }


def test_other_user_cannot_advance_owned_simulation(client):
    test_client, _ = client
    simulation_id, _ = register_login_create(test_client)
    other = {
        "username": "slice-one-other",
        "display_name": "Other",
        "password": "Slice1-password!",
    }
    test_client.post("/v1/auth/register", json=other)
    login = test_client.post(
        "/v1/auth/login",
        json={"username": other["username"], "password": other["password"]},
    )
    response = test_client.post(
        f"/v1/simulations/{simulation_id}/ticks/advance",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 403


def test_runtime_results_and_tick_roll_back_together(client, monkeypatch):
    from app.domain.models import RuntimeResult, Simulation
    from app.services.simulation_tick import SimulationTickService

    test_client, session_factory = client
    simulation_id, headers = register_login_create(test_client)
    original = SimulationTickService.run_runtime_phase
    failed_run_ids = []

    def fail_after_save(self, *args, **kwargs):
        failed_run_ids.append(str(kwargs["run_id"]))
        original(self, *args, **kwargs)
        raise RuntimeError("tick update failed")

    monkeypatch.setattr(SimulationTickService, "run_runtime_phase", fail_after_save)
    response = test_client.post(
        f"/v1/simulations/{simulation_id}/ticks/advance", headers=headers
    )
    assert response.status_code == 500
    with session_factory() as db:
        simulation = db.get(Simulation, UUID(simulation_id))
        assert simulation.current_tick == 0
        assert db.scalar(select(func.count()).select_from(RuntimeResult)) == 0

    monkeypatch.setattr(SimulationTickService, "run_runtime_phase", original)
    retry = test_client.post(
        f"/v1/simulations/{simulation_id}/ticks/advance", headers=headers
    )
    assert retry.status_code == 200
    with session_factory() as db:
        saved_run_ids = set(db.scalars(select(RuntimeResult.run_id)))
    assert len(failed_run_ids) == 1
    assert len(saved_run_ids) == 1
    assert failed_run_ids[0] not in saved_run_ids


def test_policy_changes_and_runtime_results_roll_back_together(client, monkeypatch):
    from app.domain.models import Agent, AgentState, RuntimeResult, Simulation
    from app.services import manual_tick

    test_client, session_factory = client
    simulation_id, headers = register_login_create(test_client)
    original = manual_tick.evaluate_and_apply_policy

    def fail_after_policy(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("commit boundary failed")

    monkeypatch.setattr(manual_tick, "evaluate_and_apply_policy", fail_after_policy)
    response = test_client.post(
        f"/v1/simulations/{simulation_id}/ticks/advance", headers=headers
    )

    assert response.status_code == 500
    with session_factory() as db:
        simulation_uuid = UUID(simulation_id)
        simulation = db.get(Simulation, simulation_uuid)
        participant_ids = set(
            db.scalars(
                select(Agent.id).where(
                    Agent.simulation_id == simulation_uuid,
                    Agent.fixture_key.in_(("student-01", "professor-01")),
                )
            )
        )
        states = list(
            db.scalars(
                select(AgentState).where(AgentState.agent_id.in_(participant_ids))
            )
        )
        assert simulation.current_tick == 0
        assert {state.fatigue for state in states} == {15}
        assert db.scalar(select(func.count()).select_from(RuntimeResult)) == 0


def test_consecutive_ticks_use_distinct_batch_run_ids(client):
    from app.domain.models import RuntimeResult

    test_client, session_factory = client
    simulation_id, headers = register_login_create(test_client)

    first = test_client.post(
        f"/v1/simulations/{simulation_id}/ticks/advance", headers=headers
    )
    second = test_client.post(
        f"/v1/simulations/{simulation_id}/ticks/advance", headers=headers
    )
    assert first.status_code == second.status_code == 200

    with session_factory() as db:
        stored = list(
            db.scalars(
                select(RuntimeResult).order_by(
                    RuntimeResult.tick_number, RuntimeResult.agent_id
                )
            )
        )
    run_ids_by_tick = {}
    for result in stored:
        run_ids_by_tick.setdefault(result.tick_number, set()).add(result.run_id)
        assert result.idempotency_key == (
            f"{result.run_id}:{result.tick_number}:{result.agent_id}"
        )
    assert set(run_ids_by_tick) == {1, 2}
    assert all(len(run_ids) == 1 for run_ids in run_ids_by_tick.values())
    assert run_ids_by_tick[1] != run_ids_by_tick[2]
    assert all(simulation_id not in run_ids for run_ids in run_ids_by_tick.values())


def test_concurrent_tick_returns_immediate_conflict(client, monkeypatch):
    from app.simulation.agent_runtime import AgentRuntime

    test_client, _ = client
    simulation_id, headers = register_login_create(test_client)
    entered_runtime = ThreadEvent()
    release_runtime = ThreadEvent()
    original = AgentRuntime.run
    first_call = True

    def hold_first_runtime(self, runtime_input):
        nonlocal first_call
        if first_call:
            first_call = False
            entered_runtime.set()
            assert release_runtime.wait(timeout=5)
        return original(self, runtime_input)

    monkeypatch.setattr(AgentRuntime, "run", hold_first_runtime)

    def request_tick():
        return test_client.post(
            f"/v1/simulations/{simulation_id}/ticks/advance", headers=headers
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(request_tick)
        assert entered_runtime.wait(timeout=5)
        second = executor.submit(request_tick).result(timeout=5)
        release_runtime.set()
        successful = first.result(timeout=5)

    assert successful.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "TICK_ALREADY_RUNNING"


def test_tick_api_uses_engine_and_each_batch_boundary_once(client, monkeypatch):
    from app.services.database_runtime_results import DatabaseRuntimeResultSink
    from app.services.simulation_tick import SimulationTickService
    from app.simulation.tick_engine import TickEngine

    test_client, _ = client
    simulation_id, headers = register_login_create(test_client)
    calls = {"engine": 0, "runtime_phase": 0, "save_batch": 0}
    original_engine = TickEngine.run_tick
    original_runtime_phase = SimulationTickService.run_runtime_phase
    original_save_batch = DatabaseRuntimeResultSink.save_batch

    async def count_engine(self, *args, **kwargs):
        calls["engine"] += 1
        return await original_engine(self, *args, **kwargs)

    def count_runtime_phase(self, *args, **kwargs):
        calls["runtime_phase"] += 1
        return original_runtime_phase(self, *args, **kwargs)

    def count_save_batch(self, *args, **kwargs):
        calls["save_batch"] += 1
        return original_save_batch(self, *args, **kwargs)

    monkeypatch.setattr(TickEngine, "run_tick", count_engine)
    monkeypatch.setattr(SimulationTickService, "run_runtime_phase", count_runtime_phase)
    monkeypatch.setattr(DatabaseRuntimeResultSink, "save_batch", count_save_batch)

    response = test_client.post(
        f"/v1/simulations/{simulation_id}/ticks/advance", headers=headers
    )

    assert response.status_code == 200
    assert calls == {"engine": 1, "runtime_phase": 1, "save_batch": 1}
    assert {result["agent_name"] for result in response.json()["agent_results"]} == {
        "아델",
        "에단",
    }


def test_manual_tick_preserves_tick_engine_policy_extension(client):
    from app.domain.models import Simulation
    from app.services.manual_tick import advance_manual_tick
    from app.simulation.agent_runtime import AgentRuntime, MockLLMClient

    test_client, session_factory = client
    simulation_id, _ = register_login_create(test_client)
    received_policy_inputs = []

    async def policy(inputs):
        received_policy_inputs.extend(inputs)

    with session_factory() as db:
        simulation = db.get(Simulation, UUID(simulation_id))
        result = asyncio.run(
            advance_manual_tick(
                db,
                simulation,
                runtime=AgentRuntime(MockLLMClient(), model="test-direct-runtime"),
                policy=policy,
            )
        )
        db.commit()

    assert len(received_policy_inputs) == len(result.runtime_results) == 2
    assert {item.agent_id for item in received_policy_inputs} == {
        str(runtime_result.agent_id) for runtime_result in result.runtime_results
    }
