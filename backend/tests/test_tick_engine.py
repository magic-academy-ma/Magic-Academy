import asyncio
import pytest
from unittest.mock import AsyncMock

from app.simulation.tick_engine import (
    TickEngine,
    TickConflictError,
    TickRollbackError,
    Agent,
    AgentType,
    Event,
    WorldSnapshot,
)


def make_student(agent_id: str) -> Agent:
    return Agent(id=agent_id, agent_type=AgentType.STUDENT, is_active=True)


def make_professor(agent_id: str) -> Agent:
    return Agent(id=agent_id, agent_type=AgentType.PROFESSOR, is_active=True)


def make_event(participant_ids: list[str]) -> Event:
    return Event(id="evt-1", event_type="class", participant_ids=set(participant_ids))


def make_snapshot() -> WorldSnapshot:
    return WorldSnapshot(simulation_id="sim-1", current_tick=0, data={})


# ── RED ──────────────────────────────────────────────────────────────────────


async def test_tick_runs_student_runtime():
    runtime = AsyncMock(return_value={"intent": "study"})
    engine = TickEngine(runtime=runtime)

    student = make_student("s-1")
    event = make_event(participant_ids=["s-1"])
    snapshot = make_snapshot()

    await engine.run_tick(agents=[student], event=event, snapshot=snapshot)

    runtime.assert_awaited_once_with(agent=student, event=event, snapshot=snapshot)


async def test_professor_runs_only_when_in_event():
    runtime = AsyncMock(return_value={"intent": "lecture"})
    engine = TickEngine(runtime=runtime)

    professor = make_professor("p-1")
    # Professor가 Event 참여자 목록에 없는 경우
    event = make_event(participant_ids=["s-1"])
    snapshot = make_snapshot()

    await engine.run_tick(agents=[professor], event=event, snapshot=snapshot)

    runtime.assert_not_awaited()


async def test_professor_runs_when_in_event():
    runtime = AsyncMock(return_value={"intent": "lecture"})
    engine = TickEngine(runtime=runtime)

    professor = make_professor("p-1")
    event = make_event(participant_ids=["p-1"])
    snapshot = make_snapshot()

    await engine.run_tick(agents=[professor], event=event, snapshot=snapshot)

    runtime.assert_awaited_once()


async def test_duplicate_tick_raises_conflict():
    async def slow_runtime(**kwargs):
        await asyncio.sleep(0.05)
        return {"intent": "study"}

    engine = TickEngine(runtime=slow_runtime)
    student = make_student("s-1")
    event = make_event(["s-1"])
    snapshot = make_snapshot()

    first = asyncio.create_task(
        engine.run_tick(agents=[student], event=event, snapshot=snapshot)
    )
    # 첫 Tick이 시작된 직후 두 번째 요청
    await asyncio.sleep(0)

    with pytest.raises(TickConflictError):
        await engine.run_tick(agents=[student], event=event, snapshot=snapshot)

    await first


async def test_runtime_failure_triggers_rollback():
    async def failing_runtime(**kwargs):
        raise RuntimeError("LLM timeout")

    engine = TickEngine(runtime=failing_runtime)
    student = make_student("s-1")
    event = make_event(["s-1"])
    snapshot = make_snapshot()

    with pytest.raises(TickRollbackError):
        await engine.run_tick(agents=[student], event=event, snapshot=snapshot)


async def test_tick_unlocks_after_completion():
    runtime = AsyncMock(return_value={"intent": "study"})
    engine = TickEngine(runtime=runtime)

    student = make_student("s-1")
    event = make_event(["s-1"])
    snapshot = make_snapshot()

    await engine.run_tick(agents=[student], event=event, snapshot=snapshot)
    # 완료 후 두 번째 Tick이 정상 실행돼야 한다
    await engine.run_tick(agents=[student], event=event, snapshot=snapshot)

    assert runtime.await_count == 2


async def test_tick_unlocks_after_failure():
    call_count = 0

    async def sometimes_failing(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("first call fails")
        return {"intent": "study"}

    engine = TickEngine(runtime=sometimes_failing)
    student = make_student("s-1")
    event = make_event(["s-1"])
    snapshot = make_snapshot()

    with pytest.raises(TickRollbackError):
        await engine.run_tick(agents=[student], event=event, snapshot=snapshot)

    # 실패 후에도 lock이 해제돼 두 번째 Tick이 실행돼야 한다
    await engine.run_tick(agents=[student], event=event, snapshot=snapshot)
    assert call_count == 2


async def test_inactive_agent_skipped():
    runtime = AsyncMock(return_value={"intent": "study"})
    engine = TickEngine(runtime=runtime)

    inactive_student = Agent(id="s-inactive", agent_type=AgentType.STUDENT, is_active=False)
    event = make_event(["s-inactive"])
    snapshot = make_snapshot()

    await engine.run_tick(agents=[inactive_student], event=event, snapshot=snapshot)

    runtime.assert_not_awaited()


async def test_same_snapshot_passed_to_all_agents():
    received_snapshots: list[WorldSnapshot] = []

    async def capturing_runtime(agent, event, snapshot):
        received_snapshots.append(snapshot)
        return {"intent": "study"}

    engine = TickEngine(runtime=capturing_runtime)
    agents = [make_student("s-1"), make_student("s-2")]
    event = make_event(["s-1", "s-2"])
    snapshot = make_snapshot()

    await engine.run_tick(agents=agents, event=event, snapshot=snapshot)

    assert len(received_snapshots) == 2
    assert received_snapshots[0] is received_snapshots[1]
