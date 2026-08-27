"""GET /v1/simulations/{simulation_id}/logs — Issue #182-7.

기존 events API 테스트 스타일(TEST_DATABASE_URL 필요, TestClient + register/login)을
따른다. 통합 로그의 소스는 이미 영속화된 데이터뿐이다:
  - events 테이블 (엔진 Event + 수동 Event)
  - agent_memories 테이블 중 memory_type == 'conversation'
엔진이 남긴 tick/importance/source/참여 Agent/대화 기억은 persist_event_batch 로 만든다.
"""

import os
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select, text
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
    password = "Logs-password!"
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


def get_logs(client: TestClient, headers: dict[str, str], simulation_id: str):
    response = client.get(f"/v1/simulations/{simulation_id}/logs", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def persist_engine_tick(session_factory, simulation_id: str, *, run_id: str) -> dict:
    """persist_event_batch 로 tick=1 에:
      - event_master Event 1건 (조별 과제)     -> log type 'event'
      - magic_layer  Event 1건 (저주 확산)     -> log type 'system'
      - observation 기억 1건 (로그에 안 나옴)
      - conversation 기억 1건                    -> log type 'dialogue'
    을 남기고 result payload 를 돌려준다.
    """
    from app.domain.event_persistence import EventBatch
    from app.domain.models import Agent, AgentState
    from app.services.event_persistence import persist_event_batch
    from app.services.fixtures import seed_slice_zero

    normal_event_id = uuid7()
    magic_event_id = uuid7()
    with session_factory() as session:
        seed_slice_zero(session, UUID(simulation_id))
        states = list(
            session.scalars(
                select(AgentState)
                .join(Agent, Agent.id == AgentState.agent_id)
                .where(AgentState.simulation_id == UUID(simulation_id))
                .order_by(Agent.fixture_key)
            )
        )
        speaker, listener = states[0], states[1]
        batch = EventBatch.model_validate(
            dict(
                simulation_id=UUID(simulation_id),
                run_id=run_id,
                tick_number=1,
                policy_version="logs-policy",
                resolver_version="logs-resolver",
                resolution_id="logs-resolution",
                events=[
                    dict(
                        id=normal_event_id,
                        event_type="GROUP_PROJECT",
                        title="조별 과제",
                        description="도서관에서 조별 과제를 했다.",
                        participant_agent_ids=[speaker.agent_id, listener.agent_id],
                        location_id=speaker.location_id,
                        source="event_master",
                        impact_level="medium",
                        importance=50,
                    ),
                    dict(
                        id=magic_event_id,
                        event_type="CURSE_SPREAD",
                        title="저주 확산",
                        description="복도에 저주가 번졌다.",
                        participant_agent_ids=[listener.agent_id],
                        location_id=listener.location_id,
                        source="magic_layer",
                        impact_level="high",
                        importance=80,
                    ),
                ],
                resolved_effects=[
                    dict(
                        source_agent_id=speaker.agent_id,
                        metric="stress",
                        before=speaker.stress,
                        requested_total=1,
                        applied_delta=1,
                        after=speaker.stress + 1,
                        effect_ids=["e1"],
                    )
                ],
                memories=[
                    dict(
                        agent_id=speaker.agent_id,
                        event_id=normal_event_id,
                        content="조별 과제가 힘들었다.",
                        memory_type="observation",
                        importance=40,
                        occurred_at=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
                    ),
                    dict(
                        agent_id=speaker.agent_id,
                        event_id=normal_event_id,
                        content="리아: 이번 과제 같이 하자. / 아델: 좋아, 도서관에서 보자.",
                        memory_type="conversation",
                        importance=55,
                        occurred_at=datetime(2026, 1, 1, 9, 5, tzinfo=timezone.utc),
                    ),
                ],
            )
        )
        result = persist_event_batch(session, batch)
        session.commit()
        return result


def test_logs_return_events_and_conversations_in_one_timeline(client) -> None:
    test_client, session_factory = client
    headers = register_and_login(test_client, "logs-normal")
    simulation_id = create_simulation(test_client, headers, "normal")

    # 준비: 수동 Event 1건(엔진 tick 없음) -> 그 다음 엔진 tick 1.
    manual = post_event(test_client, headers, simulation_id, "수동 사건")
    result = persist_engine_tick(session_factory, simulation_id, run_id="logs-normal-run")
    normal_event = result["events"][0]
    magic_event = result["events"][1]
    conversation = next(
        memory for memory in result["memories"] if memory["memory_type"] == "conversation"
    )

    logs = get_logs(test_client, headers, simulation_id)

    by_id = {item["id"]: item for item in logs}
    # seed 된 CLASS Event + 수동 Event + 엔진 Event 2건 + 대화 기억 1건.
    # observation 기억은 로그에 포함되지 않는다.
    assert manual["id"] in by_id
    assert normal_event["id"] in by_id
    assert magic_event["id"] in by_id
    assert conversation["id"] in by_id
    observation = next(
        memory for memory in result["memories"] if memory["memory_type"] == "observation"
    )
    assert observation["id"] not in by_id

    assert by_id[manual["id"]]["type"] == "event"
    assert by_id[manual["id"]]["tick"] is None
    assert by_id[normal_event["id"]]["type"] == "event"
    assert by_id[normal_event["id"]]["tick"] == 1
    assert by_id[normal_event["id"]]["importance"] == 50
    assert by_id[magic_event["id"]]["type"] == "system"
    assert by_id[magic_event["id"]]["importance"] == 80

    dialogue = by_id[conversation["id"]]
    assert dialogue["type"] == "dialogue"
    assert dialogue["tick"] == 1
    assert dialogue["summary"] == conversation["content"]
    assert dialogue["importance"] == 55
    # Dialogue 영속화가 없어 dialogue_id 필드는 응답에 없다.
    assert "dialogue_id" not in dialogue


def test_logs_are_ordered_by_tick_then_row_id(client) -> None:
    test_client, session_factory = client
    headers = register_and_login(test_client, "logs-order")
    simulation_id = create_simulation(test_client, headers, "order")

    seeded_class = test_client.get(
        f"/v1/simulations/{simulation_id}/events", headers=headers
    ).json()[0]
    manual = post_event(test_client, headers, simulation_id, "수동 사건")
    result = persist_engine_tick(session_factory, simulation_id, run_id="logs-order-run")
    normal_event = result["events"][0]
    magic_event = result["events"][1]
    conversation = next(
        memory for memory in result["memories"] if memory["memory_type"] == "conversation"
    )

    logs = get_logs(test_client, headers, simulation_id)

    # tick 없는 Event(준비 기록)가 먼저, 그 뒤 tick=1 기록이 행 id(uuid7) 순으로.
    assert [item["id"] for item in logs] == [
        seeded_class["id"],
        manual["id"],
        normal_event["id"],
        magic_event["id"],
        conversation["id"],
    ]
    assert [item["tick"] for item in logs] == [None, None, 1, 1, 1]


def test_logs_are_scoped_to_their_simulation(client) -> None:
    test_client, session_factory = client
    headers = register_and_login(test_client, "logs-scope")
    simulation_a = create_simulation(test_client, headers, "sim-a")
    simulation_b = create_simulation(test_client, headers, "sim-b")

    post_event(test_client, headers, simulation_a, "A 수동 사건")
    result_b = persist_engine_tick(session_factory, simulation_b, run_id="logs-scope-run-b")
    b_ids = {result_b["events"][0]["id"], result_b["events"][1]["id"]} | {
        memory["id"] for memory in result_b["memories"]
    }

    logs_a = get_logs(test_client, headers, simulation_a)
    a_ids = {item["id"] for item in logs_a}

    assert a_ids.isdisjoint(b_ids)
    # A 는 seed CLASS + 수동 Event 만. 대화/시스템 로그는 없다.
    assert all(item["type"] == "event" for item in logs_a)

    logs_b = get_logs(test_client, headers, simulation_b)
    assert {"dialogue", "system"} <= {item["type"] for item in logs_b}


def test_event_log_item_references_its_event_id(client) -> None:
    test_client, session_factory = client
    headers = register_and_login(test_client, "logs-eventref")
    simulation_id = create_simulation(test_client, headers, "eventref")

    result = persist_engine_tick(session_factory, simulation_id, run_id="logs-eventref-run")
    normal_event = result["events"][0]
    conversation = next(
        memory for memory in result["memories"] if memory["memory_type"] == "conversation"
    )

    logs = get_logs(test_client, headers, simulation_id)
    by_id = {item["id"]: item for item in logs}

    # Event 로그는 자기 자신을 event_id 로 참조한다.
    assert by_id[normal_event["id"]]["event_id"] == normal_event["id"]
    # 대화 로그는 그 대화가 매달린 Event 를 event_id 로 참조한다 (agent_memories.event_id FK).
    assert by_id[conversation["id"]]["event_id"] == normal_event["id"]


def test_logs_empty_simulation_returns_empty_list(client) -> None:
    test_client, session_factory = client
    headers = register_and_login(test_client, "logs-empty")
    simulation_id = create_simulation(test_client, headers, "empty")

    # 새 simulation 은 seed 된 CLASS Event 를 갖는다. 로그가 하나도 없는 상태를
    # 만들기 위해 직접 제거한다 (event_participants 를 먼저 지운다).
    from app.domain.models import Event, EventParticipant

    with session_factory() as session:
        owned = select(Event.id).where(Event.simulation_id == UUID(simulation_id))
        session.execute(delete(EventParticipant).where(EventParticipant.event_id.in_(owned)))
        session.execute(delete(Event).where(Event.simulation_id == UUID(simulation_id)))
        session.commit()

    response = test_client.get(
        f"/v1/simulations/{simulation_id}/logs", headers=headers
    )
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_logs_enforce_ownership(client) -> None:
    test_client, _ = client
    owner_headers = register_and_login(test_client, "logs-owner")
    other_headers = register_and_login(test_client, "logs-intruder")
    simulation_id = create_simulation(test_client, owner_headers, "owned")

    response = test_client.get(
        f"/v1/simulations/{simulation_id}/logs", headers=other_headers
    )
    assert response.status_code == 403, response.text


def test_events_api_still_works_alongside_logs(client) -> None:
    test_client, _ = client
    headers = register_and_login(test_client, "logs-regression")
    simulation_id = create_simulation(test_client, headers, "regression")

    seeded = test_client.get(
        f"/v1/simulations/{simulation_id}/events", headers=headers
    ).json()
    assert len(seeded) == 1

    first = post_event(test_client, headers, simulation_id, "사건 1")
    second = post_event(test_client, headers, simulation_id, "사건 2")

    listed = test_client.get(f"/v1/simulations/{simulation_id}/events", headers=headers)
    assert [item["id"] for item in listed.json()] == [
        seeded[0]["id"],
        first["id"],
        second["id"],
    ]

    latest = test_client.get(
        f"/v1/simulations/{simulation_id}/events/latest", headers=headers
    )
    assert latest.status_code == 200, latest.text
    assert latest.json()["id"] == second["id"]

    detail = test_client.get(
        f"/v1/simulations/{simulation_id}/events/{first['id']}", headers=headers
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["id"] == first["id"]
