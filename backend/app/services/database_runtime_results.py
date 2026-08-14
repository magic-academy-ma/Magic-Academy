from collections.abc import Sequence

from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.repositories import runtime_results as runtime_result_repository
from app.services.runtime_results import (
    IdempotencyConflictError,
    RuntimeResultBatchSaveResult,
    result_fingerprint,
)
from app.simulation.agent_runtime import AgentRuntimeResult


class RuntimeBatchMismatchError(ValueError):
    pass


class DatabaseRuntimeResultSink:
    """Persist Runtime results without owning commit or rollback."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_batch(
        self,
        results: Sequence[AgentRuntimeResult],
    ) -> RuntimeResultBatchSaveResult:
        pending, duplicate_count = _prepare_batch(results)
        if not pending:
            return RuntimeResultBatchSaveResult(
                new_count=0,
                duplicate_count=duplicate_count,
            )

        rows_to_insert = [
            {
                "id": uuid7(),
                "run_id": result.run_id,
                "tick_number": result.tick_number,
                "agent_id": result.agent_id,
                "status": result.status.value,
                "action_type": result.intent.action_type.value,
                "intent": result.intent.model_dump(mode="json"),
                "retry_count": result.retry_count,
                "failure_reason": result.failure_reason,
                "model": result.model,
                "prompt_version": result.prompt_version,
                "idempotency_key": key,
                "result_fingerprint": fingerprint,
            }
            for key, (result, fingerprint) in pending.items()
        ]
        inserted_keys = (
            runtime_result_repository.insert_all_on_idempotency_conflict_do_nothing(
                self._session,
                rows_to_insert,
            )
        )
        stored_rows = runtime_result_repository.list_by_idempotency_keys(
            self._session,
            list(pending),
        )
        stored_by_key = {
            row.idempotency_key: row for row in stored_rows
        }
        for key, (result, fingerprint) in pending.items():
            stored = stored_by_key.get(key)
            if stored is None or stored.result_fingerprint != fingerprint:
                raise IdempotencyConflictError(key)
        duplicate_count += len(pending) - len(inserted_keys)

        return RuntimeResultBatchSaveResult(
            new_count=len(inserted_keys),
            duplicate_count=duplicate_count,
        )


def _prepare_batch(
    results: Sequence[AgentRuntimeResult],
) -> tuple[dict[str, tuple[AgentRuntimeResult, str]], int]:
    pending: dict[str, tuple[AgentRuntimeResult, str]] = {}
    duplicate_count = 0
    batch_identity: tuple[str, int] | None = None
    for result in results:
        if not isinstance(result, AgentRuntimeResult):
            raise TypeError("RuntimeResultSink only accepts AgentRuntimeResult values")
        result = AgentRuntimeResult.model_validate(result.model_dump())
        identity = (result.run_id, result.tick_number)
        if batch_identity is None:
            batch_identity = identity
        elif identity != batch_identity:
            raise RuntimeBatchMismatchError(
                "save_batch accepts results from exactly one run and tick"
            )
        fingerprint = result_fingerprint(result)
        existing = pending.get(result.idempotency_key)
        if existing is not None:
            if existing[1] != fingerprint:
                raise IdempotencyConflictError(result.idempotency_key)
            duplicate_count += 1
            continue
        pending[result.idempotency_key] = (result, fingerprint)
    return pending, duplicate_count
