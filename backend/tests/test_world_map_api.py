"""GET /v1/simulations/{simulation_id}/world/map — API 명세 §10.1.

기존 simulation logs API 테스트 스타일(TEST_DATABASE_URL 필요, TestClient +
register/login)을 따른다. 맵의 소스는 시뮬레이션 시드가 만든 공간·Agent·AgentState
뿐이므로 별도 준비 없이 create_simulation 만으로 검증한다.
"""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
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
        yield test_client
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, username: str) -> dict[str, str]:
    password = "World-password!"
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


def agent_id_by_fixture_key(
    client: TestClient, headers: dict[str, str], simulation_id: str
) -> dict[str, str]:
    response = client.get(
        f"/v1/simulations/{simulation_id}/agents", headers=headers
    )
    assert response.status_code == 200, response.text
    return {agent["fixture_key"]: agent["id"] for agent in response.json()}


def test_world_map_lists_every_location_with_its_agents(client) -> None:
    headers = register_and_login(client, "world-map")
    simulation_id = create_simulation(client, headers, "world")
    ids = agent_id_by_fixture_key(client, headers, simulation_id)

    response = client.get(f"/v1/simulations/{simulation_id}/world/map", headers=headers)
    assert response.status_code == 200, response.text

    locations = response.json()["data"]["locations"]
    by_id = {location["id"]: location for location in locations}

    # 시드된 공간 6종이 code 오름차순으로 전부 포함된다.
    assert [location["id"] for location in locations] == [
        "central_square",
        "classroom",
        "dormitory",
        "lab",
        "library",
        "restaurant",
    ]
    assert by_id["dormitory"]["name"] == "기숙사"

    # student fixture 5명은 dormitory, professor 1명은 classroom 에서 시작한다.
    # agents[] 는 Agent UUID 이며, fixture_key 오름차순 순서를 유지한다.
    assert by_id["dormitory"]["agents"] == [
        ids["student-01"],
        ids["student-02"],
        ids["student-03"],
        ids["student-04"],
        ids["student-05"],
    ]
    assert by_id["classroom"]["agents"] == [ids["professor-01"]]

    # Agent 가 없는 공간도 빈 배열로 포함한다.
    assert by_id["library"]["agents"] == []
    assert by_id["restaurant"]["agents"] == []


def test_world_map_is_scoped_to_its_simulation(client) -> None:
    headers = register_and_login(client, "world-scope")
    simulation_a = create_simulation(client, headers, "sim-a")
    simulation_b = create_simulation(client, headers, "sim-b")

    map_a = client.get(
        f"/v1/simulations/{simulation_a}/world/map", headers=headers
    ).json()["data"]["locations"]
    map_b = client.get(
        f"/v1/simulations/{simulation_b}/world/map", headers=headers
    ).json()["data"]["locations"]

    # 두 맵의 공간 구성(id·name·Agent 수)은 같지만, Agent UUID 는 시뮬레이션마다
    # 새로 시드되므로 서로 겹치지 않는다.
    assert [(loc["id"], loc["name"], len(loc["agents"])) for loc in map_a] == [
        (loc["id"], loc["name"], len(loc["agents"])) for loc in map_b
    ]
    dormitory_a = next(loc for loc in map_a if loc["id"] == "dormitory")
    dormitory_b = next(loc for loc in map_b if loc["id"] == "dormitory")
    assert len(dormitory_a["agents"]) == 5
    assert set(dormitory_a["agents"]).isdisjoint(dormitory_b["agents"])


def test_world_map_enforces_ownership(client) -> None:
    owner_headers = register_and_login(client, "world-owner")
    other_headers = register_and_login(client, "world-intruder")
    simulation_id = create_simulation(client, owner_headers, "owned")

    response = client.get(
        f"/v1/simulations/{simulation_id}/world/map", headers=other_headers
    )
    assert response.status_code == 403, response.text


def test_world_map_missing_simulation_returns_404(client) -> None:
    headers = register_and_login(client, "world-missing")

    response = client.get(
        f"/v1/simulations/{uuid4()}/world/map", headers=headers
    )
    assert response.status_code == 404, response.text
