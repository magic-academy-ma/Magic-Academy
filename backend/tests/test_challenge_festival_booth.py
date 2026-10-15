"""스토리모드 CHAPTER 4 — 축제 부스 운영하기.

docs/04-feature-specs/challenge-mode-festival-booth.md: 9 Tick 계획, 개입 ①~③의
조치(Event 주입·정보 주입·일정 변경만 사용), 돌발 후보 풀 시드 추첨, 갈등 쌍 선정,
부스 공백 Tick, 부스 성과, 엔딩·챕터 기록·업적 판정을 검증한다.
"""

import random

import pytest

from app.simulation.agent_runtime import ActionType, ReactionValence
from app.simulation.challenge import festival_booth
from app.simulation.challenge.festival_booth import (
    BLAME_TICK,
    BOOTH_PERFORMANCE_STEP,
    BOOTH_PERFORMANCE_THRESHOLD,
    BOOTH_VACANCY_LIMIT,
    BOOTH_VACANCY_PENALTY,
    CLOSING_TICK,
    CONCEPT_INCIDENT_POOLS,
    FESTIVAL_STRESS_LIMIT,
    INCIDENT_FOLLOWUP_TICK,
    INCIDENT_TICK,
    OPENING_TICK,
    OPERATION_TICKS,
    POST_SETUP_TICKS,
    BoothConcept,
    BoothInterventionPlan,
    BoothRole,
    BoothStaffingRecord,
    FestivalAchievement,
    FestivalEnding,
    IncidentResponse,
    StaffingAdjustment,
    build_blame_event,
    build_festival_incident_event,
    build_festival_record,
    build_opening_event,
    build_planning_meeting_event,
    build_preparation_event,
    build_rehearsal_event,
    build_second_day_event,
    calculate_booth_performance,
    count_vacant_ticks,
    draw_festival_incident_subtype,
    evaluate_festival_achievements,
    evaluate_festival_ending,
    plan_booth_setup,
    plan_incident_response,
    plan_staffing_adjustment,
    record_booth_staffing,
    select_conflict_pair,
    select_rest_target,
    setup_choice,
    swap_conflict_roles,
)
from app.simulation.challenge.record import ChapterGrade, InterventionRecord
from app.simulation.event_master import EventMaster
from app.simulation.policy.models import AgentSnapshot
from app.simulation.policy.registries.event_policy import (
    RANDOM_INCIDENT_EFFECTS,
    build_event_effect_candidates,
)

AGENTS = ("a", "b", "c", "d", "e")
PLAZA = "plaza"
ROLES = {
    "a": BoothRole.COUNTER,
    "b": BoothRole.COUNTER,
    "c": BoothRole.PRODUCTION,
    "d": BoothRole.SUPPLY,
    "e": BoothRole.PROMOTION,
}
STATES = {agent_id: (10, 10) for agent_id in AGENTS} | {"c": (60, 30)}


def _snapshot(agent_id: str) -> AgentSnapshot:
    return AgentSnapshot(
        agent_id=agent_id, hunger=10, fatigue=10, stress=10, satisfaction=50, mood=0
    )


def _contents(injections, key):
    return [memory["content"] for memory in injections.get(key, [])]


# ─── 9 Tick 계획 ─────────────────────────────────────────────────────────────


def test_nine_tick_plan_has_planning_preparation_and_two_operation_days():
    concept = BoothConcept.FOOD
    subtype = draw_festival_incident_subtype(concept, random.Random(0))
    incident = plan_incident_response(
        choice=IncidentResponse.WATCH,
        incident_subtype=subtype,
        concept=concept,
        agent_ids=AGENTS,
        location_id=PLAZA,
    )
    closing = plan_staffing_adjustment(
        choice=StaffingAdjustment.WATCH,
        concept=concept,
        agent_ids=AGENTS,
        location_id=PLAZA,
        conflict_pair=("a", "c"),
        roles=None,
        agent_states=STATES,
        rng=random.Random(0),
    )
    common = {"concept": concept, "agent_ids": AGENTS, "location_id": PLAZA}
    events = [
        build_planning_meeting_event(agent_ids=AGENTS, location_id=PLAZA),
        build_preparation_event(**common),
        build_rehearsal_event(**common),
        build_opening_event(**common),
        build_festival_incident_event(event_subtype=subtype, **common),
        *incident.events,
        build_second_day_event(**common),
        build_blame_event(concept=concept, conflict_pair=("a", "c"), location_id=PLAZA),
        *closing.events,
    ]
    assert [event.tick for event in events] == list(range(1, 10))
    assert [event.event_type for event in events] == [
        "MEETING",
        "GROUP_PROJECT",
        "GROUP_PROJECT",
        "FESTIVAL",
        "RANDOM_INCIDENT",
        "FESTIVAL",
        "FESTIVAL",
        "GROUP_PROJECT",
        "FESTIVAL",
    ]
    assert OPERATION_TICKS == (4, 5, 6, 7, 8, 9)


