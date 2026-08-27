from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.domain.models import SimulationShare


def get_share_by_id(db: Session, share_id: UUID) -> SimulationShare | None:
    """Return the share row regardless of revoked/visibility state.

    Callers are responsible for applying visibility and revocation rules —
    this exists so the service layer can distinguish "not found" from
    "found but not accessible", both of which surface as 404 to the caller.
    """
    return db.get(SimulationShare, share_id)


def get_active_share_by_simulation(db: Session, simulation_id: UUID) -> SimulationShare | None:
    return db.scalar(
        select(SimulationShare).where(
            SimulationShare.simulation_id == simulation_id,
            SimulationShare.revoked_at.is_(None),
        )
    )


def list_public_shares(
    db: Session,
    *,
    query: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[SimulationShare]:
    statement = select(SimulationShare).where(
        SimulationShare.visibility == "public",
        SimulationShare.revoked_at.is_(None),
    )
    if query:
        like = f"%{query}%"
        statement = statement.where(
            or_(SimulationShare.title.ilike(like), SimulationShare.description.ilike(like))
        )
    statement = statement.order_by(SimulationShare.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(statement))
