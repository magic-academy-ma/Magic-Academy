from dataclasses import fields, is_dataclass
from typing import get_type_hints
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.simulation import agent_runtime, tick_engine
from app.simulation.tick_engine import MemoryCandidateItem


AGENT_ID = UUID("00000000-0000-0000-0000-000000000001")


def valid_runtime_result_payload() -> dict[str, object]:
    return {
        "run_id": "slice-3-memory-contract",
        "tick_number": 3,
        "agent_id": AGENT_ID,
        "status": "PROPOSED",
        "intent": {
            "action_type": "STUDY",
            "target_agent_id": None,
            "target_location_id": None,
            "related_event_id": None,
            "utterance": None,
            "motivation_summary": "마법 이론을 복습한다.",
            "reaction": {
                "valence": "NEUTRAL",
                "relationship_signals": [],
                "state_signals": [],
            },
            "decision_explanation": {
                "alternatives": [
                    {
                        "action_type": "STUDY",
                        "description": "마법 이론을 복습한다.",
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
        "model": "mock-llm",
        "prompt_version": "agent-runtime-10.1",
        "idempotency_key": f"slice-3-memory-contract:3:{AGENT_ID}",
    }


def test_memory_item_contract() -> None:
    assert is_dataclass(tick_engine.MemoryItem)
    assert [field.name for field in fields(tick_engine.MemoryItem)] == [
        "id",
        "content",
        "memory_type",
        "importance",
        "created_tick",
        "event_id",
    ]


def test_memory_candidate_item_contract_and_legacy_import_path() -> None:
    assert is_dataclass(agent_runtime.MemoryCandidateItem)
    assert [field.name for field in fields(agent_runtime.MemoryCandidateItem)] == [
        "content",
        "memory_type",
        "importance",
    ]
    assert not hasattr(
        agent_runtime.MemoryCandidateItem(
            content="카이와 과제를 함께 정리했다.",
            memory_type="conversation",
            importance=4,
        ),
        "id",
    )
    assert tick_engine.MemoryCandidateItem is agent_runtime.MemoryCandidateItem
    assert MemoryCandidateItem is agent_runtime.MemoryCandidateItem


def test_runtime_result_memory_candidate_defaults_to_none() -> None:
    result = agent_runtime.AgentRuntimeResult.model_validate(
        valid_runtime_result_payload()
    )

    assert result.memory_candidate is None
    assert (
        get_type_hints(agent_runtime.AgentRuntimeResult)["memory_candidate"]
        == MemoryCandidateItem | None
    )


def test_runtime_result_preserves_memory_candidate() -> None:
    payload = valid_runtime_result_payload()
    payload["memory_candidate"] = MemoryCandidateItem(
        content="마법 이론을 복습했다.",
        memory_type="observation",
        importance=6,
    )

    result = agent_runtime.AgentRuntimeResult.model_validate(payload)

    assert result.memory_candidate == MemoryCandidateItem(
        content="마법 이론을 복습했다.",
        memory_type="observation",
        importance=6,
    )


def test_runtime_result_rejects_unexpected_extra_field() -> None:
    payload = valid_runtime_result_payload()
    payload["unexpected"] = "value"

    with pytest.raises(ValidationError, match="unexpected"):
        agent_runtime.AgentRuntimeResult.model_validate(payload)
