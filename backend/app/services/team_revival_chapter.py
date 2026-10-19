"""스토리모드 CHAPTER 2 — 무너진 팀을 다시 살려라: 저장·진행 서비스.

docs/04-feature-specs/challenge-mode-team-revival.md §4.4~§4.8의 9 Tick 흐름을
controller.py·evaluation.py 순수 함수로 조립해 실제로 실행한다.

| Tick | 내용 |
| --- | --- |
| 1 | 리더·무시받는 팀원 충돌 GROUP_PROJECT → Round 1 개입 |
| 2 | Round 1 개입 조치(없으면 5명 연습) |
| 3 | 탈퇴 선언 MEETING |
| 4 | 반복되는 실수 GROUP_PROJECT → Round 2 개입 |
| 5~6 | Round 2 개입 조치(없으면 5명 연습) |
| 7 | 대회 직전 RANDOM_INCIDENT |
| 8 | 대회 준비 GROUP_PROJECT |
| 9 | 대회 최종 준비 GROUP_PROJECT → 엔딩 |
"""

from __future__ import annotations

import random
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import Relationship, StoryChapterRun, User
from app.services.simulations import create_simulation
from app.services.story_chapter_common import (
    TOTAL_TICKS,
    EventOutcome,
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
from app.simulation.agent_runtime import ActionType, AgentRuntime
from app.simulation.challenge.controller import (
    INITIAL_CONDITIONS,
    ROLE_LABELS,
    Direction,
    HiddenMotive,
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
from app.simulation.challenge.evaluation import (
    TeamRevivalEnding,
    build_team_revival_record,
    evaluate_team_revival_achievements,
    evaluate_team_revival_ending,
)
from app.simulation.challenge.forced_events import build_forced_group_project
from app.simulation.challenge.llm_override import merge_injections
from app.simulation.challenge.progress import calculate_project_progress
from app.simulation.challenge.record import (
    ChapterRecord,
    InterventionRecord,
    chapter_achievements,
)

CHAPTER = 2
ROUND1_TRIGGER_TICK = 1
ROUND1_ACTION_TICK = 2
LEAVE_DECLARATION_TICK = 3
ROUND2_TRIGGER_TICK = 4
ROUND2_ACTION_TICKS = (5, 6)
INCIDENT_TICK = 7
PREPARATION_TICK = 8
FINAL_TICK = 9

CHOICE_TICKS = {ROUND1_ACTION_TICK: "ROUND1", ROUND2_ACTION_TICKS[0]: "ROUND2"}

# §4.2 초기 상태 프리셋. 방향만 확정이고 값은 플레이테스트 후 조정할 임시값이다.
INITIAL_PRESET: dict[tuple[str, Direction], int] = {
    ("affection", Direction.LOW): -30,  # 임시값
    ("satisfaction", Direction.LOW): 20,  # 임시값
    ("stress", Direction.HIGH): 70,  # 임시값
}

ROUND1_OPTIONS = [
    (Round1Choice.REASSIGN_ROLES, "역할 재배정", "두 사람이 따로 연습하도록 팀의 역할을 다시 나눕니다."),
    (Round1Choice.MEDIATE, "대화 자리 마련", "리더와 팀원이 직접 이야기할 자리를 만듭니다."),
    (Round1Choice.WATCH, "지켜본다", "개입하지 않고 팀이 어떻게 움직이는지 지켜봅니다."),
]
ROUND2_OPTIONS = [
    (Round2Choice.PERSUADE_LEAVER, "탈퇴 선언자와 이야기하기", "팀을 나가겠다는 학생에게 남아 달라고 이야기합니다."),
    (Round2Choice.TEAM_MEETING, "팀 전체 회의", "연습을 멈추고 다섯 명이 모두 모여 이야기합니다."),
    (Round2Choice.REDISTRIBUTE, "업무 재분배", "실수가 반복된 부분의 분담을 다시 나눕니다."),
    (Round2Choice.WATCH, "지켜본다", "개입하지 않고 팀이 어떻게 움직이는지 지켜봅니다."),
]
STORIES = {
    ROUND1_ACTION_TICK: "연습 중 리더와 한 팀원의 의견이 정면으로 부딪혔습니다. 조정관으로서 어떻게 할까요?",
    ROUND2_ACTION_TICKS[0]: "같은 실수가 또 나왔고, 서로 책임을 떠넘기기 시작했습니다. 탈퇴를 선언한 학생도 마음을 정하지 못했습니다.",
}
ROUND_TITLES = {1: "갈등의 표면화", 2: "책임 공방과 탈퇴 위기", 3: "대회 직전"}


def _roster(state: dict) -> TeamRoster:
    return TeamRoster(**state["roster"])


def _motives(state: dict) -> dict[TeamRole, HiddenMotive]:
    return {
        TeamRole(role): HiddenMotive(
            grievance=value["grievance"],
            conflict_target=TeamRole(value["conflict_target"]),
            desired_role=value["desired_role"],
        )
        for role, value in state["motives"].items()
    }


def _apply_initial_conditions(db: Session, simulation_id: UUID, roster: TeamRoster) -> None:
    states = agent_states(db, roster.all_agent_ids)
    relationships = {
        (str(row.source_agent_id), str(row.target_agent_id)): row
        for row in db.scalars(
            select(Relationship).where(Relationship.simulation_id == simulation_id)
        )
    }
    for condition in INITIAL_CONDITIONS:
        value = INITIAL_PRESET[(condition.metric, condition.direction)]
        agent_id = roster.agent_id(condition.role)
        if condition.metric == "affection":
            relationships[(agent_id, roster.agent_id(condition.toward))].affection = value
        else:
            setattr(states[agent_id], condition.metric, value)
    db.flush()


def start_team_revival(db: Session, owner: User) -> StoryChapterRun:
    simulation = create_simulation(db, owner, "CHAPTER 2 무너진 팀을 다시 살려라")
    simulation.status = "running"
    seed = random.SystemRandom().randrange(2**62)
    students, _ = students_and_location(db, simulation.id)
    student_ids = [student.id for student in students]
    ensure_student_relationships(db, simulation.id, student_ids)

    shuffled = [str(agent_id) for agent_id in student_ids]
    tick_rng(seed, "roles").shuffle(shuffled)
    roster = TeamRoster(
        leader=shuffled[0],
        ignored_member=shuffled[1],
        leaver=shuffled[2],
        blamed_member=shuffled[3],
        bystander=shuffled[4],
    )
    _apply_initial_conditions(db, simulation.id, roster)
    motives = draw_hidden_motives(tick_rng(seed, "motives"))
    run = StoryChapterRun(
        id=uuid7(),
        simulation_id=simulation.id,
        chapter=CHAPTER,
        seed=seed,
        current_tick=0,
        state={
            "roster": {
                "leader": roster.leader,
                "ignored_member": roster.ignored_member,
                "leaver": roster.leaver,
                "blamed_member": roster.blamed_member,
                "bystander": roster.bystander,
            },
            "motives": {
                role.value: {
                    "grievance": motive.grievance,
                    "conflict_target": motive.conflict_target.value,
                    "desired_role": motive.desired_role,
                }
                for role, motive in motives.items()
            },
            "initial_affections": list(
                directional_affections(db, simulation.id, roster.all_agent_ids).values()
            ),
            "progress_valences": [],
        },
        status="in_progress",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_team_revival(db: Session, run_id: UUID, owner: User) -> StoryChapterRun:
    return get_owned_chapter_run(db, run_id, owner, chapter=CHAPTER)


def _validate_choice(tick: int, choice: str | None) -> None:
    expected = {ROUND1_ACTION_TICK: Round1Choice, ROUND2_ACTION_TICKS[0]: Round2Choice}.get(tick)
    if expected is None:
        if choice is not None:
            raise StoryChapterChoiceError("this tick does not accept a choice")
        return
    if choice is None:
        raise StoryChapterChoiceError("this tick requires a choice")
    try:
        expected(choice)
    except ValueError as exc:
        raise StoryChapterChoiceError("invalid choice for this tick") from exc


def _practice(tick: int, roster: TeamRoster, location_id: str, title: str = "전술 연습"):
    return build_forced_group_project(
        tick=tick, participant_agent_ids=roster.all_agent_ids, location_id=location_id, title=title
    )


def advance_team_revival(
    db: Session, *, run_id: UUID, owner: User, runtime: AgentRuntime, choice: str | None
) -> StoryChapterRun:
    run = get_owned_chapter_run(db, run_id, owner, chapter=CHAPTER, for_update=True)
    if run.status == "completed":
        raise StoryChapterCompletedError
    tick = run.current_tick + 1
    _validate_choice(tick, choice)
    state = dict(run.state)
    roster = _roster(state)
    _, location = students_and_location(db, run.simulation_id)
    location_id = str(location.id)
    injections = plan_motive_injections(ticks=[tick], roster=roster, motives=_motives(state))

    if tick == ROUND1_TRIGGER_TICK:
        events = [
            build_round1_trigger_event(
                tick=tick,
                agent_a_id=roster.leader,
                agent_b_id=roster.ignored_member,
                location_id=location_id,
            )
        ]
    elif tick == ROUND1_ACTION_TICK:
        record_intervention(run, CHOICE_TICKS[tick], choice)
        plan = plan_round1_choice(
            tick=tick, choice=Round1Choice(choice), roster=roster, location_id=location_id
        )
        events = list(plan.events) or [_practice(tick, roster, location_id)]
        injections = merge_injections(injections, plan.injections)
    elif tick == LEAVE_DECLARATION_TICK:
        events = [build_leave_declaration_event(tick=tick, roster=roster, location_id=location_id)]
    elif tick == ROUND2_TRIGGER_TICK:
        events = [build_round2_trigger_event(tick=tick, roster=roster, location_id=location_id)]
    elif tick in ROUND2_ACTION_TICKS:
        if tick == ROUND2_ACTION_TICKS[0]:
            record_intervention(run, CHOICE_TICKS[tick], choice)
            state["round2_choice"] = choice
        # 조치 Event는 첫 Tick에만, 대화 기억은 Round 2 남은 Tick마다 들어간다.
        plan = plan_round2_choice(
            ticks=ROUND2_ACTION_TICKS,
            choice=Round2Choice(state["round2_choice"]),
            roster=roster,
            location_id=location_id,
        )
        events = [event for event in plan.events if event.tick == tick] or [
            _practice(tick, roster, location_id)
        ]
        injections = merge_injections(injections, plan.injections)
    elif tick == INCIDENT_TICK:
        events = [
            build_round3_incident_event(
                tick=tick,
                event_subtype=draw_round3_incident_subtype(tick_rng(run.seed, "incident")),
                participant_agent_ids=roster.all_agent_ids,
                location_id=location_id,
            )
        ]
    elif tick == PREPARATION_TICK:
        events = [_practice(tick, roster, location_id, title="대회 준비")]
    else:
        events = [build_final_preparation_event(tick=tick, roster=roster, location_id=location_id)]

    outcomes = run_events(
        db, run=run, tick=tick, events=events, runtime=runtime, injections=injections
    )
    state["progress_valences"] = [
        *state["progress_valences"],
        *(
            item.intent.reaction.valence.value
            for outcome in outcomes
            if outcome.event_type == "GROUP_PROJECT"
            for item in outcome.results
        ),
    ]
    if tick == FINAL_TICK:
        state["leaver_joined_final"] = _leaver_joined(outcomes, roster.leaver)
        run.ending = evaluate_team_revival_ending(
            project_progress=calculate_project_progress(state["progress_valences"]),
            leaver_joined_final=state["leaver_joined_final"],
            initial_affections=state["initial_affections"],
            final_affections=list(
                directional_affections(db, run.simulation_id, roster.all_agent_ids).values()
            ),
        ).value
        run.status = "completed"
    run.state = state
    finish_tick(db, run, tick, outcomes)
    db.commit()
    db.refresh(run)
    return run


def _leaver_joined(outcomes: list[EventOutcome], leaver_id: str) -> bool:
    for outcome in outcomes:
        for item in outcome.results:
            if str(item.agent_id) == leaver_id:
                return joined_final_preparation(ActionType(item.intent.action_type))
    return False


def team_revival_record(run: StoryChapterRun) -> ChapterRecord | None:
    if run.ending is None:
        return None
    return build_team_revival_record(
        ending=TeamRevivalEnding(run.ending),
        interventions=[InterventionRecord(**item) for item in run.interventions],
    )


def _options(tick: int) -> list[dict[str, str]]:
    options = {ROUND1_ACTION_TICK: ROUND1_OPTIONS, ROUND2_ACTION_TICKS[0]: ROUND2_OPTIONS}.get(tick, [])
    return [{"value": value.value, "label": label, "description": text} for value, label, text in options]


def team_revival_response(run: StoryChapterRun) -> dict:
    roster = _roster(run.state)
    next_tick = run.current_tick + 1
    return {
        "members": [
            {"agent_id": roster.agent_id(role), "label": ROLE_LABELS[role]} for role in TeamRole
        ],
        "next_choice": (
            {
                "point": CHOICE_TICKS[next_tick],
                "story": STORIES[next_tick],
                "options": _options(next_tick),
            }
            if run.status != "completed" and next_tick in CHOICE_TICKS
            else None
        ),
        "round_title": ROUND_TITLES[min(3, (max(1, run.current_tick) - 1) // 3 + 1)],
        "total_ticks": TOTAL_TICKS,
    }


def team_revival_achievements(db: Session, run: StoryChapterRun) -> frozenset[str]:
    if run.ending is None:
        return frozenset()
    interventions = [InterventionRecord(**item) for item in run.interventions]
    return chapter_achievements(
        chapter=CHAPTER,
        status=run.status,
        interventions=interventions,
        achieved=evaluate_team_revival_achievements(
            ending=TeamRevivalEnding(run.ending),
            interventions=interventions,
            initial_affections=run.state["initial_affections"],
            final_affections=list(
                directional_affections(
                    db, run.simulation_id, _roster(run.state).all_agent_ids
                ).values()
            ),
        ),
    )
