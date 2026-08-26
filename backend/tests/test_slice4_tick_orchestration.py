"""Slice 4 Task 2/6 — 5-Student·조건부 Professor Tick orchestration.

Student/Professor 실행 대상 편성 로직과 실제 API·PostgreSQL 운영 경로의
Runtime batch, Policy, Memory 통합을 검증한다.
"""

import os
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.orm import sessionmaker

from app.domain.models import Agent

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
from app.services.runtime_target_selection import select_tick_participant_ids

SIMULATION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_IDS = [UUID(f"00000000-0000-0000-0000-{index:012d}") for index in range(1, 6)]
USER_PERSONA_ID = STUDENT_IDS[0]
PROFESSOR_ID = UUID("00000000-0000-0000-0000-000000000010")
CLASS_EVENT_ID = UUID("20000000-0000-0000-0000-000000000001")


def make_agent(agent_id: UUID, agent_type: str) -> Agent:
    return Agent(
        id=agent_id,
        simulation_id=SIMULATION_ID,
        fixture_key=str(agent_id),
        fixture_version="test",
        agent_type=agent_type,
        name=str(agent_id),
        mbti_type="ISTJ",
    )


def make_students(*, user_persona_id: UUID | None = None) -> list[Agent]:
    return [
        make_agent(
            agent_id,
            "user_persona" if agent_id == user_persona_id else "student",
        )
        for agent_id in STUDENT_IDS
    ]


def make_professor(agent_id: UUID = PROFESSOR_ID) -> Agent:
    return make_agent(agent_id, "professor")


class TestDefaultStudentFiveOrchestration:
    def test_student_five_only_by_default(self) -> None:
        """일반 Tick에서는 Student 5명만 실행 대상이 된다."""
        agents = make_students() + [make_professor()]

        selected = select_tick_participant_ids(agents)

        assert selected == tuple(STUDENT_IDS)

    def test_user_persona_included_as_ordinary_student(self) -> None:
        """User Persona는 별도 Runtime 없이 기존 Student와 동일하게 편성된다."""
        agents = make_students(user_persona_id=USER_PERSONA_ID) + [make_professor()]

        selected = select_tick_participant_ids(agents)

        assert selected == tuple(STUDENT_IDS)


class TestConditionalProfessorOrchestration:
    def test_professor_added_when_event_participant(self) -> None:
        """Professor가 Event 참여자면 6명이 실행 대상이 된다."""
        agents = make_students() + [make_professor()]

        selected = select_tick_participant_ids(
            agents, event_participant_agent_ids=[PROFESSOR_ID]
        )

        assert selected == (*STUDENT_IDS, PROFESSOR_ID)

    def test_professor_added_when_schedule_requires(self) -> None:
        """Schedule 조건 충족 시 Event 미참여 Professor도 추가된다."""
        agents = make_students() + [make_professor()]

        selected = select_tick_participant_ids(
            agents, schedule_requires_professor=True
        )

        assert selected == (*STUDENT_IDS, PROFESSOR_ID)

    def test_professor_not_added_without_condition(self) -> None:
        """Event 참여자도 아니고 Schedule 조건도 없으면 Professor는 제외된다."""
        agents = make_students() + [make_professor()]

        selected = select_tick_participant_ids(agents)

        assert PROFESSOR_ID not in selected
        assert len(selected) == 5


class TestSelectionInvariants:
    def test_duplicate_agent_id_is_deduplicated(self) -> None:
        """같은 Agent.id가 중복 전달돼도 결과는 한 번만 포함한다."""
        agents = make_students() + make_students()

        selected = select_tick_participant_ids(agents)

        assert selected == tuple(STUDENT_IDS)

    def test_selection_order_follows_agent_snapshot_order(self) -> None:
        """Student 간 상대 순서는 Agent 목록 순서를 그대로 보존한다."""
        reversed_students = list(reversed(make_students()))
        agents = reversed_students + [make_professor()]

        selected = select_tick_participant_ids(
            agents, schedule_requires_professor=True
        )

        assert selected == (*reversed(STUDENT_IDS), PROFESSOR_ID)

    def test_professor_placed_after_students_regardless_of_snapshot_order(self) -> None:
        """Agent 조회 순서(fixture_key 오름차순 등)로 Professor가 Student보다 먼저
        와도, 최종 편성 순서는 Student 전원 → Professor로 고정된다
        (Slice 4 Task 0 계약: canonical 순서는 fixture_key 정렬에 의존하지 않는다)."""
        agents = [make_professor()] + make_students()

        selected = select_tick_participant_ids(
            agents, schedule_requires_professor=True
        )

        assert selected == (*STUDENT_IDS, PROFESSOR_ID)

    def test_non_runtime_agent_type_is_excluded(self) -> None:
        """student/professor/user_persona 이외 agent_type은 실행 대상에서 제외된다."""
        agents = make_students() + [make_agent(PROFESSOR_ID, "unknown")]

        selected = select_tick_participant_ids(
            agents,
            event_participant_agent_ids=[PROFESSOR_ID],
            schedule_requires_professor=True,
        )

        assert selected == tuple(STUDENT_IDS)

    def test_empty_agents_returns_empty_selection(self) -> None:
        assert select_tick_participant_ids([]) == ()


