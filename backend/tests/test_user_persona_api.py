import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required"
)


@pytest.fixture()
def client():
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
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def register_login_create(client: TestClient):
    credentials = {
        "username": "slice4-api-owner",
        "display_name": "Slice 4 API",
        "password": "Slice4-password!",
    }
    assert client.post("/v1/auth/register", json=credentials).status_code == 201
    login = client.post(
        "/v1/auth/login",
        json={"username": credentials["username"], "password": credentials["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    simulation = client.post(
        "/v1/simulations", headers=headers, json={"name": "Slice 4 API"}
    ).json()
    agents = client.get(
        f"/v1/simulations/{simulation['id']}/agents", headers=headers
    ).json()
    student = next(agent for agent in agents if agent["fixture_key"] == "student-03")
    return simulation["id"], student["id"], headers


def valid_payload(student_id: str) -> dict:
    return {
        "agent_id": student_id,
        "mbti_type": "INFP",
        "personality_rule_version": "mbti-big-five-v0.1",
        "openness": 25,
        "conscientiousness": -25,
        "extraversion": -25,
        "agreeableness": 20,
        "emotional_stability": 0,
    }


def test_config_and_persona_api_contract(client) -> None:
    simulation_id, student_id, headers = register_login_create(client)
    config = client.get(
        f"/v1/simulations/{simulation_id}/user-persona/config", headers=headers
    )
    assert config.status_code == 200
    assert config.json()["data"]["rule_version"] == "mbti-big-five-v0.1"
    assert config.json()["data"]["step"] == 5
    assert set(config.json()["data"]["mbti_rules"]) == {
        "ISTJ", "ESTP", "INFP", "ENTJ", "ESFJ"
    }

    missing = client.get(
        f"/v1/simulations/{simulation_id}/user-persona", headers=headers
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "RESOURCE_NOT_FOUND"

    saved = client.post(
        f"/v1/simulations/{simulation_id}/user-persona",
        headers=headers,
        json=valid_payload(student_id),
    )
    assert saved.status_code == 200
    assert saved.json()["data"] == {
        "agent_id": student_id,
        "simulation_id": simulation_id,
        "agent_type": "USER_PERSONA",
        "mbti_type": "INFP",
        "openness": 25,
        "conscientiousness": -25,
        "extraversion": -25,
        "agreeableness": 20,
        "emotional_stability": 0,
        "personality_rule_version": "mbti-big-five-v0.1",
        "status": "APPLIED",
        "locked": False,
        "persona_locked_at": None,
    }

    started = client.post(
        f"/v1/simulations/{simulation_id}/start", headers=headers, json={}
    )
    assert started.status_code == 200
    assert started.json()["data"]["status"] == "running"

    locked = client.post(
        f"/v1/simulations/{simulation_id}/user-persona",
        headers=headers,
        json=valid_payload(student_id),
    )
    assert locked.status_code == 409
    assert locked.json()["code"] == "CONFLICT"


def test_persona_domain_error_is_400_and_shape_error_is_422(client) -> None:
    simulation_id, student_id, headers = register_login_create(client)
    invalid = valid_payload(student_id)
    invalid["extraversion"] = 10
    domain_error = client.post(
        f"/v1/simulations/{simulation_id}/user-persona",
        headers=headers,
        json=invalid,
    )
    shape_error = client.post(
        f"/v1/simulations/{simulation_id}/user-persona",
        headers=headers,
        json={"agent_id": student_id},
    )
    assert domain_error.status_code == 400
    assert domain_error.json()["code"] == "INVALID_PERSONALITY_CONFIGURATION"
    assert shape_error.status_code == 422
