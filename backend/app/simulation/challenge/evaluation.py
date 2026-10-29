"""도전과제 모드 — Day3 종료 시점 Perfect/Normal/Bad 판정.

docs/04-feature-specs/challenge-mode-team-revival.md §4.6/§8:
- project_progress >= PROJECT_PROGRESS_THRESHOLD
- 5명 사이 방향성 호감도 평균 >= AFFECTION_AVG_THRESHOLD
- 5명 전원 stress < STRESS_LIMIT

프로젝트가 실패했거나 누군가 번아웃되면 BAD. 프로젝트는 성공했지만 관계가
회복되지 않았으면 NORMAL. 둘 다 만족하면 PERFECT.

세 임계값은 플레이테스트 후 조정 대상인 임시값이며 이름 있는 상수로 분리한다.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

PROJECT_PROGRESS_THRESHOLD = 70  # 임시값 — 플레이테스트 후 조정
AFFECTION_AVG_THRESHOLD = 0  # 임시값 — 플레이테스트 후 조정
STRESS_LIMIT = 90  # 임시값 — 플레이테스트 후 조정


class ChallengeEnding(StrEnum):
    PERFECT = "PERFECT"
    NORMAL = "NORMAL"
    BAD = "BAD"


def evaluate_challenge_ending(
    *,
    project_progress: int,
    directional_affections: Sequence[int],
    agent_stress_levels: Sequence[int],
) -> ChallengeEnding:
    project_success = project_progress >= PROJECT_PROGRESS_THRESHOLD
    stress_ok = all(stress < STRESS_LIMIT for stress in agent_stress_levels)
    relationship_success = bool(directional_affections) and (
        sum(directional_affections) / len(directional_affections) >= AFFECTION_AVG_THRESHOLD
    )

    if not project_success or not stress_ok:
        return ChallengeEnding.BAD
    if relationship_success:
        return ChallengeEnding.PERFECT
    return ChallengeEnding.NORMAL
