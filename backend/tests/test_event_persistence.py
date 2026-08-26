"""Task 3 uses a migrated, dedicated PostgreSQL database; never truncates data."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.domain.models import Agent, AgentMemory, AgentState, Event, Simulation, User
from app.services.fixtures import seed_slice_zero
from app.services.event_persistence import persist_event_batch
from app.domain.event_persistence import EventBatch
from app.repositories.event_results import get_event_result


@pytest.fixture
def db():
    """Isolate every test in an outer transaction, including explicit commit tests."""
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required")
    engine = create_engine(url)
    with engine.connect() as connection:
        outer = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as session:
            yield session
        outer.rollback()
    engine.dispose()


def setup_simulation(db):
    """Create unique owned fixtures without touching existing rows."""
    user = User(id=uuid4(), username=str(uuid4()), display_name="test", password_hash="test", roles=["USER"])
    db.add(user)
    db.flush()
    simulation = Simulation(id=uuid4(), owner_id=user.id, name="Task3")
    db.add(simulation)
    db.flush()
    seed_slice_zero(db, simulation.id)
    state = db.scalar(select(AgentState).join(Agent, Agent.id == AgentState.agent_id).where(
        AgentState.simulation_id == simulation.id, Agent.fixture_key == "student-01"
    ))
    db.commit()
    return simulation.id, state.agent_id, state.location_id


def make_batch(db, simulation_id, agent_id, location_id, **changes):
    """Build a resolved result, not an expected_effects preview."""
    state = db.scalar(select(AgentState).where(AgentState.agent_id == agent_id))
    data = dict(
        simulation_id=simulation_id, run_id="test-run", tick_number=1,
        policy_version="test-policy", resolver_version="test-resolver", resolution_id="test-resolution",
        events=[dict(id=uuid4(), event_type="CLASS", title="Class", description="Lesson",
                     participant_agent_ids=[agent_id], location_id=location_id, source="event_master",
                     impact_level="high", importance=80)],
        resolved_effects=[dict(source_agent_id=agent_id, metric="stress", before=state.stress,
                               requested_total=1, applied_delta=1, after=state.stress + 1, effect_ids=["e1"])],
    )
    data.update(changes)
    return EventBatch.model_validate(data)


def test_rejects_preview_and_invalid_delta():
    """Unknown preview and arithmetic mismatch must not reach SQL."""
    from app.domain.event_persistence import StateDelta
    with pytest.raises(ValidationError):
        StateDelta(source_agent_id=uuid4(), metric="stress", before=1, after=3,
                   requested_total=1, applied_delta=1, effect_ids=["x"])
    with pytest.raises(ValidationError):
        StateDelta(source_agent_id=uuid4(), metric="stress", before=1, after=2,
                   requested_total=1, applied_delta=1, effect_ids=["x"], after_preview=2)


def test_save_read_and_idempotency(db):
    """Event, Memory and State survive commit and duplicate delivery is a no-op."""
    ids = setup_simulation(db)
    batch = make_batch(db, *ids)
    batch = EventBatch.model_validate({**batch.model_dump(), "memories": [dict(
        agent_id=ids[1], event_id=batch.events[0].id, content="Remember class",
        memory_type="observation", importance=80, occurred_at=datetime.now(UTC))]})
    saved = persist_event_batch(db, batch)
    db.commit()
    assert get_event_result(db, ids[0], 1) == saved
    assert persist_event_batch(db, batch) == saved
    assert db.scalar(select(func.count()).select_from(Event).where(Event.id == batch.events[0].id)) == 1
    assert db.scalar(select(func.count()).select_from(AgentMemory).where(AgentMemory.event_id == batch.events[0].id)) == 1
    assert saved["resolved_effects"][0]["after"] == batch.resolved_effects[0].after
    with pytest.raises(ValueError, match="different"):
        persist_event_batch(db, batch.model_copy(update={"resolution_id": "changed"}))


def test_failure_after_flush_rolls_back_entire_batch(db):
    """The caller's rollback restores Event, Memory, State and result together."""
    ids = setup_simulation(db)
    batch = make_batch(db, *ids)
    batch = EventBatch.model_validate({**batch.model_dump(), "memories": [dict(
        agent_id=ids[1], event_id=batch.events[0].id, content="rollback memory",
        memory_type="observation", importance=80, occurred_at=datetime.now(UTC))]})
    before = batch.resolved_effects[0].before
    persist_event_batch(db, batch)
    db.get(Simulation, ids[0]).current_tick = 1
    db.flush()
    db.rollback()  # Simulate a subsequent Tick stage failing after persistence flush.
    assert db.get(Event, batch.events[0].id) is None
    assert get_event_result(db, ids[0], 1) is None
    assert db.scalar(select(func.count()).select_from(AgentMemory).where(AgentMemory.event_id == batch.events[0].id)) == 0
    assert db.get(Simulation, ids[0]).current_tick == 0
    assert db.scalar(select(AgentState.stress).where(AgentState.agent_id == ids[1])) == before


