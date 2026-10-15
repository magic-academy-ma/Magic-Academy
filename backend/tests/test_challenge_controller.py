"""스토리모드 CHAPTER 2 — 무너진 팀을 다시 살려라: 진행 컨트롤러.

docs/04-feature-specs/challenge-mode-team-revival.md §4.2~§4.6: 역할·속사정 추첨,
Round 1~3의 Event 주입과 정보 주입을 순수 함수로 조립한다. 컨트롤러는
Agent 행동을 지정하지 않는다.
"""

import random

import pytest

from app.simulation.agent_runtime import ActionType
from app.simulation.challenge.controller import (
    MOTIVE_POOLS,
    ROUND3_INCIDENT_SUBTYPES,
    Round1Choice,
    Round2Choice,
    TeamRole,
    TeamRoster,
    build_final_preparation_event,
    build_leave_declaration_event,
    build_round1_trigger_event,
    build_round2_trigger_event,
    build_round3_incident_event,
    draw_hidden_motives,
    draw_round3_incident_subtype,
    joined_final_preparation,
    plan_motive_injections,
    plan_round1_choice,
    plan_round2_choice,
)

ROSTER = TeamRoster(leader="a", ignored_member="b", leaver="c", blamed_member="d", bystander="e")
MOTIVES = {role: MOTIVE_POOLS[role][0] for role in TeamRole}
LOCATION = "training_hall"


def _contents(injections, key):
    return [memory["content"] for memory in injections.get(key, [])]


# ─── 역할·속사정 ─────────────────────────────────────────────────────────────


def test_roster_lists_every_role_once():
    assert ROSTER.all_agent_ids == ("a", "b", "c", "d", "e")
    assert ROSTER.agent_id(TeamRole.LEAVER) == "c"


def test_hidden_motives_are_drawn_from_role_pools():
    motives = draw_hidden_motives(random.Random(1))
    assert set(motives) == set(TeamRole)
    for role, motive in motives.items():
        assert motive in MOTIVE_POOLS[role]


def test_hidden_motive_draw_is_reproducible_with_same_seed():
    assert draw_hidden_motives(random.Random(42)) == draw_hidden_motives(random.Random(42))


def test_leaver_motive_varies_across_seeds():
    drawn = {draw_hidden_motives(random.Random(seed))[TeamRole.LEAVER] for seed in range(50)}
    assert drawn == set(MOTIVE_POOLS[TeamRole.LEAVER])


def test_motive_is_injected_for_each_agent_on_each_tick():
    injections = plan_motive_injections(ticks=[1, 2], roster=ROSTER, motives=MOTIVES)
    assert set(injections) == {(tick, agent) for tick in (1, 2) for agent in ROSTER.all_agent_ids}
    leaver_memory = injections[(1, "c")][0]
    assert MOTIVES[TeamRole.LEAVER].grievance in leaver_memory["content"]
    assert leaver_memory["memory_type"] == "reflection"


# ─── Round 1 ────────────────────────────────────────────────────────────────


def test_round1_trigger_event_is_high_impact_group_project_between_two_agents():
    event = build_round1_trigger_event(tick=1, agent_a_id="a", agent_b_id="b", location_id=LOCATION)
    assert event.event_type == "GROUP_PROJECT"
    assert event.participant_agent_ids == ("a", "b")
    assert event.importance == 80  # HIGH -> Reflection 대상


def _round1(choice):
    return plan_round1_choice(tick=2, choice=choice, roster=ROSTER, location_id=LOCATION)


def test_reassign_roles_splits_group_projects_and_notifies_members():
    plan = _round1(Round1Choice.REASSIGN_ROLES)
    assert {event.participant_agent_ids for event in plan.events} == {("a", "c"), ("b", "d")}
    assert set(plan.injections) == {(2, agent) for agent in "abcd"}
    assert _contents(plan.injections, (2, "c")) == ["조정관이 팀의 역할을 다시 나눴다."]


def test_mediate_creates_meeting_between_leader_and_ignored_member():
    plan = _round1(Round1Choice.MEDIATE)
    assert len(plan.events) == 1
    assert plan.events[0].event_type == "MEETING"
    assert plan.events[0].participant_agent_ids == ("a", "b")
    assert plan.injections == {}


def test_round1_watch_adds_nothing():
    plan = _round1(Round1Choice.WATCH)
    assert plan.events == ()
    assert plan.injections == {}


def test_leave_declaration_is_high_impact_meeting_with_whole_team():
    event = build_leave_declaration_event(tick=3, roster=ROSTER, location_id=LOCATION)
    assert event.event_type == "MEETING"
    assert event.participant_agent_ids == ROSTER.all_agent_ids
    assert event.importance == 80


