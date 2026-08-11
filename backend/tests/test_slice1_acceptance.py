"""
Slice 1 인수 조건 — 은혜님 파트 (Tick·Event 흐름)

완료 기준:
- 수동 Tick 실행 시 활성 Student 1명이 Runtime을 실행한다.
- Professor는 관련 Event가 있을 때만 Runtime을 실행한다.
- Runtime 결과가 Policy로 정확히 전달된다.
- Runtime 최종 실패 시 Tick 전체가 rollback된다.
- Tick 완료 후 TickResult에 참여 Agent ID와 Runtime 결과가 담긴다.
"""
import pytest

from app.simulation.tick_engine import (
    TickAgent,
    AgentType,
    TickEvent,
    PolicyInput,
    TickConflictError,
    TickEngine,
    TickResult,
    TickRollbackError,
    RuntimeExecutionError,
    WorldSnapshot,
)


def student(sid: str) -> TickAgent:
    return TickAgent(id=sid, agent_type=AgentType.STUDENT, is_active=True)


def professor(pid: str) -> TickAgent:
    return TickAgent(id=pid, agent_type=AgentType.PROFESSOR, is_active=True)


def class_event(*participant_ids: str) -> TickEvent:
    return TickEvent(id="evt-1", event_type="class", participant_ids=set(participant_ids))


def snapshot() -> WorldSnapshot:
    return WorldSnapshot(simulation_id="sim-1", current_tick=1, data={})


# ── Runtime 결과 → Policy 전달 ────────────────────────────────────────────────


async def test_runtime_result_passed_to_policy():
    """Runtime 결과가 PolicyInput에 담겨 Policy 콜백으로 전달된다"""
    policy_inputs: list[PolicyInput] = []

    async def runtime(agent, event, snapshot):
        return {"intent": "study", "reaction": {"trust": +5}}

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

    async def runtime(agent, event, snapshot):
        return {"intent": "attend"}

    async def policy(inputs: list[PolicyInput]) -> None:
        received.extend(inputs)

    agents = [student("s-1"), student("s-2"), professor("p-1")]
    event = class_event("s-1", "s-2", "p-1")

    await TickEngine(runtime=runtime, policy=policy).run_tick(
        agents=agents, event=event, snapshot=snapshot()
    )

    assert len(received) == 3
    assert {p.agent_id for p in received} == {"s-1", "s-2", "p-1"}


async def test_policy_receives_event_context():
    """Policy 입력에 Event 정보가 포함된다"""
    received: list[PolicyInput] = []

    async def runtime(agent, event, snapshot):
        return {"intent": "study"}

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
    """TickResult에 실제 Runtime이 실행된 Agent ID 목록이 담긴다"""

    async def runtime(agent, event, snapshot):
        return {"intent": "study"}

    agents = [student("s-1"), student("s-2"), professor("p-1")]
    # Professor는 참여자 아님
    event = class_event("s-1", "s-2")

    result: TickResult = await TickEngine(runtime=runtime).run_tick(
        agents=agents, event=event, snapshot=snapshot()
    )

    assert set(result.participant_ids) == {"s-1", "s-2"}


async def test_tick_result_contains_runtime_outputs():
    """TickResult에 각 Agent의 Runtime 결과가 담긴다"""

    async def runtime(agent, event, snapshot):
        return {"intent": f"action-{agent.id}"}

    agents = [student("s-1"), student("s-2")]
    event = class_event("s-1", "s-2")

    result: TickResult = await TickEngine(runtime=runtime).run_tick(
        agents=agents, event=event, snapshot=snapshot()
    )

    assert result.runtime_outputs["s-1"] == {"intent": "action-s-1"}
    assert result.runtime_outputs["s-2"] == {"intent": "action-s-2"}


async def test_tick_result_skipped_agents_not_in_participants():
    """비활성 Agent는 TickResult participant_ids에 포함되지 않는다"""

    async def runtime(agent, event, snapshot):
        return {"intent": "study"}

    active = student("s-active")
    inactive = TickAgent(id="s-inactive", agent_type=AgentType.STUDENT, is_active=False)
    event = class_event("s-active", "s-inactive")

    result: TickResult = await TickEngine(runtime=runtime).run_tick(
        agents=[active, inactive], event=event, snapshot=snapshot()
    )

    assert "s-inactive" not in result.participant_ids
    assert "s-active" in result.participant_ids


# ── Tick 상태 전이 ────────────────────────────────────────────────────────────


async def test_tick_state_transitions_on_success():
    """Tick 완료 후 TickResult status가 completed다"""

    async def runtime(agent, event, snapshot):
        return {"intent": "study"}

    s1 = student("s-1")
    event = class_event("s-1")

    result: TickResult = await TickEngine(runtime=runtime).run_tick(
        agents=[s1], event=event, snapshot=snapshot()
    )

    assert result.status == "completed"


async def test_tick_state_is_failed_on_rollback():
    """Runtime 실패로 rollback 시 TickRollbackError가 발생한다"""

    async def failing_runtime(agent, event, snapshot):
        raise RuntimeExecutionError("timeout")

    s1 = student("s-1")
    event = class_event("s-1")

    with pytest.raises(TickRollbackError):
        await TickEngine(runtime=failing_runtime).run_tick(
            agents=[s1], event=event, snapshot=snapshot()
        )


async def test_no_participants_tick_completes_with_empty_result():
    """참여 Agent가 없으면 빈 결과로 완료된다"""

    async def runtime(agent, event, snapshot):
        return {"intent": "study"}

    # 모든 Agent가 Event 참여자가 아닌 경우
    s1 = student("s-1")
    event = class_event()  # 참여자 없음

    result: TickResult = await TickEngine(runtime=runtime).run_tick(
        agents=[s1], event=event, snapshot=snapshot()
    )

    assert result.status == "completed"
    assert result.participant_ids == []
    assert result.runtime_outputs == {}
