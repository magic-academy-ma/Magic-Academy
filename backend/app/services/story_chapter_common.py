"""스토리모드 CHAPTER 2·4 공통 실행 부품.

챕터 컨트롤러(controller.py / festival_booth.py)가 만든 Event·정보 주입·일정 변경을
round_driver로 실제 실행하고, 판정에 필요한 관계·상태 값을 DB에서 읽는다.
"""

from __future__ import annotations

import random
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import permutations
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import (
    Agent,
    AgentState,
    Location,
    Relationship,
    Simulation,
    StoryChapterRun,
    User,
)
from app.simulation.agent_runtime import AgentRuntime, AgentRuntimeResult, Block
from app.simulation.challenge.llm_override import Injections, runtime_with_injections
from app.simulation.challenge.round_driver import run_forced_event_round
from app.simulation.event_master import Event

TOTAL_TICKS = 9
TICKS_PER_ROUND = 3
STUDENT_COUNT = 5


class StoryChapterNotFoundError(LookupError):
    pass


class StoryChapterCompletedError(RuntimeError):
    pass


class StoryChapterChoiceError(ValueError):
    pass


@dataclass(frozen=True)
class EventOutcome:
    tick: int
    event_type: str
    title: str
    results: tuple[AgentRuntimeResult, ...]


def tick_rng(seed: int, purpose: str) -> random.Random:
    """run 시드에서 용도별 RNG를 만든다 — 같은 run은 항상 같은 추첨을 재현한다."""
    return random.Random(f"{seed}:{purpose}")


def round_of(tick: int) -> int:
    return min(TOTAL_TICKS // TICKS_PER_ROUND, (max(1, tick) - 1) // TICKS_PER_ROUND + 1)


def block_of(tick: int) -> Block:
    return (Block.MORNING, Block.AFTERNOON, Block.EVENING)[(tick - 1) % TICKS_PER_ROUND]


def get_owned_chapter_run(
    db: Session, run_id: UUID, owner: User, *, chapter: int, for_update: bool = False
) -> StoryChapterRun:
    query = (
        select(StoryChapterRun)
        .join(Simulation, Simulation.id == StoryChapterRun.simulation_id)
        .where(
            StoryChapterRun.id == run_id,
            StoryChapterRun.chapter == chapter,
            Simulation.owner_id == owner.id,
        )
    )
    if for_update:
        query = query.with_for_update()
    run = db.scalar(query)
    if run is None:
        raise StoryChapterNotFoundError(str(run_id))
    return run


def students_and_location(db: Session, simulation_id: UUID) -> tuple[list[Agent], Location]:
    students = list(
        db.scalars(
            select(Agent)
            .where(Agent.simulation_id == simulation_id, Agent.agent_type == "student")
            .order_by(Agent.fixture_key)
        )
    )[:STUDENT_COUNT]
    location = db.scalar(
        select(Location).where(
            Location.simulation_id == simulation_id, Location.code == "central_square"
        )
    )
    if len(students) < STUDENT_COUNT or location is None:
        raise RuntimeError("story chapter fixtures are incomplete")
    return students, location


def ensure_student_relationships(
    db: Session, simulation_id: UUID, student_ids: Sequence[UUID]
) -> None:
    """학생 사이 20개 방향 관계를 기본값(0)으로 만들어 둔다 — 시작 snapshot의 기준이다."""
    existing = {
        (row.source_agent_id, row.target_agent_id)
        for row in db.scalars(
            select(Relationship).where(Relationship.simulation_id == simulation_id)
        )
    }
    for source, target in permutations(student_ids, 2):
        if (source, target) not in existing:
            db.add(
                Relationship(
                    id=uuid7(),
                    simulation_id=simulation_id,
                    source_agent_id=source,
                    target_agent_id=target,
                )
            )
    db.flush()


def directional_affections(
    db: Session, simulation_id: UUID, student_ids: Sequence[str]
) -> dict[tuple[str, str], int]:
    ids = [UUID(agent_id) for agent_id in student_ids]
    rows = db.scalars(
        select(Relationship).where(
            Relationship.simulation_id == simulation_id,
            Relationship.source_agent_id.in_(ids),
            Relationship.target_agent_id.in_(ids),
        )
    )
    values = {(str(row.source_agent_id), str(row.target_agent_id)): row.affection for row in rows}
    return {pair: values.get(pair, 0) for pair in permutations(student_ids, 2)}


def agent_states(db: Session, student_ids: Sequence[str]) -> dict[str, AgentState]:
    rows = db.scalars(
        select(AgentState).where(AgentState.agent_id.in_([UUID(a) for a in student_ids]))
    )
    return {str(row.agent_id): row for row in rows}


def run_events(
    db: Session,
    *,
    run: StoryChapterRun,
    tick: int,
    events: Sequence[Event],
    runtime: AgentRuntime,
    injections: Injections,
    non_mandatory_agent_ids: Collection[str] = (),
) -> list[EventOutcome]:
    tick_runtime = runtime_with_injections(
        runtime, {key: value for key, value in injections.items() if key[0] == tick}
    )
    non_mandatory = {UUID(agent_id) for agent_id in non_mandatory_agent_ids}
    outcomes = []
    for event in events:
        result = run_forced_event_round(
            db,
            simulation_id=run.simulation_id,
            run_id=run.id,
            tick_number=tick,
            simulation_day=round_of(tick),
            block=block_of(tick),
            event=event,
            runtime=tick_runtime,
            non_mandatory_agent_ids=non_mandatory,
        )
        outcomes.append(
            EventOutcome(
                tick=tick,
                event_type=event.event_type,
                title=event.title,
                results=result.runtime_results,
            )
        )
    return outcomes


def choice_elapsed_seconds(run: StoryChapterRun) -> float:
    """선택지는 직전 tick이 커밋된 시점부터 열려 있었다."""
    opened_at = run.updated_at or run.created_at
    if opened_at is None:
        return 0.0
    return max(0.0, (datetime.now(timezone.utc) - opened_at).total_seconds())


def record_intervention(run: StoryChapterRun, point: str, choice: str) -> None:
    run.interventions = [
        *run.interventions,
        {"point": point, "choice": choice, "elapsed_seconds": choice_elapsed_seconds(run)},
    ]


def finish_tick(db: Session, run: StoryChapterRun, tick: int, outcomes: Sequence[EventOutcome]) -> None:
    state = dict(run.state)
    state["last_results"] = [
        {
            "agent_id": str(item.agent_id),
            "event_title": outcome.title,
            "status": item.status,
            "action_type": item.intent.action_type,
            "motivation_summary": item.intent.motivation_summary,
        }
        for outcome in outcomes
        for item in outcome.results
    ]
    run.state = state
    run.current_tick = tick
    simulation = db.get(Simulation, run.simulation_id)
    simulation.current_tick = tick
    simulation.current_day = round_of(tick)
    if run.status == "completed":
        run.completed_at = datetime.now(timezone.utc)
        simulation.status = "completed"


def public_results(run: StoryChapterRun) -> list[dict[str, Any]]:
    return list(run.state.get("last_results", []))
