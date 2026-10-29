"""도전과제 모드 — 특정 (tick, Agent)에서만 스크립트된 행동을 강제하는 LLMClient 래퍼.

docs/04-feature-specs/challenge-mode-team-revival.md §6: 실제 LLMClient를 감싸고,
지정된 (tick_number, agent_id) 조합에서만 스크립트된 응답을 반환한다. 그 외 모든
Agent·Tick은 실제 LLMClient로 위임되어 완전 자율성이 유지된다.
backend/tests/slice5_campaign.py의 CanonicalCampaignLLM 패턴을 일반화한 것이다.

override 값은 정적 응답(dict 등) 또는 ``Callable[[AgentRuntimeInput], object]``
둘 다 허용한다 — 콜러블은 강제 REST의 target_location_id처럼 그 Tick의 실제
runtime_input을 알아야 만들 수 있는 응답에 쓴다.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from uuid import UUID

from app.simulation.agent_runtime import AgentRuntimeInput, LLMClient

OverrideValue = object | Callable[[AgentRuntimeInput], object]


class ChallengeLLMOverride:
    def __init__(
        self,
        real_client: LLMClient,
        *,
        overrides: Mapping[tuple[int, UUID], OverrideValue],
    ) -> None:
        self._real_client = real_client
        self._overrides = dict(overrides)

    def generate(self, runtime_input: AgentRuntimeInput) -> object:
        key = (runtime_input.tick_number, runtime_input.agent.agent_id)
        if key in self._overrides:
            override = self._overrides[key]
            if callable(override):
                return override(runtime_input)
            return deepcopy(override)
        return self._real_client.generate(runtime_input)
