import os

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from uuid6 import uuid7

from app.domain.models import RuntimeExecution, RuntimeResult
from app.services.database_runtime_results import DatabaseRuntimeResultSink
from app.services.execution_metadata import ExecutionMetadataInput, record_execution_metadata
from tests.runtime_factories import make_runtime_result


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required"
)


def test_execution_metadata_and_runtime_results_share_rollback_boundary() -> None:
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE users, simulations RESTART IDENTITY CASCADE"))

    from app.domain.models import Agent, Simulation, User
    from app.services.fixtures import seed_slice_zero

    owner_id = uuid7()
    simulation_id = uuid7()
    with session_factory.begin() as session:
        session.add(
            User(
                id=owner_id,
                username="slice4-transaction-owner",
                display_name="Slice 4 Transaction",
                password_hash="not-a-real-password-hash",
                roles=["USER"],
            )
        )
        session.flush()
        session.add(Simulation(id=simulation_id, owner_id=owner_id, name="Slice 4"))
        session.flush()
        seed_slice_zero(session, simulation_id)

    with session_factory() as session:
        with pytest.raises(RuntimeError, match="fatal commit failure"):
            with session.begin():
                agent_id = session.scalar(
                    select(Agent.id).where(
                        Agent.simulation_id == simulation_id,
                        Agent.fixture_key == "student-01",
                    )
                )
                run_id = str(uuid7())
                result = make_runtime_result(agent_id=str(agent_id)).model_copy(
                    update={
                        "run_id": run_id,
                        "tick_number": 1,
                        "agent_id": agent_id,
                    }
                )
                result = result.model_copy(
                    update={
                        "idempotency_key": f"{run_id}:1:{result.agent_id}",
                    }
                )
                record_execution_metadata(
                    session,
                    ExecutionMetadataInput(
                        simulation_id=simulation_id,
                        run_id=run_id,
                        tick_number=1,
                        seed=42,
                        model=result.model,
                        prompt_version=result.prompt_version,
                        policy_version=None,
                    ),
                )
                DatabaseRuntimeResultSink(session).save_batch([result])
                raise RuntimeError("fatal commit failure")

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(RuntimeExecution)) == 0
        assert session.scalar(select(func.count()).select_from(RuntimeResult)) == 0
    engine.dispose()


def test_execution_metadata_is_queryable_after_commit() -> None:
    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE users, simulations RESTART IDENTITY CASCADE"))

    from app.domain.models import Simulation, User

    owner_id = uuid7()
    simulation_id = uuid7()
    run_id = str(uuid7())
    with session_factory.begin() as session:
        session.add(
            User(
                id=owner_id,
                username="slice4-metadata-owner",
                display_name="Slice 4 Metadata",
                password_hash="not-a-real-password-hash",
                roles=["USER"],
            )
        )
        session.flush()
        session.add(Simulation(id=simulation_id, owner_id=owner_id, name="Slice 4"))
        session.flush()
        record_execution_metadata(
            session,
            ExecutionMetadataInput(
                simulation_id=simulation_id,
                run_id=run_id,
                tick_number=1,
                seed=42,
                model="mock-llm",
                prompt_version="agent-runtime-10.1",
                policy_version="policy-mvp-0.1",
            ),
        )

    with session_factory() as session:
        stored = session.scalar(
            select(RuntimeExecution).where(RuntimeExecution.run_id == run_id)
        )
        assert stored.simulation_id == simulation_id
        assert stored.tick_number == 1
        assert stored.seed == 42
        assert stored.model == "mock-llm"
        assert stored.prompt_version == "agent-runtime-10.1"
        assert stored.policy_version == "policy-mvp-0.1"
    engine.dispose()
