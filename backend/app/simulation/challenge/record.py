"""스토리모드 공통 — 개입 선택 기록과 챕터 결과(활동 기록).

docs/04-feature-specs/challenge-mode-team-revival.md §4.1/§4.8:
- 모든 개입 지점에 WATCH(지켜본다)를 두고, 선택 결과와 선택에 걸린 시간을 기록한다.
- 챕터마다 GOOD/MIXED/BAD 등급의 활동 기록을 남긴다.
- FINAL 엔딩: GOOD 4개 이상이면 BEST, BAD 4개 이상이면 BAD, 그 외 NORMAL.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

WATCH = "WATCH"

# 공통 업적 「우유부단하시네요」: 사용자 개입에서 결정에 5분 이상 사용
INDECISIVE_THRESHOLD_SECONDS = 5 * 60
INDECISIVE = "INDECISIVE"

# 챕터 run이 정상 종료된 상태. 중단(ABORTED)된 run은 이 상태가 되지 않는다.
RUN_COMPLETED = "completed"


class ChapterGrade(StrEnum):
    GOOD = "GOOD"
    MIXED = "MIXED"
    BAD = "BAD"


@dataclass(frozen=True)
class InterventionRecord:
    point: str
    choice: str
    elapsed_seconds: float


@dataclass(frozen=True)
class ChapterRecord:
    chapter: int
    ending: str
    grade: ChapterGrade
    interventions: tuple[InterventionRecord, ...]


def watched_every_intervention(interventions: Sequence[InterventionRecord]) -> bool:
    return bool(interventions) and all(record.choice == WATCH for record in interventions)


def is_indecisive(interventions: Sequence[InterventionRecord]) -> bool:
    return any(
        record.elapsed_seconds >= INDECISIVE_THRESHOLD_SECONDS for record in interventions
    )


def chapter_achievements(
    *,
    chapter: int,
    status: str,
    interventions: Sequence[InterventionRecord],
    achieved: Iterable[str] = (),
) -> frozenset[str]:
    """챕터 run 하나로 얻는 업적 ID. ``achieved``는 챕터별 판정 결과다.

    run이 중단(ABORTED) 없이 끝나야 클리어이고, 끝나지 않은 run은 아무 업적도 주지 않는다.
    """
    if status != RUN_COMPLETED:
        return frozenset()
    ids = {f"CHAPTER{chapter}_CLEAR", *achieved}
    if is_indecisive(interventions):
        ids.add(INDECISIVE)
    return frozenset(ids)


# ─── FINAL — 「한 학기의 기록」 ──────────────────────────────────────────────

STORY_CHAPTER_COUNT = 4
FINAL_BEST_GOOD_COUNT = 4
FINAL_BAD_BAD_COUNT = 4


class FinalEnding(StrEnum):
    BEST = "BEST"
    NORMAL = "NORMAL"
    BAD = "BAD"


def evaluate_final_ending(grades: Sequence[ChapterGrade]) -> FinalEnding:
    if len(grades) != STORY_CHAPTER_COUNT:
        raise ValueError(f"FINAL requires {STORY_CHAPTER_COUNT} chapter records, got {len(grades)}")
    if sum(1 for grade in grades if grade == ChapterGrade.GOOD) >= FINAL_BEST_GOOD_COUNT:
        return FinalEnding.BEST
    if sum(1 for grade in grades if grade == ChapterGrade.BAD) >= FINAL_BAD_BAD_COUNT:
        return FinalEnding.BAD
    return FinalEnding.NORMAL


def ending_achievements(*, cleared_chapters: int, semester_completed: bool) -> frozenset[str]:
    """엔딩 스토리 해금: 챕터 1~4 모두 클리어(FINAL 도달). 클리어: 학기 완료."""
    ids: set[str] = set()
    if cleared_chapters >= STORY_CHAPTER_COUNT:
        ids.add("ENDING_UNLOCKED")
        if semester_completed:
            ids.add("ENDING_CLEAR")
    return frozenset(ids)
