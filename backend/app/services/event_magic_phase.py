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
from dataclasses import dataclass, field

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
    MagicLayerResult,
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
    # 이 Tick에 적용된 Magic Layer 영향도 (특수 Event 기록용).
    magic_impact: str = "medium"


REFLECTION_IMPORTANCE_THRESHOLD = 70

# event_impact 효과 강도 배율 (mvp-tick-event-policy.md §4.4).
IMPACT_MULTIPLIER_BY_NAME: dict[str, float] = {
    "low": 0.5,
    "medium": 1.0,
    "high": 1.5,
}


@dataclass(frozen=True)
class EventParameters:
    """이번 Tick에 고정된 Event/Magic 파라미터 스냅샷 (mvp-tick-event-policy.md
    §4.3–§4.5, simulation-parameters.md §4).

    ``frequency_seed``가 ``None``이면 Event Master는 빈도 정책 없이 기존처럼 동작하고,
    ``magic_frequency_seed``가 ``None``이면 Magic Layer도 빈도 게이트 없이 동작한다.
    """

    event_frequency: str = "medium"
    event_impact: str = "medium"
    frequency_seed: str | None = None
    daily_dynamic_count: int = 0
    cooldown_excluded_agent_ids: Mapping[str, frozenset[str]] = field(default_factory=dict)
    high_impact_agent_ids_today: frozenset[str] = frozenset()
    # Magic Layer 파라미터 (실행 전 고정 — simulation-parameters.md §5).
    magic_enabled: bool = True
    magic_frequency: str = "medium"
    magic_impact: str = "medium"
    magic_frequency_seed: str | None = None
    magic_daily_count: int = 0


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
    event_parameters: EventParameters | None = None,
) -> EventAndMagicResult:
    params = event_parameters or EventParameters()
    events = EventMaster().generate(
        tick=tick,
        agent_summaries=agent_summaries,
        scheduled_events=scheduled_events,
        relationship_summaries=event_master_relationship_summaries,
        event_frequency=params.event_frequency,
        event_impact=params.event_impact,
        frequency_seed=params.frequency_seed,
        daily_dynamic_count=params.daily_dynamic_count,
        cooldown_excluded_agent_ids=dict(params.cooldown_excluded_agent_ids),
        high_impact_agent_ids_today=params.high_impact_agent_ids_today,
    )
    if params.magic_enabled:
        magic_result = MagicLayer().evaluate(
            tick=tick,
            regular_events=events,
            agent_snapshots=magic_agent_snapshots,
            relationship_snapshots=magic_relationship_snapshots,
            lab_location_ids=lab_location_ids,
            magic_frequency=params.magic_frequency,
            magic_frequency_seed=params.magic_frequency_seed,
            magic_daily_count=params.magic_daily_count,
        )
    else:
        # magic_enabled=false — 이 실행에서는 Magic Layer 특수 사건을 호출하지
        # 않는다 (simulation-parameters.md §2). 일반 Event 변환은 그대로 통과.
        magic_result = MagicLayerResult(
            converted_events=tuple(events), special_events=()
        )
    impact_multiplier = IMPACT_MULTIPLIER_BY_NAME.get(params.event_impact, 1.0)
    magic_impact_multiplier = IMPACT_MULTIPLIER_BY_NAME.get(params.magic_impact, 1.0)
    event_candidates = [
        candidate
        for event in magic_result.converted_events
        for candidate in build_event_effect_candidates(
            event,
            run_id=run_id,
            agent_snapshots=agent_state_snapshots,
            impact_multiplier=impact_multiplier,
        )
    ]
    magic_candidates = build_magic_effect_candidates(
        magic_result.special_events,
        run_id=run_id,
        agent_snapshots=agent_state_snapshots,
        impact_multiplier=magic_impact_multiplier,
    )
    resolved = resolve_conflicts([*event_candidates, *magic_candidates])
    return EventAndMagicResult(
        events=magic_result.converted_events,
        special_events=magic_result.special_events,
        resolved_effects=tuple(resolved),
        magic_impact=params.magic_impact,
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
