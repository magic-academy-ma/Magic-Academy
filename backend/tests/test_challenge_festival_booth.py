"""도전과제 2 — 축제 부스 운영하기.

docs/04-feature-specs/challenge-mode-festival-booth.md: Tick별 강제 Event,
컨셉 → 돌발 subtype 매핑, R2 갈등 쌍 선정, R3 T3 대응 선택지별 강제 조치,
부스 성과 집계와 엔딩 판정을 검증한다.
"""

import random
from uuid import UUID

import pytest

from app.simulation.agent_runtime import ReactionValence
from app.simulation.challenge.evaluation import ChallengeEnding
from app.simulation.challenge.festival_booth import (
    BOOTH_PERFORMANCE_STEP,
    BOOTH_PERFORMANCE_THRESHOLD,
    CONCEPT_INCIDENT_SUBTYPES,
    FESTIVAL_STRESS_LIMIT,
    BoothConcept,
    IncidentResponse,
    build_budget_rumor_event,
    build_concept_meeting_event,
    build_festival_incident_event,
    build_opening_event,
    build_role_conflict_event,
    calculate_booth_performance,
    evaluate_festival_ending,
    plan_final_tick_events,
    plan_final_tick_llm_overrides,
    select_conflict_pair,
    select_rest_target,
)
from app.simulation.event_master import EventMaster
from app.simulation.policy.models import AgentSnapshot
from app.simulation.policy.registries.event_policy import build_event_effect_candidates
from tests.test_agent_runtime_graph import make_runtime_input

AGENTS = ("a", "b", "c", "d", "e")


def _snapshot(agent_id: str) -> AgentSnapshot:
    return AgentSnapshot(
        agent_id=agent_id, hunger=10, fatigue=10, stress=10, satisfaction=50, mood=0
    )


# ─── Round 1 ────────────────────────────────────────────────────────────────


def test_budget_rumor_is_random_incident_with_all_members():
    event = build_budget_rumor_event(tick=2, agent_ids=AGENTS, location_id="clubroom")
    assert event.event_type == "RANDOM_INCIDENT"
    assert event.event_subtype == "BUDGET_RUMOR"
    assert event.participant_agent_ids == AGENTS


def test_concept_meeting_carries_selected_concept():
    event = build_concept_meeting_event(
        tick=3, concept=BoothConcept.FOOD, agent_ids=AGENTS, location_id="clubroom"
    )
    assert event.event_type == "MEETING"
    assert "먹거리" in event.title
    assert "먹거리" in event.description


# ─── Round 2 ────────────────────────────────────────────────────────────────


def test_conflict_pair_is_lowest_mutual_affection_pair():
    affections = {("a", "c"): -10, ("c", "a"): -5, ("b", "d"): -12, ("d", "b"): 20}
    pair = select_conflict_pair(
        agent_ids=AGENTS, directional_affections=affections, rng=random.Random(0)
    )
    assert pair == ("a", "c")


def test_conflict_pair_tie_is_broken_by_seeded_rng():
    affections = {("a", "b"): -10, ("c", "d"): -10}
    picks = {
        select_conflict_pair(
            agent_ids=AGENTS, directional_affections=affections, rng=random.Random(seed)
        )
        for seed in range(30)
    }
    assert picks == {("a", "b"), ("c", "d")}
    # 같은 시드는 항상 같은 결과 (replay 재현성)
    first = select_conflict_pair(
        agent_ids=AGENTS, directional_affections=affections, rng=random.Random(7)
    )
    second = select_conflict_pair(
        agent_ids=AGENTS, directional_affections=affections, rng=random.Random(7)
    )
    assert first == second


def test_role_conflict_event_is_high_impact_group_project_for_pair_only():
    event = build_role_conflict_event(
        tick=5, concept=BoothConcept.EXHIBITION, conflict_pair=("c", "a"), location_id="clubroom"
    )
    assert event.event_type == "GROUP_PROJECT"
    assert event.participant_agent_ids == ("a", "c")
    assert event.importance == 80


# ─── Round 3 ────────────────────────────────────────────────────────────────


def test_opening_event_is_festival():
    event = build_opening_event(
        tick=7, concept=BoothConcept.FOOD, agent_ids=AGENTS, location_id="plaza"
    )
    assert event.event_type == "FESTIVAL"
    assert event.participant_agent_ids == AGENTS


@pytest.mark.parametrize("concept", list(BoothConcept))
def test_incident_subtype_follows_concept(concept):
    event = build_festival_incident_event(
        tick=8, concept=concept, agent_ids=AGENTS, location_id="plaza"
    )
    assert event.event_type == "RANDOM_INCIDENT"
    assert event.event_subtype == CONCEPT_INCIDENT_SUBTYPES[concept]


