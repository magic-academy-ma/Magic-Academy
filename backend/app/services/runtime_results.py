import json
from hashlib import sha256
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.simulation.agent_runtime import AgentRuntimeResult


@dataclass(frozen=True)
class RuntimeResultBatchSaveResult:
    new_count: int
    duplicate_count: int


class IdempotencyConflictError(Exception):
    def __init__(self, idempotency_key: str) -> None:
        self.idempotency_key = idempotency_key
        super().__init__(f"different result already exists for {idempotency_key}")


class RuntimeResultSink(Protocol):
    def save_batch(
        self, results: Sequence[AgentRuntimeResult]
    ) -> RuntimeResultBatchSaveResult: ...


class InMemoryRuntimeResultSink:
    def __init__(self) -> None:
        self._results: dict[str, AgentRuntimeResult] = {}
        self._fingerprints: dict[str, str] = {}

    def save_batch(
        self, results: Sequence[AgentRuntimeResult]
    ) -> RuntimeResultBatchSaveResult:
        pending_results: dict[str, AgentRuntimeResult] = {}
        pending_fingerprints: dict[str, str] = {}
        duplicate_count = 0

        for result in results:
            if not isinstance(result, AgentRuntimeResult):
                raise TypeError("RuntimeResultSink only accepts AgentRuntimeResult values")
            result = AgentRuntimeResult.model_validate(result.model_dump())
            key = result.idempotency_key
            fingerprint = result_fingerprint(result)

            if key in pending_fingerprints:
                if pending_fingerprints[key] != fingerprint:
                    raise IdempotencyConflictError(key)
                duplicate_count += 1
                continue

            if key in self._fingerprints:
                if self._fingerprints[key] != fingerprint:
                    raise IdempotencyConflictError(key)
                pending_fingerprints[key] = fingerprint
                duplicate_count += 1
                continue

            pending_fingerprints[key] = fingerprint
            pending_results[key] = result.model_copy(deep=True)

        self._results.update(pending_results)
        self._fingerprints.update(
            {
                key: pending_fingerprints[key]
                for key in pending_results
            }
        )
        return RuntimeResultBatchSaveResult(
            new_count=len(pending_results),
            duplicate_count=duplicate_count,
        )

    def get(self, idempotency_key: str) -> AgentRuntimeResult | None:
        result = self._results.get(idempotency_key)
        return result.model_copy(deep=True) if result is not None else None

    def list_results(self) -> list[AgentRuntimeResult]:
        return [result.model_copy(deep=True) for result in self._results.values()]


def result_fingerprint(result: AgentRuntimeResult) -> str:
    serialized = json.dumps(
        result.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(serialized.encode("utf-8")).hexdigest()
