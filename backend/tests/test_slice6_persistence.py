import os

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app.domain.models import (
    Agent,
    AgentState,
    RuntimeResult,
    Simulation,
    SimulationConfig,
    SimulationSnapshot,
    User,
)
from app.repositories.simulation_snapshots import SnapshotAlreadyExistsError
from app.services.fixtures import seed_slice_zero
from app.services.simulation_snapshots import (
    InitialSettingsLockedError,
    InvalidSimulationConfigError,
    SimulationSettingsLockedError,
    SnapshotAccessDeniedError,
    SimulationConfigInput,
    SimulationSnapshotService,
    UnsupportedSnapshotSchemaError,
)
from uuid6 import uuid7


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required"
)


@pytest.fixture()
def persistence_context():
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE users, simulations RESTART IDENTITY CASCADE"))

    owner_id = uuid7()
    simulation_id = uuid7()
    with session_factory.begin() as session:
        session.add(
            User(
                id=owner_id,
                username="slice6-owner",
                display_name="Slice 6 Owner",
                password_hash="not-a-real-password-hash",
                roles=["USER"],
            )
        )
        session.flush()
        session.add(
            Simulation(
                id=simulation_id,
                owner_id=owner_id,
                name="Slice 6 Source",
            )
        )
        session.flush()
        seed_slice_zero(session, simulation_id)
    try:
        yield session_factory, owner_id, simulation_id
    finally:
        engine.dispose()


def test_config_versions_are_monotonic_and_flush_without_commit(
    persistence_context,
) -> None:
    session_factory, _, simulation_id = persistence_context
    service = SimulationSnapshotService()
    with session_factory() as session:
        simulation = session.get(Simulation, simulation_id)
        first = service.save_config(
            session,
            simulation,
            SimulationConfigInput("low", "medium", True, {}),
        )
        second = service.save_config(
            session,
            simulation,
            SimulationConfigInput(
                "high",
                "high",
                False,
                {"agent_id": "student-03"},
                policy_version="policy-mvp-0.1",
                resolver_version="resolver-mvp-0.1",
            ),
        )
        assert (first.version, second.version) == (1, 2)
        assert second.policy_version == "policy-mvp-0.1"
        assert second.resolver_version == "resolver-mvp-0.1"
        session.rollback()
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SimulationConfig)) == 0


def test_invalid_config_and_locked_status_are_rejected(persistence_context) -> None:
    session_factory, _, simulation_id = persistence_context
    service = SimulationSnapshotService()
    with session_factory() as session:
        simulation = session.get(Simulation, simulation_id)
        with pytest.raises(InvalidSimulationConfigError, match="event_frequency"):
            service.save_config(
                session,
                simulation,
                SimulationConfigInput("always", "medium", True, {}),
            )
        simulation.status = "completed"
        with pytest.raises(SimulationSettingsLockedError, match="locked"):
            service.save_config(
                session,
                simulation,
                SimulationConfigInput("medium", "medium", True, {}),
            )


@pytest.mark.parametrize("simulation_status", ["running", "paused"])
def test_active_config_allows_event_changes_but_locks_initial_settings(
    persistence_context,
    simulation_status,
) -> None:
    session_factory, _, simulation_id = persistence_context
    service = SimulationSnapshotService()
    with session_factory() as session:
        simulation = session.get(Simulation, simulation_id)
        initial = service.save_config(
            session,
            simulation,
            SimulationConfigInput(
                "medium",
                "medium",
                True,
                {"agent_id": "student-03"},
            ),
        )
        simulation.status = simulation_status
        updated = service.save_config(
            session,
            simulation,
            SimulationConfigInput(
                "high",
                "low",
                initial.magic_enabled,
                initial.user_persona_settings,
            ),
        )
        assert (updated.event_frequency, updated.event_impact) == ("high", "low")

        with pytest.raises(InitialSettingsLockedError, match="initial settings"):
            service.save_config(
                session,
                simulation,
                SimulationConfigInput(
                    "high",
                    "low",
                    False,
                    initial.user_persona_settings,
                ),
            )
        with pytest.raises(InitialSettingsLockedError, match="initial settings"):
            service.save_config(
                session,
                simulation,
                SimulationConfigInput(
                    "high",
                    "low",
                    initial.magic_enabled,
                    {"agent_id": "student-04"},
                ),
            )


def test_snapshot_is_immutable_per_tick_and_contains_ordered_state(
    persistence_context,
) -> None:
    session_factory, _, simulation_id = persistence_context
    service = SimulationSnapshotService()
    with session_factory.begin() as session:
        simulation = session.get(Simulation, simulation_id)
        snapshot = service.create_snapshot(session, simulation)
        assert snapshot.id.version == 7
        assert snapshot.tick_number == 0
        assert snapshot.payload["schema_version"] == "slice6-snapshot-v1"
        assert len(snapshot.payload["agents"]) == 6
        assert [row["sequence"] for row in snapshot.payload["agents"]] == list(range(6))
        with pytest.raises(SnapshotAlreadyExistsError):
            service.create_snapshot(session, simulation)