def test_rest_target_is_highest_stress_plus_fatigue():
    states = {"a": (30, 30), "b": (50, 40), "c": (60, 20)}
    assert select_rest_target(states) == "b"


def test_emergency_meeting_replaces_festival_with_all_member_meeting():
    events = plan_final_tick_events(
        tick=9,
        choice=IncidentResponse.EMERGENCY_MEETING,
        concept=BoothConcept.FOOD,
        agent_ids=AGENTS,
        location_id="plaza",
    )
    assert [event.event_type for event in events] == ["MEETING"]
    assert events[0].participant_agent_ids == AGENTS


def test_rotate_rest_excludes_target_from_festival():
    events = plan_final_tick_events(
        tick=9,
        choice=IncidentResponse.ROTATE_REST,
        concept=BoothConcept.FOOD,
        agent_ids=AGENTS,
        location_id="plaza",
        rest_target_agent_id="c",
    )
    assert [event.event_type for event in events] == ["FESTIVAL"]
    assert events[0].participant_agent_ids == ("a", "b", "d", "e")


def test_push_through_keeps_all_members_in_festival():
    events = plan_final_tick_events(
        tick=9,
        choice=IncidentResponse.PUSH_THROUGH,
        concept=BoothConcept.FOOD,
        agent_ids=AGENTS,
        location_id="plaza",
    )
    assert events[0].event_type == "FESTIVAL"
    assert events[0].participant_agent_ids == AGENTS


def test_rotate_rest_overrides_target_action_to_rest():
    runtime_input = make_runtime_input()
    overrides = plan_final_tick_llm_overrides(
        tick=9,
        choice=IncidentResponse.ROTATE_REST,
        rest_target_agent_id=runtime_input.agent.agent_id,
    )
    response = overrides[(9, runtime_input.agent.agent_id)](runtime_input)
    assert response["action_type"] == "REST"


@pytest.mark.parametrize(
    "choice", [IncidentResponse.EMERGENCY_MEETING, IncidentResponse.PUSH_THROUGH]
)
def test_other_responses_produce_no_overrides(choice):
    assert plan_final_tick_llm_overrides(tick=9, choice=choice, rest_target_agent_id=UUID(int=1)) == {}


def test_rotate_rest_requires_target():
    with pytest.raises(ValueError):
        plan_final_tick_llm_overrides(tick=9, choice=IncidentResponse.ROTATE_REST)


# ─── Registry ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("subtype", "metric"),
    [
        ("BUDGET_RUMOR", "stress"),
        ("INGREDIENT_SHORTAGE", "stress"),
        ("CUSTOMER_RUSH", "fatigue"),
        ("RIVAL_BOOTH_ISSUE", "stress"),
    ],
)
def test_festival_incident_subtypes_apply_medium_tier(subtype, metric):
    event = EventMaster().build_random_incident(
        tick=1, event_subtype=subtype, participant_agent_ids=["s1"], location_id="plaza"
    )
    candidates = build_event_effect_candidates(
        event, run_id="run-1", agent_snapshots={"s1": _snapshot("s1")}
    )
    assert [(c.metric, c.delta) for c in candidates] == [(metric, 5)]


# ─── 성과·엔딩 ───────────────────────────────────────────────────────────────


def test_booth_performance_counts_only_group_project_and_festival():
    valences = [
        ("MEETING", ReactionValence.POSITIVE),
        ("RANDOM_INCIDENT", ReactionValence.POSITIVE),
        ("GROUP_PROJECT", ReactionValence.POSITIVE),
        ("festival", ReactionValence.POSITIVE),
        ("FESTIVAL", ReactionValence.NEGATIVE),
    ]
    assert calculate_booth_performance(valences) == BOOTH_PERFORMANCE_STEP


def _ending(**overrides):
    kwargs = {
        "booth_performance": BOOTH_PERFORMANCE_THRESHOLD,
        "directional_affections": [10, 5],
        "agent_stress_levels": [10, 20],
        "initial_satisfaction_levels": [50, 50],
        "final_satisfaction_levels": [60, 55],
    }
    kwargs.update(overrides)
    return evaluate_festival_ending(**kwargs)


def test_perfect_when_all_conditions_met():
    assert _ending() == ChallengeEnding.PERFECT


def test_normal_when_satisfaction_did_not_rise():
    assert _ending(final_satisfaction_levels=[50, 50]) == ChallengeEnding.NORMAL


def test_normal_when_relationships_negative():
    assert _ending(directional_affections=[-10, -5]) == ChallengeEnding.NORMAL


def test_bad_when_performance_below_threshold():
    assert _ending(booth_performance=BOOTH_PERFORMANCE_THRESHOLD - 1) == ChallengeEnding.BAD


def test_bad_when_someone_burns_out():
    assert _ending(agent_stress_levels=[10, FESTIVAL_STRESS_LIMIT]) == ChallengeEnding.BAD
