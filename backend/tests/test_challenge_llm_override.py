"""도전과제 모드 — Agent 행동 강제 오버라이드 LLMClient 래퍼.

docs/04-feature-specs/challenge-mode-team-revival.md §6: 실제 LLMClient를 감싸고
지정된 (tick_number, agent_id)에서만 스크립트된 응답을 반환하고, 그 외는 실제
LLMClient에 위임한다 — backend/tests/slice5_campaign.py의 CanonicalCampaignLLM과
동일한 패턴을 일반화한다.
"""

from app.simulation.challenge.llm_override import ChallengeLLMOverride
from tests.test_agent_runtime_graph import SequenceLLMClient, make_runtime_input


def test_override_returns_scripted_response_for_matching_tick_and_agent():
    runtime_input = make_runtime_input()  # tick_number=3
    forced = {"action_type": "REST", "forced": True}
    real_client = SequenceLLMClient([{"action_type": "WAIT"}])
    override = ChallengeLLMOverride(
        real_client,
        overrides={(3, runtime_input.agent.agent_id): forced},
    )

    result = override.generate(runtime_input)

    assert result == forced
    assert real_client.call_count == 0


def test_override_delegates_to_real_client_when_not_matched():
    runtime_input = make_runtime_input()  # tick_number=3
    real_response = {"action_type": "WAIT"}
    real_client = SequenceLLMClient([real_response])
    override = ChallengeLLMOverride(
        real_client,
        overrides={(999, runtime_input.agent.agent_id): {"action_type": "REST"}},
    )

    result = override.generate(runtime_input)

    assert result == real_response
    assert real_client.call_count == 1
    assert real_client.runtime_inputs == [runtime_input]


def test_override_supports_callable_for_dynamic_response():
    """콜러블 override는 runtime_input을 받아 그 자리에서 응답을 구성한다 —
    예: 강제 REST가 Agent의 현재 위치(target_location_id)를 알아야 할 때."""
    runtime_input = make_runtime_input()
    calls = []

    def build_response(received_input):
        calls.append(received_input)
        return {
            "action_type": "REST",
            "target_location_id": str(received_input.agent.current_location_id),
        }

    override = ChallengeLLMOverride(
        SequenceLLMClient([]),
        overrides={(3, runtime_input.agent.agent_id): build_response},
    )

    result = override.generate(runtime_input)

    assert result["target_location_id"] == str(runtime_input.agent.current_location_id)
    assert calls == [runtime_input]


def test_override_response_is_deep_copied_so_repeated_calls_are_independent():
    runtime_input = make_runtime_input()
    forced = {"action_type": "REST", "nested": {"value": 1}}
    override = ChallengeLLMOverride(
        SequenceLLMClient([]),
        overrides={(3, runtime_input.agent.agent_id): forced},
    )

    first = override.generate(runtime_input)
    first["nested"]["value"] = 999

    second = override.generate(runtime_input)

    assert second["nested"]["value"] == 1
