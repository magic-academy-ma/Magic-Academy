"""챌린지 3 — 동아리를 폐부에서 구하기."""

import pytest

from app.simulation.challenge.club_revival import (
    CLUB_MIN_MEMBERS,
    CLUB_REPUTATION_THRESHOLD,
    ClubAchievement,
    ClubEnding,
    FinalStrategy,
    InternalConflictChoice,
    RecruitmentStrategy,
    apply_final_strategy,
    apply_internal_conflict_choice,
    apply_recruitment_strategy,
    build_closure_warning_event,
    build_club_record,
    evaluate_club_achievements,
    evaluate_club_ending,
    plan_final_event,
    plan_internal_conflict_events,
    plan_recruitment_event,
    record_choice,
)
from app.simulation.challenge.record import WATCH, ChapterGrade, InterventionRecord
from app.simulation.policy.models import AgentSnapshot
from app.simulation.policy.registries.event_policy import build_event_effect_candidates

MEMBERS = ("a", "b")


def _snapshot(agent_id: str) -> AgentSnapshot:
    return AgentSnapshot(
        agent_id=agent_id, hunger=10, fatigue=10, stress=10, satisfaction=50, mood=0
    )


def test_closure_warning_targets_all_club_members():
    event = build_closure_warning_event(
        tick=1, member_ids=MEMBERS, location_id="clubroom"
    )
    assert event.event_type == "RANDOM_INCIDENT"
    assert event.event_subtype == "CLUB_CLOSURE_WARNING"
    assert event.participant_agent_ids == MEMBERS


@pytest.mark.parametrize(
    ("choice", "event_types"),
    [
        (InternalConflictChoice.MEDIATE, ["MEETING"]),
        (InternalConflictChoice.REASSIGN_ROLES, ["GROUP_PROJECT"]),
        (InternalConflictChoice.OBSERVE, []),
    ],
)
def test_internal_conflict_choices_plan_expected_events(choice, event_types):
    events = plan_internal_conflict_events(
        tick=3,
        choice=choice,
        conflict_pair=("a", "b"),
        other_member_ids=(),
        location_id="clubroom",
    )
    assert [event.event_type for event in events] == event_types


@pytest.mark.parametrize(
    ("strategy", "event_type", "label"),
    [
        (RecruitmentStrategy.PERFORMANCE_PROMOTION, "FESTIVAL", "공연 홍보"),
        (RecruitmentStrategy.EXPERIENCE_EVENT, "MEETING", "체험 행사"),
        (RecruitmentStrategy.PROFESSOR_REFERRAL, "MEETING", "교수 추천"),
    ],
)
def test_recruitment_strategy_is_carried_by_event(strategy, event_type, label):
    event = plan_recruitment_event(
        tick=6,
        strategy=strategy,
        member_ids=MEMBERS,
        location_id="clubroom",
        professor_id="professor",
    )
    assert event.event_type == event_type
    assert label in event.title


@pytest.mark.parametrize(
    ("strategy", "event_type"),
    [
        (FinalStrategy.PERFORMANCE_FOCUS, "FESTIVAL"),
        (FinalStrategy.RELATIONSHIP_RECOVERY, "MEETING"),
        (FinalStrategy.SAFE_OPERATION, "FESTIVAL"),
    ],
)
def test_final_strategy_plans_final_event(strategy, event_type):
    event = plan_final_event(
        tick=9,
        strategy=strategy,
        member_ids=MEMBERS,
        location_id="clubroom",
    )
    assert event.event_type == event_type
    assert strategy.value in event.description


def test_closure_warning_uses_existing_medium_stress_tier():
    event = build_closure_warning_event(
        tick=1, member_ids=["a"], location_id="clubroom"
    )
    candidates = build_event_effect_candidates(
        event, run_id="run-1", agent_snapshots={"a": _snapshot("a")}
    )
    assert [(candidate.metric, candidate.delta) for candidate in candidates] == [
        ("stress", 5)
    ]


def test_revival_when_members_reputation_and_relationships_are_healthy():
    ending = evaluate_club_ending(
        member_count=CLUB_MIN_MEMBERS,
        reputation=CLUB_REPUTATION_THRESHOLD,
        directional_affections=[10, 5, 0],
    )
    assert ending == ClubEnding.REVIVAL


