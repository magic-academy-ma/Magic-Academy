"""도전과제 모드 — Day3 종료 시점 Perfect/Normal/Bad 판정.

docs/04-feature-specs/challenge-mode-team-revival.md §4.6/§8: project_progress,
평균 호감도, 스트레스 세 조건으로 엔딩을 분기한다. 임계값은 플레이테스트 후
조정 대상인 임시값이며 이름 있는 상수로 분리한다.
"""

from app.simulation.challenge.evaluation import (
    AFFECTION_AVG_THRESHOLD,
    PROJECT_PROGRESS_THRESHOLD,
    STRESS_LIMIT,
    ChallengeEnding,
    evaluate_challenge_ending,
)


def test_perfect_ending_when_project_succeeds_and_relationships_recover():
    result = evaluate_challenge_ending(
        project_progress=80,
        directional_affections=[10, 20, -5],
        agent_stress_levels=[10, 20, 30, 40, 50],
    )
    assert result == ChallengeEnding.PERFECT


def test_normal_ending_when_project_succeeds_but_relationships_stay_negative():
    result = evaluate_challenge_ending(
        project_progress=70,
        directional_affections=[-10, -20],
        agent_stress_levels=[10, 20, 30, 40, 50],
    )
    assert result == ChallengeEnding.NORMAL


def test_bad_ending_when_project_fails():
    result = evaluate_challenge_ending(
        project_progress=69,
        directional_affections=[50, 50],
        agent_stress_levels=[10, 20, 30, 40, 50],
    )
    assert result == ChallengeEnding.BAD


def test_bad_ending_when_any_agent_burns_out():
    result = evaluate_challenge_ending(
        project_progress=100,
        directional_affections=[50, 50],
        agent_stress_levels=[10, 20, 30, 40, 90],  # 90 = STRESS_LIMIT, 미만 아님
    )
    assert result == ChallengeEnding.BAD


def test_thresholds_are_named_constants_not_hardcoded():
    assert PROJECT_PROGRESS_THRESHOLD == 70
    assert AFFECTION_AVG_THRESHOLD == 0
    assert STRESS_LIMIT == 90
