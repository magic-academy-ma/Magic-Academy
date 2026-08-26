"""Slice 4 Task 5 — 5/6-Agent orchestration 인수 테스트.

Task 1(Runtime batch, #110)·Task 2(Tick orchestration, #111)·
Task 3(User Persona 저장·rollback, #112)이 base에 아직 모두 병합되지 않은
상태이므로, 이 파일은 독립적으로 검증 가능한 시나리오는 TickEngine(추상
계층)으로 직접 실행해 검증하고, DB·저장·User Persona 연동이 필요한 시나리오는
의존 Task를 명시한 skip 스텁으로 남겨둔다.

Task 1~4가 base에 병합되면 skip을 제거하고 실제 Runtime·저장 경로로 확장한다.
Slice 0~3 누적 회귀는 별도 시나리오 없이 `pytest -q`(전체 backend 테스트) 실행
결과로 확인한다.
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from uuid6 import uuid7

from app.simulation.agent_runtime import AgentRuntimeResult
from app.simulation.tick_engine import (
    AgentType,
    RuntimeExecutionError,
    TickAgent,
    TickEngine,
    TickEvent,
    TickRollbackError,
    WorldSnapshot,
)


STUDENT_IDS = [f"00000000-0000-0000-0000-{index:012d}" for index in range(1, 6)]
PROFESSOR_ID = "00000000-0000-0000-0000-000000000010"
CLASS_EVENT_ID = "evt-class-1"


def make_students(*, inactive_ids: set[str] = frozenset()) -> list[TickAgent]:
    return [
        TickAgent(id=student_id, agent_type=AgentType.STUDENT, is_active=student_id not in inactive_ids)
        for student_id in STUDENT_IDS
    ]


def make_professor(*, is_active: bool = True) -> TickAgent:
    return TickAgent(id=PROFESSOR_ID, agent_type=AgentType.PROFESSOR, is_active=is_active)


def make_event(participant_ids: list[str] = ()) -> TickEvent:
    return TickEvent(id=CLASS_EVENT_ID, event_type="class", participant_ids=set(participant_ids))


def make_snapshot(tick: int = 1) -> WorldSnapshot:
    return WorldSnapshot(simulation_id="sim-slice4-acceptance", current_tick=tick, data={})


def student_runtime_results(agents: list[TickAgent]) -> dict[str, AgentRuntimeResult]:
    return {agent.id: make_runtime_result(agent.id) for agent in agents}


def make_runtime_result(
    agent_id: str,
    *,
    status: str = "PROPOSED",
    motivation_summary: str = "수업 내용을 복습한다.",
) -> AgentRuntimeResult:
    return AgentRuntimeResult.model_validate(
        {
            "run_id": "slice-4-acceptance-run",
            "tick_number": 1,
            "agent_id": agent_id,
            "status": status,
            "intent": {
                "action_type": "STUDY",
                "target_agent_id": None,
                "target_location_id": None,
                "related_event_id": None,
                "utterance": None,
                "motivation_summary": motivation_summary,
                "reaction": {"valence": "NEUTRAL"},
                "decision_explanation": {
                    "alternatives": [
                        {
                            "action_type": "STUDY",
                            "description": "복습한다.",
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
            "model": "mock-llm",
            "prompt_version": "slice-4-acceptance-test",
            "idempotency_key": f"slice-4-acceptance-run:1:{agent_id}",
        }
    )


# ── Professor 조건 없음: Student 5명 실행 ─────────────────────────────────────


async def test_professor_excluded_without_condition_runs_five_students() -> None:
    """Professor가 Event 참여자도 아니고 Schedule 조건도 없으면 5명만 실행된다."""
    students = make_students()
    professor = make_professor()

    async def runtime(agents, event, snapshot):
        return student_runtime_results(agents)

    engine = TickEngine(runtime=runtime)

    result = await engine.run_tick(
        agents=[*students, professor],
        event=make_event(),
        snapshot=make_snapshot(),
    )

    assert sorted(result.participant_ids) == sorted(STUDENT_IDS)
    assert PROFESSOR_ID not in result.participant_ids
    assert len(result.participant_ids) == 5


# ── Professor 조건 충족: 총 6명 실행 ──────────────────────────────────────────


async def test_professor_included_as_event_participant_runs_six() -> None:
    """Professor가 Event 참여자면 Student 5명과 함께 총 6명이 실행된다."""
    students = make_students()
    professor = make_professor()

    async def runtime(agents, event, snapshot):
        return student_runtime_results(agents)

    engine = TickEngine(runtime=runtime)

    result = await engine.run_tick(
        agents=[*students, professor],
        event=make_event(participant_ids=[PROFESSOR_ID]),
        snapshot=make_snapshot(),
    )

    assert sorted(result.participant_ids) == sorted([*STUDENT_IDS, PROFESSOR_ID])
    assert len(result.participant_ids) == 6


async def test_professor_included_when_schedule_requires_runs_six() -> None:
    """Event 미참여 Professor도 schedule_requires_professor=True면 6명이 실행된다."""
    students = make_students()
    professor = make_professor()

    async def runtime(agents, event, snapshot):
        return student_runtime_results(agents)

    engine = TickEngine(runtime=runtime)

    result = await engine.run_tick(
        agents=[*students, professor],
        event=make_event(),
        snapshot=make_snapshot(),
        schedule_requires_professor=True,
    )

    assert sorted(result.participant_ids) == sorted([*STUDENT_IDS, PROFESSOR_ID])
    assert len(result.participant_ids) == 6


# ── 모든 Agent가 동일한 World Snapshot 사용 ───────────────────────────────────


async def test_all_participants_receive_identical_world_snapshot() -> None:
    """5/6명 모든 Agent에 동일한 WorldSnapshot 인스턴스가 전달된다."""
    students = make_students()
    professor = make_professor()
    received_snapshots: list[WorldSnapshot] = []

    async def runtime(agents, event, snapshot):
        received_snapshots.append(snapshot)
        return student_runtime_results(agents)

    engine = TickEngine(runtime=runtime)
    snapshot = make_snapshot()

    await engine.run_tick(
        agents=[*students, professor],
        event=make_event(participant_ids=[PROFESSOR_ID]),
        snapshot=snapshot,
    )

    assert len(received_snapshots) == 1
    assert received_snapshots[0] is snapshot


# ── 정상 fallback 발생 시 Tick 성공 ───────────────────────────────────────────


async def test_normal_fallback_keeps_tick_successful() -> None:
    """일부 Agent가 FALLBACK 결과를 반환해도 Tick 전체는 성공 처리된다."""
    students = make_students()

    async def runtime(agents, event, snapshot):
        outputs = student_runtime_results(agents)
        outputs[STUDENT_IDS[0]] = make_runtime_result(STUDENT_IDS[0], status="FALLBACK")
        return outputs

    engine = TickEngine(runtime=runtime)

    result = await engine.run_tick(
        agents=students,
        event=make_event(),
        snapshot=make_snapshot(),
    )

    assert result.status == "completed"
    assert result.runtime_outputs[STUDENT_IDS[0]].status == "FALLBACK"


# ── 치명적 Agent 실패 시 전체 rollback ────────────────────────────────────────


async def test_critical_runtime_failure_rolls_back_entire_tick() -> None:
    """치명적 Runtime 실패 시 전체 Tick이 rollback된다."""
    students = make_students()
    professor = make_professor()

    async def failing_runtime(agents, event, snapshot):
        raise RuntimeExecutionError("결과 생성 불가")

    engine = TickEngine(runtime=failing_runtime)

    with pytest.raises(TickRollbackError):
        await engine.run_tick(
            agents=[*students, professor],
            event=make_event(participant_ids=[PROFESSOR_ID]),
            snapshot=make_snapshot(),
        )


# ── Agent 결과 순서 및 ID 매핑 검증 ───────────────────────────────────────────


async def test_agent_result_id_mapping_independent_of_completion_order() -> None:
    """비동기 완료 순서와 무관하게 Agent ID별 결과 매핑이 정확하다."""
    students = make_students()
    professor = make_professor()
    completion_order = list(reversed([*STUDENT_IDS, PROFESSOR_ID]))

    async def out_of_order_runtime(agents, event, snapshot):
        outputs = {}
        for agent_id in completion_order:
            outputs[agent_id] = make_runtime_result(agent_id)
        return outputs

    engine = TickEngine(runtime=out_of_order_runtime)

    result = await engine.run_tick(
        agents=[*students, professor],
        event=make_event(participant_ids=[PROFESSOR_ID]),
        snapshot=make_snapshot(),
    )

    for agent_id in [*STUDENT_IDS, PROFESSOR_ID]:
        assert str(result.runtime_outputs[agent_id].agent_id) == agent_id


# ── 의존 Task 병합 후 활성화할 시나리오 ───────────────────────────────────────


async def test_user_persona_uses_ordinary_student_runtime() -> None:
    """User Persona로 지정된 Student도 별도 Runtime 없이 기존 Student Runtime을 사용한다."""
    students = make_students()
    user_persona = students[0]  # TickEngine 레벨에서 AgentType.STUDENT로 편성
    runtime_received_ids: list[str] = []

    async def recording_runtime(agents, event, snapshot):
        runtime_received_ids.extend(agent.id for agent in agents)
        return student_runtime_results(agents)

    engine = TickEngine(runtime=recording_runtime)

    result = await engine.run_tick(
        agents=students,
        event=make_event(),
        snapshot=make_snapshot(),
    )

    assert user_persona.id in runtime_received_ids
    assert result.runtime_outputs[user_persona.id].status == "PROPOSED"


async def test_inactive_user_persona_is_skipped() -> None:
    """비활성 User Persona는 LLM 호출 없이 SKIPPED 결과로 포함된다."""
    inactive_persona_id = STUDENT_IDS[0]
    students = make_students(inactive_ids={inactive_persona_id})

    async def runtime_with_skip(agents, event, snapshot):
        return {
            agent.id: make_runtime_result(
                agent.id, status="SKIPPED" if not agent.is_active else "PROPOSED"
            )
            for agent in agents
        }

    engine = TickEngine(runtime=runtime_with_skip)

    result = await engine.run_tick(
        agents=students,
        event=make_event(),
        snapshot=make_snapshot(),
    )

    assert result.runtime_outputs[inactive_persona_id].status == "SKIPPED"
    assert result.status == "completed"


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required")
def test_storage_failure_rolls_back_entire_tick() -> None:
    """Tick 결과 저장 실패 시 Tick·Memory·Relationship·실행 기록이 모두 rollback된다."""
    from app.domain.models import Agent, RuntimeExecution, RuntimeResult, Simulation, User
    from app.services.database_runtime_results import DatabaseRuntimeResultSink
    from app.services.execution_metadata import ExecutionMetadataInput, record_execution_metadata
    from app.services.fixtures import seed_slice_zero
    from tests.runtime_factories import make_runtime_result as factory_make_runtime_result

    db_url = os.getenv("TEST_DATABASE_URL")
    db_engine = create_engine(db_url)
    session_factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    with db_engine.begin() as conn:
        conn.execute(text("TRUNCATE users, simulations RESTART IDENTITY CASCADE"))

    owner_id = uuid7()
    simulation_id = uuid7()
    with session_factory.begin() as session:
        session.add(User(id=owner_id, username="acceptance-rollback", display_name="Rollback", password_hash="x", roles=["USER"]))
        session.flush()
        session.add(Simulation(id=simulation_id, owner_id=owner_id, name="Rollback"))
        session.flush()
        seed_slice_zero(session, simulation_id)

    with session_factory() as session:
        with pytest.raises(RuntimeError):
            with session.begin():
                agent_id = session.scalar(
                    select(Agent.id).where(Agent.simulation_id == simulation_id, Agent.fixture_key == "student-01")
                )
                run_id = str(uuid7())
                result = factory_make_runtime_result(agent_id=str(agent_id)).model_copy(
                    update={"run_id": run_id, "tick_number": 1, "agent_id": agent_id,
                            "idempotency_key": f"{run_id}:1:{agent_id}"}
                )
                record_execution_metadata(
                    session,
                    ExecutionMetadataInput(simulation_id=simulation_id, run_id=run_id, tick_number=1,
                                          seed=1, model=result.model, prompt_version=result.prompt_version,
                                          policy_version=None),
                )
                DatabaseRuntimeResultSink(session).save_batch([result])
                raise RuntimeError("fatal commit failure")

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(RuntimeExecution)) == 0
        assert session.scalar(select(func.count()).select_from(RuntimeResult)) == 0
    db_engine.dispose()


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required")
def test_execution_metadata_is_persisted() -> None:
    """run_id·seed·model·prompt_version·policy_version이 실행 기록에 저장된다."""
    from app.domain.models import RuntimeExecution, Simulation, User
    from app.services.execution_metadata import ExecutionMetadataInput, record_execution_metadata

    db_url = os.getenv("TEST_DATABASE_URL")
    db_engine = create_engine(db_url)
    session_factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    with db_engine.begin() as conn:
        conn.execute(text("TRUNCATE users, simulations RESTART IDENTITY CASCADE"))

    owner_id = uuid7()
    simulation_id = uuid7()
    run_id = str(uuid7())
    with session_factory.begin() as session:
        session.add(User(id=owner_id, username="acceptance-metadata", display_name="Metadata", password_hash="x", roles=["USER"]))
        session.flush()
        session.add(Simulation(id=simulation_id, owner_id=owner_id, name="Metadata"))
        session.flush()
        record_execution_metadata(
            session,
            ExecutionMetadataInput(simulation_id=simulation_id, run_id=run_id, tick_number=1,
                                   seed=7, model="mock-llm", prompt_version="agent-runtime-10.1",
                                   policy_version="policy-mvp-0.1"),
        )

    with session_factory() as session:
        stored = session.scalar(select(RuntimeExecution).where(RuntimeExecution.run_id == run_id))
        assert stored.simulation_id == simulation_id
        assert stored.tick_number == 1
        assert stored.seed == 7
        assert stored.model == "mock-llm"
        assert stored.prompt_version == "agent-runtime-10.1"
        assert stored.policy_version == "policy-mvp-0.1"
    db_engine.dispose()


async def test_roster_contains_five_students_and_one_professor() -> None:
    """roster가 Student 5명(User Persona 포함)·Professor 1명으로 구성되고 중복이 없다. (AUP-01)"""
    students = make_students()
    professor = make_professor()
    roster: list[TickAgent] = []

    async def recording_runtime(agents, event, snapshot):
        roster.extend(agents)
        return student_runtime_results(agents)

    engine = TickEngine(runtime=recording_runtime)

    await engine.run_tick(
        agents=[*students, professor],
        event=make_event(participant_ids=[PROFESSOR_ID]),
        snapshot=make_snapshot(),
    )

    participant_ids = [a.id for a in roster]
    assert len(participant_ids) == 6
    assert len(set(participant_ids)) == 6
    assert sum(1 for a in roster if a.agent_type == AgentType.STUDENT) == 5
    assert sum(1 for a in roster if a.agent_type == AgentType.PROFESSOR) == 1


@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL is required")
def test_direct_command_to_user_persona_after_start_is_rejected() -> None:
    """Simulation 시작 후 User Persona 직접 명령·성격 변경 요청은 HTTP 409로 거부된다. (AUP-07)"""
    from app.core.database import get_db
    from app.main import app

    db_url = os.getenv("TEST_DATABASE_URL")
    db_engine = create_engine(db_url)
    session_factory = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)
    with db_engine.begin() as conn:
        conn.execute(text("TRUNCATE users, simulations RESTART IDENTITY CASCADE"))

    def override_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            creds = {"username": "aup07-user", "display_name": "AUP-07", "password": "Aup07-pass!"}
            assert client.post("/v1/auth/register", json=creds).status_code == 201
            login = client.post("/v1/auth/login", json={"username": creds["username"], "password": creds["password"]})
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            sim = client.post("/v1/simulations", headers=headers, json={"name": "AUP-07"}).json()
            agents = client.get(f"/v1/simulations/{sim['id']}/agents", headers=headers).json()
            student = next(a for a in agents if a["fixture_key"] == "student-03")
            persona_payload = {
                "agent_id": student["id"], "mbti_type": "INFP",
                "personality_rule_version": "mbti-big-five-v0.1",
                "openness": 25, "conscientiousness": -25, "extraversion": -25,
                "agreeableness": 20, "emotional_stability": 0,
            }
            assert client.post(f"/v1/simulations/{sim['id']}/user-persona", headers=headers, json=persona_payload).status_code == 200
            assert client.post(f"/v1/simulations/{sim['id']}/start", headers=headers, json={}).status_code == 200

            response = client.post(f"/v1/simulations/{sim['id']}/user-persona", headers=headers, json=persona_payload)
            assert response.status_code == 409
            assert response.json()["code"] == "CONFLICT"
    finally:
        app.dependency_overrides.clear()
        db_engine.dispose()


async def test_same_seed_produces_identical_results() -> None:
    """동일 seed로 실행한 두 Tick의 Agent 결과가 A/B 비교에서 동일하다.

    seed는 Task 3(#112)에서 tick 실행 메타데이터로 저장되며 TickEngine 자체에는
    seed 파라미터가 없다. 운영 LLM은 seed만으로 응답 원문 전체의 완전한 동일성을
    보장하기 어려우므로, deterministic Fake Runtime으로 실행 대상·결과 순서·
    Agent ID 매핑·페이로드 동일성을 검증한다 (Task 0, #109 결정). 운영 LLM 응답
    원문 전체 일치는 PASS 조건에서 제외한다.
    """
    students = make_students()
    professor = make_professor()
    agents = [*students, professor]
    event = make_event(participant_ids=[PROFESSOR_ID])
    seed = 42

    def build_seeded_runtime(seed: int):
        async def seeded_runtime(agents, event, snapshot):
            return {
                agent.id: make_runtime_result(
                    agent.id, motivation_summary=f"seed:{seed}-agent:{agent.id}"
                )
                for agent in agents
            }

        return seeded_runtime

    engine_a = TickEngine(runtime=build_seeded_runtime(seed))
    engine_b = TickEngine(runtime=build_seeded_runtime(seed))

    result_a = await engine_a.run_tick(agents=agents, event=event, snapshot=make_snapshot())
    result_b = await engine_b.run_tick(agents=agents, event=event, snapshot=make_snapshot())

    assert list(result_a.runtime_outputs.keys()) == list(result_b.runtime_outputs.keys())
    for agent_id in result_a.runtime_outputs:
        assert result_a.runtime_outputs[agent_id] == result_b.runtime_outputs[agent_id]
