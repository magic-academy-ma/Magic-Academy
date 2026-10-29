"""스토리모드 CHAPTER 2 — 엔딩·챕터 기록·업적 판정.

docs/04-feature-specs/challenge-mode-team-revival.md §4.7~§4.9.
"""

import pytest

from app.simulation.challenge.evaluation import (
    AFFECTION_AVG_THRESHOLD,
    PROJECT_PROGRESS_THRESHOLD,
    TeamRevivalAchievement,
    TeamRevivalEnding,
    build_team_revival_record,
    evaluate_team_revival_achievements,
    evaluate_team_revival_ending,
)
from app.simulation.challenge.record import WATCH, ChapterGrade, InterventionRecord


def _ending(**overrides):
    params = {
        "project_progress": 80,
        "leaver_joined_final": True,
        "initial_affections": [-10, -10],
        "final_affections": [10, 10],
    }
    params.update(overrides)
    return evaluate_team_revival_ending(**params)


def test_united_when_team_stays_and_relationships_improve():
    assert _ending() == TeamRevivalEnding.UNITED


def test_disbanded_when_leaver_skips_final_preparation():
    assert _ending(leaver_joined_final=False) == TeamRevivalEnding.DISBANDED


def test_disbanded_when_project_progress_below_threshold():
    assert _ending(project_progress=PROJECT_PROGRESS_THRESHOLD - 1) == TeamRevivalEnding.DISBANDED


def test_partial_when_affection_did_not_rise_from_start():
    assert _ending(initial_affections=[20, 20], final_affections=[10, 10]) == TeamRevivalEnding.PARTIAL


def test_partial_when_affection_rose_but_stays_below_threshold():
    assert _ending(initial_affections=[-30], final_affections=[-10]) == TeamRevivalEnding.PARTIAL


def test_thresholds_are_named_constants():
    assert PROJECT_PROGRESS_THRESHOLD == 70
    assert AFFECTION_AVG_THRESHOLD == 0


@pytest.mark.parametrize(
    ("ending", "grade"),
    [
        (TeamRevivalEnding.UNITED, ChapterGrade.GOOD),
        (TeamRevivalEnding.PARTIAL, ChapterGrade.MIXED),
        (TeamRevivalEnding.DISBANDED, ChapterGrade.BAD),
    ],
)
def test_record_maps_ending_to_grade(ending, grade):
    interventions = [InterventionRecord("R1", WATCH, 1.0)]
    record = build_team_revival_record(ending=ending, interventions=interventions)
    assert record.chapter == 2
    assert record.ending == ending.value
    assert record.grade == grade
    assert record.interventions == tuple(interventions)


def _achievements(**overrides):
    params = {
        "ending": TeamRevivalEnding.PARTIAL,
        "interventions": [
            InterventionRecord("R1", "MEDIATE", 1.0),
            InterventionRecord("R2", WATCH, 1.0),
        ],
        "initial_affections": [0, 0],
        "final_affections": [0, 0],
    }
    params.update(overrides)
    return evaluate_team_revival_achievements(**params)


def test_worsened_relations_when_average_affection_drops():
    assert TeamRevivalAchievement.WORSENED_RELATIONS in _achievements(
        initial_affections=[10, 10], final_affections=[10, 5]
    )
    assert TeamRevivalAchievement.WORSENED_RELATIONS not in _achievements()


def test_hands_off_revival_requires_all_watch_and_united():
    all_watch = [InterventionRecord("R1", WATCH, 1.0), InterventionRecord("R2", WATCH, 1.0)]
    assert TeamRevivalAchievement.HANDS_OFF_REVIVAL in _achievements(
        ending=TeamRevivalEnding.UNITED, interventions=all_watch
    )
    assert TeamRevivalAchievement.HANDS_OFF_REVIVAL not in _achievements(
        ending=TeamRevivalEnding.PARTIAL, interventions=all_watch
    )
    assert TeamRevivalAchievement.HANDS_OFF_REVIVAL not in _achievements(
        ending=TeamRevivalEnding.UNITED
    )


def test_enemies_to_allies_requires_every_edge_positive():
    assert TeamRevivalAchievement.ENEMIES_TO_ALLIES in _achievements(final_affections=[1, 5, 10])
    assert TeamRevivalAchievement.ENEMIES_TO_ALLIES not in _achievements(final_affections=[1, 0, 10])