def test_concept_is_carried_in_event_description_after_setup():
    event = build_preparation_event(
        concept=BoothConcept.EXHIBITION, agent_ids=AGENTS, location_id=PLAZA
    )
    assert "전시형" in event.description


# ─── 개입 ① 컨셉·역할 배정 ───────────────────────────────────────────────────


def test_role_assignment_injects_own_role_notice_every_tick_after_setup():
    plan = plan_booth_setup(concept=BoothConcept.FOOD, agent_ids=AGENTS, roles=ROLES)
    assert plan.events == ()
    assert plan.roles == ROLES
    assert set(plan.injections) == {(tick, agent_id) for tick in POST_SETUP_TICKS for agent_id in AGENTS}
    assert "SUPPLY" in _contents(plan.injections, (2, "d"))[0]
    assert "COUNTER" in _contents(plan.injections, (9, "a"))[0]


def test_skipping_role_assignment_is_watch_without_notice():
    plan = plan_booth_setup(concept=BoothConcept.FOOD, agent_ids=AGENTS, roles=None)
    assert plan == BoothInterventionPlan()
    assert setup_choice(None) == "WATCH"
    assert setup_choice(ROLES) == "ASSIGN_ROLES"


def test_role_assignment_must_cover_every_agent():
    with pytest.raises(ValueError):
        plan_booth_setup(
            concept=BoothConcept.FOOD, agent_ids=AGENTS, roles={"a": BoothRole.COUNTER}
        )


# ─── 돌발 후보 풀 ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("concept", list(BoothConcept))
def test_incident_is_drawn_from_concept_pool(concept):
    picks = {draw_festival_incident_subtype(concept, random.Random(seed)) for seed in range(40)}
    assert picks == set(CONCEPT_INCIDENT_POOLS[concept])


@pytest.mark.parametrize("concept", list(BoothConcept))
def test_incident_draw_is_reproducible_with_same_seed(concept):
    first = [draw_festival_incident_subtype(concept, random.Random(seed)) for seed in range(10)]
    second = [draw_festival_incident_subtype(concept, random.Random(seed)) for seed in range(10)]
    assert first == second


def test_incident_event_rejects_subtype_outside_concept_pool():
    with pytest.raises(ValueError):
        build_festival_incident_event(
            event_subtype="RIVAL_BOOTH_ISSUE",
            concept=BoothConcept.FOOD,
            agent_ids=AGENTS,
            location_id=PLAZA,
        )


def test_incident_event_is_random_incident_at_r2_t2():
    event = build_festival_incident_event(
        event_subtype="CUSTOMER_RUSH",
        concept=BoothConcept.EXPERIENCE,
        agent_ids=AGENTS,
        location_id=PLAZA,
    )
    assert event.tick == INCIDENT_TICK
    assert event.event_type == "RANDOM_INCIDENT"
    assert event.event_subtype == "CUSTOMER_RUSH"


# ─── 개입 ② 돌발 대응 ───────────────────────────────────────────────────────


def _incident(choice, **kwargs):
    return plan_incident_response(
        choice=choice,
        incident_subtype="INGREDIENT_SHORTAGE",
        concept=BoothConcept.FOOD,
        agent_ids=AGENTS,
        location_id=PLAZA,
        **kwargs,
    )


def test_send_help_with_target_keeps_festival_and_relaxes_target_schedule():
    plan = _incident(IncidentResponse.SEND_HELP, help_agent_id="d")
    assert [event.event_type for event in plan.events] == ["FESTIVAL"]
    assert plan.events[0].participant_agent_ids == AGENTS
    assert plan.events[0].tick == INCIDENT_FOLLOWUP_TICK
    assert plan.non_mandatory_agent_ids == {"d"}
    assert list(plan.injections) == [(INCIDENT_FOLLOWUP_TICK, "d")]
    assert "재료 부족" in _contents(plan.injections, (6, "d"))[0]


def test_send_help_without_target_notifies_everyone_and_keeps_schedules():
    plan = _incident(IncidentResponse.SEND_HELP)
    assert plan.events[0].participant_agent_ids == AGENTS
    assert plan.non_mandatory_agent_ids == frozenset()
    assert set(plan.injections) == {(6, agent_id) for agent_id in AGENTS}


