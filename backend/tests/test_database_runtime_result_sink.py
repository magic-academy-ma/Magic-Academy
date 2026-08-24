import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.domain.models import RuntimeResult
from app.repositories.runtime_results import (
    get_by_idempotency_key,
    list_errors_by_run,
    list_results_by_run,
)
from app.services.database_runtime_results import DatabaseRuntimeResultSink
from app.services.runtime_results import IdempotencyConflictError
from app.simulation.agent_runtime import (
    AgentRuntimeInput,
    AgentRuntimeResult,
    MockLLMClient,
    RuntimeStatus,
    validate_intent_candidate,
)


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")

AGENT_IDS = [UUID(f"00000000-0000-7000-8000-{index:012d}") for index in range(1, 4)]
LOCATION_ID = UUID("10000000-0000-7000-8000-000000000001")
EVENT_ID = UUID("20000000-0000-7000-8000-000000000001")


@pytest.fixture()
def session_factory():
    engine = create_engine(TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE runtime_results, users, simulations, locations, agents RESTART IDENTITY CASCADE"))
        connection.execute(
            text(
                "INSERT INTO users (id, username, display_name, password_hash, roles) "
                "VALUES (:id, 'runtime-owner', 'Runtime Owner', 'hash', '[\"USER\"]'::jsonb)"
            ),
            {"id": uuid4()},
        )
        owner_id = connection.scalar(text("SELECT id FROM users WHERE username = 'runtime-owner'"))
        simulation_id = uuid4()
        connection.execute(
            text("INSERT INTO simulations (id, owner_id, name) VALUES (:id, :owner_id, 'Runtime Test')"),
            {"id": simulation_id, "owner_id": owner_id},
        )
        for index, agent_id in enumerate(AGENT_IDS, start=1):
            connection.execute(
                text(
                    "INSERT INTO agents "
                    "(id, simulation_id, fixture_key, fixture_version, agent_type, name, gender, mbti_type, active_status) "
                    "VALUES (:id, :simulation_id, :fixture_key, 'runtime-test-v1', 'student', :name, 'unspecified', 'ISTJ', true)"
                ),
                {
                    "id": agent_id,
                    "simulation_id": simulation_id,
                    "fixture_key": f"runtime-{index}",
                    "name": f"Runtime Agent {index}",
                },
            )
    yield factory
    engine.dispose()


def make_result(
    agent_index: int = 0,
    *,
    status: RuntimeStatus = RuntimeStatus.PROPOSED,
) -> AgentRuntimeResult:
    agent_id = AGENT_IDS[agent_index]
    runtime_input = AgentRuntimeInput.model_validate(
        {
            "run_id": "runtime-db-run",
            "tick_number": 3,
            "block": "MORNING",
            "agent": {
                "agent_id": agent_id,
                "fixture_key": "student-01",
                "agent_type": "student",
                "name": "Student",
                "mbti": "ISTJ",
                "big_five": {key: 0 for key in ("openness", "conscientiousness", "extraversion", "agreeableness", "emotional_stability")},
                "state": {"hunger": 0, "fatigue": 0, "stress": 0, "satisfaction": 0, "mood": 0},
                "current_location_id": LOCATION_ID,
                "active_status": True,
            },
            "nearby_agents": [],
            "relationships": [],
            "memories": [],
            "events": [{"event_id": EVENT_ID, "event_type": "class", "location_id": LOCATION_ID, "participant_agent_ids": [agent_id]}],
            "schedule": {"event_id": EVENT_ID, "schedule_type": "class", "is_mandatory": True, "location_id": LOCATION_ID, "start_tick": 3, "end_tick": 3},
            "valid_agent_ids": AGENT_IDS,
            "valid_location_ids": [LOCATION_ID],
        }
    )
    intent = validate_intent_candidate(MockLLMClient().generate(runtime_input), runtime_input)
    return AgentRuntimeResult(
        run_id=runtime_input.run_id,
        tick_number=runtime_input.tick_number,
        agent_id=agent_id,
        status=status,
        intent=intent,
        retry_count=1 if status == RuntimeStatus.FALLBACK else 0,
        failure_reason="validation failed" if status == RuntimeStatus.FALLBACK else None,
        model="mock-llm",
        prompt_version="agent-runtime-10.1",
        idempotency_key=f"{runtime_input.run_id}:{runtime_input.tick_number}:{agent_id}",
    )


def test_database_sink_saves_tick_batch_and_repository_reads_it(session_factory) -> None:
    results = [make_result(0), make_result(1, status=RuntimeStatus.FALLBACK)]

    with session_factory() as session:
        with session.begin():
            saved = DatabaseRuntimeResultSink(session).save_batch(results)

    assert saved.new_count == 2
    assert saved.duplicate_count == 0
    with session_factory() as session:
        assert get_by_idempotency_key(session, results[0].idempotency_key).action_type == results[0].intent.action_type
        assert len(list_results_by_run(session, "runtime-db-run")) == 2
        errors = list_errors_by_run(session, "runtime-db-run")
        assert len(errors) == 1
        assert errors[0].failure_reason == "validation failed"


def test_database_sink_persists_only_structured_decision_explanation(session_factory) -> None:
    result = make_result()

    with session_factory() as session:
        with session.begin():
            DatabaseRuntimeResultSink(session).save_batch([result])

    with session_factory() as session:
        stored = get_by_idempotency_key(session, result.idempotency_key)
        explanation = stored.intent["decision_explanation"]
        assert set(explanation) == {"alternatives", "influencing_factors"}
        assert "chain_of_thought" not in stored.intent
        assert "reasoning" not in stored.intent


def test_database_sink_treats_same_result_as_idempotent_noop(session_factory) -> None:
    result = make_result()
    with session_factory() as session:
        with session.begin():
            DatabaseRuntimeResultSink(session).save_batch([result])

    with session_factory() as session:
        with session.begin():
            saved = DatabaseRuntimeResultSink(session).save_batch(
                [result.model_copy(deep=True)]
            )

    assert saved.new_count == 0
    assert saved.duplicate_count == 1


def test_database_sink_treats_concurrent_same_result_as_idempotent_noop(
    session_factory,
) -> None:
    start_barrier = Barrier(2)

    result = make_result()

    def save_concurrently(_):
        with session_factory() as session:
            with session.begin():
                start_barrier.wait()
                return DatabaseRuntimeResultSink(session).save_batch([result])

    with ThreadPoolExecutor(max_workers=2) as executor:
        saves = list(executor.map(save_concurrently, range(2)))

    assert sum(save.new_count for save in saves) == 1
    assert sum(save.duplicate_count for save in saves) == 1
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(RuntimeResult)) == 1


