from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import (
    Agent,
    ClubChallengeRun,
    Location,
    Relationship,
    Simulation,
    User,
)
from app.services.simulations import create_simulation
from app.simulation.agent_runtime import AgentRuntime, Block, ReactionValence
from app.simulation.challenge.club_revival import (
    CLUB_INITIAL_MEMBERS,
    CLUB_INITIAL_REPUTATION,
    ClubEnding,
    FinalStrategy,
    InternalConflictChoice,
    RecruitmentStrategy,
    apply_final_strategy,
    apply_internal_conflict_choice,
    apply_recruitment_strategy,
    build_closure_warning_event,
    build_club_record,
    evaluate_club_ending,
    plan_final_event,
    plan_internal_conflict_events,
    plan_recruitment_event,
    record_choice,
)
from app.simulation.challenge.forced_events import (
    build_forced_group_project,
    build_forced_meeting,
)
from app.simulation.challenge.record import ChapterRecord, InterventionRecord
from app.simulation.challenge.round_driver import (
    ForcedEventRoundResult,
    run_forced_event_round,
)
from app.simulation.event_master import Event, ImpactLevel


class ClubChallengeNotFoundError(LookupError):
    pass


class ClubChallengeCompletedError(RuntimeError):
    pass


class ClubChallengeChoiceError(ValueError):
    pass


INITIAL_CLUB_MEMBER_FIXTURE_KEYS = ("student-01", "student-02")