def test_send_help_target_must_be_booth_member():
    with pytest.raises(ValueError):
        _incident(IncidentResponse.SEND_HELP, help_agent_id="z")


def test_help_target_only_allowed_for_send_help():
    with pytest.raises(ValueError):
        _incident(IncidentResponse.KEEP_BOOTH, help_agent_id="d")


def test_keep_booth_notifies_all_and_keeps_full_festival():
    plan = _incident(IncidentResponse.KEEP_BOOTH)
    assert plan.events[0].event_type == "FESTIVAL"
    assert plan.events[0].participant_agent_ids == AGENTS
    assert set(plan.injections) == {(6, agent_id) for agent_id in AGENTS}
    assert plan.non_mandatory_agent_ids == frozenset()


def test_emergency_meeting_replaces_festival_with_all_member_meeting():
    plan = _incident(IncidentResponse.EMERGENCY_MEETING)
    assert [event.event_type for event in plan.events] == ["MEETING"]
    assert plan.events[0].participant_agent_ids == AGENTS
    assert plan.injections == {}


def test_incident_watch_runs_plain_festival():
    plan = _incident(IncidentResponse.WATCH)
    assert plan.events[0].event_type == "FESTIVAL"
    assert plan.injections == {}
    assert plan.non_mandatory_agent_ids == frozenset()


# ─── R3 T2 책임 공방 ────────────────────────────────────────────────────────


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
    first = select_conflict_pair(
        agent_ids=AGENTS, directional_affections=affections, rng=random.Random(7)
    )
    second = select_conflict_pair(
        agent_ids=AGENTS, directional_affections=affections, rng=random.Random(7)
    )
    assert first == second


def test_blame_event_is_high_impact_group_project_for_pair_only():
    event = build_blame_event(
        concept=BoothConcept.EXHIBITION, conflict_pair=("c", "a"), location_id=PLAZA
    )
    assert event.tick == BLAME_TICK
    assert event.event_type == "GROUP_PROJECT"
    assert event.participant_agent_ids == ("a", "c")
    assert event.importance == 80


# ─── 개입 ③ 인력 조정 ───────────────────────────────────────────────────────


def _staffing(choice, roles=ROLES, pair=("a", "c"), seed=0):
    return plan_staffing_adjustment(
        choice=choice,
        concept=BoothConcept.FOOD,
        agent_ids=AGENTS,
        location_id=PLAZA,
        conflict_pair=pair,
        roles=roles,
        agent_states=STATES,
        rng=random.Random(seed),
    )


def test_rest_target_is_highest_stress_plus_fatigue():
    states = {"a": (30, 30), "b": (50, 40), "c": (60, 20)}
    assert select_rest_target(states) == "b"


def test_suggest_rest_notifies_target_and_relaxes_schedule_only():
    plan = _staffing(StaffingAdjustment.SUGGEST_REST)
    assert [event.event_type for event in plan.events] == ["FESTIVAL"]
    assert plan.events[0].tick == CLOSING_TICK
    assert plan.events[0].participant_agent_ids == AGENTS
    assert plan.non_mandatory_agent_ids == {"c"}
    assert list(plan.injections) == [(CLOSING_TICK, "c")]


def test_swap_roles_exchanges_conflict_pair_roles():
    plan = _staffing(StaffingAdjustment.SWAP_ROLES)
    assert plan.roles["a"] == BoothRole.PRODUCTION
    assert plan.roles["c"] == BoothRole.COUNTER
    assert set(plan.injections) == {(9, "a"), (9, "c")}
    assert "PRODUCTION" in _contents(plan.injections, (9, "a"))[0]
    assert plan.non_mandatory_agent_ids == frozenset()


def test_swap_roles_moves_one_to_promotion_when_roles_are_same():
    changes = swap_conflict_roles(roles=ROLES, conflict_pair=("a", "b"), rng=random.Random(0))
    assert len(changes) == 1
    assert list(changes.values()) == [BoothRole.PROMOTION]


def test_swap_roles_moves_promotion_to_counter_when_both_promotion():
    roles = ROLES | {"a": BoothRole.PROMOTION}
    changes = swap_conflict_roles(roles=roles, conflict_pair=("a", "e"), rng=random.Random(0))
    assert list(changes.values()) == [BoothRole.COUNTER]


def test_swap_roles_without_assignment_moves_one_to_promotion():
    plan = _staffing(StaffingAdjustment.SWAP_ROLES, roles=None)
    assert plan.roles is None
    assert len(plan.injections) == 1
    assert "PROMOTION" in next(iter(plan.injections.values()))[0]["content"]
    picks = {
        next(iter(swap_conflict_roles(roles=None, conflict_pair=("a", "c"), rng=random.Random(s))))
        for s in range(20)
    }
    assert picks == {"a", "c"}


