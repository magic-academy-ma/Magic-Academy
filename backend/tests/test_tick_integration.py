"""
Tick API 통합 테스트

issue-72(실제 Agent Runtime 연동)와 인증·소유권 검사 구현 완료 전까지
Tick endpoint는 실제 앱에서 비활성화 상태여야 한다.
"""
from fastapi.testclient import TestClient


def test_tick_endpoint_disabled_until_runtime_integration():
    """issue-72 연동 전까지 Tick endpoint는 404를 반환해야 한다."""
    from app.main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/v1/tick/sim-1/run", json={
        "agents": [{"id": "s-1", "agent_type": "student", "is_active": True}],
        "event": {"id": "evt-1", "event_type": "class", "participant_ids": ["s-1"]},
        "snapshot": {"simulation_id": "sim-1", "current_tick": 0},
    })
    assert response.status_code == 404, (
        "Tick endpoint가 활성화돼 있습니다. "
        "issue-72 Runtime 연동 및 인증·소유권 검사 완료 전까지 비활성화 상태를 유지하세요."
    )
