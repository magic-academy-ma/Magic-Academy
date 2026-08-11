"""
Tick API 통합 테스트

실제 FastAPI 앱(app.main)에 Tick router가 올바르게 등록됐는지 확인한다.
DB 의존성 없이 router 등록 여부만 검증한다.
"""
from fastapi.testclient import TestClient


def test_tick_endpoint_is_registered_in_main_app():
    """실제 앱에서 POST /v1/tick/{simulation_id}/run가 404가 아닌지 확인한다."""
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    # body 없이 요청 → router 등록 시 422, 미등록 시 404
    response = client.post("/v1/tick/sim-1/run", json={})
    assert response.status_code != 404, (
        "Tick router가 실제 앱에 등록되지 않았습니다. "
        "app/api/router.py에 make_tick_router()를 추가하세요."
    )


def test_tick_endpoint_returns_200_with_valid_body():
    """stub runtime으로 등록된 실제 앱에서 유효한 요청이 200을 반환하는지 확인한다."""
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/v1/tick/sim-1/run", json={
        "agents": [{"id": "s-1", "agent_type": "student", "is_active": True}],
        "event": {"id": "evt-1", "event_type": "class", "participant_ids": ["s-1"]},
        "snapshot": {"simulation_id": "sim-1", "current_tick": 0},
    })
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert "s-1" in body["participant_ids"]
