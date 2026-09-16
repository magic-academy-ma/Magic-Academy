"""도전과제 모드 — Round 1~3 진행 컨트롤러.

docs/04-feature-specs/challenge-mode-team-revival.md §4: Round1 갈등 트리거와
선택지별 강제 조치, Round2 과로 대응 선택지, Round3 돌발 사건 강제 주입을
순수 함수로 조립한다. 실제 Tick 실행 연동(별도 통합 작업)은 이 모듈 범위 밖.
"""

from uuid import UUID

import pytest

from app.simulation.challenge.controller import (
    ROUND3_INCIDENT_SUBTYPES,
    Round1Choice,
    Round2Choice,
    build_round1_trigger_event,
    build_round3_incident_event,
    plan_round1_choice_events,
    plan_round2_group_project_participants,
    plan_round2_llm_overrides,
)
from tests.test_agent_runtime_graph import make_runtime_input


AGENT_A, AGENT_B, AGENT_C, AGENT_D, AGENT_E = "a", "b", "c", "d", "e"


# ─── Round 1 ────────────────────────────────────────────────────────────────


def test_round1_trigger_event_is_high_impact_group_project_between_a_and_b():
    event = build_round1_trigger_event(
        tick=1, agent_a_id=AGENT_A, agent_b_id=AGENT_B, location_id="classroom"
    )
    assert event.event_type == "GROUP_PROJECT"
    assert event.participant_agent_ids == (AGENT_A, AGENT_B)
    assert event.importance == 80  # HIGH -> Reflection 대상


def test_reassign_roles_splits_a_and_b_into_separate_group_projects():
    events = plan_round1_choice_events(
        tick=1,
        choice=Round1Choice.REASSIGN_ROLES,
        agent_a_id=AGENT_A,
        agent_b_id=AGENT_B,
        agent_c_id=AGENT_C,
        agent_d_id=AGENT_D,
        location_id="classroom",
    )
    assert len(events) == 2
    participant_sets = {event.participant_agent_ids for event in events}
    assert participant_sets == {(AGENT_A, AGENT_C), (AGENT_B, AGENT_D)}


def test_force_meeting_creates_single_meeting_event_between_a_and_b():
    events = plan_round1_choice_events(
        tick=1,
        choice=Round1Choice.FORCE_MEETING,
        agent_a_id=AGENT_A,
        agent_b_id=AGENT_B,
        agent_c_id=AGENT_C,
        agent_d_id=AGENT_D,
        location_id="classroom",
    )
    assert len(events) == 1
    assert events[0].event_type == "MEETING"
    assert events[0].participant_agent_ids == (AGENT_A, AGENT_B)


def test_let_agents_resolve_injects_no_additional_events():
    events = plan_round1_choice_events(
        tick=1,
        choice=Round1Choice.LET_AGENTS_RESOLVE,
        agent_a_id=AGENT_A,
        agent_b_id=AGENT_B,
        agent_c_id=AGENT_C,
        agent_d_id=AGENT_D,
        location_id="classroom",
    )
    assert events == []


# ─── Round 2 ────────────────────────────────────────────────────────────────


def test_let_rest_overrides_target_agent_action_for_this_tick_only():
    runtime_input = make_runtime_input()  # tick_number=3
    overrides = plan_round2_llm_overrides(
        tick=3, target_agent_id=runtime_input.agent.agent_id, choice=Round2Choice.LET_REST
    )
    key = (3, runtime_input.agent.agent_id)
    assert key in overrides

    response = overrides[key](runtime_input)
    assert response["action_type"] == "REST"
    assert response["target_location_id"] == str(runtime_input.agent.current_location_id)


@pytest.mark.parametrize("choice", [Round2Choice.REASSIGN_WORKLOAD, Round2Choice.PUSH_THROUGH])
def test_non_rest_choices_produce_no_overrides(choice):
    overrides = plan_round2_llm_overrides(
        tick=3, target_agent_id=UUID(int=1), choice=choice
    )
    assert overrides == {}


def test_reassign_workload_swaps_target_agent_for_replacement():
    participants = plan_round2_group_project_participants(
        original_participants=[AGENT_C, AGENT_A],
        target_agent_id=AGENT_C,
        replacement_agent_id=AGENT_E,
        choice=Round2Choice.REASSIGN_WORKLOAD,
    )
    assert participants == (AGENT_E, AGENT_A)


@pytest.mark.parametrize("choice", [Round2Choice.LET_REST, Round2Choice.PUSH_THROUGH])
def test_other_choices_leave_group_project_participants_unchanged(choice):
    participants = plan_round2_group_project_participants(
        original_participants=[AGENT_C, AGENT_A],
        target_agent_id=AGENT_C,
        replacement_agent_id=AGENT_E,
        choice=choice,
    )
    assert participants == (AGENT_C, AGENT_A)


# ─── Round 3 ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("subtype", ROUND3_INCIDENT_SUBTYPES)
def test_round3_incident_event_uses_registered_subtype(subtype):
    event = build_round3_incident_event(
        tick=7, event_subtype=subtype, participant_agent_ids=[AGENT_A, AGENT_B], location_id="hall"
    )
    assert event.event_type == "RANDOM_INCIDENT"
    assert event.event_subtype == subtype


def test_round3_incident_event_rejects_unregistered_subtype():
    with pytest.raises(ValueError):
        build_round3_incident_event(
            tick=7, event_subtype="UNKNOWN", participant_agent_ids=[AGENT_A], location_id="hall"
        )