def test_rejects_cross_simulation_and_stale_state(db):
    """Cross-simulation references and stale snapshots never become committed data."""
    ids = setup_simulation(db)
    other = setup_simulation(db)
    batch = make_batch(db, *ids)
    foreign = batch.events[0].model_copy(update={"location_id": other[2]})
    with pytest.raises(ValueError, match="Location"):
        persist_event_batch(db, batch.model_copy(update={"events": (foreign,)}))
    db.rollback()
    state = db.scalar(select(AgentState).where(AgentState.agent_id == ids[1]))
    state.stress += 2
    db.flush()
    with pytest.raises(ValueError, match="stale"):
        persist_event_batch(db, batch)
    db.rollback()
    assert db.get(Event, batch.events[0].id) is None


def test_missing_and_curse_expire_at_exact_tick(db):
    """Missing N -> active/cursed N+3 -> curse expires N+6."""
    ids = setup_simulation(db)
    batch = make_batch(db, *ids, missing_agent_ids=[ids[1]])
    special = batch.events[0].model_copy(update={"event_type": "STUDENT_MISSING", "source": "magic_layer"})
    batch = batch.model_copy(update={"events": (special,)})
    persist_event_batch(db, batch)
    agent = db.get(Agent, ids[1])
    assert (agent.active_status, agent.inactive_until_tick) == ("inactive_temporary", 4)
    for tick in range(2, 8):
        db.get(Simulation, ids[0]).current_tick = tick - 1
        db.flush()
        empty = batch.model_copy(update={"tick_number": tick, "events": (), "resolved_effects": (), "missing_agent_ids": ()})
        persist_event_batch(db, empty)
        if tick == 3:
            assert agent.active_status == "inactive_temporary"
        if tick == 4:
            assert agent.active_status == "active"
            assert agent.cursed_until_tick == 7
        if tick == 7:
            assert agent.cursed_until_tick is None


def test_memory_failure_after_event_and_state_flush(db, monkeypatch):
    """A later repository failure must leave no earlier Event or State writes."""
    from app.repositories.memory_repository import MemoryRepository
    ids = setup_simulation(db)
    batch = make_batch(db, *ids)
    batch = EventBatch.model_validate({**batch.model_dump(), "memories": [dict(
        agent_id=ids[1], event_id=batch.events[0].id, content="failure",
        memory_type="observation", importance=80, occurred_at=datetime.now(UTC))]})

    def fail(*args, **kwargs):
        """Inject failure only after verifying earlier writes reached the DB."""
        assert db.get(Event, batch.events[0].id) is not None
        assert db.scalar(select(AgentState.stress).where(AgentState.agent_id == ids[1])) == batch.resolved_effects[0].after
        raise RuntimeError("Memory storage failed")

    monkeypatch.setattr(MemoryRepository, "create", fail)
    with pytest.raises(RuntimeError, match="Memory storage"):
        persist_event_batch(db, batch)
    db.rollback()
    assert db.get(Event, batch.events[0].id) is None
    assert db.scalar(select(AgentState.stress).where(AgentState.agent_id == ids[1])) == batch.resolved_effects[0].before


