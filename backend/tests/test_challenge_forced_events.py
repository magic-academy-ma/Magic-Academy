"""도전과제 모드 — Round1 강제 Event 주입 헬퍼.

docs/04-feature-specs/challenge-mode-team-revival.md §4.3/§6: '역할 재배정'은
GROUP_PROJECT를 참여자 조합이 다른 두 Event로 분리하고, '직접 대화시킴'은
MEETING을 강제 주입한다. 둘 다 EventMaster의 자동 생성 로직을 거치지 않고
Event dataclass를 직접 구성한다.
"""

import pytest

from app.simulation.challenge.forced_events import (
    build_forced_group_project,
    build_forced_meeting,
)
from app.simulation.event_master import ImpactLevel


def test_build_forced_group_project_creates_event_with_given_participants():
    event = build_forced_group_project(
        tick=1,
        participant_agent_ids=["b", "a"],
        location_id="classroom",
    )

    assert event.event_type == "GROUP_PROJECT"
    assert event.participant_agent_ids == ("a", "b")
    assert event.tick == 1
    assert event.location_id == "classroom"
    assert event.source == "challenge_controller"


def test_build_forced_group_project_defaults_to_high_impact_for_reflection():
    event = build_forced_group_project(
        tick=1, participant_agent_ids=["a", "b"], location_id="classroom"
    )

    assert event.impact_level == ImpactLevel.HIGH
    assert event.importance == 80


def test_build_forced_group_project_rejects_fewer_than_two_participants():
    with pytest.raises(ValueError):
        build_forced_group_project(tick=1, participant_agent_ids=["a"], location_id="classroom")


def test_role_reassignment_splits_participants_into_separate_group_project_events():
    """'역할 재배정' 구현: A·B를 서로 다른 GROUP_PROJECT 인스턴스로 분리."""
    event_a = build_forced_group_project(
        tick=1, participant_agent_ids=["a", "c"], location_id="classroom"
    )
    event_b = build_forced_group_project(
        tick=1, participant_agent_ids=["b", "d"], location_id="library"
    )

    assert event_a.participant_agent_ids == ("a", "c")
    assert event_b.participant_agent_ids == ("b", "d")
    assert event_a.event_key != event_b.event_key


def test_build_forced_meeting_creates_event_with_given_participants():
    event = build_forced_meeting(
        tick=1, participant_agent_ids=["a", "b"], location_id="classroom"
    )

    assert event.event_type == "MEETING"
    assert event.participant_agent_ids == ("a", "b")
    assert event.source == "challenge_controller"


def test_build_forced_meeting_rejects_fewer_than_two_participants():
    with pytest.raises(ValueError):
        build_forced_meeting(tick=1, participant_agent_ids=["a"], location_id="classroom")
