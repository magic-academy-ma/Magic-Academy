"""GET /v1/simulations/{simulation_id}/dialogues/{dialogue_id} — Dialogue Persistence.

기존 events/logs API 테스트 스타일(TEST_DATABASE_URL 필요, TestClient + register/login)을
따른다. Dialogue 는 DatabaseDialogueSink 로 미리 영속화한다.
"""

import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.domain.models import Agent
from app.services.database_dialogue_results import DatabaseDialogueSink
from app.services.fixtures import seed_slice_zero
from app.simulation.agent_runtime import AgentRuntimeResult
from app.simulation.intent_conflict import resolve_talk_conflicts

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")

RUN_ID = "dlg-api-run"
TICK = 6


@pytest.fixture()
def client():
    from app.core.database import get_db
    from app.main import app

    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE users, simulations, locations, agents, agent_states, "
                "dialogues, dialogue_messages RESTART IDENTITY CASCADE"
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
    password = "Dialogue-password!"
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


def _talk(agent_id: UUID, target_id: UUID, utterance: str | None) -> AgentRuntimeResult:
    return AgentRuntimeResult.model_validate(
        {
            "run_id": RUN_ID,
            "tick_number": TICK,
            "agent_id": agent_id,
            "status": "PROPOSED",
            "intent": {
                "action_type": "TALK",
                "target_agent_id": target_id,
                "target_location_id": None,
                "related_event_id": None,
                "utterance": utterance,
                "motivation_summary": "대화",
                "reaction": {
                    "valence": "NEUTRAL",
                    "relationship_signals": [],
                    "state_signals": [],
                },
                "decision_explanation": {
                    "alternatives": [
                        {
                            "action_type": "TALK",
                            "description": "대화한다.",
                            "relative_priority": "HIGH",
                            "selected": True,
                        }
                    ],
                    "influencing_factors": [],
                },
                "memory_candidates": [],
            },
            "retry_count": 0,
            "failure_reason": None,
            "model": "test",
            "prompt_version": "test",
            "idempotency_key": f"{RUN_ID}:{TICK}:{agent_id}",
        }
    )


def seed_dialogue(session_factory, simulation_id: str) -> tuple[str, list[str]]:
    with session_factory() as session:
        seed_slice_zero(session, UUID(simulation_id))
        agent_ids = list(
            session.scalars(
                select(Agent.id)
                .where(Agent.simulation_id == UUID(simulation_id))
                .order_by(Agent.fixture_key)
            )
        )
        speaker, listener = agent_ids[0], agent_ids[1]
        resolution = resolve_talk_conflicts(
            (_talk(speaker, listener, "룬 파동이 불안정해."), _talk(listener, speaker, "나도 봤어."))
        )
        DatabaseDialogueSink(session).save_batch(resolution)
        session.flush()
        from app.domain.models import Dialogue

        dialogue_id = session.scalar(
            select(Dialogue.id).where(Dialogue.simulation_id == UUID(simulation_id))
        )
        session.commit()
    return str(dialogue_id), [str(speaker), str(listener)]


def test_get_dialogue_returns_participants_and_ordered_messages(client) -> None:
    test_client, session_factory = client
    headers = register_and_login(test_client, "dlg-owner")
    simulation_id = create_simulation(test_client, headers, "sim")
    dialogue_id, (speaker, listener) = seed_dialogue(session_factory, simulation_id)

    response = test_client.get(
        f"/v1/simulations/{simulation_id}/dialogues/{dialogue_id}", headers=headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dialogue_id"] == dialogue_id
    assert body["simulation_id"] == simulation_id
    assert body["tick"] == TICK
    assert set(body["participants"]) == {speaker, listener}
    assert body["messages"] == [
        {"speaker": speaker, "utterance": "룬 파동이 불안정해.", "order": 0},
        {"speaker": listener, "utterance": "나도 봤어.", "order": 1},
    ]


def test_dialogue_cannot_be_read_through_another_simulation(client) -> None:
    test_client, session_factory = client
    headers = register_and_login(test_client, "dlg-scope")
    simulation_a = create_simulation(test_client, headers, "sim-a")
    simulation_b = create_simulation(test_client, headers, "sim-b")
    dialogue_id, _ = seed_dialogue(session_factory, simulation_b)

    response = test_client.get(
        f"/v1/simulations/{simulation_a}/dialogues/{dialogue_id}", headers=headers
    )

    assert response.status_code == 404, response.text


def test_missing_dialogue_returns_404(client) -> None:
    test_client, _ = client
    headers = register_and_login(test_client, "dlg-missing")
    simulation_id = create_simulation(test_client, headers, "sim")

    response = test_client.get(
        f"/v1/simulations/{simulation_id}/dialogues/{uuid4()}", headers=headers
    )

    assert response.status_code == 404, response.text


def test_dialogue_enforces_ownership(client) -> None:
    test_client, session_factory = client
    owner_headers = register_and_login(test_client, "dlg-real-owner")
    intruder_headers = register_and_login(test_client, "dlg-intruder")
    simulation_id = create_simulation(test_client, owner_headers, "owned")
    dialogue_id, _ = seed_dialogue(session_factory, simulation_id)

    response = test_client.get(
        f"/v1/simulations/{simulation_id}/dialogues/{dialogue_id}", headers=intruder_headers
    )

    assert response.status_code == 403, response.text