# ─── Round 2 ────────────────────────────────────────────────────────────────


def test_round2_trigger_is_group_project_with_whole_team():
    event = build_round2_trigger_event(tick=4, roster=ROSTER, location_id=LOCATION)
    assert event.event_type == "GROUP_PROJECT"
    assert event.participant_agent_ids == ROSTER.all_agent_ids


def _round2(choice):
    return plan_round2_choice(ticks=[5, 6], choice=choice, roster=ROSTER, location_id=LOCATION)


def test_persuade_leaver_injects_conversation_on_each_remaining_tick():
    plan = _round2(Round2Choice.PERSUADE_LEAVER)
    assert plan.events == ()
    assert set(plan.injections) == {(5, "c"), (6, "c")}
    assert plan.injections[(5, "c")][0]["memory_type"] == "conversation"


def test_team_meeting_replaces_next_tick_with_whole_team_meeting():
    plan = _round2(Round2Choice.TEAM_MEETING)
    assert len(plan.events) == 1
    assert plan.events[0].event_type == "MEETING"
    assert plan.events[0].tick == 5
    assert plan.events[0].participant_agent_ids == ROSTER.all_agent_ids


def test_redistribute_separates_leaver_and_blamed_member():
    plan = _round2(Round2Choice.REDISTRIBUTE)
    assert {event.participant_agent_ids for event in plan.events} == {("c", "e"), ("a", "b", "d")}
    assert set(plan.injections) == {(5, "c"), (5, "d")}


def test_round2_watch_adds_nothing():
    plan = _round2(Round2Choice.WATCH)
    assert plan.events == ()
    assert plan.injections == {}


def test_round2_requires_remaining_ticks():
    with pytest.raises(ValueError):
        plan_round2_choice(ticks=[], choice=Round2Choice.WATCH, roster=ROSTER, location_id=LOCATION)


def test_intervention_texts_never_reveal_hidden_motives():
    """파악 판정이 없으므로 조정관의 개입 문구에 속사정이 들어가지 않는다."""
    secrets = [
        text
        for motive in MOTIVES.values()
        for text in (motive.grievance, motive.desired_role)
    ]
    plans = [_round1(choice) for choice in Round1Choice] + [_round2(choice) for choice in Round2Choice]
    for plan in plans:
        texts = [event.description for event in plan.events] + [
            memory["content"] for memories in plan.injections.values() for memory in memories
        ]
        for text in texts:
            assert not any(secret in text for secret in secrets)


@pytest.mark.parametrize("choice", list(Round1Choice))
def test_round1_choices_never_script_agent_actions(choice):
    plan = _round1(choice)
    for memories in plan.injections.values():
        for memory in memories:
            assert "action_type" not in memory


@pytest.mark.parametrize("choice", list(Round2Choice))
def test_round2_choices_never_script_agent_actions(choice):
    plan = _round2(choice)
    for memories in plan.injections.values():
        for memory in memories:
            assert "action_type" not in memory


# ─── Round 3 ────────────────────────────────────────────────────────────────


def test_round3_incident_draw_is_reproducible_and_registered():
    first = draw_round3_incident_subtype(random.Random(7))
    assert first == draw_round3_incident_subtype(random.Random(7))
    assert first in ROUND3_INCIDENT_SUBTYPES


@pytest.mark.parametrize("subtype", ROUND3_INCIDENT_SUBTYPES)
def test_round3_incident_event_uses_registered_subtype(subtype):
    event = build_round3_incident_event(
        tick=7, event_subtype=subtype, participant_agent_ids=["a", "b"], location_id="hall"
    )
    assert event.event_type == "RANDOM_INCIDENT"
    assert event.event_subtype == subtype


def test_round3_incident_event_rejects_unregistered_subtype():
    with pytest.raises(ValueError):
        build_round3_incident_event(
            tick=7, event_subtype="UNKNOWN", participant_agent_ids=["a"], location_id="hall"
        )


def test_final_preparation_includes_whole_team():
    event = build_final_preparation_event(tick=9, roster=ROSTER, location_id=LOCATION)
    assert event.event_type == "GROUP_PROJECT"
    assert event.participant_agent_ids == ROSTER.all_agent_ids


def test_only_avoid_counts_as_skipping_final_preparation():
    assert not joined_final_preparation(ActionType.AVOID)
    assert joined_final_preparation(ActionType.PARTICIPATE_EVENT)
    assert joined_final_preparation(ActionType.TALK)
