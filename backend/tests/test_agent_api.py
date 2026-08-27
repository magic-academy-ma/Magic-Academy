import os
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from uuid6 import uuid7

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")


@pytest.fixture()
def client():
    from app.core.database import get_db
    from app.main import app

    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE users, simulations, locations, agents, agent_states RESTART IDENTITY CASCADE"))

    def override_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client, session_factory
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, username: str) -> dict[str, str]:
    password = "Slice23-password!"
    assert client.post(
        "/v1/auth/register",
        json={"username": username, "display_name": username, "password": password},
    ).status_code == 201
    login = client.post("/v1/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_simulation(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post("/v1/simulations", headers=headers, json={"name": "Slice 2-3"})
    assert response.status_code == 201
    return response.json()


def test_agent_detail_state_and_query_validation(client):
    test_client, _ = client
    headers = register_and_login(test_client, "agent-api-owner")
    simulation = create_simulation(test_client, headers)
    agents = test_client.get(f"/v1/simulations/{simulation['id']}/agents", headers=headers).json()
    # 에이전트 목록은 fixture_key 오름차순 정렬이라 agents[0]는 professor-01이다.
    # MVP 단일 전공(마법공학과)에는 학생만 소속되므로 student-01을 명시적으로 고른다.
    student = next(agent for agent in agents if agent["fixture_key"] == "student-01")
    agent_id = student["id"]

    detail = test_client.get(f"/v1/agents/{agent_id}", headers=headers)
    state = test_client.get(f"/v1/agents/{agent_id}/state", headers=headers)
    invalid_limit = test_client.get(f"/v1/agents/{agent_id}/memories?limit=11", headers=headers)

    assert detail.status_code == 200
    assert detail.json()["id"] == agent_id
    # student-01은 MVP 단일 전공(마법공학과)에 소속된다.
    majors = [
        org
        for org in detail.json()["organizations"]
        if org["organization_type"] == "major"
    ]
    assert [org["name"] for org in majors] == ["마법공학과"]
    assert state.status_code == 200
    assert state.json()["current_location"]["id"] == student["location"]["id"]
    assert invalid_limit.status_code == 422


def test_memory_relationship_and_decision_explanation(client):
    from app.domain.models import AgentMemory, Relationship, RuntimeResult

    test_client, session_factory = client
    headers = register_and_login(test_client, "inspector-owner")
    simulation = create_simulation(test_client, headers)
    agents = test_client.get(f"/v1/simulations/{simulation['id']}/agents", headers=headers).json()
    source_id, target_id = UUID(agents[0]["id"]), UUID(agents[1]["id"])
    with session_factory() as db:
        db.add(AgentMemory(
            id=uuid7(), agent_id=source_id, event_id=None, content="기억",
            memory_type="observation", importance=50, created_tick=1,
            occurred_at=datetime.now(UTC), embedding=None,
        ))
        db.add(Relationship(
            id=uuid7(), simulation_id=UUID(simulation["id"]), source_agent_id=source_id,
            target_agent_id=target_id, trust=3,
        ))
        db.add(RuntimeResult(
            id=uuid7(), run_id="api-test", tick_number=1, agent_id=source_id,
            status="PROPOSED", action_type="STUDY",
            intent={
                "decision_explanation": {
                    "alternatives": [
                        {
                            "action_type": "STUDY",
                            "description": "공부한다.",
                            "relative_priority": "HIGH",
                            "selected": True,
                            "reasoning": "must not be exposed",
                        }
                    ],
                    "influencing_factors": [],
                    "chain_of_thought": "must not be exposed",
                },
                "hidden_prompt": "must not be exposed",
                "reasoning": "must not be exposed",
            },
            retry_count=0, failure_reason=None, model="mock", prompt_version="test",
            idempotency_key=f"api-test:1:{source_id}", result_fingerprint="0" * 64,
        ))
        db.commit()

    memories = test_client.get(f"/v1/agents/{source_id}/memories", headers=headers)
    relationships = test_client.get(f"/v1/agents/{source_id}/relationships", headers=headers)
    explanation = test_client.get(f"/v1/agents/{source_id}/decision-explanation?tick=1", headers=headers)
    assert memories.status_code == 200 and memories.json()[0]["content"] == "기억"
    assert relationships.status_code == 200 and relationships.json()[0]["trust"] == 3
    assert explanation.status_code == 200
    assert explanation.json()["alternatives"] == [
        {
            "action_type": "STUDY",
            "description": "공부한다.",
            "relative_priority": "HIGH",
            "selected": True,
        }
    ]
    serialized = explanation.text
    for forbidden in ("chain_of_thought", "hidden_prompt", "reasoning"):
        assert forbidden not in serialized


def test_other_owner_cannot_access_agent(client):
    test_client, _ = client
    owner_headers = register_and_login(test_client, "agent-owner")
    other_headers = register_and_login(test_client, "agent-other")
    simulation = create_simulation(test_client, owner_headers)
    agent_id = test_client.get(
        f"/v1/simulations/{simulation['id']}/agents", headers=owner_headers
    ).json()[0]["id"]
    paths = (
        f"/v1/agents/{agent_id}",
        f"/v1/agents/{agent_id}/state",
        f"/v1/agents/{agent_id}/relationships",
        f"/v1/agents/{agent_id}/memories",
        f"/v1/agents/{agent_id}/decision-explanation?tick=1",
    )
    for path in paths:
        assert test_client.get(path, headers=other_headers).status_code == 403

    missing_id = uuid7()
    missing_paths = (
        f"/v1/agents/{missing_id}",
        f"/v1/agents/{missing_id}/state",
        f"/v1/agents/{missing_id}/relationships",
        f"/v1/agents/{missing_id}/memories",
        f"/v1/agents/{missing_id}/decision-explanation?tick=1",
    )
    for path in missing_paths:
        assert test_client.get(path, headers=owner_headers).status_code == 404


@pytest.mark.parametrize(
    "path",
    (
        "/memories?limit=0",
        "/memories?limit=11",
        "/decision-explanation?tick=-1",
        "/decision-explanation",
    ),
)
def test_agent_query_validation(client, path):
    test_client, _ = client
    headers = register_and_login(test_client, f"query-{abs(hash(path))}")
    simulation = create_simulation(test_client, headers)
    agent_id = test_client.get(
        f"/v1/simulations/{simulation['id']}/agents", headers=headers
    ).json()[0]["id"]

    assert test_client.get(f"/v1/agents/{agent_id}{path}", headers=headers).status_code == 422
