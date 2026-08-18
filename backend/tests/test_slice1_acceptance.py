"""
Slice 1 인수 조건 — 은혜님 파트 (Tick·Event 흐름)

완료 기준:
- 수동 Tick 실행 시 Student가 Runtime batch에 포함된다.
- Professor는 관련 Event가 있거나 schedule이 요구할 때만 Runtime에 포함된다.
- Runtime 결과가 Policy로 정확히 전달된다.
- Runtime 최종 실패 시 Tick 전체가 rollback된다.
- Tick 완료 후 TickResult에 참여 Agent ID와 Runtime 결과가 담긴다.
- 비활성 Agent도 Runtime batch에 포함되며 SKIPPED 결과가 저장된다.
"""
import pytest

from app.simulation.tick_engine import (
    AgentType,
    PolicyInput,
    RuntimeExecutionError,
    TickAgent,
    TickConflictError,
    TickEngine,
    TickResult,
    TickRollbackError,
    WorldSnapshot,
    TickEvent,
)


def student(sid: str, *, is_active: bool = True) -> TickAgent:
    return TickAgent(id=sid, agent_type=AgentType.STUDENT, is_active=is_active)


def professor(pid: str, *, is_active: bool = True) -> TickAgent:
    return TickAgent(id=pid, agent_type=AgentType.PROFESSOR, is_active=is_active)


def class_event(*participant_ids: str) -> TickEvent:
    return TickEvent(id="evt-1", event_type="class", participant_ids=set(participant_ids))


def snapshot() -> WorldSnapshot:
    return WorldSnapshot(simulation_id="sim-1", current_tick=1, data={})


# ── Runtime 결과 → Policy 전달 ────────────────────────────────────────────────


async def test_runtime_result_passed_to_policy():
    """Runtime 결과가 PolicyInput에 담겨 Policy 콜백으로 전달된다"""
    policy_inputs: list[PolicyInput] = []

    async def runtime(agents, event, snap):
        return {a.id: {"intent": "study", "reaction": {"trust": +5}} for a in agents}

    async def policy(inputs: list[PolicyInput]) -> None:
        policy_inputs.extend(inputs)

    s1 = student("s-1")
    event = class_event("s-1")

    await TickEngine(runtime=runtime, policy=policy).run_tick(
        agents=[s1], event=event, snapshot=snapshot()
    )

    assert len(policy_inputs) == 1
    assert policy_inputs[0].agent_id == "s-1"
    assert policy_inputs[0].runtime_result == {"intent": "study", "reaction": {"trust": +5}}


async def test_all_participants_results_passed_to_policy():
    """참여 Agent 전원의 Runtime 결과가 Policy에 한꺼번에 전달된다"""
    received: list[PolicyInput] = []

    async def runtime(agents, event, snap):
        return {a.id: {"intent": "attend"} for a in agents}

    async def policy(inputs: list[PolicyInput]) -> None:
        received.extend(inputs)

    agents = [student("s-1"), professor("p-1")]
    event = class_event("s-1", "p-1")

    await TickEngine(runtime=runtime, policy=policy).run_tick(
        agents=agents, event=event, snapshot=snapshot()
    )

    assert len(received) == 2
    assert {p.agent_id for p in received} == {"s-1", "p-1"}


async def test_policy_receives_event_context():
    """Policy 입력에 Event 정보가 포함된다"""
    received: list[PolicyInput] = []

    async def runtime(agents, event, snap):
        return {a.id: {"intent": "study"} for a in agents}

    async def policy(inputs: list[PolicyInput]) -> None:
        received.extend(inputs)

    s1 = student("s-1")
    event = class_event("s-1")

    await TickEngine(runtime=runtime, policy=policy).run_tick(
        agents=[s1], event=event, snapshot=snapshot()
    )

    assert received[0].event_id == "evt-1"


# ── TickResult ────────────────────────────────────────────────────────────────