# ── SimulationTickService 연동 뼈대 ────────────────────────────────────────
# 실제 API·PostgreSQL에서 Runtime batch, Policy, Memory 연결을 검증한다.


@pytest.fixture()
def api_context():
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL is required")
    from app.core.database import get_db
    from app.main import app
    from app.services.runtime_dependency import get_agent_runtime
    from app.simulation.agent_runtime import AgentRuntime, MockLLMClient

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
    app.dependency_overrides[get_agent_runtime] = lambda: AgentRuntime(
        MockLLMClient(), model="slice4-task6-runtime"
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, session_factory
    app.dependency_overrides.clear()
    engine.dispose()


def create_simulation(client: TestClient) -> tuple[UUID, dict[str, str]]:
    credentials = {
        "username": "slice4-task6-owner",
        "display_name": "Slice 4 Task 6",
        "password": "Slice4-task6-password!",
    }
    assert client.post("/v1/auth/register", json=credentials).status_code == 201
    login = client.post(
        "/v1/auth/login",
        json={
            "username": credentials["username"],
            "password": credentials["password"],
        },
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    created = client.post(
        "/v1/simulations", headers=headers, json={"name": "Task 6 integration"}
    )
    assert created.status_code == 201
    return UUID(created.json()["id"]), headers


def test_tick_calls_runtime_batch_exactly_once_per_tick(api_context, monkeypatch) -> None:
    """Tick당 Runtime batch가 정확히 1회 호출된다."""
    from app.repositories.memory_repository import MemoryRepository
    from app.services.runtime_orchestrator import RuntimeOrchestrator
    from app.simulation.policy import engine as policy_engine

    client, session_factory = api_context
    simulation_id, headers = create_simulation(client)
    calls = {"batch": 0, "policy": 0, "retrieve": 0, "store": 0}
    received_ids: list[UUID] = []
    original_batch = RuntimeOrchestrator.run_batch
    original_policy = policy_engine.evaluate_policy
    original_retrieve = MemoryRepository.retrieve_for_runtime
    original_create = MemoryRepository.create

    def count_batch(self, runtime_inputs):
        calls["batch"] += 1
        received_ids.extend(item.agent.agent_id for item in runtime_inputs)
        return original_batch(self, runtime_inputs)

    def count_policy(policy_input):
        calls["policy"] += 1
        return original_policy(policy_input)

    def count_retrieve(self, *args, **kwargs):
        calls["retrieve"] += 1
        return original_retrieve(self, *args, **kwargs)

    def count_create(self, *args, **kwargs):
        calls["store"] += 1
        return original_create(self, *args, **kwargs)

    monkeypatch.setattr(RuntimeOrchestrator, "run_batch", count_batch)
    monkeypatch.setattr(policy_engine, "evaluate_policy", count_policy)
    monkeypatch.setattr(MemoryRepository, "retrieve_for_runtime", count_retrieve)
    monkeypatch.setattr(MemoryRepository, "create", count_create)

    response = client.post(
        f"/v1/simulations/{simulation_id}/ticks/advance", headers=headers
    )

    assert response.status_code == 200, response.text
    with session_factory() as db:
        fixtures_by_id = {
            agent.id: agent.fixture_key
            for agent in db.scalars(
                select(Agent).where(Agent.simulation_id == simulation_id)
            )
        }
    expected_keys = [
        *(f"student-{index:02d}" for index in range(1, 6)),
        "professor-01",
    ]
    assert [fixtures_by_id[agent_id] for agent_id in received_ids] == expected_keys
    assert [result["agent_name"] for result in response.json()["agent_results"]] == [
        "아델",
        "레오",
        "리아",
        "카이",
        "세라",
        "에단",
    ]
    assert calls == {"batch": 1, "policy": 1, "retrieve": 6, "store": 6}


def test_all_agents_receive_identical_world_snapshot(api_context, monkeypatch) -> None:
    """Professor 미참여 시 Student 5명이 동일 World Snapshot으로 실행된다."""
    from app.domain.models import Event, EventParticipant
    from app.simulation.tick_engine import TickEngine

    client, session_factory = api_context
    simulation_id, headers = create_simulation(client)
    with session_factory.begin() as db:
        professor_id = db.scalar(
            select(Agent.id).where(
                Agent.simulation_id == simulation_id,
                Agent.agent_type == "professor",
            )
        )
        class_event_id = db.scalar(
            select(Event.id).where(Event.simulation_id == simulation_id)
        )
        db.execute(
            delete(EventParticipant).where(
                EventParticipant.event_id == class_event_id,
                EventParticipant.agent_id == professor_id,
            )
        )

    snapshots = []
    original_run_tick = TickEngine.run_tick

    async def capture_snapshot(self, agents, event, snapshot, **kwargs):
        snapshots.append(snapshot)
        return await original_run_tick(self, agents, event, snapshot, **kwargs)

    monkeypatch.setattr(TickEngine, "run_tick", capture_snapshot)
    response = client.post(
        f"/v1/simulations/{simulation_id}/ticks/advance", headers=headers
    )

    assert response.status_code == 200, response.text
    assert len(snapshots) == 1
    assert [result["agent_name"] for result in response.json()["agent_results"]] == [
        "아델",
        "레오",
        "리아",
        "카이",
        "세라",
    ]
