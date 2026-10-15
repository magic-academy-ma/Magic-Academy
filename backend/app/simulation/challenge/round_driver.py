"""도전과제 모드 — 강제 Event 1개를 실제로 실행하는 드라이버.

docs/04-feature-specs/challenge-mode-team-revival.md §5/§6: Event Master의 동적
생성 로직을 거치지 않고, 이미 확정된 강제 Event(controller.build_round1_trigger_event
등)를 그대로 실행한다. Agent Runtime은 참여 Agent에 한해 정상적으로 돌아가고
(완전 자율 유지), 그 결과는 기존 프로덕션 커밋 경로 두 가지를 그대로 재사용해
DB에 반영한다:
  1. evaluate_and_apply_policy() — 참여 Agent의 Reaction을 관계·상태 delta로
  2. build_event_effect_candidates() — Event 자체의 기본 효과(예: GROUP_PROJECT
     stress+3)를 상태 delta로

manual_tick.py의 프로덕션 Tick 루프(Memory 검색/저장, WebSocket, Snapshot,
학사 일정 처리 등)는 쓰지 않는다 — 도전과제 전용 경량 실행이며, 그 부분들은
필요해지면 별도로 붙인다.

**범위 경계 (중요)**: 이 드라이버는 강제 Event의 참여 Agent만 실행한다. 실제
게임의 "활성 Student 5명은 매 tick 전원 실행" 규칙(agent-runtime.md §4.4)과
달리, 비참여 Agent의 그 Tick 행동은 이 함수가 처리하지 않는다 — Round 전체를
9 Tick(3일×3블록)짜리 완전한 Tick으로 만들어 전원을 매번 실행하는 것은 별도의
더 큰 통합 작업이다. 지금은 "강제 Event 1개 실행"이라는 가장 작은 단위까지만
구현한다.

**미검증 코드**: 이 환경에는 로컬 Postgres가 없어 DB 연동 테스트를 실행하지
못했다. evaluate_and_apply_policy/SimulationTickService 등 기존 프로덕션
패턴을 최대한 그대로 따랐지만, `docker compose exec backend python -m pytest`로
직접 검증이 필요하다.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import (
    AgentState,
    Event as DomainEvent,
    EventParticipant,
)
from app.services.database_dialogue_results import DatabaseDialogueSink
from app.services.database_runtime_results import DatabaseRuntimeResultSink
from app.services.policy_commit import evaluate_and_apply_policy
from app.services.runtime_input_adapter import RuntimeInputAdapter
from app.services.runtime_orchestrator import RuntimeOrchestrator
from app.services.simulation_tick import SimulationTickService
from app.simulation.agent_runtime import AgentRuntime, AgentRuntimeResult, Block, EventType, ScheduleSummary
from app.simulation.event_master import Event as ChallengeEvent
from app.simulation.policy.models import AgentSnapshot as PolicyAgentSnapshot
from app.simulation.policy.registries.event_policy import build_event_effect_candidates


@dataclass(frozen=True)
class ForcedEventRoundResult:
    runtime_results: tuple[AgentRuntimeResult, ...]


def _persist_forced_event(
    db: Session,
    *,
    simulation_id: UUID,
    simulation_day: int,
    event: ChallengeEvent,
    participant_agent_ids: list[UUID],
) -> tuple[DomainEvent, list[EventParticipant]]:
    db_event = DomainEvent(
        id=uuid7(),
        simulation_id=simulation_id,
        location_id=UUID(event.location_id),
        event_type=event.event_type.lower(),
        title=event.title,
        description=event.description or None,
        status="ongoing",
        simulation_day=simulation_day,
        event_metadata=(
            {"event_subtype": event.event_subtype} if event.event_subtype else {}
        ),
    )
    db.add(db_event)
    db.flush()
    participants = [
        EventParticipant(id=uuid7(), event_id=db_event.id, agent_id=agent_id)
        for agent_id in participant_agent_ids
    ]
    db.add_all(participants)
    db.flush()
    return db_event, participants


def _apply_event_base_effects(
    db: Session, *, run_id: str, event: ChallengeEvent
) -> None:
    """Event 자체의 기본 효과(예: GROUP_PROJECT stress+3)를 참여 Agent에 적용한다.

    evaluate_and_apply_policy()가 이미 커밋한 AgentState 객체를 동일 세션에서
    다시 조회해(SQLAlchemy identity map) 최신값 기준으로 한 번 더 적용한다 —
    두 경로(Reaction 효과, Event 기본 효과)는 policy-engine.md §9.1에 따라
    항상 분리 계산·합산되는 서로 다른 효과이므로 이중 적용이 아니다.
    """
    agent_ids = [UUID(agent_id) for agent_id in event.participant_agent_ids]
    states = list(
        db.scalars(
            select(AgentState).where(AgentState.agent_id.in_(agent_ids)).with_for_update()
        )
    )
    states_by_agent_id = {str(state.agent_id): state for state in states}
    snapshots = {
        agent_id: PolicyAgentSnapshot(
            agent_id=agent_id,
            hunger=state.hunger,
            fatigue=state.fatigue,
            stress=state.stress,
            satisfaction=state.satisfaction,
            mood=state.mood,
        )
        for agent_id, state in states_by_agent_id.items()
    }
    candidates = build_event_effect_candidates(event, run_id=run_id, agent_snapshots=snapshots)
    for candidate in candidates:
        state = states_by_agent_id[candidate.source_agent_id]
        current = getattr(state, candidate.metric)
        minimum = -100 if candidate.metric == "mood" else 0
        after = max(minimum, min(100, current + candidate.delta))
        setattr(state, candidate.metric, after)
    db.flush()


def run_forced_event_round(
    db: Session,
    *,
    simulation_id: UUID,
    run_id: UUID,
    tick_number: int,
    simulation_day: int,
    block: Block,
    event: ChallengeEvent,
    runtime: AgentRuntime,
    non_mandatory_agent_ids: Collection[UUID] = (),
) -> ForcedEventRoundResult:
    """강제 Event를 DB에 기록하고, 참여 Agent만 Agent Runtime으로 실행한 뒤
    Reaction 효과와 Event 기본 효과를 모두 DB에 커밋한다.

    ``runtime``은 이미 필요한 LLMClient(``ChallengeLLMOverride`` 포함 가능)로
    구성되어 전달되어야 한다 — 이 함수는 LLM 선택에 관여하지 않는다.

    ``non_mandatory_agent_ids``의 Agent는 이 Event 일정을 비필수(``is_mandatory=False``)로
    받는다(CHAPTER 4 SUGGEST_REST 등). Runtime 경로는 한 번 실행에 일정 1개만 쓰므로
    필수·비필수 그룹을 따로 실행하고 결과를 합친다 — 두 그룹 사이의 TALK 충돌
    해소는 일어나지 않는다.
    """
    participant_agent_ids = [UUID(agent_id) for agent_id in event.participant_agent_ids]

    db_event, db_participants = _persist_forced_event(
        db,
        simulation_id=simulation_id,
        simulation_day=simulation_day,
        event=event,
        participant_agent_ids=participant_agent_ids,
    )

    service = SimulationTickService(
        RuntimeInputAdapter(
            RuntimeOrchestrator(
                runtime,
                DatabaseRuntimeResultSink(db),
                dialogue_sink=DatabaseDialogueSink(db),
            )
        )
    )
    groups = (
        (True, [a for a in participant_agent_ids if a not in non_mandatory_agent_ids]),
        (False, [a for a in participant_agent_ids if a in non_mandatory_agent_ids]),
    )
    results: list[AgentRuntimeResult] = []
    for is_mandatory, agent_ids in groups:
        if not agent_ids:
            continue
        batch = service.run_runtime_phase(
            db,
            simulation_id=simulation_id,
            run_id=run_id,
            tick_number=tick_number,
            block=block,
            preselected_agent_ids=agent_ids,
            schedule=ScheduleSummary(
                event_id=db_event.id,
                schedule_type=EventType(event.event_type.lower()),
                is_mandatory=is_mandatory,
                location_id=db_event.location_id,
                start_tick=tick_number,
                end_tick=tick_number,
            ),
            events=[db_event],
            event_participants={db_event.id: db_participants},
        )
        results.extend(batch.results)

    evaluate_and_apply_policy(
        db,
        simulation_id=simulation_id,
        run_id=run_id,
        tick_number=tick_number,
        runtime_results=tuple(results),
    )
    _apply_event_base_effects(db, run_id=str(run_id), event=event)

    return ForcedEventRoundResult(runtime_results=tuple(results))
