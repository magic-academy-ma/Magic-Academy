from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
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


def insert_all_on_idempotency_conflict_do_nothing(
    session: Session,
    rows: Sequence[dict[str, Any]],
) -> set[str]:
    if not rows:
        return set()
    statement = (
        insert(RuntimeResult)
        .values(list(rows))
        .on_conflict_do_nothing(index_elements=[RuntimeResult.idempotency_key])
        .returning(RuntimeResult.idempotency_key)
    )
    return set(session.scalars(statement).all())