def start_club_challenge(db: Session, owner: User) -> tuple[Simulation, ClubChallengeRun]:
    simulation = create_simulation(db, owner, "동아리를 폐부에서 구하기")
    simulation.status = "running"
    run = ClubChallengeRun(
        id=uuid7(),
        simulation_id=simulation.id,
        current_tick=0,
        member_count=CLUB_INITIAL_MEMBERS,
        reputation=CLUB_INITIAL_REPUTATION,
        choices={},
        status="in_progress",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return simulation, run


def get_owned_club_challenge(
    db: Session, run_id: UUID, owner: User, *, for_update: bool = False
) -> ClubChallengeRun:
    query = (
        select(ClubChallengeRun)
        .join(Simulation, Simulation.id == ClubChallengeRun.simulation_id)
        .where(ClubChallengeRun.id == run_id, Simulation.owner_id == owner.id)
    )
    if for_update:
        query = query.with_for_update()
    run = db.scalar(query)
    if run is None:
        raise ClubChallengeNotFoundError(str(run_id))
    return run


def _participants(db: Session, simulation_id: UUID) -> tuple[list[Agent], Agent | None, Location]:
    students = list(
        db.scalars(
            select(Agent)
            .where(Agent.simulation_id == simulation_id, Agent.agent_type == "student")
            .order_by(Agent.fixture_key)
        )
    )
    professor = db.scalar(
        select(Agent).where(
            Agent.simulation_id == simulation_id, Agent.agent_type == "professor"
        )
    )
    location = db.scalar(
        select(Location).where(
            Location.simulation_id == simulation_id,
            Location.code == "central_square",
        )
    )
    if len(students) < 5 or location is None:
        raise RuntimeError("club challenge fixtures are incomplete")
    return students, professor, location


def club_member_agents(students: list[Agent], member_count: int) -> list[Agent]:
    initial_members = [
        agent for agent in students if agent.fixture_key in INITIAL_CLUB_MEMBER_FIXTURE_KEYS
    ]
    candidates = [agent for agent in students if agent not in initial_members]
    return (initial_members + candidates)[:member_count]


def _build_events(
    *,
    tick: int,
    choice: str | None,
    students: list[Agent],
    member_count: int,
    professor: Agent | None,
    location: Location,
) -> list[Event]:
    member_ids = [str(agent.id) for agent in club_member_agents(students, member_count)]
    candidate_ids = [str(agent.id) for agent in students if str(agent.id) not in member_ids]
    location_id = str(location.id)
    if tick == 1:
        return [
            build_closure_warning_event(
                tick=tick, member_ids=member_ids, location_id=location_id
            )
        ]
    if tick == 2:
        return [
            build_forced_meeting(
                tick=tick,
                participant_agent_ids=member_ids,
                location_id=location_id,
                impact_level=ImpactLevel.HIGH,
                title="폐부 경고 이후 내부 갈등",
            )
        ]
    if tick == 3:
        events = plan_internal_conflict_events(
            tick=tick,
            choice=InternalConflictChoice(choice),
            conflict_pair=(member_ids[0], member_ids[1]),
            other_member_ids=member_ids[2:],
            location_id=location_id,
        )
        if events:
            return list(events)
        return [
            build_forced_meeting(
                tick=tick,
                participant_agent_ids=member_ids,
                location_id=location_id,
                title="개입 없이 내부 갈등 지켜보기",
            )
        ]
    if tick == 4:
        return [
            build_forced_meeting(
                tick=tick,
                participant_agent_ids=member_ids,
                location_id=location_id,
                title="신입 회원 모집 계획 회의",
            )
        ]
    if tick == 5:
        return [
            build_forced_group_project(
                tick=tick,
                participant_agent_ids=member_ids,
                location_id=location_id,
                title="동아리 홍보 준비",
            )
        ]
    if tick == 6:
        return [
            plan_recruitment_event(
                tick=tick,
                strategy=RecruitmentStrategy(choice),
                member_ids=[*member_ids, *candidate_ids],
                professor_id=str(professor.id) if professor else None,
                location_id=location_id,
            )
        ]
    if tick == 7:
        return [
            build_forced_group_project(
                tick=tick,
                participant_agent_ids=member_ids,
                location_id=location_id,
                title="최종 행사 준비",
            )
        ]
    if tick == 8:
        return [
            build_forced_meeting(
                tick=tick,
                participant_agent_ids=member_ids,
                location_id=location_id,
                title="최종 심사 리허설",
            )
        ]
    return [
        plan_final_event(
            tick=tick,
            strategy=FinalStrategy(choice),
            member_ids=member_ids,
            location_id=location_id,
        )
    ]


def _validate_choice(tick: int, choice: str | None) -> None:
    expected = {
        3: InternalConflictChoice,
        6: RecruitmentStrategy,
        9: FinalStrategy,
    }.get(tick)
    if expected is None:
        if choice is not None:
            raise ClubChallengeChoiceError("this tick does not accept a choice")
        return
    if choice is None:
        raise ClubChallengeChoiceError("this tick requires a choice")
    try:
        expected(choice)
    except ValueError as exc:
        raise ClubChallengeChoiceError("invalid choice for this tick") from exc


def _average_student_affection(
    db: Session, simulation_id: UUID, students: list[Agent]
) -> list[int]:
    student_ids = [student.id for student in students]
    return list(
        db.scalars(
            select(Relationship.affection).where(
                Relationship.simulation_id == simulation_id,
                Relationship.source_agent_id.in_(student_ids),
                Relationship.target_agent_id.in_(student_ids),
            )
        )
    )


def advance_club_challenge(
    db: Session,
    *,
    run_id: UUID,
    owner: User,
    runtime: AgentRuntime,
    choice: str | None,
) -> tuple[ClubChallengeRun, ForcedEventRoundResult]:
    run = get_owned_club_challenge(db, run_id, owner, for_update=True)
    if run.status == "completed":
        raise ClubChallengeCompletedError
    next_tick = run.current_tick + 1
    _validate_choice(next_tick, choice)
    students, professor, location = _participants(db, run.simulation_id)
    events = _build_events(
        tick=next_tick,
        choice=choice,
        students=students,
        member_count=run.member_count,
        professor=professor,
        location=location,
    )

    runtime_results = []
    for event in events:
        event_result = run_forced_event_round(
            db,
            simulation_id=run.simulation_id,
            run_id=run.id,
            tick_number=next_tick,
            simulation_day=((next_tick - 1) // 3) + 1,
            block=(Block.MORNING, Block.AFTERNOON, Block.EVENING)[(next_tick - 1) % 3],
            event=event,
            runtime=runtime,
        )
        runtime_results.extend(event_result.runtime_results)
    result = ForcedEventRoundResult(runtime_results=tuple(runtime_results))

    choices = dict(run.choices)
    if choice is not None:
        choices[str(next_tick)] = choice
        # 선택지는 직전 tick이 커밋된 시점부터 열려 있었다.
        opened_at = run.updated_at or run.created_at
        elapsed = (
            max(0.0, (datetime.now(timezone.utc) - opened_at).total_seconds())
            if opened_at
            else 0.0
        )
        run.interventions = [
            *run.interventions,
            {
                "point": str(next_tick),
                "choice": record_choice(choice),
                "elapsed_seconds": elapsed,
            },
        ]
    run.choices = choices
    if next_tick == 3:
        negative = any(
            item.intent.reaction.valence == ReactionValence.NEGATIVE
            for item in result.runtime_results
        )
        run.member_count, run.reputation = apply_internal_conflict_choice(
            member_count=run.member_count,
            reputation=run.reputation,
            choice=InternalConflictChoice(choice),
            negative_reaction=negative,
        )
    elif next_tick == 6:
        run.member_count, run.reputation = apply_recruitment_strategy(
            member_count=run.member_count,
            reputation=run.reputation,
            strategy=RecruitmentStrategy(choice),
        )
    elif next_tick == 9:
        run.reputation = apply_final_strategy(
            reputation=run.reputation, strategy=FinalStrategy(choice)
        )
        run.ending = evaluate_club_ending(
            member_count=run.member_count,
            reputation=run.reputation,
            directional_affections=_average_student_affection(
                db,
                run.simulation_id,
                club_member_agents(students, run.member_count),
            ),
        ).value
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        simulation = db.get(Simulation, run.simulation_id)
        simulation.status = "completed"

    run.current_tick = next_tick
    simulation = db.get(Simulation, run.simulation_id)
    simulation.current_tick = next_tick
    simulation.current_day = ((next_tick - 1) // 3) + 1
    db.commit()
    db.refresh(run)
    return run, result


def club_chapter_record(run: ClubChallengeRun) -> ChapterRecord | None:
    if run.ending is None:
        return None
    return build_club_record(
        ending=ClubEnding(run.ending),
        interventions=[InterventionRecord(**item) for item in run.interventions],
    )
