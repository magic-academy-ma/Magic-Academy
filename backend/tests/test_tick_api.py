"""
Tick API 엔드포인트 테스트

POST /v1/tick/{simulationId}/run

DB 연결 없이 TickEngine 의존성 주입으로 검증한다.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.simulation.tick_engine import (
    TickAgent,
    AgentType,
    TickEvent,
    TickConflictError,
    TickEngine,
    TickResult,
    WorldSnapshot,
)


# ── 테스트용 앱 픽스처 ──────────────────────────────────────────────────────────


def make_test_app(engine: TickEngine) -> FastAPI:
    from app.api.ticks import make_tick_router
    app = FastAPI()
    app.include_router(make_tick_router(engine), prefix="/v1")
    return app


def make_engine(runtime=None) -> TickEngine:
    async def default_runtime(agent, event, snapshot):
        return {"intent": "study"}

    return TickEngine(runtime=runtime or default_runtime)


# ── 정상 케이스 ───────────────────────────────────────────────────────────────


def test_tick_returns_200_on_success():
    client = TestClient(make_test_app(make_engine()))
    response = client.post("/v1/tick/sim-1/run", json={
        "agents": [{"id": "s-1", "agent_type": "student", "is_active": True}],
        "event": {"id": "evt-1", "event_type": "class", "participant_ids": ["s-1"]},
        "snapshot": {"simulation_id": "sim-1", "current_tick": 0},
    })
    assert response.status_code == 200


def test_tick_response_contains_participant_ids():
    client = TestClient(make_test_app(make_engine()))
    response = client.post("/v1/tick/sim-1/run", json={
        "agents": [{"id": "s-1", "agent_type": "student", "is_active": True}],
        "event": {"id": "evt-1", "event_type": "class", "participant_ids": ["s-1"]},
        "snapshot": {"simulation_id": "sim-1", "current_tick": 0},
    })
    body = response.json()
    assert body["status"] == "completed"
    assert "s-1" in body["participant_ids"]


def test_tick_with_professor_not_in_event_excludes_professor():
    client = TestClient(make_test_app(make_engine()))
    response = client.post("/v1/tick/sim-1/run", json={
        "agents": [
            {"id": "s-1", "agent_type": "student", "is_active": True},
            {"id": "p-1", "agent_type": "professor", "is_active": True},
        ],
        "event": {"id": "evt-1", "event_type": "class", "participant_ids": ["s-1"]},
        "snapshot": {"simulation_id": "sim-1", "current_tick": 0},
    })
    body = response.json()
    assert "s-1" in body["participant_ids"]
    assert "p-1" not in body["participant_ids"]


# ── 중복 Tick → 409 ───────────────────────────────────────────────────────────


def test_duplicate_tick_returns_409():
    import asyncio

    call_count = 0

    async def slow_runtime(agent, event, snapshot):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return {"intent": "study"}

    engine = make_engine(runtime=slow_runtime)

    # 엔진을 이미 실행 중 상태로 만든다
    engine._running = True

    client = TestClient(make_test_app(engine))
    response = client.post("/v1/tick/sim-1/run", json={
        "agents": [{"id": "s-1", "agent_type": "student", "is_active": True}],
        "event": {"id": "evt-1", "event_type": "class", "participant_ids": ["s-1"]},
        "snapshot": {"simulation_id": "sim-1", "current_tick": 0},
    })
    assert response.status_code == 409


# ── Runtime 실패 → 500 ────────────────────────────────────────────────────────


def test_runtime_failure_returns_500():
    async def failing_runtime(agent, event, snapshot):
        raise RuntimeError("LLM timeout")

    client = TestClient(make_test_app(make_engine(runtime=failing_runtime)))
    response = client.post("/v1/tick/sim-1/run", json={
        "agents": [{"id": "s-1", "agent_type": "student", "is_active": True}],
        "event": {"id": "evt-1", "event_type": "class", "participant_ids": ["s-1"]},
        "snapshot": {"simulation_id": "sim-1", "current_tick": 0},
    })
    assert response.status_code == 500


# ── 입력 검증 ─────────────────────────────────────────────────────────────────


def test_invalid_agent_type_returns_422():
    client = TestClient(make_test_app(make_engine()))
    response = client.post("/v1/tick/sim-1/run", json={
        "agents": [{"id": "x-1", "agent_type": "unknown", "is_active": True}],
        "event": {"id": "evt-1", "event_type": "class", "participant_ids": ["x-1"]},
        "snapshot": {"simulation_id": "sim-1", "current_tick": 0},
    })
    assert response.status_code == 422
