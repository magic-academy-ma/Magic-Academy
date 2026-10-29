"""스토리모드 CHAPTER 4 — 축제 부스 운영하기: 저장·진행 서비스.

docs/04-feature-specs/challenge-mode-festival-booth.md §4.3의 9 Tick 흐름을
festival_booth.py 순수 함수로 조립해 실제로 실행한다. 개입은 Tick 1·5·8 직후
세 번이고, 조치는 각각 Tick 2·6·9에 적용된다.
"""

from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import asdict
from uuid import UUID

from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import StoryChapterRun, User
from app.services.simulations import create_simulation
from app.services.story_chapter_common import (
    TOTAL_TICKS,
    StoryChapterChoiceError,
    StoryChapterCompletedError,
    agent_states,
    directional_affections,
    ensure_student_relationships,
    finish_tick,
    get_owned_chapter_run,
    record_intervention,
    run_events,
    students_and_location,
    tick_rng,
)
from app.simulation.agent_runtime import ActionType, AgentRuntime, ReactionValence
from app.simulation.challenge.festival_booth import (
    BLAME_TICK,
    CLOSING_TICK,
    CONCEPT_LABELS,
    INCIDENT_FOLLOWUP_TICK,
    INCIDENT_LABELS,
    INCIDENT_TICK,
    OPENING_TICK,
    PLANNING_TICK,
    POST_SETUP_TICKS,
    PREPARATION_TICK,
    REHEARSAL_TICK,
    ROLE_LABELS,
    SECOND_DAY_TICK,
    BoothConcept,
    BoothRole,
    BoothStaffingRecord,
    FestivalEnding,
    IncidentResponse,
    InterventionPoint,
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
    setup_choice,
)
from app.simulation.challenge.llm_override import merge_injections
from app.simulation.challenge.record import (
    ChapterRecord,
    InterventionRecord,
    chapter_achievements,
)

CHAPTER = 4
CHOICE_TICKS = {
    PREPARATION_TICK: InterventionPoint.BOOTH_SETUP,
    INCIDENT_FOLLOWUP_TICK: InterventionPoint.INCIDENT_RESPONSE,
    CLOSING_TICK: InterventionPoint.STAFFING_ADJUSTMENT,
}
ROUND_TITLES = {1: "기획·준비", 2: "별빛제 첫날", 3: "별빛제 둘째 날"}

CONCEPT_DESCRIPTIONS = {
    BoothConcept.FOOD: "먹거리를 만들어 파는 부스입니다.",
    BoothConcept.EXPERIENCE: "손님이 직접 마법을 체험하는 부스입니다.",
    BoothConcept.EXHIBITION: "학생들의 마법 작품을 전시하는 부스입니다.",
}
INCIDENT_OPTIONS = [
    (IncidentResponse.SEND_HELP, "문제 해결에 인원 투입", "부스를 잠시 떠나 문제를 처리해 달라고 부탁합니다. 한 명을 지목할 수 있습니다."),
    (IncidentResponse.KEEP_BOOTH, "부스 운영 집중", "문제는 나중에 처리하고 지금은 부스를 지키자고 알립니다."),
    (IncidentResponse.EMERGENCY_MEETING, "긴급 대책 회의", "부스를 잠시 비우고 다섯 명이 모여 대책을 세웁니다."),
    (IncidentResponse.WATCH, "지켜본다", "개입하지 않고 학생들에게 맡깁니다."),
]
STAFFING_OPTIONS = [
    (StaffingAdjustment.SUGGEST_REST, "휴식 권유", "가장 지친 학생에게 이번에는 쉬어도 된다고 말합니다."),
    (StaffingAdjustment.SWAP_ROLES, "역할 교체", "책임 공방을 벌인 두 사람의 역할을 바꿉니다."),
    (StaffingAdjustment.MEDIATE, "중재", "두 사람 사이를 중재하고 남은 운영을 함께 마무리하자고 이야기합니다."),
    (StaffingAdjustment.WATCH, "지켜본다", "개입하지 않고 학생들에게 맡깁니다."),
]


