"""스토리모드 CHAPTER 2 — Day3 종료 시점 엔딩·챕터 기록·업적 판정.

docs/04-feature-specs/challenge-mode-team-revival.md §4.7~§4.9:
- DISBANDED: 탈퇴 선언자가 최종 준비에 불참했거나 project_progress 미달
- UNITED: DISBANDED가 아니고, affection 평균이 임계값 이상이며 run 시작보다 상승
- PARTIAL: 그 외

임계값은 플레이테스트 후 조정 대상인 임시값이며 이름 있는 상수로 분리한다.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from app.simulation.challenge.record import (
    ChapterGrade,
    ChapterRecord,
    InterventionRecord,
    watched_every_intervention,
)

PROJECT_PROGRESS_THRESHOLD = 70  # 임시값 — 플레이테스트 후 조정
AFFECTION_AVG_THRESHOLD = 0  # 임시값 — 플레이테스트 후 조정


class TeamRevivalEnding(StrEnum):
    UNITED = "UNITED"
    PARTIAL = "PARTIAL"
    DISBANDED = "DISBANDED"


ENDING_GRADES: dict[TeamRevivalEnding, ChapterGrade] = {
    TeamRevivalEnding.UNITED: ChapterGrade.GOOD,
    TeamRevivalEnding.PARTIAL: ChapterGrade.MIXED,
    TeamRevivalEnding.DISBANDED: ChapterGrade.BAD,
}


class TeamRevivalAchievement(StrEnum):
    WORSENED_RELATIONS = "WORSENED_RELATIONS"  # 마이너스의 손
    HANDS_OFF_REVIVAL = "HANDS_OFF_REVIVAL"  # 다 계획이 있구나!
    ENEMIES_TO_ALLIES = "ENEMIES_TO_ALLIES"  # 원수에서 전우로


def _mean(values: Sequence[int]) -> float:
    if not values:
        raise ValueError("affection values must not be empty")
    return sum(values) / len(values)


def evaluate_team_revival_ending(
    *,
    project_progress: int,
    leaver_joined_final: bool,
    initial_affections: Sequence[int],
    final_affections: Sequence[int],
) -> TeamRevivalEnding:
    if not leaver_joined_final or project_progress < PROJECT_PROGRESS_THRESHOLD:
        return TeamRevivalEnding.DISBANDED
    final_mean = _mean(final_affections)
    if final_mean >= AFFECTION_AVG_THRESHOLD and final_mean > _mean(initial_affections):
        return TeamRevivalEnding.UNITED
    return TeamRevivalEnding.PARTIAL


def build_team_revival_record(
    *, ending: TeamRevivalEnding, interventions: Sequence[InterventionRecord]
) -> ChapterRecord:
    return ChapterRecord(
        chapter=2,
        ending=ending.value,
        grade=ENDING_GRADES[ending],
        interventions=tuple(interventions),
    )


def evaluate_team_revival_achievements(
    *,
    ending: TeamRevivalEnding,
    interventions: Sequence[InterventionRecord],
    initial_affections: Sequence[int],
    final_affections: Sequence[int],
) -> frozenset[TeamRevivalAchievement]:
    """기획 확정 업적만 판정한다. 파악 단계 대화는 개입으로 보지 않는다(§4.9)."""
    achieved: set[TeamRevivalAchievement] = set()
    if _mean(final_affections) < _mean(initial_affections):
        achieved.add(TeamRevivalAchievement.WORSENED_RELATIONS)
    if ending == TeamRevivalEnding.UNITED and watched_every_intervention(interventions):
        achieved.add(TeamRevivalAchievement.HANDS_OFF_REVIVAL)
    if all(affection > 0 for affection in final_affections):
        achieved.add(TeamRevivalAchievement.ENEMIES_TO_ALLIES)
    return frozenset(achieved)
