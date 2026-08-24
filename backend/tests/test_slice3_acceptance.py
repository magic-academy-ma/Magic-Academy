"""
Slice 3 인수 조건 — Memory·Inspector

완료 기준:
- Tick N의 경험으로 Memory가 생성된다.
- Tick N+1에서 조회된 Memory가 Runtime 입력에 포함된다.
- retrieval_trace가 TickResult에 포함된다.
- 활성 Memory 10개 상한이 적용된다.
- Memory 포함/제외 행동 차이가 검증된다.
- COT(decision_explanation)는 DB에 저장되지 않는다.
"""
import subprocess
from app.simulation.tick_engine import (
    AgentType,
    MemoryCandidateItem,
    MemoryItem,
    TickAgent,
    TickEngine,
    TickEvent,
    WorldSnapshot,
)
from tests.runtime_factories import make_runtime_result


def make_snapshot(tick: int = 1):
    return WorldSnapshot(
        simulation_id="sim-e2e-3",
        current_tick=tick,
        data={"agent_snapshots": {}, "relationship_snapshots": [], "valid_agent_ids": {"s-1"}},
    )


async def test_e2e_memory_created_in_tick_n():
    """Tick N에서 memory_candidate를 반환하면 MemoryStoreFn이 호출된다"""
    stored: list = []

    async def runtime(agents, event, snapshot):
        return {
            agent.id: make_runtime_result(
                agent.id,
                memory_candidate=MemoryCandidateItem(
                    content="마법 수업에서 새로운 주문을 익혔다",
                    memory_type="observation",
                    importance=6,
                ),
            )
            for agent in agents
        }

    async def store(agent_id, event_id, candidate, tick):
        stored.append((agent_id, candidate.content, tick))
        return "mem-tick1"

    engine = TickEngine(runtime=runtime, memory_store=store)
    result = await engine.run_tick(
        agents=[TickAgent(id="s-1", agent_type=AgentType.STUDENT, is_active=True)],
        event=TickEvent(id="evt-1", event_type="class", participant_ids={"s-1"}),
        snapshot=make_snapshot(tick=1),
    )

    assert result.created_memory_ids["s-1"] == ["mem-tick1"]
    assert stored[0] == ("s-1", "마법 수업에서 새로운 주문을 익혔다", 1)


async def test_e2e_memory_used_in_tick_n_plus_1():
    """Tick N+1에서 Memory가 snapshot.data['memories']에 포함된다"""
    received: list = []

    async def retriever(agent_id, tick, query):
        return [MemoryItem(id="mem-tick1", content="마법 수업에서 새로운 주문을 익혔다",
                           memory_type="observation", importance=55, created_tick=1, event_id="evt-1")]

    async def runtime(agents, event, snapshot):
        for agent in agents:
            received.append(snapshot.data.get("memories", {}).get(agent.id, []))
        return {agent.id: make_runtime_result(agent.id) for agent in agents}

    engine = TickEngine(runtime=runtime, memory_retriever=retriever)
    result = await engine.run_tick(
        agents=[TickAgent(id="s-1", agent_type=AgentType.STUDENT, is_active=True)],
        event=TickEvent(id="evt-2", event_type="class", participant_ids={"s-1"}),
        snapshot=make_snapshot(tick=2),
    )

    assert received[0][0].id == "mem-tick1"
    assert result.retrieval_traces["s-1"] == ["mem-tick1"]


async def test_e2e_no_memory_retriever_does_not_break():
    """memory_retriever가 없어도 Tick이 정상 완료된다"""

    async def runtime(agents, event, snapshot):
        return {agent.id: make_runtime_result(agent.id, action_type="WAIT") for agent in agents}

    engine = TickEngine(runtime=runtime)
    result = await engine.run_tick(
        agents=[TickAgent(id="s-1", agent_type=AgentType.STUDENT, is_active=True)],
        event=TickEvent(id="evt-1", event_type="class", participant_ids={"s-1"}),
        snapshot=make_snapshot(),
    )

    assert result.status == "completed"
    assert result.retrieval_traces == {}
    assert result.created_memory_ids == {}


async def test_e2e_slice0_1_2_regression():
    """누적 회귀: Slice 0~2 인수 조건이 여전히 통과한다"""
    import sys
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/test_slice0_acceptance.py",
         "tests/test_slice1_acceptance.py",
         "tests/test_slice2_policy_engine.py",
         "-v", "--tb=short"],
        capture_output=True, text=True,
        cwd=backend_dir,
    )
    assert result.returncode == 0, f"Slice 0~2 회귀 실패:\n{result.stdout}\n{result.stderr}"
