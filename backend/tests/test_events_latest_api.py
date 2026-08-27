"""GET /v1/simulations/{simulation_id}/events/latest — Issue #182-5.

기존 events API 테스트 스타일(TEST_DATABASE_URL 필요, TestClient + register/login)을
따른다. 엔진이 남긴 tick/importance/참여 Agent 는 persist_event_batch 로 만든다.
"""

import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

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
    password = "Latest-password!"
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
    """엔진 경로(persist_event_batch)로 tick=1 Event 1건을 남긴다."""
    from app.domain.event_persistence import EventBatch
    from app.domain.models import Agent, AgentState
    from app.services.event_persistence import persist_event_batch
    from app.services.fixtures import seed_slice_zero

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
                run_id="latest-run",
                tick_number=1,
                policy_version="latest-policy",
                resolver_version="latest-resolver",
                resolution_id="latest-resolution",
                events=[
                    dict(
                        id=uuid4(),
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
            )
        )
        result = persist_event_batch(session, batch)
        session.commit()
        return result


def test_latest_event_returns_most_recent_ordering(client) -> None:
    test_client, _ = client
    headers = register_and_login(test_client, "latest-order")
    simulation_id = create_simulation(test_client, headers, "order")

    post_event(test_client, headers, simulation_id, "첫 사건")
    post_event(test_client, headers, simulation_id, "둘째 사건")
    newest = post_event(test_client, headers, simulation_id, "가장 최근 사건")

    response = test_client.get(
        f"/v1/simulations/{simulation_id}/events/latest", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == newest["id"]
    assert body["title"] == "가장 최근 사건"
    # 수동 생성 Event 에는 엔진 metadata 가 없다.
    assert body["tick"] is None
    assert body["importance"] is None
    assert body["target_agent_ids"] == []


def test_latest_event_is_scoped_to_its_simulation(client) -> None:
    test_client, _ = client
    headers = register_and_login(test_client, "latest-scope")
    simulation_a = create_simulation(test_client, headers, "sim-a")
    simulation_b = create_simulation(test_client, headers, "sim-b")

    event_a = post_event(test_client, headers, simulation_a, "A 사건")
    event_b = post_event(test_client, headers, simulation_b, "B 사건")

    latest_a = test_client.get(
        f"/v1/simulations/{simulation_a}/events/latest", headers=headers
    ).json()
    latest_b = test_client.get(
        f"/v1/simulations/{simulation_b}/events/latest", headers=headers
    ).json()

    assert latest_a["id"] == event_a["id"]
    assert latest_a["simulation_id"] == simulation_a
    assert latest_b["id"] == event_b["id"]
    assert latest_b["simulation_id"] == simulation_b


def test_latest_event_absent_returns_404(client) -> None:
    test_client, _ = client
    headers = register_and_login(test_client, "latest-empty")
    simulation_id = create_simulation(test_client, headers, "empty")

    response = test_client.get(
        f"/v1/simulations/{simulation_id}/events/latest", headers=headers
    )
    assert response.status_code == 404, response.text


def test_latest_event_exposes_engine_tick_importance_and_agents(client) -> None:
    test_client, session_factory = client
    headers = register_and_login(test_client, "latest-engine")
    simulation_id = create_simulation(test_client, headers, "engine")

    result = persist_engine_event(session_factory, simulation_id)
    expected_event = result["events"][0]

    response = test_client.get(
        f"/v1/simulations/{simulation_id}/events/latest", headers=headers
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == expected_event["id"]
    assert body["event_type"] == "group_project"
    assert body["tick"] == 1
    assert body["importance"] == 50
    assert body["target_agent_ids"] == list(expected_event["participant_agent_ids"])
    assert body["description"] == "도서관에서 조별 과제를 했다."


def test_latest_event_enforces_ownership(client) -> None:
    test_client, _ = client
    owner_headers = register_and_login(test_client, "latest-owner")
    other_headers = register_and_login(test_client, "latest-intruder")
    simulation_id = create_simulation(test_client, owner_headers, "owned")
    post_event(test_client, owner_headers, simulation_id, "사건")

    response = test_client.get(
        f"/v1/simulations/{simulation_id}/events/latest", headers=other_headers
    )
    assert response.status_code == 403, response.text


def test_events_list_endpoint_still_returns_all(client) -> None:
    test_client, _ = client
    headers = register_and_login(test_client, "latest-regression")
    simulation_id = create_simulation(test_client, headers, "regression")

    first = post_event(test_client, headers, simulation_id, "사건 1")
    second = post_event(test_client, headers, simulation_id, "사건 2")

    listed = test_client.get(
        f"/v1/simulations/{simulation_id}/events", headers=headers
    )
    assert listed.status_code == 200, listed.text
    ids = [item["id"] for item in listed.json()]
    assert ids == [first["id"], second["id"]]
