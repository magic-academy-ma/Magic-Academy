"""Slice 3 Task 3: Tick Engine Memory 파이프라인 통합 테스트"""
from app.simulation.tick_engine import (
    AgentType,
    MemoryCandidateItem,
    MemoryItem,
    TickAgent,
    TickEngine,
    TickEvent,
    WorldSnapshot,
)
from app.simulation.policy.types import AgentRuntimeResult


def make_snapshot(tick: int = 2):
    return WorldSnapshot(
        simulation_id="sim-test",
        current_tick=tick,
        data={"agent_snapshots": {}, "relationship_snapshots": [], "valid_agent_ids": {"s-1"}},
    )


async def test_tick_loads_memories_before_runtime():
    """MemoryRetrieverFn이 호출되고 결과가 snapshot.data["memories"]에 주입된다"""
    retriever_calls: list[tuple] = []
    received_by_runtime: list = []

    async def retriever(agent_id: str, current_tick: int, query_text: str):
        retriever_calls.append((agent_id, current_tick))
        return [MemoryItem(id="m-1", content="이전 기억", memory_type="observation",
                           importance=50, created_tick=1, event_id=None)]

    async def runtime(agents, event, snapshot):
        for agent in agents:
            received_by_runtime.append(
                snapshot.data.get("memories", {}).get(agent.id, [])
            )
        return {agent.id: AgentRuntimeResult(agent_id=agent.id, action_type="STUDY", target_agent_id=None) for agent in agents}

    engine = TickEngine(runtime=runtime, memory_retriever=retriever)
    await engine.run_tick(
        agents=[TickAgent(id="s-1", agent_type=AgentType.STUDENT, is_active=True)],
        event=TickEvent(id="evt-1", event_type="class", participant_ids={"s-1"}),
        snapshot=make_snapshot(),
    )

    assert len(retriever_calls) == 1
    assert retriever_calls[0][0] == "s-1"
    assert len(received_by_runtime[0]) == 1
    assert received_by_runtime[0][0].id == "m-1"


async def test_retrieval_trace_in_tick_result():
    """TickResult.retrieval_traces에 전달된 Memory ID가 기록된다"""
    async def retriever(agent_id, tick, query):
        return [
            MemoryItem(id="m-1", content="기억1", memory_type="observation", importance=50, created_tick=1, event_id=None),
            MemoryItem(id="m-2", content="기억2", memory_type="observation", importance=40, created_tick=1, event_id=None),
        ]

    async def runtime(agents, event, snapshot):
        return {agent.id: AgentRuntimeResult(agent_id=agent.id, action_type="STUDY", target_agent_id=None) for agent in agents}

    engine = TickEngine(runtime=runtime, memory_retriever=retriever)
    result = await engine.run_tick(
        agents=[TickAgent(id="s-1", agent_type=AgentType.STUDENT, is_active=True)],
        event=TickEvent(id="evt-1", event_type="class", participant_ids={"s-1"}),
        snapshot=make_snapshot(),
    )

    assert result.retrieval_traces["s-1"] == ["m-1", "m-2"]


async def test_memory_candidate_stored_after_tick():
    """Runtime memory_candidate → MemoryStoreFn 호출, created_memory_ids에 기록"""
    store_calls: list = []

    async def retriever(agent_id, tick, query):
        return []

    async def runtime(agents, event, snapshot):
        return {
            agent.id: AgentRuntimeResult(
                agent_id=agent.id,
                action_type="STUDY",
                target_agent_id=None,
                memory_candidate=MemoryCandidateItem(
                    content="마법을 배웠다",
                    memory_type="observation",
                    importance=60,
                ),
            )
            for agent in agents
        }

    async def store(agent_id, event_id, candidate, tick):
        store_calls.append((agent_id, event_id, candidate.content, tick))
        return "new-mem-id"

    engine = TickEngine(runtime=runtime, memory_retriever=retriever, memory_store=store)
    result = await engine.run_tick(
        agents=[TickAgent(id="s-1", agent_type=AgentType.STUDENT, is_active=True)],
        event=TickEvent(id="evt-1", event_type="class", participant_ids={"s-1"}),
        snapshot=make_snapshot(),
    )

    assert len(store_calls) == 1
    assert store_calls[0] == ("s-1", "evt-1", "마법을 배웠다", 2)
    assert result.created_memory_ids["s-1"] == ["new-mem-id"]


async def test_no_store_call_when_no_candidate():
    """memory_candidate가 None이면 MemoryStoreFn을 호출하지 않는다"""
    store_calls: list = []

    async def retriever(agent_id, tick, query):
        return []

    async def runtime(agents, event, snapshot):
        return {agent.id: AgentRuntimeResult(agent_id=agent.id, action_type="WAIT", target_agent_id=None) for agent in agents}

    async def store(agent_id, event_id, candidate, tick):
        store_calls.append(agent_id)
        return "id"

    engine = TickEngine(runtime=runtime, memory_retriever=retriever, memory_store=store)
    await engine.run_tick(
        agents=[TickAgent(id="s-1", agent_type=AgentType.STUDENT, is_active=True)],
        event=TickEvent(id="evt-1", event_type="class", participant_ids={"s-1"}),
        snapshot=make_snapshot(),
    )

    assert len(store_calls) == 0


async def test_no_retriever_tick_completes_normally():
    """memory_retriever 없어도 Tick이 정상 완료되고 retrieval_traces는 빈 dict다"""
    async def runtime(agents, event, snapshot):
        return {agent.id: AgentRuntimeResult(agent_id=agent.id, action_type="WAIT", target_agent_id=None) for agent in agents}

    engine = TickEngine(runtime=runtime)
    result = await engine.run_tick(
        agents=[TickAgent(id="s-1", agent_type=AgentType.STUDENT, is_active=True)],
        event=TickEvent(id="evt-1", event_type="class", participant_ids={"s-1"}),
        snapshot=make_snapshot(),
    )

    assert result.status == "completed"
    assert result.retrieval_traces == {}
    assert result.created_memory_ids == {}
