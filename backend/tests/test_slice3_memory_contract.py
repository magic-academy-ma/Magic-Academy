from dataclasses import fields, is_dataclass

from app.simulation import agent_runtime, tick_engine
from app.simulation.tick_engine import MemoryCandidateItem


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