def test_conditional_when_only_minimum_members_are_secured():
    ending = evaluate_club_ending(
        member_count=CLUB_MIN_MEMBERS,
        reputation=CLUB_REPUTATION_THRESHOLD - 1,
        directional_affections=[10, 5],
    )
    assert ending == ClubEnding.CONDITIONAL


def test_one_member_ending_is_preserved():
    assert (
        evaluate_club_ending(
            member_count=1,
            reputation=CLUB_REPUTATION_THRESHOLD,
            directional_affections=[],
        )
        == ClubEnding.ONE_MEMBER
    )


def test_club_closes_when_membership_is_below_minimum():
    assert (
        evaluate_club_ending(
            member_count=2,
            reputation=CLUB_REPUTATION_THRESHOLD,
            directional_affections=[10],
        )
        == ClubEnding.CLOSED
    )


def test_confirmed_choices_update_members_and_reputation():
    members, reputation = apply_internal_conflict_choice(
        member_count=2,
        reputation=40,
        choice=InternalConflictChoice.REASSIGN_ROLES,
        negative_reaction=False,
    )
    assert (members, reputation) == (2, 45)

    members, reputation = apply_recruitment_strategy(
        member_count=members,
        reputation=reputation,
        strategy=RecruitmentStrategy.EXPERIENCE_EVENT,
    )
    assert (members, reputation) == (4, 55)
    assert (
        apply_final_strategy(
            reputation=reputation, strategy=FinalStrategy.SAFE_OPERATION
        )
        == 70
    )


def test_observing_negative_conflict_can_leave_one_member():
    assert apply_internal_conflict_choice(
        member_count=2,
        reputation=40,
        choice=InternalConflictChoice.OBSERVE,
        negative_reaction=True,
    ) == (1, 40)


@pytest.mark.parametrize(
    ("ending", "grade"),
    [
        (ClubEnding.REVIVAL, ChapterGrade.GOOD),
        (ClubEnding.CONDITIONAL, ChapterGrade.MIXED),
        (ClubEnding.ONE_MEMBER, ChapterGrade.BAD),
        (ClubEnding.CLOSED, ChapterGrade.BAD),
    ],
)
def test_club_record_is_chapter_three_with_story_grade(ending, grade):
    interventions = [InterventionRecord("3", WATCH, 12.0)]
    record = build_club_record(ending=ending, interventions=interventions)
    assert record.chapter == 3
    assert record.ending == ending.value
    assert record.grade == grade
    assert record.interventions == tuple(interventions)


def test_observe_choice_is_recorded_as_watch():
    assert record_choice(InternalConflictChoice.OBSERVE.value) == WATCH
    assert (
        record_choice(RecruitmentStrategy.EXPERIENCE_EVENT.value)
        == RecruitmentStrategy.EXPERIENCE_EVENT.value
    )


# ─── 업적 (§5) ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("ending", "achievement"),
    [
        (ClubEnding.REVIVAL, {ClubAchievement.GLORY_DAYS}),
        (ClubEnding.CONDITIONAL, {ClubAchievement.MEMBERS_FIRST}),
        (ClubEnding.ONE_MEMBER, {ClubAchievement.CLUB_OF_ONE}),
        (ClubEnding.CLOSED, set()),
    ],
)
def test_club_ending_achievements(ending, achievement):
    assert evaluate_club_achievements(
        ending=ending, initial_member_affections=[0, 0], final_member_affections=[0, 0]
    ) == achievement


def test_catastrophe_when_initial_members_relationship_worsened():
    assert ClubAchievement.CATASTROPHE in evaluate_club_achievements(
        ending=ClubEnding.CLOSED,
        initial_member_affections=[10, 0],
        final_member_affections=[5, 4],
    )


@pytest.mark.parametrize("final", [[5, 5], [10, 0], [20, 0]])
def test_no_catastrophe_when_relationship_held_or_improved(final):
    assert ClubAchievement.CATASTROPHE not in evaluate_club_achievements(
        ending=ClubEnding.CONDITIONAL,
        initial_member_affections=[10, 0],
        final_member_affections=final,
    )


def test_no_catastrophe_without_start_snapshot():
    assert ClubAchievement.CATASTROPHE not in evaluate_club_achievements(
        ending=ClubEnding.CLOSED, initial_member_affections=[], final_member_affections=[-5, -5]
    )
