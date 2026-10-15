"""스토리모드 공통 — 개입 기록과 챕터 결과.

docs/04-feature-specs/challenge-mode-team-revival.md §4.1/§4.8.
"""

from app.simulation.challenge.record import (
    INDECISIVE_THRESHOLD_SECONDS,
    WATCH,
    InterventionRecord,
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
