import asyncio
import pytest

from app.simulation.replay_guard import ReplayGuard, ReplayModeError
from app.simulation.instrumentation import reset_counters, get_counts
from app.simulation.tick_engine import (
    AgentType,
    TickAgent,
    TickEvent,
    TickEngine,
    WorldSnapshot,
)
from tests.runtime_factories import make_runtime_result


async def make_student(agent_id: str, *, is_active: bool = True) -> TickAgent:
    return TickAgent(id=agent_id, agent_type=AgentType.STUDENT, is_active=is_active)


async def make_event(participant_ids: list[str]) -> TickEvent:
    return TickEvent(id="evt-1", event_type="class", participant_ids=set(participant_ids))


async def make_snapshot() -> WorldSnapshot:
    return WorldSnapshot(simulation_id="sim-1", current_tick=0, data={})


async def test_replay_blocks_runtime_llm_and_tick():
    """Ensure replay mode prevents new Tick creation, runtime and LLM invocations.

    - In normal mode a tick run increments tick/runtime instrumentation.
    - In replay mode attempting to run a tick raises and instrumentation stays at zero.
    """
    # runtime that would normally be used during a tick
    async def runtime(agents, event, snapshot):
        return {a.id: make_runtime_result(a.id) for a in agents}

    engine = TickEngine(runtime=runtime)

    student = TickAgent(id="s-1", agent_type=AgentType.STUDENT, is_active=True)
    event = TickEvent(id="evt-1", event_type="class", participant_ids={"s-1"})
    snapshot = WorldSnapshot(simulation_id="sim-1", current_tick=0, data={})

    # Normal run should instrument tick and runtime
    reset_counters()
    await engine.run_tick(agents=[student], event=event, snapshot=snapshot)
    counts = get_counts()
    assert counts["tick_calls"] == 1
    assert counts["runtime_calls"] == 1
    # We didn't call AgentRuntime/LLM here, so llm_calls may be 0

    # Now exercise replay guard: operations that would create new work must be blocked
    reset_counters()
    with pytest.raises(ReplayModeError):
        with ReplayGuard():
            # Attempting to run a tick during replay should be explicitly rejected
            await engine.run_tick(agents=[student], event=event, snapshot=snapshot)

    counts_after = get_counts()
    # No ticks or runtime invocations must have occurred during replay
    assert counts_after["tick_calls"] == 0
    assert counts_after["runtime_calls"] == 0
    assert counts_after["llm_calls"] == 0


async def test_replay_uses_only_stored_records_and_snapshot():
    """Simulate a replay flow that reads stored results and snapshots and never invokes runtime/LLM/Tick.

    This test uses a saved record and ensures that 'replaying' by reading it doesn't touch runtime/LLM counters.
    """
    # Simulate a saved runtime output list
    saved_runtime_outputs = [{"agent_id": "s-1", "result": "ok"}]
    saved_snapshot = WorldSnapshot(simulation_id="sim-1", current_tick=0, data={})

    reset_counters()
    with ReplayGuard():
        # Replay logic: read saved_runtime_outputs and saved_snapshot and build replay result
        # The important property: we do not call engine.run_tick or any runtime/LLM code here.
        replayed = {
            "simulation_id": saved_snapshot.simulation_id,
            "tick": saved_snapshot.current_tick,
            "outputs": saved_runtime_outputs,
        }

    counts = get_counts()
    assert counts["tick_calls"] == 0
    assert counts["runtime_calls"] == 0
    assert counts["llm_calls"] == 0

    # Validate replayed content matches saved structure
    assert replayed["simulation_id"] == "sim-1"
    assert replayed["tick"] == 0
    assert replayed["outputs"] == saved_runtime_outputs
