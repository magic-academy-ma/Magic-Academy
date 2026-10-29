"""도전과제 모드 — project_progress 계산.

docs/04-feature-specs/challenge-mode-team-revival.md §8: GROUP_PROJECT 참여자의
reaction.valence를 집계한다. POSITIVE면 진행도 증가, NEGATIVE면 감소, NEUTRAL/
미참여는 변화 없음. project_progress는 별도로 저장하지 않고(§6) 평가 시점에
Event 기록에서 계산한다 — 이 모듈은 그 집계 로직만 담당한다.
"""

from app.simulation.agent_runtime import ReactionValence
from app.simulation.challenge.progress import DEFAULT_PROGRESS_STEP, calculate_project_progress


def test_positive_valence_increases_progress():
    assert (
        calculate_project_progress([ReactionValence.POSITIVE], start=50)
        == 50 + DEFAULT_PROGRESS_STEP
    )


def test_negative_valence_decreases_progress():
    assert (
        calculate_project_progress([ReactionValence.NEGATIVE], start=50)
        == 50 - DEFAULT_PROGRESS_STEP
    )


def test_neutral_valence_does_not_change_progress():
    assert calculate_project_progress([ReactionValence.NEUTRAL], start=50) == 50


def test_no_participation_does_not_change_progress():
    assert calculate_project_progress([], start=50) == 50


def test_progress_clamped_to_0_and_100():
    assert calculate_project_progress([ReactionValence.NEGATIVE] * 10, start=10) == 0
    assert calculate_project_progress([ReactionValence.POSITIVE] * 10, start=90) == 100


def test_multiple_participants_accumulate():
    progress = calculate_project_progress(
        [ReactionValence.POSITIVE, ReactionValence.POSITIVE, ReactionValence.NEGATIVE],
        start=0,
    )
    assert progress == DEFAULT_PROGRESS_STEP
