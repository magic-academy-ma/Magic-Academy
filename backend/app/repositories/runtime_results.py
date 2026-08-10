from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import RuntimeResult


def get_by_idempotency_key(
    session: Session,
    idempotency_key: str,
) -> RuntimeResult | None:
    return session.scalar(
        select(RuntimeResult).where(RuntimeResult.idempotency_key == idempotency_key)
    )


def list_by_idempotency_keys(
    session: Session,
    idempotency_keys: Sequence[str],
) -> list[RuntimeResult]:
    if not idempotency_keys:
        return []
    return list(
        session.scalars(
            select(RuntimeResult).where(
                RuntimeResult.idempotency_key.in_(idempotency_keys)
            )
        ).all()
    )


def list_results_by_run(session: Session, run_id: str) -> list[RuntimeResult]:
    return list(
        session.scalars(
            select(RuntimeResult)
            .where(RuntimeResult.run_id == run_id)
            .order_by(RuntimeResult.tick_number, RuntimeResult.agent_id)
        ).all()
    )


def list_errors_by_run(session: Session, run_id: str) -> list[RuntimeResult]:
    return list(
        session.scalars(
            select(RuntimeResult)
            .where(
                RuntimeResult.run_id == run_id,
                RuntimeResult.failure_reason.is_not(None),
            )
            .order_by(RuntimeResult.tick_number, RuntimeResult.agent_id)
        ).all()
    )


def add_all(session: Session, rows: Sequence[RuntimeResult]) -> None:
    session.add_all(rows)
