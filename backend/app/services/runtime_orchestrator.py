from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.services.runtime_results import (
    RuntimeResultBatchSaveResult,
    RuntimeResultSink,
)
from app.services.runtime_target_selection import RuntimeTargetSelector
from app.simulation.agent_context_assembler import AgentContextAssembler
from app.simulation.agent_runtime import (
    AgentContext,
    AgentRuntimeInput,
    AgentRuntimeResult,
    Block,
    EventSummary,
    ScheduleSummary,
)


class AgentRuntimeExecutor(Protocol):
    def run(self, runtime_input: AgentRuntimeInput) -> AgentRuntimeResult: ...


@dataclass(frozen=True)
class RuntimeBatchExecutionResult:
    results: tuple[AgentRuntimeResult, ...]
    save_result: RuntimeResultBatchSaveResult


class RuntimeOrchestrator:
    MAX_CONCURRENT_RUNTIMES = 6

    def __init__(
        self,
        runtime: AgentRuntimeExecutor,
        result_sink: RuntimeResultSink,
        context_assembler: AgentContextAssembler | None = None,
    ) -> None:
        self._runtime = runtime
        self._result_sink = result_sink
        self._context_assembler = context_assembler or AgentContextAssembler()
        self._target_selector = RuntimeTargetSelector()

    def run_preselected(
        self,
        *,
        run_id: str,
        tick_number: int,
        seed: int = 0,
        block: Block,
        agent_candidates: Sequence[AgentContext],
        preselected_agent_ids: Sequence[UUID],
        schedule: ScheduleSummary,
        events: Sequence[EventSummary],
        valid_agent_ids: Sequence[UUID],
        valid_location_ids: Sequence[UUID],
    ) -> RuntimeBatchExecutionResult:
        selected_agents = self._target_selector.select(
            agent_candidates,
            preselected_agent_ids=preselected_agent_ids,
        )
        runtime_inputs = tuple(
            self._context_assembler.assemble(
                run_id=run_id,
                tick_number=tick_number,
                seed=seed,
                block=block,
                agent_id=agent.agent_id,
                fixture_key=agent.fixture_key,
                agent_type=agent.agent_type,
                name=agent.name,
                mbti=agent.mbti,
                big_five=agent.big_five,
                state=agent.state,
                current_location_id=agent.current_location_id,
                active_status=agent.active_status,
                events=events,
                schedule=schedule,
                valid_agent_ids=valid_agent_ids,
                valid_location_ids=valid_location_ids,
            )
            for agent in selected_agents
        )
        return self.run_batch(runtime_inputs)

    def run_batch(
        self, runtime_inputs: Sequence[AgentRuntimeInput]
    ) -> RuntimeBatchExecutionResult:
        with ThreadPoolExecutor(
            max_workers=self.MAX_CONCURRENT_RUNTIMES
        ) as executor:
            results = tuple(executor.map(self._runtime.run, runtime_inputs))
        save_result = self._result_sink.save_batch(results)
        return RuntimeBatchExecutionResult(
            results=results,
            save_result=save_result,
        )