def test_mediate_injects_conversation_memory_to_pair():
    plan = _staffing(StaffingAdjustment.MEDIATE)
    assert plan.events[0].participant_agent_ids == AGENTS
    assert set(plan.injections) == {(9, "a"), (9, "c")}
    assert plan.injections[(9, "a")][0]["memory_type"] == "conversation"


def test_staffing_watch_runs_plain_festival():
    plan = _staffing(StaffingAdjustment.WATCH)
    assert plan.events[0].event_type == "FESTIVAL"
    assert plan.injections == {}
    assert plan.roles == ROLES


# ─── 행동 지정 없음 ─────────────────────────────────────────────────────────


def _all_plans():
    plans = [plan_booth_setup(concept=BoothConcept.FOOD, agent_ids=AGENTS, roles=ROLES)]
    plans += [_incident(choice) for choice in IncidentResponse]
    plans.append(_incident(IncidentResponse.SEND_HELP, help_agent_id="d"))
    plans += [_staffing(choice) for choice in StaffingAdjustment]
    return plans


def test_every_choice_uses_only_events_injections_and_schedule_changes():
    for plan in _all_plans():
        assert isinstance(plan, BoothInterventionPlan)
        for memories in plan.injections.values():
            for memory in memories:
                assert set(memory) == {
                    "id", "content", "memory_type", "importance", "created_tick", "event_id"
                }
                assert memory["memory_type"] in {"observation", "conversation"}


def test_no_forced_action_paths_remain():
    assert not hasattr(festival_booth, "_build_forced_rest_response")
    assert not hasattr(festival_booth, "plan_final_tick_llm_overrides")
    assert "BUDGET_RUMOR" not in RANDOM_INCIDENT_EFFECTS


# ─── Registry ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("subtype", "metric"),
    [
        ("INGREDIENT_SHORTAGE", "stress"),
        ("CUSTOMER_RUSH", "fatigue"),
        ("RIVAL_BOOTH_ISSUE", "stress"),
    ],
)
def test_festival_incident_subtypes_apply_medium_tier(subtype, metric):
    event = EventMaster().build_random_incident(
        tick=1, event_subtype=subtype, participant_agent_ids=["s1"], location_id=PLAZA
    )
    candidates = build_event_effect_candidates(
        event, run_id="run-1", agent_snapshots={"s1": _snapshot("s1")}
    )
    assert [(c.metric, c.delta) for c in candidates] == [(metric, 5)]


# ─── 부스 공백 Tick ─────────────────────────────────────────────────────────


def test_festival_tick_counts_non_avoid_participants():
    record = record_booth_staffing(
        tick=OPENING_TICK,
        event_type="FESTIVAL",
        action_types={"a": ActionType.PARTICIPATE_EVENT, "b": ActionType.AVOID, "c": ActionType.HELP},
    )
    assert record == BoothStaffingRecord(tick=4, staff_count=2, vacant=False)


def test_festival_tick_with_everyone_avoiding_is_vacant():
    record = record_booth_staffing(
        tick=CLOSING_TICK,
        event_type="festival",
        action_types={agent_id: ActionType.AVOID for agent_id in AGENTS},
    )
    assert record.vacant
    assert record.staff_count == 0


def test_meeting_replacing_operation_tick_is_vacant():
    record = record_booth_staffing(
        tick=INCIDENT_FOLLOWUP_TICK,
        event_type="MEETING",
        action_types={agent_id: ActionType.PARTICIPATE_EVENT for agent_id in AGENTS},
    )
    assert record.vacant


@pytest.mark.parametrize(
    ("tick", "event_type"),
    [(1, "MEETING"), (2, "GROUP_PROJECT"), (INCIDENT_TICK, "RANDOM_INCIDENT"), (BLAME_TICK, "GROUP_PROJECT")],
)
def test_non_booth_ticks_are_not_recorded(tick, event_type):
    assert record_booth_staffing(tick=tick, event_type=event_type, action_types={}) is None


def test_count_vacant_ticks():
    records = [
        BoothStaffingRecord(tick=4, staff_count=3, vacant=False),
        BoothStaffingRecord(tick=6, staff_count=0, vacant=True),
        BoothStaffingRecord(tick=9, staff_count=0, vacant=True),
    ]
    assert count_vacant_ticks(records) == 2


# ─── booth_performance ──────────────────────────────────────────────────────


