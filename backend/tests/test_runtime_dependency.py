import pytest

from app.core.config import Settings
from app.services import runtime_dependency
from app.services.runtime_dependency import RuntimeConfigurationError, create_agent_runtime
from app.simulation.agent_runtime import MockLLMClient
from tests.test_agent_runtime_graph import make_runtime_input


class FakeAnthropicLLMClient:
    created_with = None

    def __init__(self, *, api_key, model, max_tokens):
        type(self).created_with = {
            "api_key": api_key,
            "model": model,
            "max_tokens": max_tokens,
        }
        self._delegate = MockLLMClient()

    def generate(self, runtime_input):
        return self._delegate.generate(runtime_input)


def settings(**overrides):
    return Settings(
        jwt_secret="test-secret-key-minimum-32-characters-long",
        **overrides,
    )


def test_runtime_settings_use_haiku_defaults():
    configured = settings()

    assert configured.agent_runtime_model == "claude-haiku-4-5-20251001"
    assert configured.agent_runtime_max_tokens == 4096
    assert configured.agent_tick_llm_quota == 12


def test_factory_wires_llm_quota_from_settings(monkeypatch):
    monkeypatch.setattr(
        runtime_dependency, "AnthropicLLMClient", FakeAnthropicLLMClient
    )
    configured = settings(
        anthropic_api_key="fake",
        agent_tick_llm_quota=9,
    )

    runtime = create_agent_runtime(configured)

    assert runtime.llm_quota is not None
    assert runtime.llm_quota.limit == 9
    assert runtime.llm_quota.used == 0


def test_factory_builds_anthropic_runtime_with_configured_metadata(monkeypatch):
    monkeypatch.setattr(
        runtime_dependency, "AnthropicLLMClient", FakeAnthropicLLMClient
    )
    configured = settings(
        anthropic_api_key="fake",
        agent_runtime_model="configured-model",
        agent_runtime_max_tokens=1234,
    )

    runtime = create_agent_runtime(configured)
    result = runtime.run(make_runtime_input())

    assert FakeAnthropicLLMClient.created_with == {
        "api_key": "test-anthropic-key",
        "model": "configured-model",
        "max_tokens": 1234,
    }
    assert result.model == "configured-model"
    assert not isinstance(runtime._llm_client, MockLLMClient)


@pytest.mark.parametrize("api_key", [None, "", "   "])
def test_factory_rejects_missing_or_blank_api_key(api_key):
    with pytest.raises(RuntimeConfigurationError, match="ANTHROPIC_API_KEY"):
        create_agent_runtime(settings(anthropic_api_key=api_key))
