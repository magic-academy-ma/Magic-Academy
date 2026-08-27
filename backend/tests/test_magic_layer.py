"""Slice 5 Task 1 — Magic Layer unit tests (Issue #101)."""

from app.simulation.magic_layer import (
    CURSE_SPREAD,
    MAGIC_EXPLOSION,
    MAGICAL_DISCOVERY,
    RITUAL_FAILURE,
    STUDENT_MISSING,
    AgentSnapshot,
    MagicLayer,
)
from app.simulation.policy.models import RelationshipSnapshot


def snap(
    agent_id: str,
    *,
    agent_type: str = "student",
    location: str | None = "dormitory",
    fatigue: int = 10,
    is_cursed: bool = False,
    recent_stress: tuple[int, ...] = (),
    active: bool = True,
) -> AgentSnapshot:
    return AgentSnapshot(
        agent_id=agent_id,
        agent_type=agent_type,
        active_status=active,
        current_location_id=location,
        fatigue=fatigue,
        is_cursed=is_cursed,
        recent_stress=recent_stress,
    )


# ---------------------------------------------------------------------------
# 9. STUDENT_MISSING 조건 경계
# ---------------------------------------------------------------------------
def test_student_missing_fires_on_10_of_10_streak():
    snapshots = [snap("s1", recent_stress=tuple([95] * 10))]
    result = MagicLayer().evaluate(tick=11, regular_events=[], agent_snapshots=snapshots)
    assert [e.event_subtype for e in result.special_events] == [STUDENT_MISSING]
    assert result.special_events[0].missing_agent_ids == ("s1",)


def test_student_missing_does_not_fire_on_9_of_10_streak():
    snapshots = [snap("s1", recent_stress=tuple([95] * 9 + [10]))]
    result = MagicLayer().evaluate(tick=11, regular_events=[], agent_snapshots=snapshots)
    assert result.special_events == ()


def test_student_missing_excludes_professor():
    snapshots = [snap("p1", agent_type="professor", recent_stress=tuple([95] * 10))]
    result = MagicLayer().evaluate(tick=11, regular_events=[], agent_snapshots=snapshots)
    assert result.special_events == ()


# ---------------------------------------------------------------------------
# 10. MAGIC_EXPLOSION
# ---------------------------------------------------------------------------
def test_magic_explosion_fires_when_ratio_meets_threshold():
    # 4명 중 fatigue>=80은 4명(100% >= 80%).
    snapshots = [
        snap("s1", location="lab", fatigue=85),
        snap("s2", location="lab", fatigue=90),
        snap("s3", location="lab", fatigue=80),
        snap("s4", location="lab", fatigue=95),
    ]
    result = MagicLayer().evaluate(tick=1, regular_events=[], agent_snapshots=snapshots)
    assert [e.event_subtype for e in result.special_events] == [MAGIC_EXPLOSION]
    assert set(result.special_events[0].participant_agent_ids) == {"s1", "s2", "s3", "s4"}


def test_magic_explosion_does_not_fire_below_ratio_threshold():
    # 3명 중 fatigue>=80은 1명(33%) -> 80% 미달.
    snapshots = [
        snap("s1", location="lab", fatigue=85),
        snap("s2", location="lab", fatigue=20),
        snap("s3", location="lab", fatigue=20),
    ]
    result = MagicLayer().evaluate(tick=1, regular_events=[], agent_snapshots=snapshots)
    assert result.special_events == ()


def test_magic_explosion_does_not_fire_below_min_students():
    snapshots = [snap("s1", location="lab", fatigue=90), snap("s2", location="lab", fatigue=90)]
    result = MagicLayer().evaluate(tick=1, regular_events=[], agent_snapshots=snapshots)
    assert result.special_events == ()


# ---------------------------------------------------------------------------
# 11. RITUAL_FAILURE
# ---------------------------------------------------------------------------
def test_ritual_failure_fires_with_enough_participants_and_bad_relationship():
    snapshots = [snap(f"s{i}", location="hall") for i in range(1, 5)]
    relationships = [
        RelationshipSnapshot("s1", "s2", trust=-10, tension=10),
        RelationshipSnapshot("s2", "s1", trust=-10, tension=10),
    ]
    result = MagicLayer().evaluate(
        tick=1, regular_events=[], agent_snapshots=snapshots, relationship_snapshots=relationships
    )
    assert [e.event_subtype for e in result.special_events] == [RITUAL_FAILURE]
    assert len(result.special_events[0].participant_agent_ids) == 4


def test_ritual_failure_does_not_fire_below_min_participants():
    snapshots = [snap(f"s{i}", location="hall") for i in range(1, 4)]
    relationships = [RelationshipSnapshot("s1", "s2", trust=-50, tension=90)]
    result = MagicLayer().evaluate(
        tick=1, regular_events=[], agent_snapshots=snapshots, relationship_snapshots=relationships
    )
    assert result.special_events == ()


def test_ritual_failure_does_not_fire_with_good_relationship():
    snapshots = [snap(f"s{i}", location="hall") for i in range(1, 5)]
    relationships = [
        RelationshipSnapshot("s1", "s2", trust=50, tension=0),
        RelationshipSnapshot("s2", "s1", trust=50, tension=0),
    ]
    result = MagicLayer().evaluate(
        tick=1, regular_events=[], agent_snapshots=snapshots, relationship_snapshots=relationships
    )
    assert result.special_events == ()


