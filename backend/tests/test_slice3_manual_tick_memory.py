import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from uuid6 import uuid7

from app.domain.models import Agent, AgentMemory, Event, User
from app.services.manual_tick import advance_manual_tick
from app.services.memory_adapter import MemoryAdapter
from app.services.simulations import create_simulation
from app.simulation.agent_runtime import AgentRuntime, AgentRuntimeInput, MockLLMClient

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")


class FakeEmbeddingClient:
    async def embed(self, text: str) -> list[float]:
        return [0.1] * 1536


class RecordingLLMClient:
    def __init__(self) -> None:
        self.inputs: list[AgentRuntimeInput] = []
        self._delegate = MockLLMClient()

    def generate(self, runtime_input):
        self.inputs.append(runtime_input)
        return self._delegate.generate(runtime_input)


@pytest.fixture()
def session_factory():
    engine = create_engine(TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE runtime_results, agent_memories, event_participants, events, "
                "users, simulations, locations, agents RESTART IDENTITY CASCADE"
            )
        )
    yield factory
    engine.dispose()


def test_manual_tick_stores_then_retrieves_memory_for_next_runtime_input(session_factory) -> None:
    recording_client = RecordingLLMClient()
    runtime = AgentRuntime(recording_client, model="slice3-memory-integration")

    with session_factory() as db:
        owner = User(
            id=uuid7(),
            username="slice3-memory-owner",
            display_name="Slice 3 Memory Owner",
            password_hash="test-only",
            roles=["USER"],
        )
        db.add(owner)
        db.flush()
        simulation = create_simulation(db, owner, "Slice 3 Memory E2E")
        student = db.scalar(
            select(Agent).where(
                Agent.simulation_id == simulation.id,
                Agent.fixture_key == "student-01",
            )
        )
        event = db.scalar(
            select(Event).where(
                Event.simulation_id == simulation.id,
                Event.event_type == "class",
            )
        )
        now = datetime.now(UTC)
        db.add_all(
            [
                AgentMemory(
                    id=uuid7(),
                    agent_id=student.id,
                    event_id=event.id,
                    content=f"기존 기억 {index}",
                    memory_type="observation",
                    importance=index,
                    created_tick=0,
                    occurred_at=now - timedelta(minutes=index),
                    embedding=[0.1] * 1536,
                )
                for index in range(10)
            ]
        )
        db.commit()

        adapter = MemoryAdapter(db, embedding_client=FakeEmbeddingClient())
        first = asyncio.run(
            advance_manual_tick(db, simulation, runtime=runtime, memory_adapter=adapter)
        )
        db.commit()

        assert str(student.id) in first.retrieval_traces
        assert db.scalar(
            select(func.count()).select_from(AgentMemory).where(AgentMemory.agent_id == student.id)
        ) == 10
        assert db.scalar(
            select(func.count()).select_from(AgentMemory).where(
                AgentMemory.agent_id == student.id,
                AgentMemory.created_tick == 1,
            )
        ) == 1

        recording_client.inputs.clear()
        second = asyncio.run(
            advance_manual_tick(db, simulation, runtime=runtime, memory_adapter=adapter)
        )
        db.commit()

        student_input = next(item for item in recording_client.inputs if item.agent.agent_id == student.id)
        assert student_input.memories
        assert any(memory["created_tick"] == 1 for memory in student_input.memories)
        assert str(student.id) in second.retrieval_traces
        assert db.scalar(
            select(func.count()).select_from(AgentMemory).where(AgentMemory.agent_id == student.id)
        ) == 10
