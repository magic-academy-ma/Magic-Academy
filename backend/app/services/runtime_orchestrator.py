from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.services.runtime_results import (
    RuntimeResultBatchSaveResult,
    RuntimeResultSink,
)
from app.simulation.agent_runtime import AgentRuntimeInput, AgentRuntimeResult


class AgentRuntimeExecutor(Protocol):
    def run(self, runtime_input: AgentRuntimeInput) -> AgentRuntimeResult: ...


@dataclass(frozen=True)
class RuntimeBatchExecutionResult:
    results: tuple[AgentRuntimeResult, ...]
    save_result: RuntimeResultBatchSaveResult


class RuntimeOrchestrator:
    def __init__(
        self,
        runtime: AgentRuntimeExecutor,
        result_sink: RuntimeResultSink,
    ) -> None:
        self._runtime = runtime
        self._result_sink = result_sink

    def run_batch(
        self, runtime_inputs: Sequence[AgentRuntimeInput]
    ) -> RuntimeBatchExecutionResult:
        results = tuple(
            self._runtime.run(runtime_input)
            for runtime_input in runtime_inputs
        )
        save_result = self._result_sink.save_batch(results)
        return RuntimeBatchExecutionResult(
            results=results,
            save_result=save_result,
        )
