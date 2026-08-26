from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.api.schemas import (
    RestoreSnapshotRequest,
    SimulationConfigPatchRequest,
    SimulationConfigPutRequest,
)
from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import Simulation, User
from app.repositories.simulation_snapshots import SimulationSnapshotRepository
from app.services.simulation_replay import (
    ReplayResourceNotFoundError,
    SimulationReplayService,
    SnapshotMismatchError,
    UnsupportedReplaySnapshotSchemaError,
)
from app.services.simulation_snapshots import (
    InitialSettingsLockedError,
    InvalidSimulationConfigError,
    SimulationConfigInput,
    SimulationSettingsLockedError,
    SimulationSnapshotService,
    UnsupportedSnapshotSchemaError,
)


class Slice6APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


class Slice6ErrorRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_handler = super().get_route_handler()

        async def handler(request: Request):
            try:
                return await original_handler(request)
            except Slice6APIError as exc:
                return _error_response(exc.status_code, exc.code, exc.message)
            except RequestValidationError:
                return _error_response(400, "INVALID_REPLAY_REQUEST", "Invalid request")
            except HTTPException as exc:
                codes = {
                    401: "AUTHENTICATION_REQUIRED",
                    403: "SIMULATION_ACCESS_DENIED",
                    404: "REPLAY_RESOURCE_NOT_FOUND",
                }
                return _error_response(
                    exc.status_code,
                    codes.get(exc.status_code, "INVALID_REPLAY_REQUEST"),
                    str(exc.detail),
                )

        return handler


router = APIRouter(
    prefix="/simulations",
    tags=["simulation-history"],
    route_class=Slice6ErrorRoute,
)
snapshot_service = SimulationSnapshotService()
replay_service = SimulationReplayService()
snapshot_repository = SimulationSnapshotRepository()


def _owned_simulation(db: Session, simulation_id: UUID, user: User) -> Simulation:
    simulation = db.get(Simulation, simulation_id)
    if simulation is None:
        raise Slice6APIError(404, "REPLAY_RESOURCE_NOT_FOUND", "Simulation not found")
    if simulation.owner_id != user.id:
        raise Slice6APIError(403, "SIMULATION_ACCESS_DENIED", "Simulation access denied")
    return simulation


def _config_data(config) -> dict[str, Any]:
    return {
        "event_frequency": config.event_frequency,
        "event_impact": config.event_impact,
        "magic_enabled": config.magic_enabled,
        "config_version": config.version,
        "changed_at": config.created_at.isoformat(),
    }


def _save_config(
    db: Session,
    simulation: Simulation,
    config_input: SimulationConfigInput,
) -> JSONResponse:
    try:
        config = snapshot_service.save_config(db, simulation, config_input)
        db.commit()
        db.refresh(config)
    except SimulationSettingsLockedError as exc:
        db.rollback()
        raise Slice6APIError(409, "SIMULATION_SETTINGS_LOCKED", str(exc)) from exc
    except InitialSettingsLockedError as exc:
        db.rollback()
        raise Slice6APIError(409, "INITIAL_SETTINGS_LOCKED", str(exc)) from exc
    except InvalidSimulationConfigError as exc:
        db.rollback()
        raise Slice6APIError(400, "INVALID_REPLAY_REQUEST", str(exc)) from exc
    return JSONResponse(content={"data": _config_data(config)})


