import os
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")


@pytest.fixture()
def client(monkeypatch):
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


def register_and_login(client: TestClient, username: str) -> tuple[dict, dict[str, str]]:
    password = "Slice0-password!"
    register = client.post(
        "/v1/auth/register",
        json={"username": username, "display_name": username, "password": password},
    )
    assert register.status_code == 201
    login = client.post("/v1/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200
    return register.json(), {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_missing_and_forged_tokens_return_401(client) -> None:
    test_client, _ = client
    simulation_id = uuid4()
    missing = test_client.get(f"/v1/simulations/{simulation_id}")
    forged = test_client.get(
        f"/v1/simulations/{simulation_id}",
        headers={"Authorization": "Bearer forged.token.value"},
    )
    assert missing.status_code == 401
    assert forged.status_code == 401
    assert missing.headers["www-authenticate"] == "Bearer"


def test_expired_token_returns_401_and_missing_user_role_returns_403(client) -> None:
    from app.core.security import create_access_token
    from app.domain.models import User

    test_client, session_factory = client
    registered, headers = register_and_login(test_client, "claims-user")
    with session_factory() as db:
        user = db.get(User, UUID(registered["id"]))
        expired = create_access_token(user, datetime.now(UTC) - timedelta(days=1))
        user.roles = []
        db.commit()
    expired_response = test_client.get(
        f"/v1/simulations/{uuid4()}", headers={"Authorization": f"Bearer {expired}"}
    )
    role_response = test_client.get(f"/v1/simulations/{uuid4()}", headers=headers)
    assert expired_response.status_code == 401
    assert role_response.status_code == 403


@pytest.mark.parametrize("claim,value", [("iss", "wrong-issuer"), ("aud", "wrong-audience")])
def test_invalid_issuer_or_audience_returns_401(client, claim, value) -> None:
    from app.core.config import get_settings

    test_client, _ = client
    registered, _ = register_and_login(test_client, f"invalid-{claim}")
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": registered["id"], "roles": ["USER"], "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience, "iat": now, "exp": now + timedelta(minutes=5), "jti": str(uuid4()),
    }
    claims[claim] = value
    token = jwt.encode(claims, settings.jwt_secret, algorithm="HS256")
    response = test_client.get(
        f"/v1/simulations/{uuid4()}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


def test_registration_login_creation_and_idempotent_seed(client) -> None:
    from app.domain.models import (
        Agent,
        AgentState,
        Event,
        EventParticipant,
        Location,
        ProfessorProfile,
        StudentProfile,
    )
    from app.services.fixtures import AGENT_FIXTURES, seed_slice_zero

    test_client, session_factory = client
    user, headers = register_and_login(test_client, "owner-a")
    created = test_client.post("/v1/simulations", headers=headers, json={"name": "Slice 0"})
    assert created.status_code == 201
    assert created.json()["owner_id"] == user["id"]
    simulation_id = created.json()["id"]

    agents_response = test_client.get(f"/v1/simulations/{simulation_id}/agents", headers=headers)
    assert agents_response.status_code == 200
    agents = agents_response.json()
    assert len(agents) == 6
    assert sum(agent["agent_type"] == "student" for agent in agents) == 5
    assert sum(agent["agent_type"] == "professor" for agent in agents) == 1
    assert [agent["fixture_key"] for agent in agents] == sorted(agent["fixture_key"] for agent in agents)
    assert all(UUID(agent["id"]).version == 7 for agent in agents)
    fixtures_by_key = {fixture.key: fixture for fixture in AGENT_FIXTURES}
    for response_agent in agents:
        fixture = fixtures_by_key[response_agent["fixture_key"]]
        assert response_agent["fixture_version"] == fixture.version
        assert response_agent["name"] == fixture.name
        assert response_agent["agent_type"] == fixture.agent_type
        assert response_agent["mbti_type"] == fixture.mbti_type
        assert response_agent["profile"] == {
            "openness": fixture.openness,
            "conscientiousness": fixture.conscientiousness,
            "extraversion": fixture.extraversion,
            "agreeableness": fixture.agreeableness,
            "emotional_stability": fixture.emotional_stability,
        }
        assert response_agent["state"] == {
            "hunger": fixture.hunger,
            "fatigue": fixture.fatigue,
            "stress": fixture.stress,
            "satisfaction": fixture.satisfaction,
            "mood": fixture.mood,
            "current_action": None,
        }
        assert response_agent["location"]["code"] == fixture.location_code
        if fixture.agent_type == "student":
            assert response_agent["student_profile"] == {
                "grade": fixture.grade,
                "interest_field": fixture.interest_field,
            }
            assert response_agent["professor_profile"] is None
        else:
            assert response_agent["student_profile"] is None
            assert response_agent["professor_profile"] == {
                "academic_rank": fixture.academic_rank,
                "specialty": fixture.specialty,
            }

    with session_factory() as db:
        seed_slice_zero(db, UUID(simulation_id))
        db.commit()
        assert db.scalar(select(func.count()).select_from(Agent)) == 6
        assert db.scalar(select(func.count()).select_from(AgentState)) == 6
        assert db.scalar(select(func.count()).select_from(Location)) == 2
        assert db.scalar(select(func.count()).select_from(StudentProfile)) == 5
        assert db.scalar(select(func.count()).select_from(ProfessorProfile)) == 1
        assert db.scalar(select(func.count()).select_from(Event)) == 1
        assert db.scalar(select(func.count()).select_from(EventParticipant)) == 2
        for stored_agent in db.scalars(select(Agent)).all():
            fixture = fixtures_by_key[stored_agent.fixture_key]
            assert (
                stored_agent.openness,
                stored_agent.conscientiousness,
                stored_agent.extraversion,
                stored_agent.agreeableness,
                stored_agent.emotional_stability,
            ) == (
                fixture.openness,
                fixture.conscientiousness,
                fixture.extraversion,
                fixture.agreeableness,
                fixture.emotional_stability,
            )
            stored_state = db.scalar(
                select(AgentState).where(AgentState.agent_id == stored_agent.id)
            )
            assert (
                stored_state.hunger,
                stored_state.fatigue,
                stored_state.stress,
                stored_state.satisfaction,
                stored_state.mood,
                stored_state.current_action,
            ) == (
                fixture.hunger,
                fixture.fatigue,
                fixture.stress,
                fixture.satisfaction,
                fixture.mood,
                None,
            )
            stored_location = db.get(Location, stored_state.location_id)
            assert stored_location.code == fixture.location_code
            if fixture.agent_type == "student":
                stored_profile = db.get(StudentProfile, stored_agent.id)
                assert (stored_profile.grade, stored_profile.interest_field) == (
                    fixture.grade,
                    fixture.interest_field,
                )
            else:
                stored_profile = db.get(ProfessorProfile, stored_agent.id)
                assert (stored_profile.academic_rank, stored_profile.specialty) == (
                    fixture.academic_rank,
                    fixture.specialty,
                )


def test_owner_gets_200_other_user_gets_403_and_missing_gets_404(client) -> None:
    test_client, _ = client
    _, owner_headers = register_and_login(test_client, "owner-a")
    _, other_headers = register_and_login(test_client, "owner-b")
    created = test_client.post("/v1/simulations", headers=owner_headers, json={"name": "Owned"})
    simulation_id = created.json()["id"]
    assert test_client.get(f"/v1/simulations/{simulation_id}", headers=owner_headers).status_code == 200
    assert test_client.get(f"/v1/simulations/{simulation_id}", headers=other_headers).status_code == 403
    assert test_client.get(f"/v1/simulations/{uuid4()}", headers=owner_headers).status_code == 404
    assert test_client.get(f"/v1/simulations/{simulation_id}/agents", headers=other_headers).status_code == 403


def test_duplicate_username_returns_409_and_bad_password_returns_401(client) -> None:
    test_client, _ = client
    register_and_login(test_client, "duplicate")
    duplicate = test_client.post(
        "/v1/auth/register",
        json={"username": "duplicate", "display_name": "Again", "password": "Slice0-password!"},
    )
    bad_login = test_client.post(
        "/v1/auth/login", json={"username": "duplicate", "password": "wrong-password"}
    )
    assert duplicate.status_code == 409
    assert bad_login.status_code == 401


def test_fixture_failure_rolls_back_entire_simulation(client, monkeypatch) -> None:
    from app.domain.models import Agent, AgentState, Location, Simulation

    test_client, session_factory = client
    _, headers = register_and_login(test_client, "rollback-owner")

    def fail_seed(*_args, **_kwargs):
        raise RuntimeError("fixture failure")

    monkeypatch.setattr("app.services.simulations.seed_slice_zero", fail_seed)
    response = test_client.post("/v1/simulations", headers=headers, json={"name": "Rollback"})
    assert response.status_code == 500
    with session_factory() as db:
        for model in (Simulation, Location, Agent, AgentState):
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_agent_state_rejects_location_from_another_simulation(client) -> None:
    from app.domain.models import AgentState, Location

    test_client, session_factory = client
    _, headers = register_and_login(test_client, "boundary-owner")
    first = test_client.post("/v1/simulations", headers=headers, json={"name": "First"}).json()
    second = test_client.post("/v1/simulations", headers=headers, json={"name": "Second"}).json()
    with session_factory() as db:
        first_location = db.scalar(select(Location).where(Location.simulation_id == UUID(first["id"])))
        second_state = db.scalar(select(AgentState).where(AgentState.simulation_id == UUID(second["id"])))
        second_state.location_id = first_location.id
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
