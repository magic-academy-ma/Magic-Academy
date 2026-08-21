import asyncio
import pytest
from unittest.mock import AsyncMock

from app.simulation.tick_engine import (
    AgentType,
    RuntimeExecutionError,
    TickAgent,
    TickConflictError,
    TickEngine,
    TickEvent,
    TickRollbackError,
    WorldSnapshot,
)
from tests.runtime_factories import make_runtime_result


def make_student(agent_id: str, *, is_active: bool = True) -> TickAgent:
    return TickAgent(id=agent_id, agent_type=AgentType.STUDENT, is_active=is_active)


def make_professor(agent_id: str, *, is_active: bool = True) -> TickAgent:
    return TickAgent(id=agent_id, agent_type=AgentType.PROFESSOR, is_active=is_active)


def make_event(participant_ids: list[str]) -> TickEvent:
    return TickEvent(id="evt-1", event_type="class", participant_ids=set(participant_ids))


def make_snapshot() -> WorldSnapshot:
    return WorldSnapshot(simulation_id="sim-1", current_tick=0, data={})


# ── Runtime batch 호출 ────────────────────────────────────────────────────────


async def test_tick_runs_student_runtime():
    """Student가 있으면 Runtime batch가 1회 호출된다"""
    student = make_student("s-1")
    runtime = AsyncMock(return_value={"s-1": make_runtime_result("s-1")})
    engine = TickEngine(runtime=runtime)

    event = make_event(participant_ids=["s-1"])
    snapshot = make_snapshot()

    await engine.run_tick(agents=[student], event=event, snapshot=snapshot)

    runtime.assert_awaited_once_with([student], event, snapshot)


async def test_professor_runs_only_when_in_event():
    """Professor가 Event 참여자가 아니고 schedule_requires_professor=False면 Runtime 미호출"""
    runtime = AsyncMock(return_value={})
    engine = TickEngine(runtime=runtime)

    professor = make_professor("p-1")
    event = make_event(participant_ids=["s-1"])
    snapshot = make_snapshot()

    await engine.run_tick(agents=[professor], event=event, snapshot=snapshot)

    runtime.assert_not_awaited()


async def test_professor_runs_when_in_event():
    """Professor가 Event 참여자면 Runtime batch 호출된다"""
    professor = make_professor("p-1")
    runtime = AsyncMock(return_value={"p-1": make_runtime_result("p-1", action_type="TEACH_CLASS")})
    engine = TickEngine(runtime=runtime)

    event = make_event(participant_ids=["p-1"])
    snapshot = make_snapshot()

    await engine.run_tick(agents=[professor], event=event, snapshot=snapshot)

    runtime.assert_awaited_once()


async def test_professor_runs_when_schedule_requires():
    """schedule_requires_professor=True면 Event 미참여 Professor도 Runtime batch 호출된다"""
    professor = make_professor("p-1")
    runtime = AsyncMock(return_value={"p-1": make_runtime_result("p-1", action_type="TEACH_CLASS")})
    engine = TickEngine(runtime=runtime)

    event = make_event(participant_ids=[])
    snapshot = make_snapshot()

    await engine.run_tick(
        agents=[professor], event=event, snapshot=snapshot, schedule_requires_professor=True
    )

    runtime.assert_awaited_once()


# ── 비활성 Agent 처리 ─────────────────────────────────────────────────────────


async def test_inactive_student_in_runtime_batch():
    """비활성 Student도 Runtime batch에 포함된다 (Runtime이 SKIPPED 결과를 반환)"""
    inactive_student = make_student("s-inactive", is_active=False)
    skipped_result = make_runtime_result("s-inactive", status="SKIPPED")
    runtime = AsyncMock(return_value={"s-inactive": skipped_result})
    engine = TickEngine(runtime=runtime)

    event = make_event(["s-inactive"])
    snapshot = make_snapshot()

    result = await engine.run_tick(agents=[inactive_student], event=event, snapshot=snapshot)

    runtime.assert_awaited_once()
    assert "s-inactive" in result.participant_ids
    assert result.runtime_outputs["s-inactive"] == skipped_result


# ── 중복 Tick 방지 ────────────────────────────────────────────────────────────


async def test_duplicate_tick_raises_conflict():
    async def slow_runtime(agents, event, snapshot):
        await asyncio.sleep(0.05)
        return {a.id: make_runtime_result(a.id) for a in agents}

    engine = TickEngine(runtime=slow_runtime)
    student = make_student("s-1")
    event = make_event(["s-1"])
    snapshot = make_snapshot()

    first = asyncio.create_task(
        engine.run_tick(agents=[student], event=event, snapshot=snapshot)
    )
    await asyncio.sleep(0)

    with pytest.raises(TickConflictError):
        await engine.run_tick(agents=[student], event=event, snapshot=snapshot)

    await first