@router.put("/{simulation_id}/parameters")
def put_parameters(
    simulation_id: UUID,
    request: SimulationConfigPutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> JSONResponse:
    simulation = _owned_simulation(db, simulation_id, current_user)
    latest = snapshot_service.configs.latest(db, simulation.id)
    return _save_config(
        db,
        simulation,
        SimulationConfigInput(
            event_frequency=request.event_frequency,
            event_impact=request.event_impact,
            magic_enabled=request.magic_enabled,
            user_persona_settings=(latest.user_persona_settings if latest else {}),
            policy_version=(latest.policy_version if latest else None),
            resolver_version=(latest.resolver_version if latest else None),
        ),
    )


@router.patch("/{simulation_id}/parameters")
def patch_parameters(
    simulation_id: UUID,
    request: SimulationConfigPatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> JSONResponse:
    simulation = _owned_simulation(db, simulation_id, current_user)
    latest = snapshot_service.configs.latest(db, simulation.id)
    if latest is None:
        raise Slice6APIError(409, "INITIAL_SETTINGS_LOCKED", "Initial settings not found")
    return _save_config(
        db,
        simulation,
        SimulationConfigInput(
            event_frequency=request.event_frequency,
            event_impact=request.event_impact,
            magic_enabled=latest.magic_enabled,
            user_persona_settings=latest.user_persona_settings,
            policy_version=latest.policy_version,
            resolver_version=latest.resolver_version,
        ),
    )


@router.get("/{simulation_id}/snapshots/{tick_number}")
def get_snapshot(
    simulation_id: UUID,
    tick_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> dict[str, Any]:
    _owned_simulation(db, simulation_id, current_user)
    snapshot = snapshot_repository.get_at_tick(db, simulation_id, tick_number)
    if snapshot is None or snapshot.simulation_id != simulation_id:
        raise Slice6APIError(404, "REPLAY_RESOURCE_NOT_FOUND", "Snapshot not found")
    payload = dict(snapshot.payload)
    return {
        "data": {
            "snapshot_id": str(snapshot.id),
            "tick_number": snapshot.tick_number,
            "simulation_day": payload.get("simulation", {}).get("current_day"),
            **payload,
        }
    }


@router.post("/{simulation_id}/restore")
def restore_snapshot(
    simulation_id: UUID,
    request: RestoreSnapshotRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> dict[str, Any]:
    _owned_simulation(db, simulation_id, current_user)
    snapshot = snapshot_repository.get(db, request.snapshot_id)
    if snapshot is None:
        raise Slice6APIError(404, "REPLAY_RESOURCE_NOT_FOUND", "Snapshot not found")
    source = db.get(Simulation, snapshot.simulation_id)
    if source is None:
        raise Slice6APIError(404, "REPLAY_RESOURCE_NOT_FOUND", "Simulation not found")
    if source.owner_id != current_user.id:
        raise Slice6APIError(403, "SIMULATION_ACCESS_DENIED", "Simulation access denied")
    if snapshot.simulation_id != simulation_id:
        raise Slice6APIError(409, "SNAPSHOT_MISMATCH", "Snapshot does not match simulation")
    try:
        payload = snapshot_service.restore_snapshot(
            db, snapshot.id, owner_id=current_user.id
        )
    except UnsupportedSnapshotSchemaError as exc:
        raise Slice6APIError(409, "UNSUPPORTED_SNAPSHOT_SCHEMA", str(exc)) from exc
    return {"data": payload}


@router.get("/{simulation_id}/replay")
def get_replay_list(
    simulation_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: int | None = Query(default=None, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> dict[str, Any]:
    _owned_simulation(db, simulation_id, current_user)
    items, has_more = replay_service.list_ticks(
        db, simulation_id, after_tick=cursor, limit=limit
    )
    next_cursor = str(items[-1]["tick_number"]) if has_more and items else None
    return {
        "data": items,
        "meta": {"next_cursor": next_cursor, "has_more": has_more},
    }


@router.get("/{simulation_id}/replay/{tick_number}")
def get_replay_tick(
    simulation_id: UUID,
    tick_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> dict[str, Any]:
    _owned_simulation(db, simulation_id, current_user)
    try:
        return {"data": replay_service.get_tick(db, simulation_id, tick_number)}
    except ReplayResourceNotFoundError as exc:
        raise Slice6APIError(404, "REPLAY_RESOURCE_NOT_FOUND", str(exc)) from exc
    except SnapshotMismatchError as exc:
        raise Slice6APIError(409, "SNAPSHOT_MISMATCH", str(exc)) from exc
    except UnsupportedReplaySnapshotSchemaError as exc:
        raise Slice6APIError(409, "UNSUPPORTED_SNAPSHOT_SCHEMA", str(exc)) from exc