def test_restore_reconstructs_snapshot_without_database_writes(
    persistence_context,
) -> None:
    session_factory, owner_id, simulation_id = persistence_context
    service = SimulationSnapshotService()
    with session_factory.begin() as session:
        source = session.get(Simulation, simulation_id)
        source_state = session.scalar(
            select(AgentState)
            .join(Agent, Agent.id == AgentState.agent_id)
            .where(Agent.fixture_key == "student-01")
        )
        source_state.stress = 77
        snapshot = service.create_snapshot(session, source)
        snapshot_id = snapshot.id

    with session_factory() as session:
        restored = service.restore_snapshot(
            session,
            snapshot_id,
            owner_id=owner_id,
        )
        restored_student = next(
            row
            for row in restored["agent_states"]
            if row["agent_id"]
            == next(
                agent["id"]
                for agent in restored["agents"]
                if agent["fixture_key"] == "student-01"
            )
        )
        assert restored_student["stress"] == 77
        assert restored["simulation"]["id"] == str(simulation_id)
        assert session.scalar(select(func.count()).select_from(Simulation)) == 1
        assert session.scalar(select(func.count()).select_from(Agent)) == 6
        assert not session.new
        assert not session.dirty
        assert not session.deleted


def test_restore_keeps_runtime_results_as_source_history(persistence_context) -> None:
    session_factory, owner_id, simulation_id = persistence_context
    service = SimulationSnapshotService()
    with session_factory.begin() as session:
        source_agent_id = session.scalar(
            select(Agent.id).where(
                Agent.simulation_id == simulation_id,
                Agent.fixture_key == "student-01",
            )
        )
        session.add(
            RuntimeResult(
                id=uuid7(),
                run_id="source-run-1",
                tick_number=0,
                agent_id=source_agent_id,
                status="PROPOSED",
                action_type="IDLE",
                intent={},
                retry_count=0,
                model="test-model",
                prompt_version="test-prompt-v1",
                idempotency_key="source-run-1:0:student-01",
                result_fingerprint="a" * 64,
            )
        )
        session.flush()
        snapshot = service.create_snapshot(
            session, session.get(Simulation, simulation_id)
        )
        snapshot_id = snapshot.id
        assert len(snapshot.payload["runtime_results"]) == 1

    with session_factory() as session:
        restored = service.restore_snapshot(
            session,
            snapshot_id,
            owner_id=owner_id,
        )
        assert len(restored["runtime_results"]) == 1
        assert session.scalar(select(func.count()).select_from(RuntimeResult)) == 1
        assert session.scalar(select(func.count()).select_from(Simulation)) == 1


def test_restore_rejects_different_owner(persistence_context) -> None:
    session_factory, _, simulation_id = persistence_context
    service = SimulationSnapshotService()
    with session_factory.begin() as session:
        snapshot = service.create_snapshot(
            session, session.get(Simulation, simulation_id)
        )
        snapshot_id = snapshot.id

    with session_factory() as session:
        with pytest.raises(SnapshotAccessDeniedError):
            service.restore_snapshot(
                session,
                snapshot_id,
                owner_id=uuid7(),
            )


def test_restore_rejects_unsupported_snapshot_schema(persistence_context) -> None:
    session_factory, owner_id, simulation_id = persistence_context
    service = SimulationSnapshotService()
    with session_factory.begin() as session:
        snapshot = service.create_snapshot(
            session, session.get(Simulation, simulation_id)
        )
        snapshot.payload = {
            **snapshot.payload,
            "schema_version": "unsupported-snapshot-version",
        }
        snapshot_id = snapshot.id

    with session_factory() as session:
        with pytest.raises(
            UnsupportedSnapshotSchemaError,
            match="unsupported snapshot schema",
        ):
            service.restore_snapshot(
                session,
                snapshot_id,
                owner_id=owner_id,
            )


def test_restore_returns_a_copy_of_the_immutable_payload(persistence_context) -> None:
    session_factory, owner_id, simulation_id = persistence_context
    service = SimulationSnapshotService()
    with session_factory.begin() as session:
        snapshot = service.create_snapshot(
            session, session.get(Simulation, simulation_id)
        )
        snapshot_id = snapshot.id

    with session_factory() as session:
        restored = service.restore_snapshot(session, snapshot_id, owner_id=owner_id)
        restored["simulation"]["name"] = "mutated response"

    with session_factory() as session:
        stored = session.get(SimulationSnapshot, snapshot_id)
        assert stored.payload["simulation"]["name"] == "Slice 6 Source"
        assert session.scalar(select(func.count()).select_from(Simulation)) == 1
