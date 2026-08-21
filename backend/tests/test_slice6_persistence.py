import os

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

from app.domain.models import (
    Agent,
    AgentState,
    Simulation,
    SimulationConfig,
    SimulationSnapshot,
    User,
)
from app.repositories.simulation_snapshots import SnapshotAlreadyExistsError
from app.services.fixtures import seed_slice_zero
from app.services.simulation_snapshots import (
    InvalidSimulationConfigError,
    SimulationConfigInput,
    SimulationSnapshotService,
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
        with pytest.raises(InvalidSimulationConfigError, match="locked"):
            service.save_config(
                session,
                simulation,
                SimulationConfigInput("medium", "medium", True, {}),
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


def test_restore_creates_new_branch_with_remapped_state(persistence_context) -> None:
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

    with session_factory.begin() as session:
        restored = service.restore_as_branch(
            session, snapshot_id, owner_id=owner_id, name="Restored branch"
        )
        restored_id = restored.id
        assert restored.id != simulation_id
        assert restored.origin_simulation_id == simulation_id
        assert restored.origin_snapshot_id == snapshot_id

    with session_factory() as session:
        restored_agents = list(
            session.scalars(select(Agent).where(Agent.simulation_id == restored_id))
        )
        assert len(restored_agents) == 6
        assert not ({agent.id for agent in restored_agents} & {
            agent.id
            for agent in session.scalars(
                select(Agent).where(Agent.simulation_id == simulation_id)
            )
        })
        restored_student = next(
            agent for agent in restored_agents if agent.fixture_key == "student-01"
        )
        assert session.scalar(
            select(AgentState.stress).where(AgentState.agent_id == restored_student.id)
        ) == 77


def test_restore_failure_can_roll_back_entire_branch(
    persistence_context, monkeypatch
) -> None:
    session_factory, owner_id, simulation_id = persistence_context
    service = SimulationSnapshotService()
    with session_factory.begin() as session:
        snapshot = service.create_snapshot(
            session, session.get(Simulation, simulation_id)
        )
        snapshot_id = snapshot.id

    def fail_restore(*args, **kwargs):
        raise RuntimeError("restore failed")

    monkeypatch.setattr(service, "_restore_state", fail_restore)
    with session_factory() as session:
        with pytest.raises(RuntimeError, match="restore failed"):
            service.restore_as_branch(
                session, snapshot_id, owner_id=owner_id, name="Broken branch"
            )
        session.rollback()
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Simulation)) == 1
