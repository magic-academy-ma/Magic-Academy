"""Slice 5 Task 1 — Event Master unit tests (Issue #101)."""

import pytest

from app.simulation.event_master import (
    AgentSummary,
    EventMaster,
    ImpactLevel,
    RelationshipSummary,
    ScheduledEventInput,
)
from app.simulation.policy.registries.event_policy import build_event_effect_candidates
from app.simulation.policy.models import AgentSnapshot as PolicyAgentSnapshot


def student(agent_id: str, *, major_id: str = "방어 마법", location: str = "dormitory", active: bool = True) -> AgentSummary:
    return AgentSummary(
        agent_id=agent_id,
        name=f"학생-{agent_id}",
        role="student",
        major_id=major_id,
        year=1,
        active_status=active,
        current_location_id=location,
        mood=0,
        stress=10,
        fatigue=10,
    )


def professor(agent_id: str, *, location: str = "classroom") -> AgentSummary:
    return AgentSummary(
        agent_id=agent_id,
        name=f"교수-{agent_id}",
        role="professor",
        major_id=None,
        year=None,
        active_status=True,
        current_location_id=location,
        mood=0,
        stress=10,
        fatigue=10,
    )


def test_class_scheduled_event_is_generated():
    """1. CLASS 예정 Event 생성 — 기존 Schedule/Event 구조를 그대로 변환한다."""
    summaries = [student("s1"), professor("p1", location="dormitory")]
    scheduled = [
        ScheduledEventInput(
            event_id="evt-class-1",
            event_type="CLASS",
            location_id="dormitory",
            participant_agent_ids=("s1", "p1"),
            title="통합마법학 개론",
            impact_level=ImpactLevel.MEDIUM,
        )
    ]
    events = EventMaster().generate(tick=1, agent_summaries=summaries, scheduled_events=scheduled)

    class_events = [e for e in events if e.event_type == "CLASS"]
    assert len(class_events) == 1
    event = class_events[0]
    assert event.participant_agent_ids == ("p1", "s1")
    assert event.source == "event_master"
    assert event.tick == 1


def test_exam_scheduled_event_is_generated():
    """2. EXAM 예정 Event 생성."""
    summaries = [student("s1")]
    scheduled = [
        ScheduledEventInput(
            event_id="evt-exam-1",
            event_type="EXAM",
            location_id="classroom",
            participant_agent_ids=("s1",),
            impact_level=ImpactLevel.HIGH,
        )
    ]
    events = EventMaster().generate(tick=5, agent_summaries=summaries, scheduled_events=scheduled)

    exam_events = [e for e in events if e.event_type == "EXAM"]
    assert len(exam_events) == 1
    assert exam_events[0].importance == 80


def test_group_project_dynamic_event_generated_for_same_major_same_location():
    """3a. GROUP_PROJECT 동적 Event 생성 (같은 major_id + 같은 위치)."""
    summaries = [
        student("s1", major_id="고대 마법", location="library"),
        student("s2", major_id="고대 마법", location="library"),
    ]
    events = EventMaster().generate(tick=3, agent_summaries=summaries)

    group_events = [e for e in events if e.event_type == "GROUP_PROJECT"]
    assert len(group_events) == 1
    assert set(group_events[0].participant_agent_ids) == {"s1", "s2"}
    assert group_events[0].location_id == "library"


def test_meeting_dynamic_event_generated_for_friendly_colocated_agents():
    """3b. MEETING 동적 Event 생성 (우호적 관계 + 같은 위치)."""
    summaries = [
        student("s1", location="dormitory"),
        student("s2", location="dormitory"),
    ]
    relationships = [RelationshipSummary("s1", "s2", affection=10, closeness=10)]
    events = EventMaster().generate(
        tick=3, agent_summaries=summaries, relationship_summaries=relationships
    )

    meeting_events = [e for e in events if e.event_type == "MEETING"]
    assert len(meeting_events) == 1
    assert set(meeting_events[0].participant_agent_ids) == {"s1", "s2"}


def test_meeting_not_generated_without_relationship_history():
    """MEETING은 관계 데이터가 없는 첫 tick에는 생성되지 않는다 (회귀 방지 근거)."""
    summaries = [student("s1", location="dormitory"), student("s2", location="dormitory")]
    events = EventMaster().generate(tick=1, agent_summaries=summaries)

    assert [e for e in events if e.event_type == "MEETING"] == []