def start_festival_booth(db: Session, owner: User) -> StoryChapterRun:
    simulation = create_simulation(db, owner, "CHAPTER 4 축제 부스 운영하기")
    simulation.status = "running"
    seed = random.SystemRandom().randrange(2**62)
    students, _ = students_and_location(db, simulation.id)
    ensure_student_relationships(db, simulation.id, [student.id for student in students])
    agent_ids = [str(student.id) for student in students]
    states = agent_states(db, agent_ids)
    run = StoryChapterRun(
        id=uuid7(),
        simulation_id=simulation.id,
        chapter=CHAPTER,
        seed=seed,
        current_tick=0,
        state={
            "agent_ids": agent_ids,
            "initial_satisfaction": [states[agent_id].satisfaction for agent_id in agent_ids],
            "peak_stress": {agent_id: states[agent_id].stress for agent_id in agent_ids},
            "staffing": [],
            "performance": [],
        },
        status="in_progress",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_festival_booth(db: Session, run_id: UUID, owner: User) -> StoryChapterRun:
    return get_owned_chapter_run(db, run_id, owner, chapter=CHAPTER)


def _roles(state: Mapping) -> dict[str, BoothRole] | None:
    roles = state.get("roles")
    return None if roles is None else {agent_id: BoothRole(role) for agent_id, role in roles.items()}


def _validate(
    tick: int,
    *,
    choice: str | None,
    concept: str | None,
    roles: Mapping[str, str] | None,
    help_agent_id: str | None,
    agent_ids: list[str],
) -> None:
    point = CHOICE_TICKS.get(tick)
    if point is None:
        if choice or concept or roles or help_agent_id:
            raise StoryChapterChoiceError("this tick does not accept a choice")
        return
    try:
        if point == InterventionPoint.BOOTH_SETUP:
            if concept is None:
                raise StoryChapterChoiceError("booth setup requires a concept")
            BoothConcept(concept)
            if roles is not None:
                if set(roles) != set(agent_ids):
                    raise StoryChapterChoiceError("roles must assign every student")
                for role in roles.values():
                    BoothRole(role)
            return
        if choice is None:
            raise StoryChapterChoiceError("this tick requires a choice")
        if point == InterventionPoint.INCIDENT_RESPONSE:
            IncidentResponse(choice)
            if help_agent_id is not None and (
                choice != IncidentResponse.SEND_HELP or help_agent_id not in agent_ids
            ):
                raise StoryChapterChoiceError("invalid help target")
        else:
            StaffingAdjustment(choice)
    except ValueError as exc:
        if isinstance(exc, StoryChapterChoiceError):
            raise
        raise StoryChapterChoiceError("invalid choice for this tick") from exc


def advance_festival_booth(
    db: Session,
    *,
    run_id: UUID,
    owner: User,
    runtime: AgentRuntime,
    choice: str | None = None,
    concept: str | None = None,
    roles: Mapping[str, str] | None = None,
    help_agent_id: str | None = None,
) -> StoryChapterRun:
    run = get_owned_chapter_run(db, run_id, owner, chapter=CHAPTER, for_update=True)
    if run.status == "completed":
        raise StoryChapterCompletedError
    tick = run.current_tick + 1
    state = dict(run.state)
    agent_ids = state["agent_ids"]
    _validate(
        tick, choice=choice, concept=concept, roles=roles, help_agent_id=help_agent_id,
        agent_ids=agent_ids,
    )
    _, location = students_and_location(db, run.simulation_id)
    location_id = str(location.id)
    non_mandatory: frozenset[str] = frozenset()
    injections = {}

    if tick == PREPARATION_TICK:
        state["concept"] = concept
        state["roles"] = dict(roles) if roles is not None else None
        state["incident_subtype"] = draw_festival_incident_subtype(
            BoothConcept(concept), tick_rng(run.seed, "incident")
        )
        record_intervention(run, InterventionPoint.BOOTH_SETUP.value, setup_choice(roles))
    booth_concept = BoothConcept(state["concept"]) if "concept" in state else None

    if tick == PLANNING_TICK:
        events = [build_planning_meeting_event(agent_ids=agent_ids, location_id=location_id)]
    elif tick == PREPARATION_TICK:
        events = [build_preparation_event(concept=booth_concept, agent_ids=agent_ids, location_id=location_id)]
    elif tick == REHEARSAL_TICK:
        events = [build_rehearsal_event(concept=booth_concept, agent_ids=agent_ids, location_id=location_id)]
    elif tick == OPENING_TICK:
        events = [build_opening_event(concept=booth_concept, agent_ids=agent_ids, location_id=location_id)]
    elif tick == INCIDENT_TICK:
        events = [
            build_festival_incident_event(
                event_subtype=state["incident_subtype"],
                concept=booth_concept,
                agent_ids=agent_ids,
                location_id=location_id,
            )
        ]
    elif tick == INCIDENT_FOLLOWUP_TICK:
        record_intervention(run, InterventionPoint.INCIDENT_RESPONSE.value, choice)
        plan = plan_incident_response(
            choice=IncidentResponse(choice),
            incident_subtype=state["incident_subtype"],
            concept=booth_concept,
            agent_ids=agent_ids,
            location_id=location_id,
            help_agent_id=help_agent_id,
        )
        events, injections, non_mandatory = list(plan.events), plan.injections, plan.non_mandatory_agent_ids
    elif tick == SECOND_DAY_TICK:
        # §4.6: 갈등 쌍은 R2 종료 시점 관계로 정한다.
        state["conflict_pair"] = list(
            select_conflict_pair(
                agent_ids=agent_ids,
                directional_affections=directional_affections(db, run.simulation_id, agent_ids),
                rng=tick_rng(run.seed, "conflict_pair"),
            )
        )
        events = [build_second_day_event(concept=booth_concept, agent_ids=agent_ids, location_id=location_id)]
    elif tick == BLAME_TICK:
        events = [
            build_blame_event(
                concept=booth_concept,
                conflict_pair=tuple(state["conflict_pair"]),
                location_id=location_id,
            )
        ]
    else:
        record_intervention(run, InterventionPoint.STAFFING_ADJUSTMENT.value, choice)
        states = agent_states(db, agent_ids)
        plan = plan_staffing_adjustment(
            choice=StaffingAdjustment(choice),
            concept=booth_concept,
            agent_ids=agent_ids,
            location_id=location_id,
            conflict_pair=tuple(state["conflict_pair"]),
            roles=_roles(state),
            agent_states={a: (states[a].stress, states[a].fatigue) for a in agent_ids},
            rng=tick_rng(run.seed, "staffing"),
        )
        if plan.roles is not None:
            state["roles"] = {agent_id: role.value for agent_id, role in plan.roles.items()}
        events, injections, non_mandatory = list(plan.events), plan.injections, plan.non_mandatory_agent_ids

    if tick in POST_SETUP_TICKS and tick != CLOSING_TICK:
        # 역할 공지는 매 Tick 다시 알린다. 마무리 Tick은 인력 조정 공지가 대신한다.
        setup = plan_booth_setup(
            concept=booth_concept, agent_ids=agent_ids, roles=_roles(state), ticks=[tick]
        )
        injections = merge_injections(setup.injections, injections)

    outcomes = run_events(
        db,
        run=run,
        tick=tick,
        events=events,
        runtime=runtime,
        injections=injections,
        non_mandatory_agent_ids=non_mandatory,
    )
    for outcome in outcomes:
        staffing = record_booth_staffing(
            tick=tick,
            event_type=outcome.event_type,
            action_types={str(item.agent_id): ActionType(item.intent.action_type) for item in outcome.results},
        )
        if staffing is not None:
            state["staffing"] = [*state["staffing"], asdict(staffing)]
        state["performance"] = [
            *state["performance"],
            *([tick, outcome.event_type, item.intent.reaction.valence.value] for item in outcome.results),
        ]
    current_states = agent_states(db, agent_ids)
    state["peak_stress"] = {
        agent_id: max(state["peak_stress"][agent_id], current_states[agent_id].stress)
        for agent_id in agent_ids
    }

    if tick == CLOSING_TICK:
        records = [BoothStaffingRecord(**record) for record in state["staffing"]]
        vacant = count_vacant_ticks(records)
        run.ending = evaluate_festival_ending(
            booth_performance=calculate_booth_performance(
                [(t, kind, ReactionValence(valence)) for t, kind, valence in state["performance"]],
                vacant_tick_count=vacant,
            ),
            vacant_tick_count=vacant,
            directional_affections=list(
                directional_affections(db, run.simulation_id, agent_ids).values()
            ),
            agent_stress_levels=[current_states[a].stress for a in agent_ids],
            initial_satisfaction_levels=state["initial_satisfaction"],
            final_satisfaction_levels=[current_states[a].satisfaction for a in agent_ids],
        ).value
        run.status = "completed"
    run.state = state
    finish_tick(db, run, tick, outcomes)
    db.commit()
    db.refresh(run)
    return run


def festival_booth_record(run: StoryChapterRun) -> ChapterRecord | None:
    if run.ending is None:
        return None
    return build_festival_record(
        ending=FestivalEnding(run.ending),
        interventions=[InterventionRecord(**item) for item in run.interventions],
    )


def festival_booth_achievements(run: StoryChapterRun) -> frozenset[str]:
    if run.ending is None:
        return frozenset()
    return chapter_achievements(
        chapter=CHAPTER,
        status=run.status,
        interventions=[InterventionRecord(**item) for item in run.interventions],
        achieved=evaluate_festival_achievements(
            ending=FestivalEnding(run.ending),
            vacant_tick_count=count_vacant_ticks(
                [BoothStaffingRecord(**record) for record in run.state["staffing"]]
            ),
            peak_stress_levels=list(run.state["peak_stress"].values()),
        ),
    )


def _choice_options(options) -> list[dict[str, str]]:
    return [{"value": value.value, "label": label, "description": text} for value, label, text in options]


def _next_choice(run: StoryChapterRun) -> dict | None:
    point = CHOICE_TICKS.get(run.current_tick + 1)
    if run.status == "completed" or point is None:
        return None
    state = run.state
    if point == InterventionPoint.BOOTH_SETUP:
        return {
            "point": point.value,
            "story": "기획 회의가 끝났습니다. 부스 컨셉을 정하고, 학생마다 역할을 맡길지 정하세요. 역할을 맡기지 않으면 학생들이 스스로 나눕니다.",
            "concepts": [
                {"value": c.value, "label": CONCEPT_LABELS[c], "description": CONCEPT_DESCRIPTIONS[c]}
                for c in BoothConcept
            ],
            "roles": [{"value": r.value, "label": ROLE_LABELS[r]} for r in BoothRole],
            "options": [],
        }
    if point == InterventionPoint.INCIDENT_RESPONSE:
        return {
            "point": point.value,
            "story": f"부스에 돌발 상황이 생겼습니다: {INCIDENT_LABELS[state['incident_subtype']]}. 어떻게 대응할까요?",
            "options": _choice_options(INCIDENT_OPTIONS),
            "help_target": True,
        }
    return {
        "point": point.value,
        "story": "작은 실수를 두고 두 학생 사이에 책임 공방이 벌어졌습니다. 마지막 운영을 앞두고 인력을 어떻게 조정할까요?",
        "options": _choice_options(STAFFING_OPTIONS),
    }


def festival_booth_response(run: StoryChapterRun) -> dict:
    state = run.state
    roles = _roles(state)
    records = [BoothStaffingRecord(**record) for record in state.get("staffing", [])]
    return {
        "members": [
            {
                "agent_id": agent_id,
                "label": ROLE_LABELS[roles[agent_id]] if roles else "역할 자율",
            }
            for agent_id in state["agent_ids"]
        ],
        "concept": CONCEPT_LABELS[BoothConcept(state["concept"])] if "concept" in state else None,
        "incident": (
            INCIDENT_LABELS[state["incident_subtype"]] if run.current_tick >= INCIDENT_TICK else None
        ),
        "conflict_pair": state.get("conflict_pair") if run.current_tick >= BLAME_TICK else None,
        "staffing": [asdict(record) for record in records],
        "vacant_ticks": count_vacant_ticks(records),
        "next_choice": _next_choice(run),
        "round_title": ROUND_TITLES[min(3, (max(1, run.current_tick) - 1) // 3 + 1)],
        "total_ticks": TOTAL_TICKS,
    }
