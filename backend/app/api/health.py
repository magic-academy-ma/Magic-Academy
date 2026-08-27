from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import engine
from app.core.migration_status import get_current_db_revisions, get_head_revisions

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Application, DB connectivity and migration-head readiness (contract §6.1).

    Returns 503 until the DB is reachable *and* its applied Alembic
    revision(s) match this deployment's migration heads, so a rolling
    deploy is never marked ready before `alembic upgrade head` has
    actually completed against it.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            current_revisions = get_current_db_revisions(connection)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    expected_revisions = get_head_revisions()
    if current_revisions != expected_revisions:
        raise HTTPException(status_code=503, detail="Database migrations are not up to date")

    return {"status": "ok", "database": "ok", "migration": "ok"}