@pytest.mark.parametrize(
    "impact_level,expected_importance",
    [(ImpactLevel.LOW, 30), (ImpactLevel.MEDIUM, 50), (ImpactLevel.HIGH, 80)],
)
def test_impact_level_maps_to_importance(impact_level, expected_importance):
    """4. impact_level -> importance 30/50/80 매핑."""
    summaries = [student("s1")]
    scheduled = [
        ScheduledEventInput(
            event_id="evt-1",
            event_type="CLASS",
            location_id="dormitory",
            participant_agent_ids=("s1",),
            impact_level=impact_level,
        )
    ]
    events = EventMaster().generate(tick=1, agent_summaries=summaries, scheduled_events=scheduled)
    assert events[0].importance == expected_importance


def test_random_incident_requires_event_subtype():
    """5. RANDOM_INCIDENT에 event_subtype 필수."""
    with pytest.raises(ValueError):
        EventMaster().build_random_incident(
            tick=1,
            event_subtype="",
            participant_agent_ids=("s1",),
            location_id="dormitory",
        )

    event = EventMaster().build_random_incident(
        tick=1,
        event_subtype="POWER_OUTAGE",
        participant_agent_ids=("s1",),
        location_id="dormitory",
    )
    assert event.event_type == "RANDOM_INCIDENT"
    assert event.event_subtype == "POWER_OUTAGE"


def test_inactive_agent_excluded_from_event_candidates():
    """6. inactive Agent가 잘못된 Event 후보에 포함되지 않음."""
    summaries = [
        student("s1", major_id="고대 마법", location="library", active=True),
        student("s2", major_id="고대 마법", location="library", active=False),
    ]
    scheduled = [
        ScheduledEventInput(
            event_id="evt-1",
            event_type="CLASS",
            location_id="library",
            participant_agent_ids=("s1", "s2"),
        )
    ]
    events = EventMaster().generate(tick=1, agent_summaries=summaries, scheduled_events=scheduled)

    class_event = next(e for e in events if e.event_type == "CLASS")
    assert class_event.participant_agent_ids == ("s1",)
    # inactive Agent만 있으면 GROUP_PROJECT 후보 자체가 생기지 않는다.
    assert [e for e in events if e.event_type == "GROUP_PROJECT"] == []


def test_generation_is_deterministic_for_identical_input():
    """7. 동일 입력에서 deterministic 결과."""
    summaries = [
        student("s1", major_id="고대 마법", location="library"),
        student("s2", major_id="고대 마법", location="library"),
    ]
    relationships = [RelationshipSummary("s1", "s2", affection=5, closeness=5)]

    first = EventMaster().generate(tick=4, agent_summaries=summaries, relationship_summaries=relationships)
    second = EventMaster().generate(tick=4, agent_summaries=summaries, relationship_summaries=relationships)

    assert first == second


def test_general_event_effect_id_is_stable_and_distinct():
    """8. 일반 Event canonical effect_id 안정성 — 같은 Event는 같은 effect_id, 다른 Event는 다른 effect_id."""
    summaries = [student("s1")]
    scheduled = [
        ScheduledEventInput(
            event_id="evt-1", event_type="CLASS", location_id="dormitory", participant_agent_ids=("s1",)
        )
    ]
    snapshot = {"s1": PolicyAgentSnapshot(agent_id="s1", hunger=50, fatigue=10, stress=10, satisfaction=50)}

    events_a = EventMaster().generate(tick=1, agent_summaries=summaries, scheduled_events=scheduled)
    events_b = EventMaster().generate(tick=1, agent_summaries=summaries, scheduled_events=scheduled)
    candidates_a = build_event_effect_candidates(events_a[0], run_id="run-1", agent_snapshots=snapshot)
    candidates_b = build_event_effect_candidates(events_b[0], run_id="run-1", agent_snapshots=snapshot)
    assert [c.effect_id for c in candidates_a] == [c.effect_id for c in candidates_b]
    assert all(not c.effect_id.count("random") for c in candidates_a)  # UUID 아닌 canonical 문자열

    other_scheduled = [
        ScheduledEventInput(
            event_id="evt-2", event_type="EXAM", location_id="dormitory", participant_agent_ids=("s1",)
        )
    ]
    events_c = EventMaster().generate(tick=1, agent_summaries=summaries, scheduled_events=other_scheduled)
    candidates_c = build_event_effect_candidates(events_c[0], run_id="run-1", agent_snapshots=snapshot)
    assert {c.effect_id for c in candidates_a}.isdisjoint({c.effect_id for c in candidates_c})
