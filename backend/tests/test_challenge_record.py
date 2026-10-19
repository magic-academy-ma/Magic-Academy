"""스토리모드 공통 — 개입 기록과 챕터 결과.

docs/04-feature-specs/challenge-mode-team-revival.md §4.1/§4.8.
"""

import pytest

from app.simulation.challenge.record import (
    INDECISIVE_THRESHOLD_SECONDS,
    WATCH,
    ChapterGrade,
    FinalEnding,
    InterventionRecord,
    chapter_achievements,
    ending_achievements,
    evaluate_final_ending,
    is_indecisive,
    watched_every_intervention,
)


def test_watched_every_intervention_requires_all_watch():
    assert watched_every_intervention(
        [InterventionRecord("R1", WATCH, 3.0), InterventionRecord("R2", WATCH, 4.0)]
    )
    assert not watched_every_intervention(
        [InterventionRecord("R1", WATCH, 3.0), InterventionRecord("R2", "TEAM_MEETING", 4.0)]
    )


def test_watched_every_intervention_is_false_without_records():
    assert not watched_every_intervention([])


def test_indecisive_when_any_decision_takes_five_minutes_or_more():
    assert INDECISIVE_THRESHOLD_SECONDS == 300
    assert is_indecisive([InterventionRecord("R1", WATCH, 10), InterventionRecord("R2", WATCH, 300)])
    assert not is_indecisive([InterventionRecord("R1", WATCH, 299.9)])


@pytest.mark.parametrize(
    ("grades", "ending"),
    [
        ([ChapterGrade.GOOD] * 4, FinalEnding.BEST),
        ([ChapterGrade.BAD] * 4, FinalEnding.BAD),
        ([ChapterGrade.GOOD, ChapterGrade.GOOD, ChapterGrade.GOOD, ChapterGrade.MIXED], FinalEnding.NORMAL),
        ([ChapterGrade.BAD, ChapterGrade.BAD, ChapterGrade.BAD, ChapterGrade.MIXED], FinalEnding.NORMAL),
        ([ChapterGrade.GOOD, ChapterGrade.MIXED, ChapterGrade.BAD, ChapterGrade.MIXED], FinalEnding.NORMAL),
    ],
)
def test_final_ending_needs_four_matching_records(grades, ending):
    assert evaluate_final_ending(grades) == ending


def test_final_ending_requires_all_four_chapters():
    with pytest.raises(ValueError):
        evaluate_final_ending([ChapterGrade.GOOD] * 3)


# ─── 업적: 챕터 클리어·우유부단·엔딩 스토리 ──────────────────────────────────


@pytest.mark.parametrize("chapter", [1, 2, 3, 4])
def test_completed_chapter_run_is_a_clear(chapter):
    assert chapter_achievements(chapter=chapter, status="completed", interventions=[]) == {
        f"CHAPTER{chapter}_CLEAR"
    }


@pytest.mark.parametrize("status", ["ABORTED", "in_progress"])
def test_unfinished_or_aborted_run_grants_nothing(status):
    slow = [InterventionRecord("ROUND1", WATCH, INDECISIVE_THRESHOLD_SECONDS)]
    assert chapter_achievements(
        chapter=2, status=status, interventions=slow, achieved={"WORSENED_RELATIONS"}
    ) == frozenset()


def test_chapter_achievements_add_chapter_judgement_and_indecisive():
    slow = [InterventionRecord("3", "MEDIATE", INDECISIVE_THRESHOLD_SECONDS)]
    assert chapter_achievements(
        chapter=3, status="completed", interventions=slow, achieved={"GLORY_DAYS"}
    ) == {"CHAPTER3_CLEAR", "GLORY_DAYS", "INDECISIVE"}


def test_quick_decisions_are_not_indecisive():
    quick = [InterventionRecord("3", "MEDIATE", INDECISIVE_THRESHOLD_SECONDS - 1)]
    assert "INDECISIVE" not in chapter_achievements(
        chapter=3, status="completed", interventions=quick
    )


@pytest.mark.parametrize(
    ("cleared", "completed", "expected"),
    [
        (3, False, set()),
        (4, False, {"ENDING_UNLOCKED"}),
        (4, True, {"ENDING_UNLOCKED", "ENDING_CLEAR"}),
    ],
)
def test_ending_story_unlocks_after_four_clears_and_clears_with_the_semester(
    cleared, completed, expected
):
    assert ending_achievements(cleared_chapters=cleared, semester_completed=completed) == expected
