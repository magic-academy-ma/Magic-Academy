"""Dialogue persistence — Runtime mutual TALK pairs are written to the DB.

기존 DB 테스트 스타일(TEST_DATABASE_URL 필요)을 따른다. Runtime 이 만든 대화를
DatabaseDialogueSink 가 simulation DB 에 영속화하고, 발화 순서/참여자/안정적 id 가
보존되는지 검증한다.
"""

import os
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker
from uuid6 import uuid7

from app.domain.models import Agent, Dialogue, DialogueMessage, Simulation, User
from app.services.database_dialogue_results import (
    DatabaseDialogueSink,
    DialogueParticipantError,
)
from app.services.dialogue_results import DialogueBatchSaveResult
from app.services.fixtures import seed_slice_zero
from app.simulation.agent_runtime import AgentRuntimeResult
from app.simulation.intent_conflict import resolve_talk_conflicts

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")

RUN_ID = "dlg-persist-run"
TICK = 4


@pytest.fixture()
def session_factory():
    engine = create_engine(TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE users, simulations, locations, agents, agent_states, "
                "dialogues, dialogue_messages RESTART IDENTITY CASCADE"
            )
        )
    return factory


def _seed_simulation(session_factory) -> tuple[UUID, list[UUID]]:
    simulation_id = uuid7()
    with session_factory() as session:
        user_id = uuid7()
        session.add(
            User(
                id=user_id,
                username=f"dlg-{user_id.hex[:8]}",
                display_name="dlg",
                password_hash="x",
            )
        )
        session.add(
            Simulation(id=simulation_id, owner_id=user_id, name="dlg", status="ready")
        )
        session.flush()
        seed_slice_zero(session, simulation_id)
        agent_ids = list(
            session.scalars(
                select(Agent.id)
                .where(Agent.simulation_id == simulation_id)
                .order_by(Agent.fixture_key)
            )
        )
        session.commit()
    return simulation_id, agent_ids


def _talk(agent_id: UUID, target_id: UUID, utterance: str | None) -> AgentRuntimeResult:
    return AgentRuntimeResult.model_validate(
        {
            "run_id": RUN_ID,
            "tick_number": TICK,
            "agent_id": agent_id,
            "status": "PROPOSED",
            "intent": {
                "action_type": "TALK",
                "target_agent_id": target_id,
                "target_location_id": None,
                "related_event_id": None,
                "utterance": utterance,
                "motivation_summary": "대화",
                "reaction": {
                    "valence": "NEUTRAL",
                    "relationship_signals": [],
                    "state_signals": [],
                },
                "decision_explanation": {
                    "alternatives": [
                        {
                            "action_type": "TALK",
                            "description": "대화한다.",
                            "relative_priority": "HIGH",
                            "selected": True,
                        }
                    ],
                    "influencing_factors": [],
                },
                "memory_candidates": [],
            },
            "retry_count": 0,
            "failure_reason": None,
            "model": "test",
            "prompt_version": "test",
            "idempotency_key": f"{RUN_ID}:{TICK}:{agent_id}",
        }
    )


def test_mutual_talk_pair_is_persisted_with_ordered_messages(session_factory) -> None:
    simulation_id, agent_ids = _seed_simulation(session_factory)
    speaker, listener = agent_ids[0], agent_ids[1]
    resolution = resolve_talk_conflicts(
        (_talk(speaker, listener, "결계가 흔들려."), _talk(listener, speaker, "확인해볼게."))
    )

    with session_factory() as session:
        result = DatabaseDialogueSink(session).save_batch(resolution)
        session.commit()

    assert result == DialogueBatchSaveResult(new_count=1, duplicate_count=0)

    with session_factory() as session:
        dialogue = session.scalar(
            select(Dialogue).where(Dialogue.simulation_id == simulation_id)
        )
        assert dialogue is not None
        assert dialogue.run_id == RUN_ID
        assert dialogue.tick_number == TICK
        assert {dialogue.participant_a_id, dialogue.participant_b_id} == {speaker, listener}
        messages = list(
            session.scalars(
                select(DialogueMessage)
                .where(DialogueMessage.dialogue_id == dialogue.id)
                .order_by(DialogueMessage.message_order)
            )
        )
    assert [(m.message_order, m.speaker_agent_id, m.utterance) for m in messages] == [
        (0, speaker, "결계가 흔들려."),
        (1, listener, "확인해볼게."),
    ]


def test_dialogue_id_is_a_stable_db_uuid(session_factory) -> None:
    _, agent_ids = _seed_simulation(session_factory)
    resolution = resolve_talk_conflicts(
        (_talk(agent_ids[0], agent_ids[1], "a"), _talk(agent_ids[1], agent_ids[0], "b"))
    )
    with session_factory() as session:
        DatabaseDialogueSink(session).save_batch(resolution)
        session.commit()
    with session_factory() as session:
        ids = list(session.scalars(select(Dialogue.id)))
    assert len(ids) == 1
    assert isinstance(ids[0], UUID)


def test_save_batch_is_idempotent_for_same_pair_and_tick(session_factory) -> None:
    _, agent_ids = _seed_simulation(session_factory)
    resolution = resolve_talk_conflicts(
        (_talk(agent_ids[0], agent_ids[1], "a"), _talk(agent_ids[1], agent_ids[0], "b"))
    )
    with session_factory() as session:
        first = DatabaseDialogueSink(session).save_batch(resolution)
        session.commit()
    with session_factory() as session:
        second = DatabaseDialogueSink(session).save_batch(resolution)
        session.commit()

    assert (first.new_count, second.new_count, second.duplicate_count) == (1, 0, 1)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Dialogue)) == 1
        assert session.scalar(select(func.count()).select_from(DialogueMessage)) == 2


def test_non_talk_batch_writes_no_dialogue(session_factory) -> None:
    _, agent_ids = _seed_simulation(session_factory)
    # 성립하지 않는 TALK 하나뿐 → WAIT_FALLBACK, mutual pair 없음.
    resolution = resolve_talk_conflicts((_talk(agent_ids[0], agent_ids[1], "혼잣말"),))
    with session_factory() as session:
        result = DatabaseDialogueSink(session).save_batch(resolution)
        session.commit()
    assert result == DialogueBatchSaveResult(new_count=0, duplicate_count=0)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Dialogue)) == 0


def test_unknown_participant_agent_is_rejected(session_factory) -> None:
    _, agent_ids = _seed_simulation(session_factory)
    ghost = uuid4()
    resolution = resolve_talk_conflicts(
        (_talk(agent_ids[0], ghost, "a"), _talk(ghost, agent_ids[0], "b"))
    )
    with session_factory() as session, pytest.raises(DialogueParticipantError):
        DatabaseDialogueSink(session).save_batch(resolution)