def test_booth_performance_counts_preparation_and_operation_festival_only():
    valences = [
        (1, "MEETING", ReactionValence.POSITIVE),
        (2, "GROUP_PROJECT", ReactionValence.POSITIVE),
        (3, "group_project", ReactionValence.POSITIVE),
        (5, "RANDOM_INCIDENT", ReactionValence.POSITIVE),
        (6, "MEETING", ReactionValence.POSITIVE),
        (7, "FESTIVAL", ReactionValence.POSITIVE),
        (8, "GROUP_PROJECT", ReactionValence.POSITIVE),
        (9, "FESTIVAL", ReactionValence.NEGATIVE),
    ]
    assert calculate_booth_performance(valences, vacant_tick_count=0) == 2 * BOOTH_PERFORMANCE_STEP


def test_vacant_ticks_lower_booth_performance():
    valences = [(tick, "FESTIVAL", ReactionValence.POSITIVE) for tick in (4, 7, 9)]
    full = calculate_booth_performance(valences, vacant_tick_count=0)
    assert calculate_booth_performance(valences, vacant_tick_count=1) == full - BOOTH_VACANCY_PENALTY
    assert calculate_booth_performance([], vacant_tick_count=3) == 0


# ─── 엔딩·챕터 기록 ─────────────────────────────────────────────────────────


def _ending(**overrides):
    kwargs = {
        "booth_performance": BOOTH_PERFORMANCE_THRESHOLD,
        "vacant_tick_count": 0,
        "directional_affections": [10, 5],
        "agent_stress_levels": [10, 20],
        "initial_satisfaction_levels": [50, 50],
        "final_satisfaction_levels": [60, 55],
    }
    kwargs.update(overrides)
    return evaluate_festival_ending(**kwargs)


def test_popular_when_all_conditions_met():
    assert _ending() == FestivalEnding.POPULAR


def test_halted_when_performance_below_threshold():
    assert _ending(booth_performance=BOOTH_PERFORMANCE_THRESHOLD - 1) == FestivalEnding.HALTED


def test_halted_when_vacancies_exceed_limit():
    assert _ending(vacant_tick_count=BOOTH_VACANCY_LIMIT + 1) == FestivalEnding.HALTED
    assert _ending(vacant_tick_count=BOOTH_VACANCY_LIMIT) == FestivalEnding.POPULAR


def test_burnout_blocks_popular_but_does_not_halt():
    assert _ending(agent_stress_levels=[10, FESTIVAL_STRESS_LIMIT]) == FestivalEnding.COMPLETED


def test_completed_when_satisfaction_did_not_rise():
    assert _ending(final_satisfaction_levels=[50, 50]) == FestivalEnding.COMPLETED


def test_completed_when_relationships_negative():
    assert _ending(directional_affections=[-10, -5]) == FestivalEnding.COMPLETED


@pytest.mark.parametrize(
    ("ending", "grade"),
    [
        (FestivalEnding.POPULAR, ChapterGrade.GOOD),
        (FestivalEnding.COMPLETED, ChapterGrade.MIXED),
        (FestivalEnding.HALTED, ChapterGrade.BAD),
    ],
)
def test_chapter_record_grade(ending, grade):
    interventions = [InterventionRecord(point="BOOTH_SETUP", choice="WATCH", elapsed_seconds=3.0)]
    record = build_festival_record(ending=ending, interventions=interventions)
    assert record.chapter == 4
    assert record.ending == ending.value
    assert record.grade == grade
    assert record.interventions == tuple(interventions)


# ─── 업적 ───────────────────────────────────────────────────────────────────


def test_show_must_go_on_requires_no_vacancy_and_popular():
    achieved = evaluate_festival_achievements(
        ending=FestivalEnding.POPULAR, vacant_tick_count=0, peak_stress_levels=[10, 20]
    )
    assert achieved == {FestivalAchievement.SHOW_MUST_GO_ON}
    assert FestivalAchievement.SHOW_MUST_GO_ON not in evaluate_festival_achievements(
        ending=FestivalEnding.COMPLETED, vacant_tick_count=0, peak_stress_levels=[10]
    )


def test_booth_left_empty_on_any_vacancy():
    achieved = evaluate_festival_achievements(
        ending=FestivalEnding.POPULAR, vacant_tick_count=1, peak_stress_levels=[10]
    )
    assert achieved == {FestivalAchievement.BOOTH_LEFT_EMPTY}


def test_festival_is_over_when_anyone_hit_stress_limit():
    achieved = evaluate_festival_achievements(
        ending=FestivalEnding.COMPLETED,
        vacant_tick_count=0,
        peak_stress_levels=[10, FESTIVAL_STRESS_LIMIT],
    )
    assert achieved == {FestivalAchievement.FESTIVAL_IS_OVER}
