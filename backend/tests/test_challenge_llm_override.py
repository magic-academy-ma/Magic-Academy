"""스토리모드 — runtime 입력 정보 주입 LLMClient 래퍼.

docs/04-feature-specs/challenge-mode-team-revival.md §4.1/§6: 지정된 (tick, agent)
입력의 memories 앞에 정보를 덧붙이고, 항상 실제 LLMClient로 위임한다. 스크립트된
행동 응답을 대신 반환하지 않는다.
"""

from app.simulation.challenge.llm_override import (
    ChallengeLLMOverride,
    build_injected_memory,
    merge_injections,
)
from tests.test_agent_runtime_graph import SequenceLLMClient, make_runtime_input


def _memory(runtime_input, kind="notice", content="조정관 공지"):
    return build_injected_memory(
        tick=runtime_input.tick_number,
        agent_id=str(runtime_input.agent.agent_id),
        kind=kind,
        content=content,
    )


def test_injection_prepends_memory_and_always_delegates_to_real_client():
    runtime_input = make_runtime_input()  # tick_number=3
    real_response = {"action_type": "WAIT"}
    real_client = SequenceLLMClient([real_response])
    memory = _memory(runtime_input)
    override = ChallengeLLMOverride(
        real_client,
        injections={(3, str(runtime_input.agent.agent_id)): [memory]},
    )

    result = override.generate(runtime_input)

    assert result == real_response
    assert real_client.call_count == 1
    received = real_client.runtime_inputs[0]
    assert received.memories[0] == memory
    assert received.memories[1:] == runtime_input.memories


def test_unmatched_input_is_passed_through_unchanged():
    runtime_input = make_runtime_input()
    real_client = SequenceLLMClient([{"action_type": "WAIT"}])
    override = ChallengeLLMOverride(
        real_client,
        injections={(999, str(runtime_input.agent.agent_id)): [_memory(runtime_input)]},
    )

    override.generate(runtime_input)

    assert real_client.runtime_inputs == [runtime_input]


def test_original_runtime_input_is_not_mutated():
    runtime_input = make_runtime_input()
    original_memories = list(runtime_input.memories)
    override = ChallengeLLMOverride(
        SequenceLLMClient([{"action_type": "WAIT"}]),
        injections={(3, str(runtime_input.agent.agent_id)): [_memory(runtime_input)]},
    )

    override.generate(runtime_input)

    assert runtime_input.memories == original_memories


def test_injected_memory_has_runtime_memory_shape():
    memory = build_injected_memory(
        tick=4, agent_id="a", kind="persuade", content="이야기", memory_type="conversation"
    )
    assert set(memory) == {"id", "content", "memory_type", "importance", "created_tick", "event_id"}
    assert memory["id"] == "challenge:persuade:4:a"
    assert memory["memory_type"] == "conversation"
    assert memory["created_tick"] == 4


def test_merge_injections_concatenates_per_key():
    first = {(1, "a"): [{"id": "x"}]}
    second = {(1, "a"): [{"id": "y"}], (2, "b"): [{"id": "z"}]}

    merged = merge_injections(first, second)

    assert merged == {(1, "a"): [{"id": "x"}, {"id": "y"}], (2, "b"): [{"id": "z"}]}
