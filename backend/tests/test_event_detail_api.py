"""GET /v1/simulations/{simulation_id}/events/{event_id} — Issue #182-6.

기존 events API 테스트 스타일(TEST_DATABASE_URL 필요, TestClient + register/login)을
따른다. 엔진이 남긴 tick/importance/impact_level/source/참여 Agent/related_memory 는
persist_event_batch 로 만든다.
"""

import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")


@pytest.fixture()
def client():
    from app.core.database import get_db
    from app.main import app

    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE users, simulations, locations, agents, agent_states "
                "RESTART IDENTITY CASCADE"
            )
        )

    def override_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client, session_factory
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, username: str) -> dict[str, str]:
    password = "Detail-password!"
    assert (
        client.post(
            "/v1/auth/register",
            json={"username": username, "display_name": username, "password": password},
        ).status_code
        == 201
    )
    login = client.post("/v1/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_simulation(client: TestClient, headers: dict[str, str], name: str) -> str:
    return client.post("/v1/simulations", headers=headers, json={"name": name}).json()["id"]


def post_event(client: TestClient, headers: dict[str, str], simulation_id: str, title: str) -> dict:
    response = client.post(
        f"/v1/simulations/{simulation_id}/events",
        headers=headers,
        json={"event_type": "class", "title": title, "simulation_day": 1},
    )
    assert response.status_code == 201, response.text
    return response.json()


def persist_engine_event(session_factory, simulation_id: str) -> dict:
    """엔진 경로(persist_event_batch)로 tick=1 Event 1건 + 그 Event 를 참조하는 기억 1건을 남긴다."""
    from app.domain.event_persistence import EventBatch
    from app.domain.models import Agent, AgentState
    from app.services.event_persistence import persist_event_batch
    from app.services.fixtures import seed_slice_zero

    event_id = uuid4()
    with session_factory() as session:
        seed_slice_zero(session, UUID(simulation_id))
        state = session.scalar(
            select(AgentState)
            .join(Agent, Agent.id == AgentState.agent_id)
            .where(AgentState.simulation_id == UUID(simulation_id), Agent.fixture_key == "student-01")
        )
        batch = EventBatch.model_validate(
            dict(
                simulation_id=UUID(simulation_id),
                run_id="detail-run",
                tick_number=1,
                policy_version="detail-policy",
                resolver_version="detail-resolver",
                resolution_id="detail-resolution",
                events=[
                    dict(
                        id=event_id,
                        event_type="GROUP_PROJECT",
                        title="조별 과제",
                        description="도서관에서 조별 과제를 했다.",
                        participant_agent_ids=[state.agent_id],
                        location_id=state.location_id,
                        source="event_master",
                        impact_level="medium",
                        importance=50,
                    )
                ],
                resolved_effects=[
                    dict(
                        source_agent_id=state.agent_id,
                        metric="stress",
                        before=state.stress,
                        requested_total=1,
                        applied_delta=1,
                        after=state.stress + 1,
                        effect_ids=["e1"],
                    )
                ],
                memories=[
                    dict(
                        agent_id=state.agent_id,
                        event_id=event_id,
                        content="조별 과제가 힘들었다.",
                        memory_type="observation",
                        importance=40,
                        occurred_at=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
                    )
                ],
            )
        )
        result = persist_event_batch(session, batch)
        session.commit()
        return result


def test_event_detail_returns_manual_event(client) -> None:
    test_client, _ = client
    headers = register_and_login(test_client, "detail-manual")
    simulation_id = create_simulation(test_client, headers, "manual")

    created = post_event(test_client, headers, simulation_id, "수동 사건")

    response = test_client.get(
        f"/v1/simulations/{simulation_id}/events/{created['id']}", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == created["id"]
    assert body["simulation_id"] == simulation_id
    assert body["event_type"] == "class"
    assert body["title"] == "수동 사건"
    assert body["status"] == "scheduled"
    assert body["simulation_day"] == 1
    # 수동 생성 Event 에는 엔진 metadata 가 없다.
    assert body["tick"] is None
    assert body["importance"] is None
    assert body["impact_level"] is None
    assert body["source"] is None
    assert body["event_subtype"] is None
    assert body["target_agent_ids"] == []
    assert body["related_memories"] == []


def test_event_detail_is_scoped_to_its_simulation(client) -> None:
    test_client, _ = client
    headers = register_and_login(test_client, "detail-scope")
    simulation_a = create_simulation(test_client, headers, "sim-a")
    simulation_b = create_simulation(test_client, headers, "sim-b")

    event_b = post_event(test_client, headers, simulation_b, "B 사건")

    # 다른 simulation 의 event_id 로는 조회할 수 없다.
    response = test_client.get(
        f"/v1/simulations/{simulation_a}/events/{event_b['id']}", headers=headers
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Event not found"

    # 올바른 simulation 으로는 조회된다.
    ok = test_client.get(
        f"/v1/simulations/{simulation_b}/events/{event_b['id']}", headers=headers
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["id"] == event_b["id"]


def test_event_detail_unknown_event_returns_404(client) -> None:
    test_client, _ = client
    headers = register_and_login(test_client, "detail-missing")
    simulation_id = create_simulation(test_client, headers, "missing")

    response = test_client.get(
        f"/v1/simulations/{simulation_id}/events/{uuid4()}", headers=headers
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Event not found"


def test_event_detail_unknown_simulation_returns_404(client) -> None:
    test_client, _ = client
    headers = register_and_login(test_client, "detail-nosim")

    response = test_client.get(
        f"/v1/simulations/{uuid4()}/events/{uuid4()}", headers=headers
    )
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Simulation not found"


def test_event_detail_exposes_engine_fields_and_related_memories(client) -> None:
    test_client, session_factory = client
    headers = register_and_login(test_client, "detail-engine")
    simulation_id = create_simulation(test_client, headers, "engine")

    result = persist_engine_event(session_factory, simulation_id)
    expected_event = result["events"][0]
    expected_memory = result["memories"][0]

    response = test_client.get(
        f"/v1/simulations/{simulation_id}/events/{expected_event['id']}", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == expected_event["id"]
    assert body["event_type"] == "group_project"
    assert body["description"] == "도서관에서 조별 과제를 했다."
    assert body["tick"] == 1
    assert body["importance"] == 50
    assert body["impact_level"] == "medium"
    assert body["source"] == "event_master"
    assert body["event_subtype"] is None
    participant_ids = list(expected_event["participant_agent_ids"])
    assert body["target_agent_ids"] == participant_ids

    assert len(body["related_memories"]) == 1
    memory = body["related_memories"][0]
    assert memory["id"] == expected_memory["id"]
    assert memory["content"] == "조별 과제가 힘들었다."
    assert memory["memory_type"] == "observation"
    assert memory["importance"] == 40
    assert memory["created_tick"] == 1
    assert memory["agent_id"] == participant_ids[0]


def test_event_detail_enforces_ownership(client) -> None:
    test_client, _ = client
    owner_headers = register_and_login(test_client, "detail-owner")
    other_headers = register_and_login(test_client, "detail-intruder")
    simulation_id = create_simulation(test_client, owner_headers, "owned")
    created = post_event(test_client, owner_headers, simulation_id, "사건")

    response = test_client.get(
        f"/v1/simulations/{simulation_id}/events/{created['id']}", headers=other_headers
    )
    assert response.status_code == 403, response.text


def test_events_list_and_latest_endpoints_still_work(client) -> None:
    test_client, _ = client
    headers = register_and_login(test_client, "detail-regression")
    simulation_id = create_simulation(test_client, headers, "regression")

    first = post_event(test_client, headers, simulation_id, "사건 1")
    second = post_event(test_client, headers, simulation_id, "사건 2")

    listed = test_client.get(f"/v1/simulations/{simulation_id}/events", headers=headers)
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [first["id"], second["id"]]

    latest = test_client.get(
        f"/v1/simulations/{simulation_id}/events/latest", headers=headers
    )
    assert latest.status_code == 200, latest.text
    assert latest.json()["id"] == second["id"]
