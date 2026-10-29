"""스토리모드 — 특정 (tick, Agent)의 runtime 입력에 정보를 주입하는 LLMClient 래퍼.

docs/04-feature-specs/challenge-mode-team-revival.md §4.1/§6: 컨트롤러는 Agent의
행동(Intent)을 직접 정하지 않는다. 지정된 (tick_number, agent_id)에서 runtime
입력의 ``memories`` 앞에 조정관 공지·대화 기억 같은 정보를 덧붙인 뒤, 항상 실제
LLMClient로 위임한다. 정보를 받은 Agent가 어떻게 행동할지는 Agent Runtime이 정한다.

주입된 기억은 이번 입력에만 들어가고 DB에 저장되지 않는다 — 여러 Tick에 걸쳐
알려야 하는 정보는 Tick마다 따로 주입한다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any

from app.simulation.agent_runtime import AgentRuntime, AgentRuntimeInput, LLMClient
from app.simulation.event_master import IMPACT_LEVEL_TO_IMPORTANCE, ImpactLevel

InjectionKey = tuple[int, str]
Injections = dict[InjectionKey, list[dict[str, Any]]]


def build_injected_memory(
    *,
    tick: int,
    agent_id: str,
    kind: str,
    content: str,
    memory_type: str = "observation",
) -> dict[str, Any]:
    """runtime 입력 ``memories``와 같은 모양(manual_tick.py 참고)의 주입용 기억 1건.
    memory_type은 DB 값(observation/conversation/reflection/plan)을 쓰고, kind는 같은
    (tick, agent)에 여러 건을 주입해도 id가 겹치지 않게 하는 구분자다."""
    return {
        "id": f"challenge:{kind}:{tick}:{agent_id}",
        "content": content,
        "memory_type": memory_type,
        "importance": IMPACT_LEVEL_TO_IMPORTANCE[ImpactLevel.HIGH],
        "created_tick": tick,
        "event_id": None,
    }


def merge_injections(*plans: Mapping[InjectionKey, Sequence[dict[str, Any]]]) -> Injections:
    """여러 계획의 주입을 (tick, agent) 단위로 이어 붙인다."""
    merged: Injections = {}
    for plan in plans:
        for key, memories in plan.items():
            merged.setdefault(key, []).extend(memories)
    return merged


class ChallengeLLMOverride:
    def __init__(
        self,
        real_client: LLMClient,
        *,
        injections: Mapping[InjectionKey, Sequence[dict[str, Any]]],
    ) -> None:
        self._real_client = real_client
        self._injections = {key: list(memories) for key, memories in injections.items()}

    def generate(self, runtime_input: AgentRuntimeInput) -> object:
        key = (runtime_input.tick_number, str(runtime_input.agent.agent_id))
        injected = self._injections.get(key)
        if injected:
            runtime_input = runtime_input.model_copy(
                update={"memories": [*deepcopy(injected), *runtime_input.memories]}
            )
        return self._real_client.generate(runtime_input)


def runtime_with_injections(
    runtime: AgentRuntime, injections: Mapping[InjectionKey, Sequence[dict[str, Any]]]
) -> AgentRuntime:
    """요청에 쓰는 Runtime과 같은 설정으로, LLMClient만 정보 주입 래퍼로 감싼 Runtime."""
    if not injections:
        return runtime
    return AgentRuntime(
        ChallengeLLMOverride(runtime._llm_client, injections=injections),
        model=runtime._model,
        prompt_version=runtime._prompt_version,
        llm_quota=runtime.llm_quota,
    )
