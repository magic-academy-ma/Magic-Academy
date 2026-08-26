"""Slice 5 Task 1 — Event Master -> Magic Layer -> Policy/Resolver bridge.

Wires the three components through their existing typed contracts so the
pipeline is not a dead implementation (Issue #101 §7). This module performs
no DB writes and does not call ``persist_event_batch``: turning its result
into a Task 3 ``EventBatch`` and committing it inside the fenced Tick
transaction is Task 5's job (slice-5-integration.md §5,
"TODO(#101/#105): ... lease/fence 검증·Tick 진행·WS 발행을 상위 통합 경계에서 수행한다").
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.simulation.event_master import (
    AgentSummary as EventMasterAgentSummary,
    Event,
    EventMaster,
    RelationshipSummary as EventMasterRelationshipSummary,
    ScheduledEventInput,
)
from app.simulation.magic_layer import (
    AgentSnapshot as MagicAgentSnapshot,
    MagicLayer,
    SpecialEvent,
)
from app.simulation.policy.conflict import resolve_conflicts
from app.simulation.policy.models import AgentSnapshot, EffectCandidate, RelationshipSnapshot
from app.simulation.policy.registries.event_policy import (
    build_event_effect_candidates,
    build_magic_effect_candidates,
)


@dataclass(frozen=True)
class EventAndMagicResult:
    events: tuple[Event, ...]
    special_events: tuple[SpecialEvent, ...]
    resolved_effects: tuple[EffectCandidate, ...]
    reflection_eligible_event_keys: tuple[str, ...]


REFLECTION_IMPORTANCE_THRESHOLD = 70


def run_event_and_magic_phase(
    *,
    run_id: str,
    tick: int,
    agent_summaries: Sequence[EventMasterAgentSummary],
    agent_state_snapshots: Mapping[str, AgentSnapshot],
    magic_agent_snapshots: Sequence[MagicAgentSnapshot],
    scheduled_events: Sequence[ScheduledEventInput] = (),
    event_master_relationship_summaries: Sequence[EventMasterRelationshipSummary] = (),
    magic_relationship_snapshots: Sequence[RelationshipSnapshot] = (),
    lab_location_ids: frozenset[str] = frozenset(),
) -> EventAndMagicResult:
    events = EventMaster().generate(
        tick=tick,
        agent_summaries=agent_summaries,
        scheduled_events=scheduled_events,
        relationship_summaries=event_master_relationship_summaries,
    )
    magic_result = MagicLayer().evaluate(
        tick=tick,
        regular_events=events,
        agent_snapshots=magic_agent_snapshots,
        relationship_snapshots=magic_relationship_snapshots,
        lab_location_ids=lab_location_ids,
    )
    event_candidates = [
        candidate
        for event in magic_result.converted_events
        for candidate in build_event_effect_candidates(
            event, run_id=run_id, agent_snapshots=agent_state_snapshots
        )
    ]
    magic_candidates = build_magic_effect_candidates(
        magic_result.special_events, run_id=run_id, agent_snapshots=agent_state_snapshots
    )
    resolved = resolve_conflicts([*event_candidates, *magic_candidates])
    return EventAndMagicResult(
        events=magic_result.converted_events,
        special_events=magic_result.special_events,
        resolved_effects=tuple(resolved),
        reflection_eligible_event_keys=tuple(
            [
                event.event_key
                for event in magic_result.converted_events
                if event.importance >= REFLECTION_IMPORTANCE_THRESHOLD
            ]
            + [
                f"magic:{event.event_subtype}:{event.tick}"
                for event in magic_result.special_events
            ]
        ),
    )
