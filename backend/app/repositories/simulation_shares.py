from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import SimulationShare


def get_share_by_id(db: Session, share_id: UUID) -> SimulationShare | None:
    return db.scalar(
        select(SimulationShare).where(
            SimulationShare.id == share_id,
            SimulationShare.revoked_at.is_(None),
        )
    )


def get_active_share_by_simulation(db: Session, simulation_id: UUID) -> SimulationShare | None:
    return db.scalar(
        select(SimulationShare).where(
            SimulationShare.simulation_id == simulation_id,
            SimulationShare.revoked_at.is_(None),
        )
    )


def list_public_shares(db: Session) -> list[SimulationShare]:
    return list(
        db.scalars(
            select(SimulationShare)
            .where(
                SimulationShare.visibility == "public",
                SimulationShare.revoked_at.is_(None),
            )
            .order_by(SimulationShare.created_at.desc())
        ).all()
    )
