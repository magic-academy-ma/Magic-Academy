from types import SimpleNamespace

import anthropic
import httpx
import pytest
from pydantic import ValidationError

from app.simulation.agent_runtime import AgentRuntime, IntentCandidate, LLMInvocationError
from app.simulation.anthropic_llm_client import AnthropicLLMClient, SYSTEM_PROMPT
from tests.test_agent_runtime_graph import make_runtime_input, valid_response


class FakeMessages:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class FakeAnthropic:
    def __init__(self, outcome):
        self.messages = FakeMessages(outcome)


def test_generate_uses_configured_structured_output_request():
    runtime_input = make_runtime_input()
    candidate = IntentCandidate.model_validate(valid_response(runtime_input))
    sdk_client = FakeAnthropic(SimpleNamespace(parsed_output=candidate))
    client = AnthropicLLMClient(
        client=sdk_client,
        model="configured-model",
        max_tokens=1234,
    )

    result = client.generate(runtime_input)

    assert result is candidate
    assert len(sdk_client.messages.calls) == 1
    request = sdk_client.messages.calls[0]
    assert request["model"] == "configured-model"
    assert request["max_tokens"] == 1234
    assert request["output_format"] is IntentCandidate
    assert runtime_input.run_id in request["messages"][0]["content"]
    assert str(runtime_input.agent.agent_id) in request["messages"][0]["content"]


def test_system_prompt_defines_concise_action_target_contract():
    assert "WAIT: all target and related Event fields must be null" in SYSTEM_PROMPT
    assert "ATTEND_CLASS or TEACH_CLASS" in SYSTEM_PROMPT
    assert "Keep every explanation concise" in SYSTEM_PROMPT


def test_structured_output_validation_error_reports_safe_field_path():
    runtime_input = make_runtime_input()
    invalid = valid_response(runtime_input)
    invalid["decision_explanation"]["alternatives"][0]["selected"] = False

    with pytest.raises(ValidationError) as validation:
        IntentCandidate.model_validate(invalid)

    client = AnthropicLLMClient(
        client=FakeAnthropic(validation.value),
        model="configured-model",
        max_tokens=4096,
    )

    with pytest.raises(LLMInvocationError) as exc_info:
        client.generate(runtime_input)

    message = str(exc_info.value)
    assert "ValidationError" in message
    assert "value_error" in message
    assert "motivation_summary" not in message


def test_anthropic_api_error_is_sanitized_as_retryable_runtime_error():
    runtime_input = make_runtime_input()
    prompt_secret = "private-memory-content"
    api_key = "test-secret-api-key"
    runtime_input.memories.append({"content": prompt_secret})
    api_error = anthropic.APIConnectionError(
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    )
    sdk_client = FakeAnthropic(api_error)
    client = AnthropicLLMClient(
        client=sdk_client,
        api_key=api_key,
        model="configured-model",
        max_tokens=4096,
    )

    with pytest.raises(LLMInvocationError) as exc_info:
        client.generate(runtime_input)

    assert "APIConnectionError" in str(exc_info.value)
    assert prompt_secret not in str(exc_info.value)
    assert api_key not in str(exc_info.value)


def test_structured_output_validation_error_is_retryable_runtime_error():
    client = AnthropicLLMClient(
        client=FakeAnthropic(ValueError("invalid structured response")),
        model="configured-model",
        max_tokens=4096,
    )

    with pytest.raises(LLMInvocationError, match="ValueError"):
        client.generate(make_runtime_input())


def test_missing_parsed_output_is_retryable_runtime_error():
    client = AnthropicLLMClient(
        client=FakeAnthropic(SimpleNamespace(parsed_output=None)),
        model="configured-model",
        max_tokens=4096,
    )

    with pytest.raises(LLMInvocationError, match="parsed output"):
        client.generate(make_runtime_input())


def test_anthropic_error_follows_existing_retry_and_fallback_contract():
    api_error = anthropic.APIConnectionError(
        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    )
    sdk_client = FakeAnthropic(api_error)
    runtime = AgentRuntime(
        AnthropicLLMClient(
            client=sdk_client,
            model="configured-model",
            max_tokens=4096,
        ),
        model="configured-model",
    )

    result = runtime.run(make_runtime_input())

    assert result.status == "FALLBACK"
    assert result.retry_count == 1
    assert len(sdk_client.messages.calls) == 2


def test_inactive_agent_skips_anthropic_call():
    sdk_client = FakeAnthropic(SimpleNamespace(parsed_output=None))
    runtime = AgentRuntime(
        AnthropicLLMClient(
            client=sdk_client,
            model="configured-model",
            max_tokens=4096,
        ),
        model="configured-model",
    )

    result = runtime.run(make_runtime_input(active=False))

    assert result.status == "SKIPPED"
    assert sdk_client.messages.calls == []