def test_database_sink_rejects_noncanonical_idempotency_key(session_factory) -> None:
    result = make_result().model_copy(update={"idempotency_key": "another-key"})

    with session_factory() as session:
        with pytest.raises(ValidationError, match="run_id:tick_number:agent_id"):
            with session.begin():
                DatabaseRuntimeResultSink(session).save_batch([result])


def test_database_sink_rejects_same_key_with_different_result(session_factory) -> None:
    result = make_result()
    with session_factory() as session:
        with session.begin():
            DatabaseRuntimeResultSink(session).save_batch([result])
    changed = result.model_copy(deep=True)
    changed.intent.motivation_summary = "different result"

    with session_factory() as session:
        with pytest.raises(IdempotencyConflictError):
            with session.begin():
                DatabaseRuntimeResultSink(session).save_batch([changed])


def test_database_sink_participates_in_caller_transaction(session_factory) -> None:
    result = make_result()

    with session_factory() as session:
        with pytest.raises(RuntimeError, match="later Tick phase failed"):
            with session.begin():
                DatabaseRuntimeResultSink(session).save_batch([result])
                raise RuntimeError("later Tick phase failed")

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(RuntimeResult)) == 0


def test_database_sink_rolls_back_whole_batch_when_one_insert_fails(session_factory) -> None:
    valid = make_result(0)
    missing_agent_id = uuid4()
    missing_agent = make_result(1).model_copy(
        update={
            "agent_id": missing_agent_id,
            "idempotency_key": f"runtime-db-run:3:{missing_agent_id}",
        }
    )

    with session_factory() as session:
        with pytest.raises(IntegrityError):
            with session.begin():
                DatabaseRuntimeResultSink(session).save_batch([valid, missing_agent])

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(RuntimeResult)) == 0
