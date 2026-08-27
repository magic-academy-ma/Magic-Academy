from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.models import Simulation, SimulationConfig, SimulationSnapshot
from app.repositories.simulation_snapshots import (
    SimulationConfigRepository,
    SimulationSnapshotRepository,
)


class InvalidSimulationConfigError(ValueError):
    pass


class SimulationSettingsLockedError(InvalidSimulationConfigError):
    pass


class InitialSettingsLockedError(InvalidSimulationConfigError):
    pass


class SnapshotAccessDeniedError(PermissionError):
    pass


class SnapshotNotFoundError(LookupError):
    pass


class UnsupportedSnapshotSchemaError(ValueError):
    pass


ALLOWED_LEVELS = {"low", "medium", "high"}
EVENT_CONFIGURABLE_STATUSES = {"ready", "running", "paused"}


@dataclass(frozen=True)
class SimulationConfigInput:
    event_frequency: str
    event_impact: str
    magic_enabled: bool
    user_persona_settings: dict[str, Any]
    policy_version: str | None = None
    resolver_version: str | None = None


class SimulationSnapshotService:
    def __init__(self) -> None:
        self.configs = SimulationConfigRepository()
        self.snapshots = SimulationSnapshotRepository()

    def save_config(
        self,
        session: Session,
        simulation: Simulation,
        config_input: SimulationConfigInput,
    ):
        if simulation.status not in EVENT_CONFIGURABLE_STATUSES:
            raise SimulationSettingsLockedError(
                f"settings are locked while simulation status is {simulation.status}"
            )
        if config_input.event_frequency not in ALLOWED_LEVELS:
            raise InvalidSimulationConfigError("invalid event_frequency")
        if config_input.event_impact not in ALLOWED_LEVELS:
            raise InvalidSimulationConfigError("invalid event_impact")
        latest = self.configs.latest(session, simulation.id)
        if simulation.status != "ready":
            if latest is None or (
                config_input.magic_enabled != latest.magic_enabled
                or config_input.user_persona_settings
                != latest.user_persona_settings
            ):
                raise InitialSettingsLockedError(
                    "initial settings are locked after simulation start"
                )
        return self.configs.create_version(
            session,
            simulation,
            event_frequency=config_input.event_frequency,
            event_impact=config_input.event_impact,
            magic_enabled=config_input.magic_enabled,
            user_persona_settings=config_input.user_persona_settings,
            policy_version=config_input.policy_version,
            resolver_version=config_input.resolver_version,
        )

    def create_snapshot(
        self,
        session: Session,
        simulation: Simulation,
        config: SimulationConfig | None = None,
    ) -> SimulationSnapshot:
        """``config``이 주어지면 그 버전을 스냅샷에 고정한다 (Tick 시작 시 고정한
        파라미터가 진행 중 변경분에 오염되지 않도록 — mvp-tick-event-policy.md §4.5).
        주어지지 않으면 최신 config를 사용하고, 없으면 기본값으로 생성한다.
        """
        if config is None:
            config = self.configs.latest(session, simulation.id)
        if config is None:
            # 아직 config가 없는 시뮬레이션(예: Tick 시작 시점 §4.5)에는 기본값
            # v1을 부트스트랩한다. 이는 시스템이 확정된 기본 설정을 물질화하는
            # 것이지 사용자가 초기 설정을 바꾸는 것이 아니므로, save_config의 초기
            # 설정 잠금(InitialSettingsLockedError, status != "ready" 이면서
            # latest is None)에 걸려서는 안 된다. 잠금 정책은 사용자 경로
            # (app/api/simulation_history.py → save_config)에서 그대로 유지된다.
            config = self.configs.create_version(
                session,
                simulation,
                event_frequency="medium",
                event_impact="medium",
                magic_enabled=simulation.magic_enabled,
                user_persona_settings={},
                policy_version=None,
                resolver_version=None,
            )
        return self.snapshots.create(session, simulation, config)

    def restore_snapshot(
        self,
        session: Session,
        snapshot_id: UUID,
        *,
        owner_id: UUID,
    ) -> dict[str, Any]:
        snapshot = self.snapshots.get(session, snapshot_id)
        if snapshot is None:
            raise SnapshotNotFoundError(str(snapshot_id))
        source = session.get(Simulation, snapshot.simulation_id)
        if source is None:
            raise SnapshotNotFoundError(str(snapshot.simulation_id))
        if source.owner_id != owner_id:
            raise SnapshotAccessDeniedError(str(snapshot_id))

        payload = snapshot.payload
        if payload.get("schema_version") != "slice6-snapshot-v1":
            raise UnsupportedSnapshotSchemaError("unsupported snapshot schema")
        return deepcopy(payload)
