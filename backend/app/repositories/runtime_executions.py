from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import RuntimeExecution


def get_by_run_id(session: Session, run_id: str) -> RuntimeExecution | None:
    return session.scalar(
        select(RuntimeExecution).where(RuntimeExecution.run_id == run_id)
    )


def add(session: Session, execution: RuntimeExecution) -> RuntimeExecution:
    session.add(execution)
    session.flush()
    return execution