# ── Rollback ──────────────────────────────────────────────────────────────────


async def test_runtime_failure_triggers_rollback():
    async def failing_runtime(agents, event, snapshot):
        raise RuntimeExecutionError("LLM timeout")

    engine = TickEngine(runtime=failing_runtime)
    student = make_student("s-1")
    event = make_event(["s-1"])
    snapshot = make_snapshot()

    with pytest.raises(TickRollbackError):
        await engine.run_tick(agents=[student], event=event, snapshot=snapshot)


async def test_tick_unlocks_after_completion():
    runtime = AsyncMock(return_value={"s-1": make_runtime_result("s-1")})
    engine = TickEngine(runtime=runtime)

    student = make_student("s-1")
    event = make_event(["s-1"])
    snapshot = make_snapshot()

    await engine.run_tick(agents=[student], event=event, snapshot=snapshot)
    await engine.run_tick(agents=[student], event=event, snapshot=snapshot)

    assert runtime.await_count == 2


async def test_tick_unlocks_after_failure():
    call_count = 0

    async def sometimes_failing(agents, event, snapshot):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeExecutionError("first call fails")
        return {a.id: make_runtime_result(a.id) for a in agents}

    engine = TickEngine(runtime=sometimes_failing)
    student = make_student("s-1")
    event = make_event(["s-1"])
    snapshot = make_snapshot()

    with pytest.raises(TickRollbackError):
        await engine.run_tick(agents=[student], event=event, snapshot=snapshot)

    await engine.run_tick(agents=[student], event=event, snapshot=snapshot)
    assert call_count == 2


async def test_code_bug_propagates_without_wrapping():
    """RuntimeExecutionError가 아닌 예외(코드 버그)는 TickRollbackError로 감싸지 않고 propagate한다"""
    async def buggy_runtime(agents, event, snapshot):
        raise TypeError("unexpected argument")

    engine = TickEngine(runtime=buggy_runtime)
    student = make_student("s-1")
    event = make_event(["s-1"])
    snapshot = make_snapshot()

    with pytest.raises(TypeError):
        await engine.run_tick(agents=[student], event=event, snapshot=snapshot)


async def test_tick_unlocks_after_code_bug():
    """코드 버그로 Tick이 실패해도 lock이 해제된다"""
    call_count = 0

    async def buggy_then_ok(agents, event, snapshot):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise TypeError("bug")
        return {a.id: make_runtime_result(a.id) for a in agents}

    engine = TickEngine(runtime=buggy_then_ok)
    student = make_student("s-1")
    event = make_event(["s-1"])
    snapshot = make_snapshot()

    with pytest.raises(TypeError):
        await engine.run_tick(agents=[student], event=event, snapshot=snapshot)

    await engine.run_tick(agents=[student], event=event, snapshot=snapshot)
    assert call_count == 2


async def test_different_simulation_ids_run_concurrently():
    """다른 simulation_id는 동시에 409 없이 실행 가능해야 한다."""
    started: list[str] = []

    async def tracking_runtime(agents, event, snapshot):
        started.append(snapshot.simulation_id)
        await asyncio.sleep(0.01)
        return {a.id: make_runtime_result(a.id) for a in agents}

    engine = TickEngine(runtime=tracking_runtime)
    student = make_student("s-1")
    event = make_event(["s-1"])

    snapshot_a = WorldSnapshot(simulation_id="sim-A", current_tick=0)
    snapshot_b = WorldSnapshot(simulation_id="sim-B", current_tick=0)

    task_a = asyncio.create_task(engine.run_tick(agents=[student], event=event, snapshot=snapshot_a))
    await asyncio.sleep(0)
    task_b = asyncio.create_task(engine.run_tick(agents=[student], event=event, snapshot=snapshot_b))

    await asyncio.gather(task_a, task_b)
    assert sorted(started) == ["sim-A", "sim-B"]


async def test_same_simulation_id_blocks_concurrent_tick():
    """같은 simulation_id는 동시에 실행되면 TickConflictError가 발생해야 한다."""
    async def slow_runtime(agents, event, snapshot):
        await asyncio.sleep(0.05)
        return {a.id: make_runtime_result(a.id) for a in agents}

    engine = TickEngine(runtime=slow_runtime)
    student = make_student("s-1")
    event = make_event(["s-1"])
    snapshot = make_snapshot()  # simulation_id = "sim-1"

    first = asyncio.create_task(engine.run_tick(agents=[student], event=event, snapshot=snapshot))
    await asyncio.sleep(0)

    with pytest.raises(TickConflictError):
        await engine.run_tick(agents=[student], event=event, snapshot=snapshot)

    await first
