from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Agent, RuntimeResult, SimulationSnapshot
from app.repositories.simulation_snapshots import SimulationSnapshotRepository


class ReplayResourceNotFoundError(LookupError):
    pass


class SnapshotMismatchError(ValueError):
    pass


class UnsupportedReplaySnapshotSchemaError(ValueError):
    pass


class SimulationReplayService:
    def __init__(self) -> None:
        self.snapshots = SimulationSnapshotRepository()

    def list_ticks(
        self,
        session: Session,
        simulation_id: UUID,
        *,
        after_tick: int | None,
        limit: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        snapshots = self.snapshots.list_by_simulation(
            session,
            simulation_id,
            after_tick=after_tick,
            limit=limit + 1,
        )
        has_more = len(snapshots) > limit
        items = [self._list_item(snapshot) for snapshot in snapshots[:limit]]
        return items, has_more

    def get_tick(
        self,
        session: Session,
        simulation_id: UUID,
        tick_number: int,
    ) -> dict[str, Any]:
        snapshot = self.snapshots.get_at_tick(session, simulation_id, tick_number)
        if snapshot is None:
            raise ReplayResourceNotFoundError("Snapshot not found")
        self._validate_snapshot(snapshot, simulation_id, tick_number)

        runtime_results = list(
            session.scalars(
                select(RuntimeResult)
                .join(Agent, Agent.id == RuntimeResult.agent_id)
                .where(
                    Agent.simulation_id == simulation_id,
                    RuntimeResult.tick_number == tick_number,
                )
                .order_by(RuntimeResult.created_at, RuntimeResult.id)
            )
        )
        if not runtime_results:
            raise ReplayResourceNotFoundError("RuntimeResult not found")
        if any(result.tick_number != snapshot.tick_number for result in runtime_results):
            raise SnapshotMismatchError("RuntimeResult and Snapshot ticks do not match")

        payload = deepcopy(snapshot.payload)
        stored_runtime_results = payload.get("runtime_results", [])
        stored_ids = [
            row.get("id")
            for row in stored_runtime_results
            if row.get("tick_number") == tick_number
        ]
        result_ids = [str(result.id) for result in runtime_results]
        if stored_ids != result_ids:
            raise SnapshotMismatchError("Snapshot RuntimeResult history does not match")

        simulation = payload.get("simulation", {})
        return {
            "snapshot_id": str(snapshot.id),
            "tick_number": snapshot.tick_number,
            "simulation_day": simulation.get("current_day"),
            "events": payload.get("events", []),
            "agent_snapshots": payload.get("agent_states", []),
            "relationship_deltas": payload.get("relationship_deltas", []),
            "runtime_results": stored_runtime_results,
        }

    @staticmethod
    def _list_item(snapshot: SimulationSnapshot) -> dict[str, Any]:
        simulation = snapshot.payload.get("simulation", {})
        return {
            "snapshot_id": str(snapshot.id),
            "tick_number": snapshot.tick_number,
            "simulation_day": simulation.get("current_day"),
        }

    @staticmethod
    def _validate_snapshot(
        snapshot: SimulationSnapshot,
        simulation_id: UUID,
        tick_number: int,
    ) -> None:
        if snapshot.simulation_id != simulation_id or snapshot.tick_number != tick_number:
            raise SnapshotMismatchError("Snapshot does not match the requested simulation tick")
        if snapshot.payload.get("schema_version") != "slice6-snapshot-v1":
            raise UnsupportedReplaySnapshotSchemaError("Unsupported snapshot schema")
        payload_simulation_id = snapshot.payload.get("simulation", {}).get("id")
        if payload_simulation_id != str(simulation_id):
            raise SnapshotMismatchError("Snapshot simulation does not match")