# ---------------------------------------------------------------------------
# 12. MAGICAL_DISCOVERY
# ---------------------------------------------------------------------------
def test_magical_discovery_fires_when_no_prior_candidates():
    snapshots = [
        snap("p1", agent_type="professor", location="lab"),
        snap("s1", location="lab"),
    ]
    result = MagicLayer().evaluate(
        tick=1, regular_events=[], agent_snapshots=snapshots, lab_location_ids=frozenset({"lab"})
    )
    assert [e.event_subtype for e in result.special_events] == [MAGICAL_DISCOVERY]
    assert set(result.special_events[0].participant_agent_ids) == {"p1", "s1"}


def test_magical_discovery_blocked_when_higher_priority_candidate_exists():
    snapshots = [
        snap("p1", agent_type="professor", location="lab"),
        snap("s1", location="lab"),
        snap("m1", recent_stress=tuple([95] * 10)),  # STUDENT_MISSING candidate
    ]
    result = MagicLayer().evaluate(
        tick=11, regular_events=[], agent_snapshots=snapshots, lab_location_ids=frozenset({"lab"})
    )
    assert [e.event_subtype for e in result.special_events] == [STUDENT_MISSING]


def test_magical_discovery_requires_professor_and_student_together():
    snapshots = [snap("p1", agent_type="professor", location="lab")]
    result = MagicLayer().evaluate(
        tick=1, regular_events=[], agent_snapshots=snapshots, lab_location_ids=frozenset({"lab"})
    )
    assert result.special_events == ()


# ---------------------------------------------------------------------------
# 13. CURSE_SPREAD
# ---------------------------------------------------------------------------
def test_curse_spread_fires_for_contacted_agent():
    snapshots = [
        snap("cursed1", location="dormitory", is_cursed=True),
        snap("s1", location="dormitory"),
    ]
    result = MagicLayer().evaluate(tick=1, regular_events=[], agent_snapshots=snapshots)
    assert [e.event_subtype for e in result.special_events] == [CURSE_SPREAD]
    assert result.special_events[0].newly_cursed_agent_ids == ("s1",)


def test_curse_spread_excludes_non_contacted_agent():
    snapshots = [
        snap("cursed1", location="dormitory", is_cursed=True),
        snap("s1", location="classroom"),
    ]
    result = MagicLayer().evaluate(tick=1, regular_events=[], agent_snapshots=snapshots)
    assert result.special_events == ()


def test_curse_spread_does_not_reapply_to_already_cursed_contact():
    snapshots = [
        snap("cursed1", location="dormitory", is_cursed=True),
        snap("cursed2", location="dormitory", is_cursed=True),
    ]
    result = MagicLayer().evaluate(tick=1, regular_events=[], agent_snapshots=snapshots)
    assert result.special_events == ()


# ---------------------------------------------------------------------------
# 14. Magic priority
# ---------------------------------------------------------------------------
def test_priority_student_missing_over_curse_spread():
    snapshots = [
        snap("m1", recent_stress=tuple([95] * 10)),
        snap("cursed1", location="dormitory", is_cursed=True),
        snap("s1", location="dormitory"),
    ]
    result = MagicLayer().evaluate(tick=11, regular_events=[], agent_snapshots=snapshots)
    assert [e.event_subtype for e in result.special_events] == [STUDENT_MISSING]


def test_priority_curse_spread_over_magic_explosion():
    snapshots = [
        snap("cursed1", location="dormitory", is_cursed=True),
        snap("s1", location="dormitory"),
        snap("e1", location="lab", fatigue=90),
        snap("e2", location="lab", fatigue=90),
        snap("e3", location="lab", fatigue=90),
    ]
    result = MagicLayer().evaluate(tick=1, regular_events=[], agent_snapshots=snapshots)
    assert [e.event_subtype for e in result.special_events] == [CURSE_SPREAD]


def test_priority_magic_explosion_over_ritual_failure():
    snapshots = [
        snap("e1", location="lab", fatigue=90),
        snap("e2", location="lab", fatigue=90),
        snap("e3", location="lab", fatigue=90),
        *[snap(f"r{i}", location="hall") for i in range(1, 5)],
    ]
    relationships = [RelationshipSnapshot("r1", "r2", trust=-50, tension=90)]
    result = MagicLayer().evaluate(
        tick=1, regular_events=[], agent_snapshots=snapshots, relationship_snapshots=relationships
    )
    assert [e.event_subtype for e in result.special_events] == [MAGIC_EXPLOSION]


def test_priority_ritual_failure_over_magical_discovery():
    snapshots = [
        *[snap(f"r{i}", location="hall") for i in range(1, 5)],
        snap("p1", agent_type="professor", location="lab"),
        snap("s1", location="lab"),
    ]
    relationships = [RelationshipSnapshot("r1", "r2", trust=-50, tension=90)]
    result = MagicLayer().evaluate(
        tick=1,
        regular_events=[],
        agent_snapshots=snapshots,
        relationship_snapshots=relationships,
        lab_location_ids=frozenset({"lab"}),
    )
    assert [e.event_subtype for e in result.special_events] == [RITUAL_FAILURE]
