"""스토리모드 공통 — 개입 선택 기록과 챕터 결과(활동 기록).

docs/04-feature-specs/challenge-mode-team-revival.md §4.1/§4.8:
- 모든 개입 지점에 WATCH(지켜본다)를 두고, 선택 결과와 선택에 걸린 시간을 기록한다.
- 챕터마다 GOOD/MIXED/BAD 등급의 활동 기록을 남긴다.
- FINAL 엔딩: GOOD 4개 이상이면 BEST, BAD 4개 이상이면 BAD, 그 외 NORMAL.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

WATCH = "WATCH"

# 공통 업적 「우유부단하시네요」: 사용자 개입에서 결정에 5분 이상 사용
INDECISIVE_THRESHOLD_SECONDS = 5 * 60


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
