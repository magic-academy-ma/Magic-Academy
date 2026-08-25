from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID, uuid7

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.domain.models import Simulation, SimulationShare, User
from app.repositories.simulation_shares import (
    get_active_share_by_simulation,
    get_share_by_id,
    list_public_shares,
)


def _build_export_payload(db: Session, simulation_id: UUID) -> dict[str, object]:
    simulation = db.get(Simulation, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")

    return {
        "schema_version": "1",
        "simulation": {
            "id": str(simulation.id),
            "owner_id": str(simulation.owner_id),
            "name": simulation.name,
            "status": simulation.status,
            "current_day": simulation.current_day,
            "current_tick": simulation.current_tick,
            "magic_enabled": simulation.magic_enabled,
        },
        "snapshot": {
            "created_at": simulation.created_at.isoformat() if simulation.created_at else None,
            "updated_at": simulation.updated_at.isoformat() if simulation.updated_at else None,
        },
    }


def create_simulation_share(
    db: Session,
    owner: User,
    simulation_id: UUID,
    visibility: str = "private",
    export_payload: dict[str, object] | None = None,
) -> SimulationShare:
    if visibility not in {"private", "unlisted", "public"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported visibility")

    simulation = db.get(Simulation, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    if simulation.owner_id != owner.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Simulation access denied")

    if get_active_share_by_simulation(db, simulation_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Simulation already shared")

    payload = _build_export_payload(db, simulation_id)
    if export_payload is not None:
        payload = {"schema_version": "1", "snapshot": deepcopy(export_payload)}

    share = SimulationShare(
        id=uuid7(),
        simulation_id=simulation_id,
        owner_id=owner.id,
        visibility=visibility,
        export_schema_version="1",
        export_payload=deepcopy(payload),
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return share


def get_public_simulation_shares(db: Session) -> list[SimulationShare]:
    return list_public_shares(db)


def get_simulation_share_detail(db: Session, share_id: UUID, viewer: User | None = None) -> SimulationShare:
    share = get_share_by_id(db, share_id)
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared simulation not found")

    if share.visibility == "private" and (viewer is None or viewer.id != share.owner_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared simulation not found")

    if viewer is not None and viewer.id != share.owner_id and share.visibility == "unlisted":
        return share

    return share


def cancel_simulation_share(db: Session, owner: User, simulation_id: UUID) -> None:
    share = get_active_share_by_simulation(db, simulation_id)
    if share is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared simulation not found")
    if share.owner_id != owner.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Simulation access denied")

    share.revoked_at = datetime.now(UTC)
    db.commit()
