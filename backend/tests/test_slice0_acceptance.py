"""
Slice 0 인수 조건 — 은혜님 파트 (Tick Engine 진입 조건)

지유님(통합 Owner)의 Slice 0 구현 완료 후 이 테스트들이 전부 통과해야 한다.
Tick Engine이 6-Agent roster를 올바르게 수신·처리할 수 있는지를 검증한다.
"""
import asyncio
import pytest

from app.simulation.tick_engine import (
    AgentType,
    TickAgent,
    TickConflictError,
    TickEngine,
    TickEvent,
    WorldSnapshot,
)

STUDENT_COUNT = 5
PROFESSOR_COUNT = 1
TOTAL_AGENT_COUNT = STUDENT_COUNT + PROFESSOR_COUNT


# ── Fixtures ─────────────────────────────────────────────────────────────────


def initial_roster() -> list[TickAgent]:
    """Slice 0 seed 후 기대하는 6-Agent roster (mock)"""
    students = [
        TickAgent(id=f"student-0{i}", agent_type=AgentType.STUDENT, is_active=True)
        for i in range(1, STUDENT_COUNT + 1)
    ]
    professor = TickAgent(id="professor-01", agent_type=AgentType.PROFESSOR, is_active=True)
    return students + [professor]


def class_event(participant_ids: set[str]) -> TickEvent:
    return TickEvent(id="evt-class-1", event_type="class", participant_ids=participant_ids)


def initial_snapshot() -> WorldSnapshot:
    return WorldSnapshot(simulation_id="sim-1", current_tick=0, data={})


# ── Agent roster 계약 ─────────────────────────────────────────────────────────


def test_roster_has_5_students():
    roster = initial_roster()
    students = [a for a in roster if a.agent_type == AgentType.STUDENT]
    assert len(students) == STUDENT_COUNT


def test_roster_has_1_professor():
    roster = initial_roster()
    professors = [a for a in roster if a.agent_type == AgentType.PROFESSOR]
    assert len(professors) == PROFESSOR_COUNT


def test_roster_total_is_6():
    assert len(initial_roster()) == TOTAL_AGENT_COUNT


def test_all_agents_active_at_simulation_start():
    assert all(a.is_active for a in initial_roster())


# ── Tick Engine 진입 조건 ─────────────────────────────────────────────────────


async def test_tick_engine_runs_all_students_in_class_event():
    """수업 Event에서 Student 5명 전원이 Runtime batch에 포함된다"""
    called_ids: list[str] = []

    async def runtime(agents, event, snapshot):
        called_ids.extend(a.id for a in agents)
        return {a.id: {"intent": "attend"} for a in agents}

    roster = initial_roster()
    student_ids = {a.id for a in roster if a.agent_type == AgentType.STUDENT}
    event = class_event(participant_ids=student_ids)

    await TickEngine(runtime=runtime).run_tick(
        agents=roster, event=event, snapshot=initial_snapshot()
    )

    assert len(called_ids) == STUDENT_COUNT


async def test_professor_not_called_when_not_in_class_event():
    """Professor가 수업 Event 참여자가 아닐 때 Runtime batch에 포함되지 않는다"""
    received_types: list[AgentType] = []

    async def runtime(agents, event, snapshot):
        received_types.extend(a.agent_type for a in agents)
        return {a.id: {"intent": "attend"} for a in agents}

    roster = initial_roster()
    student_ids = {a.id for a in roster if a.agent_type == AgentType.STUDENT}
    event = class_event(participant_ids=student_ids)

    await TickEngine(runtime=runtime).run_tick(
        agents=roster, event=event, snapshot=initial_snapshot()
    )

    assert AgentType.PROFESSOR not in received_types


async def test_professor_called_when_in_class_event():
    """Professor가 수업 Event 참여자일 때 Runtime batch에 포함된다"""
    received_types: list[AgentType] = []

    async def runtime(agents, event, snapshot):
        received_types.extend(a.agent_type for a in agents)
        return {a.id: {"intent": "lecture"} for a in agents}

    roster = initial_roster()
    all_ids = {a.id for a in roster}
    event = class_event(participant_ids=all_ids)

    await TickEngine(runtime=runtime).run_tick(
        agents=roster, event=event, snapshot=initial_snapshot()
    )

    assert AgentType.PROFESSOR in received_types
    assert received_types.count(AgentType.PROFESSOR) == 1


async def test_same_snapshot_delivered_to_all_participants():
    """Runtime batch 호출 시 모든 참여 Agent에게 동일한 WorldSnapshot이 전달된다"""
    received_snapshot: list[WorldSnapshot] = []

    async def runtime(agents, event, snapshot):
        received_snapshot.append(snapshot)
        return {a.id: {"intent": "attend"} for a in agents}

    roster = initial_roster()
    all_ids = {a.id for a in roster}
    event = class_event(participant_ids=all_ids)
    snapshot = initial_snapshot()

    await TickEngine(runtime=runtime).run_tick(
        agents=roster, event=event, snapshot=snapshot
    )

    # batch 방식에서 snapshot은 1회 전달되며 원본과 동일해야 한다
    assert len(received_snapshot) == 1
    assert received_snapshot[0] is snapshot


async def test_tick_engine_rejects_second_tick_while_running():
    """Tick 실행 중 두 번째 Tick 요청을 거부한다 (중복 실행 방지)"""
    async def slow_runtime(agents, event, snapshot):
        await asyncio.sleep(0.05)
        return {a.id: {"intent": "attend"} for a in agents}

    engine = TickEngine(runtime=slow_runtime)
    roster = initial_roster()
    student_ids = {a.id for a in roster if a.agent_type == AgentType.STUDENT}
    event = class_event(participant_ids=student_ids)
    snapshot = initial_snapshot()

    first = asyncio.create_task(
        engine.run_tick(agents=roster, event=event, snapshot=snapshot)
    )
    await asyncio.sleep(0)

    with pytest.raises(TickConflictError):
        await engine.run_tick(agents=roster, event=event, snapshot=snapshot)

    await first
