from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import RuntimeExecution
from app.repositories import runtime_executions


@dataclass(frozen=True)
class ExecutionMetadataInput:
    simulation_id: UUID
    run_id: str
    tick_number: int
    seed: int
    model: str
    prompt_version: str
    policy_version: str


class ExecutionMetadataConflictError(ValueError):
    pass


def record_execution_metadata(
    session: Session, metadata: ExecutionMetadataInput
) -> RuntimeExecution:
    existing = runtime_executions.get_by_run_id(session, metadata.run_id)
    if existing is not None:
        expected = (
            metadata.simulation_id,
            metadata.tick_number,
            metadata.seed,
            metadata.model,
            metadata.prompt_version,
            metadata.policy_version,
        )
        actual = (
            existing.simulation_id,
            existing.tick_number,
            existing.seed,
            existing.model,
            existing.prompt_version,
            existing.policy_version,
        )
        if actual != expected:
            raise ExecutionMetadataConflictError(metadata.run_id)
        return existing
    return runtime_executions.add(
        session,
        RuntimeExecution(
            id=uuid7(),
            simulation_id=metadata.simulation_id,
            run_id=metadata.run_id,
            tick_number=metadata.tick_number,
            seed=metadata.seed,
            model=metadata.model,
            prompt_version=metadata.prompt_version,
            policy_version=metadata.policy_version,
        ),
    )
