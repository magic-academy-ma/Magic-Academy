from fastapi.testclient import TestClient


def test_tick_endpoint_is_registered_and_requires_authentication():
    from app.main import app
    from app.services.runtime_dependency import get_agent_runtime
    from app.simulation.agent_runtime import AgentRuntime, MockLLMClient

    sim_id = "00000000-0000-0000-0000-000000000001"
    app.dependency_overrides[get_agent_runtime] = lambda: AgentRuntime(
        MockLLMClient(), model="test-runtime-override"
    )
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(f"/v1/simulations/{sim_id}/ticks/advance")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_agent_runtime, None)
