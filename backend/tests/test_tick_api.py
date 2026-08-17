"""
Tick API 엔드포인트 테스트

POST /v1/simulations/{simulation_id}/ticks/advance

DB·인증 의존성은 mock으로 대체하고 TickEngine DI로 핵심 동작을 검증한다.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.simulation.tick_engine import (
    RuntimeExecutionError,
    TickEngine,
)

SIM_ID = "00000000-0000-0000-0000-000000000001"


def make_test_app(engine: TickEngine) -> FastAPI:
    from app.api.ticks import make_tick_router
    from app.core.database import get_db
    from app.core.security import require_user_role

    app = FastAPI()
    app.include_router(make_tick_router(engine), prefix="/v1")
    app.dependency_overrides[get_db] = lambda: MagicMock()
    app.dependency_overrides[require_user_role] = lambda: MagicMock()
    return app


def make_engine(runtime=None) -> TickEngine:
    async def default_runtime(agents, event, snapshot):
        return {a.id: {"intent": "study"} for a in agents}

    return TickEngine(runtime=runtime or default_runtime)


# ── 정상 케이스 ───────────────────────────────────────────────────────────────


@patch("app.api.ticks.require_owned_simulation")
def test_tick_returns_200_on_success(mock_require):
    client = TestClient(make_test_app(make_engine()))
    response = client.post(f"/v1/simulations/{SIM_ID}/ticks/advance")
    assert response.status_code == 200


@patch("app.api.ticks.require_owned_simulation")
def test_tick_response_shape(mock_require):
    client = TestClient(make_test_app(make_engine()))
    response = client.post(f"/v1/simulations/{SIM_ID}/ticks/advance")
    body = response.json()
    assert "status" in body
    assert "participant_ids" in body
    assert "runtime_outputs" in body


# ── 중복 Tick → 409 ───────────────────────────────────────────────────────────


@patch("app.api.ticks.require_owned_simulation")
def test_duplicate_tick_returns_409(mock_require):
    # TODO: PR #60 연결 후 실제 동시 요청 또는 transaction 경계 검증으로 교체
    engine = make_engine()
    engine._running = True  # type: ignore[attr-defined]

    client = TestClient(make_test_app(engine))
    response = client.post(f"/v1/simulations/{SIM_ID}/ticks/advance")
    assert response.status_code == 409


# ── 입력 검증 ─────────────────────────────────────────────────────────────────


@patch("app.api.ticks.require_owned_simulation")
def test_invalid_simulation_id_returns_422(mock_require):
    client = TestClient(make_test_app(make_engine()))
    response = client.post("/v1/simulations/not-a-uuid/ticks/advance")
    assert response.status_code == 422
