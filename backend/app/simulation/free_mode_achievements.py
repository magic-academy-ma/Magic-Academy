"""자유 모드 업적 판정 (docs/04-feature-specs/achievements.md §5.1).

- 실종된 학생의 귀환 목격: 플레이어가 돌아온 학생의 Inspector를 연다.
- 마법 발견 목격: 플레이어가 Event Log에서 마법 발견 이벤트를 누른다.
- 저주 이벤트 발생: 실종됐던 학생이 돌아와 저주가 처음 걸린다.
- 저주 확산: Tick 저장 후 저주 상태인 Agent가 동시에 3명 이상이다(누적 아님).
- 저주 해결: 저주를 처음 가져온 학생의 저주가 끝나 퍼진 저주가 모두 함께 풀린다.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

MISSING_STUDENT_RETURN = "MISSING_STUDENT_RETURN"
MAGIC_DISCOVERY = "MAGIC_DISCOVERY"
CURSE_TRIGGERED = "CURSE_TRIGGERED"
CURSE_SPREAD = "CURSE_SPREAD"
CURSE_LIFTED = "CURSE_LIFTED"

CURSE_SPREAD_THRESHOLD = 3

ACTIVE = "active"
MISSING = "inactive_temporary"
MAGICAL_DISCOVERY_EVENT = "magical_discovery"


@dataclass(frozen=True)
class AgentStatus:
    active_status: str
    cursed: bool


def inspector_achievements(*, was_missing: bool, active_status: str) -> set[str]:
    """돌아온 학생 = 이 Simulation에서 실종됐다가 지금 active로 복귀한 학생."""
    if was_missing and active_status == ACTIVE:
        return {MISSING_STUDENT_RETURN}
    return set()


def event_witness_achievements(event_type: str) -> set[str]:
    if event_type.lower() == MAGICAL_DISCOVERY_EVENT:
        return {MAGIC_DISCOVERY}
    return set()


def tick_achievements(
    before: Mapping[str, AgentStatus], after: Mapping[str, AgentStatus]
) -> set[str]:
    """한 Tick 저장 전후의 Agent 상태로 저주 업적을 판정한다."""
    achieved: set[str] = set()
    if any(
        status.active_status == MISSING
        and after[agent_id].active_status == ACTIVE
        and after[agent_id].cursed
        for agent_id, status in before.items()
    ):
        achieved.add(CURSE_TRIGGERED)
    if sum(1 for status in after.values() if status.cursed) >= CURSE_SPREAD_THRESHOLD:
        achieved.add(CURSE_SPREAD)
    if any(status.cursed and not after[agent_id].cursed for agent_id, status in before.items()):
        achieved.add(CURSE_LIFTED)
    return achieved
