"""Slice 3 Task 5: Memory 포함/제외 A/B — deterministic mock Runtime 사용"""
import pytest
from app.simulation.tick_engine import (
    AgentType,
    MemoryItem,
    TickAgent,
    TickEngine,
    TickEvent,
    WorldSnapshot,
)
from app.simulation.policy.types import AgentRuntimeResult


def make_snapshot(tick: int = 2):
    return WorldSnapshot(
        simulation_id="sim-ab",
        current_tick=tick,
        data={"agent_snapshots": {}, "relationship_snapshots": [], "valid_agent_ids": {"s-1"}},
    )


async def test_memory_presence_changes_action_type():
    """Memory 있을 때 TALK, 없을 때 STUDY — 동일 Runtime에서 행동 차이 검증"""

    async def memory_aware_runtime(agent, event, snapshot):
        memories = snapshot.data.get("memories", {}).get(agent.id, [])
        action = "TALK" if memories else "STUDY"
        return AgentRuntimeResult(agent_id=agent.id, action_type=action, target_agent_id=None)

    async def retriever_with(agent_id, tick, query):
        return [MemoryItem(id="m-1", content="협력 기억", memory_type="observation",
                           importance=50, created_tick=1, event_id=None)]

    async def retriever_without(agent_id, tick, query):
        return []

    engine_with = TickEngine(runtime=memory_aware_runtime, memory_retriever=retriever_with)
    engine_without = TickEngine(runtime=memory_aware_runtime, memory_retriever=retriever_without)

    result_with = await engine_with.run_tick(
        agents=[TickAgent(id="s-1", agent_type=AgentType.STUDENT, is_active=True)],
        event=TickEvent(id="evt-1", event_type="class", participant_ids={"s-1"}),
        snapshot=make_snapshot(),
    )
    result_without = await engine_without.run_tick(
        agents=[TickAgent(id="s-1", agent_type=AgentType.STUDENT, is_active=True)],
        event=TickEvent(id="evt-1", event_type="class", participant_ids={"s-1"}),
        snapshot=make_snapshot(),
    )

    assert result_with.runtime_outputs["s-1"].action_type == "TALK"
    assert result_without.runtime_outputs["s-1"].action_type == "STUDY"


async def test_retrieval_trace_matches_passed_ids():
    """retrieval_traces는 실제 전달된 Memory ID만 정확히 포함한다"""

    async def retriever(agent_id, tick, query):
        return [
            MemoryItem(id="m-a", content="기억A", memory_type="observation", importance=50, created_tick=1, event_id=None),
            MemoryItem(id="m-b", content="기억B", memory_type="observation", importance=40, created_tick=2, event_id=None),
        ]

    async def runtime(agent, event, snapshot):
        return AgentRuntimeResult(agent_id=agent.id, action_type="STUDY", target_agent_id=None)

    engine = TickEngine(runtime=runtime, memory_retriever=retriever)
    result = await engine.run_tick(
        agents=[TickAgent(id="s-1", agent_type=AgentType.STUDENT, is_active=True)],
        event=TickEvent(id="evt-1", event_type="class", participant_ids={"s-1"}),
        snapshot=make_snapshot(),
    )

    assert result.retrieval_traces["s-1"] == ["m-a", "m-b"]


# TODO: Task 1 (지유님) 완료 후 추가
# async def test_enforce_cap_via_repository(repo, db_session, seed_agents):
#     """Memory 11개 → enforce_cap(10) → 1개 삭제, importance 최저값 제거"""
#     ...