def test_rest_matches_committed_result_and_ownership(db):
    """The registered route uses actual JWT verification and owner checks."""
    from fastapi.testclient import TestClient
    from app.core.database import get_db
    from app.core.security import create_access_token
    from app.main import app

    ids = setup_simulation(db)
    other = setup_simulation(db)
    batch = make_batch(db, *ids)
    saved = persist_event_batch(db, batch)
    db.commit()
    owner = db.get(User, db.get(Simulation, ids[0]).owner_id)
    stranger = db.get(User, db.get(Simulation, other[0]).owner_id)
    headers = {"Authorization": "Bearer " + create_access_token(owner)}
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            path = f"/v1/simulations/{ids[0]}/event-results/1"
            assert client.get(path).status_code == 401
            assert client.get(path, headers={"Authorization": "Bearer invalid"}).status_code == 401
            response = client.get(path, headers=headers)
            assert response.status_code == 200
            assert response.json() == saved
            assert client.get(path, headers={"Authorization": "Bearer " + create_access_token(stranger)}).status_code == 403
            assert client.get(f"/v1/simulations/{uuid4()}/event-results/1", headers=headers).status_code == 404
            assert client.get(f"/v1/simulations/{ids[0]}/event-results/2", headers=headers).status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_rejects_foreign_memory_and_duplicate_state_target(db):
    """Cross-simulation Memory and unresolved duplicate targets are rejected."""
    ids = setup_simulation(db)
    other = setup_simulation(db)
    batch = make_batch(db, *ids)
    foreign = EventBatch.model_validate({**batch.model_dump(), "memories": [dict(
        agent_id=other[1], event_id=batch.events[0].id, content="foreign",
        memory_type="observation", importance=50, occurred_at=datetime.now(UTC))]})
    with pytest.raises(ValueError, match="participating"):
        persist_event_batch(db, foreign)
    with pytest.raises(ValidationError, match="duplicate"):
        EventBatch.model_validate({**batch.model_dump(), "resolved_effects": [batch.resolved_effects[0]] * 2})


def test_memory_cap_and_magic_type_preserved(db):
    """New memories respect the existing cap; Magic is not RANDOM_INCIDENT."""
    ids = setup_simulation(db)
    batch = make_batch(db, *ids)
    event = batch.events[0].model_copy(update={"event_type": "MAGIC_EXPLOSION", "source": "magic_layer"})
    batch = EventBatch.model_validate({**batch.model_dump(), "events": [event], "memories": [dict(
        agent_id=ids[1], event_id=event.id, content=f"memory {index}",
        memory_type="observation", importance=80, occurred_at=datetime.now(UTC)) for index in range(12)]})
    saved = persist_event_batch(db, batch)
    db.commit()
    assert db.get(Event, event.id).event_type == "magic_explosion"
    assert db.scalar(select(func.count()).select_from(AgentMemory).where(AgentMemory.agent_id == ids[1])) == 10
    assert len(saved["memories"]) == 10


def test_concurrent_delivery_is_applied_once():
    """Two real transactions serialize on the Simulation row and reuse results."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL required")
    engine = create_engine(url)
    try:
        with Session(engine) as session:
            ids = setup_simulation(session)
            batch = make_batch(session, *ids)
        barrier = Barrier(2)

        def deliver():
            """Commit a batch with Tick progress in the caller's transaction."""
            with Session(engine) as session, session.begin():
                barrier.wait(timeout=10)
                result = persist_event_batch(session, batch)
                session.get(Simulation, ids[0]).current_tick = 1
                return result

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: deliver(), range(2)))
        assert results[0] == results[1]
        with Session(engine) as session:
            assert session.scalar(select(AgentState.stress).where(AgentState.agent_id == ids[1])) == batch.resolved_effects[0].after
            assert session.scalar(select(func.count()).select_from(Event).where(Event.id == batch.events[0].id)) == 1
            assert get_event_result(session, ids[0], 1) == results[0]
    finally:
        engine.dispose()


def test_database_failure_rolls_back_prior_writes(db):
    """A real constraint failure aborts State, Event and result persistence."""
    from sqlalchemy.exc import IntegrityError
    ids = setup_simulation(db)
    batch = make_batch(db, *ids)
    persist_event_batch(db, batch)
    db.get(Simulation, ids[0]).current_tick = -1
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
    assert db.get(Event, batch.events[0].id) is None
    assert get_event_result(db, ids[0], 1) is None
    assert db.scalar(select(AgentState.stress).where(AgentState.agent_id == ids[1])) == batch.resolved_effects[0].before