async def test_tick_result_contains_participant_ids():
    """TickResult에 Runtime batch에 전달된 Agent ID 목록이 담긴다"""

    async def runtime(agents, event, snap):
        return {a.id: {"intent": "study"} for a in agents}

    # Student는 모두 포함, Professor는 Event 미참여 시 제외
    agents = [student("s-1"), professor("p-1")]
    event = class_event("s-1")

    result: TickResult = await TickEngine(runtime=runtime).run_tick(
        agents=agents, event=event, snapshot=snapshot()
    )

    assert "s-1" in result.participant_ids
    assert "p-1" not in result.participant_ids


async def test_tick_result_contains_runtime_outputs():
    """TickResult에 각 Agent의 Runtime 결과가 담긴다"""

    async def runtime(agents, event, snap):
        return {a.id: {"intent": f"action-{a.id}"} for a in agents}

    agents = [student("s-1"), student("s-2")]
    event = class_event("s-1", "s-2")

    result: TickResult = await TickEngine(runtime=runtime).run_tick(
        agents=agents, event=event, snapshot=snapshot()
    )

    assert result.runtime_outputs["s-1"] == {"intent": "action-s-1"}
    assert result.runtime_outputs["s-2"] == {"intent": "action-s-2"}


async def test_inactive_agent_in_runtime_batch_with_skipped_result():
    """비활성 Agent도 Runtime batch에 포함되며 SKIPPED 결과가 저장된다"""

    llm_call_count = 0

    async def runtime(agents, event, snap):
        result = {}
        for a in agents:
            if not a.is_active:
                result[a.id] = {"status": "SKIPPED"}
            else:
                nonlocal llm_call_count
                llm_call_count += 1
                result[a.id] = {"intent": "study"}
        return result

    active = student("s-active")
    inactive = student("s-inactive", is_active=False)
    event = class_event("s-active", "s-inactive")

    result: TickResult = await TickEngine(runtime=runtime).run_tick(
        agents=[active, inactive], event=event, snapshot=snapshot()
    )

    # 비활성 Agent도 participant_ids에 포함
    assert "s-inactive" in result.participant_ids
    assert "s-active" in result.participant_ids
    # SKIPPED 결과가 runtime_outputs에 포함
    assert result.runtime_outputs["s-inactive"] == {"status": "SKIPPED"}
    # LLM 호출은 활성 Agent에만
    assert llm_call_count == 1


# ── Tick 상태 전이 ────────────────────────────────────────────────────────────


async def test_tick_state_transitions_on_success():
    """Tick 완료 후 TickResult status가 completed다"""

    async def runtime(agents, event, snap):
        return {a.id: {"intent": "study"} for a in agents}

    s1 = student("s-1")
    event = class_event("s-1")

    result: TickResult = await TickEngine(runtime=runtime).run_tick(
        agents=[s1], event=event, snapshot=snapshot()
    )

    assert result.status == "completed"


async def test_tick_state_is_failed_on_rollback():
    """Runtime 실패로 rollback 시 TickRollbackError가 발생한다"""

    async def failing_runtime(agents, event, snap):
        raise RuntimeExecutionError("timeout")

    s1 = student("s-1")
    event = class_event("s-1")

    with pytest.raises(TickRollbackError):
        await TickEngine(runtime=failing_runtime).run_tick(
            agents=[s1], event=event, snapshot=snapshot()
        )


async def test_no_participants_tick_completes_with_empty_result():
    """참여 Agent가 없으면 빈 결과로 완료된다"""

    async def runtime(agents, event, snap):
        return {}

    # Professor만 있고 Event 미참여, schedule_requires_professor=False
    p1 = professor("p-1")
    event = class_event()

    result: TickResult = await TickEngine(runtime=runtime).run_tick(
        agents=[p1], event=event, snapshot=snapshot()
    )

    assert result.status == "completed"
    assert result.participant_ids == []
    assert result.runtime_outputs == {}
