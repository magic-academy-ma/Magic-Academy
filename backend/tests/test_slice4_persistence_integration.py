import os
from datetime import UTC, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker
from uuid6 import uuid7


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required"
)


@pytest.fixture()
def api_client():
    from app.core.database import get_db
    from app.main import app
    from app.services.runtime_dependency import get_agent_runtime
    from app.simulation.agent_runtime import AgentRuntime, MockLLMClient

    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )
    with engine.begin() as connection:
        connection.execute(
            text("TRUNCATE users, simulations RESTART IDENTITY CASCADE")
        )

    def override_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_agent_runtime] = lambda: AgentRuntime(
        MockLLMClient(),
        model="slice4-persistence-model",
        prompt_version="slice4-persistence-prompt-v1",
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, session_factory
    app.dependency_overrides.clear()
    engine.dispose()


def register_login_create(client: TestClient) -> tuple[UUID, dict[str, str]]:
    credentials = {
        "username": "slice4-persistence-owner",
        "display_name": "Slice 4 Persistence",
        "password": "Slice4-password!",
    }
    assert client.post("/v1/auth/register", json=credentials).status_code == 201
    login = client.post(
        "/v1/auth/login",
        json={
            "username": credentials["username"],
            "password": credentials["password"],
        },
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    created = client.post(
        "/v1/simulations", headers=headers, json={"name": "Slice 4 Persistence"}
    )
    assert created.status_code == 201
    return UUID(created.json()["id"]), headers


def world_snapshot(session: Session, simulation_id: UUID) -> tuple[tuple, ...]:
    """Capture the PostgreSQL rows that back the Tick world snapshot."""
    from app.domain.models import AgentState

    rows = session.execute(
        select(
            AgentState.agent_id,
            AgentState.location_id,
            AgentState.hunger,
            AgentState.fatigue,
            AgentState.stress,
            AgentState.satisfaction,
            AgentState.mood,
            AgentState.current_action,
        )
        .where(AgentState.simulation_id == simulation_id)
        .order_by(AgentState.agent_id)
    ).all()
    return tuple(tuple(row) for row in rows)


def seed_rollback_rows(session: Session, simulation_id: UUID) -> None:
    from app.domain.models import Agent, AgentMemory, Relationship

    agents = list(
        session.scalars(
            select(Agent)
            .where(Agent.simulation_id == simulation_id)
            .order_by(Agent.fixture_key)
        )
    )
    source, target = agents[:2]
    session.add(
        Relationship(
            id=uuid7(),
            simulation_id=simulation_id,
            source_agent_id=source.id,
            target_agent_id=target.id,
            affection=4,
            closeness=5,
            trust=6,
            tension=7,
            rivalry=8,
            dependency=9,
        )
    )
    session.add(
        AgentMemory(
            id=uuid7(),
            agent_id=source.id,
            event_id=None,
            content="rollback baseline memory",
            memory_type="observation",
            importance=40,
            created_tick=0,
            occurred_at=datetime.now(UTC),
            embedding=None,
        )
    )
    session.commit()


def persistence_snapshot(session: Session, simulation_id: UUID) -> dict:
    from app.domain.models import (
        AgentMemory,
        Relationship,
        RuntimeExecution,
        RuntimeResult,
        Simulation,
    )

    simulation = session.get(Simulation, simulation_id)
    return {
        "current_tick": simulation.current_tick,
        "current_day": simulation.current_day,
        "world_snapshot": world_snapshot(session, simulation_id),
        "memories": tuple(
            session.execute(
                select(
                    AgentMemory.id,
                    AgentMemory.agent_id,
                    AgentMemory.content,
                    AgentMemory.importance,
                    AgentMemory.created_tick,
                ).order_by(AgentMemory.id)
            ).all()
        ),
        "relationships": tuple(
            session.execute(
                select(
                    Relationship.id,
                    Relationship.source_agent_id,
                    Relationship.target_agent_id,
                    Relationship.affection,
                    Relationship.closeness,
                    Relationship.trust,
                    Relationship.tension,
                    Relationship.rivalry,
                    Relationship.dependency,
                )
                .where(Relationship.simulation_id == simulation_id)
                .order_by(Relationship.id)
            ).all()
        ),
        "runtime_executions": session.scalar(
            select(func.count()).select_from(RuntimeExecution)
        ),
        "runtime_results": session.scalar(
            select(func.count()).select_from(RuntimeResult)
        ),
    }


def test_runtime_batch_failure_preserves_tick_and_db_world_snapshot(
    api_client, monkeypatch
) -> None:
    from app.main import app
    from app.services.runtime_dependency import get_agent_runtime
    from app.simulation.tick_engine import RuntimeExecutionError

    client, session_factory = api_client
    simulation_id, headers = register_login_create(client)
    with session_factory() as session:
        seed_rollback_rows(session, simulation_id)
        before = persistence_snapshot(session, simulation_id)

    class FailingRuntime:
        def run(self, _runtime_input):
            raise RuntimeExecutionError("runtime batch failed")

    app.dependency_overrides[get_agent_runtime] = lambda: FailingRuntime()
    response = client.post(
        f"/v1/simulations/{simulation_id}/ticks/advance", headers=headers
    )

    assert response.status_code == 500
    with session_factory() as session:
        assert persistence_snapshot(session, simulation_id) == before


def test_metadata_failure_rolls_back_runtime_results_and_tick_writes(
    api_client, monkeypatch
) -> None:
    from app.domain.models import AgentMemory, AgentState, Relationship
    from app.api import ticks
    from app.services import manual_tick

    client, session_factory = api_client
    simulation_id, headers = register_login_create(client)
    with session_factory() as session:
        seed_rollback_rows(session, simulation_id)
        before = persistence_snapshot(session, simulation_id)

    original_record = manual_tick.record_execution_metadata
    original_advance = manual_tick.advance_manual_tick

    async def advance_with_policy(session, simulation, *, runtime):
        async def policy(_inputs):
            return None

        return await original_advance(
            session,
            simulation,
            runtime=runtime,
            policy=policy,
            policy_version="policy-slice4-transaction-v1",
            seed=4242,
        )

    def fail_after_all_tick_writes(session, metadata):
        assert metadata.seed == 4242
        assert metadata.model == "slice4-persistence-model"
        assert metadata.prompt_version == "slice4-persistence-prompt-v1"
        assert metadata.policy_version == "policy-slice4-transaction-v1"
        execution = original_record(session, metadata)
        state = session.scalar(
            select(AgentState)
            .where(AgentState.simulation_id == simulation_id)
            .order_by(AgentState.agent_id)
            .limit(1)
        )
        relationship = session.scalar(
            select(Relationship).where(
                Relationship.simulation_id == simulation_id
            )
        )
        state.stress += 10
        relationship.trust += 10
        session.add(
            AgentMemory(
                id=uuid7(),
                agent_id=state.agent_id,
                event_id=None,
                content="must be rolled back",
                memory_type="observation",
                importance=50,
                created_tick=metadata.tick_number,
                occurred_at=datetime.now(UTC),
                embedding=None,
            )
        )
        session.flush()
        assert execution.id is not None
        raise RuntimeError("metadata boundary failure")

    monkeypatch.setattr(
        manual_tick, "record_execution_metadata", fail_after_all_tick_writes
    )
    monkeypatch.setattr(ticks, "advance_manual_tick", advance_with_policy)
    response = client.post(
        f"/v1/simulations/{simulation_id}/ticks/advance", headers=headers
    )

    assert response.status_code == 500
    with session_factory() as session:
        assert persistence_snapshot(session, simulation_id) == before


def test_persona_start_and_execution_metadata_persist_through_api_to_db(
    api_client,
) -> None:
    from app.domain.models import (
        Agent,
        RuntimeExecution,
        RuntimeResult,
        Simulation,
        UserPersonaConfig,
    )

    client, session_factory = api_client
    simulation_id, headers = register_login_create(client)
    agents = client.get(
        f"/v1/simulations/{simulation_id}/agents", headers=headers
    ).json()
    persona_id = next(
        agent["id"] for agent in agents if agent["fixture_key"] == "student-03"
    )
    persona_payload = {
        "agent_id": persona_id,
        "mbti_type": "INFP",
        "personality_rule_version": "mbti-big-five-v0.1",
        "openness": 25,
        "conscientiousness": -25,
        "extraversion": -25,
        "agreeableness": 20,
        "emotional_stability": 0,
    }

    assert client.post(
        f"/v1/simulations/{simulation_id}/user-persona",
        headers=headers,
        json=persona_payload,
    ).status_code == 200
    assert client.post(
        f"/v1/simulations/{simulation_id}/start", headers=headers
    ).status_code == 200
    tick = client.post(
        f"/v1/simulations/{simulation_id}/ticks/advance", headers=headers
    )
    assert tick.status_code == 200, tick.text

    with session_factory() as session:
        simulation = session.get(Simulation, simulation_id)
        persona = session.get(Agent, UUID(persona_id))
        config = session.scalar(
            select(UserPersonaConfig).where(
                UserPersonaConfig.simulation_id == simulation_id
            )
        )
        execution = session.scalar(
            select(RuntimeExecution).where(
                RuntimeExecution.simulation_id == simulation_id
            )
        )
        results = list(
            session.scalars(
                select(RuntimeResult).where(
                    RuntimeResult.run_id == execution.run_id
                )
            )
        )

        assert simulation.status == "running"
        assert simulation.current_tick == 1
        assert persona.persona_locked_at is not None
        assert persona.mbti_type == config.mbti_type == "INFP"
        assert execution.seed >= 0
        assert execution.model == "slice4-persistence-model"
        assert execution.prompt_version == "slice4-persistence-prompt-v1"
        assert execution.policy_version is None
        assert results
        assert {result.model for result in results} == {execution.model}
        assert {result.prompt_version for result in results} == {
            execution.prompt_version
        }
