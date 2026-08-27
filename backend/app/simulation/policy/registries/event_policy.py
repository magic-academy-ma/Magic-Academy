"""Slice 5 Task 1 — Event Policy Registry.

Converts Event Master's general Event effects and Magic Layer's typed
direction/intensity signals into canonical ``EffectCandidate``s, reusing the
existing Signal → Delta rules (``registries.signal_policy``) and Policy models
(``policy.models``). Numbers come from docs/03-system-design/policy-signal-delta.md
§7/§8.1, restated in docs/04-feature-specs/slice-5-integration.md §1/§2 (Task 0
confirmed values — this module must not invent new numbers).

Relationship changes are never produced here (both docs: "관계 변화는 Event
기본 효과로 만들지 마세요" / Reaction 전용 typed RelationshipSignal 경로만 사용).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.simulation.agent_runtime import SignalIntensity, StateSignalType
from app.simulation.event_master import Event
from app.simulation.magic_layer import (
    CURSE_SPREAD,
    MAGIC_EXPLOSION,
    MAGICAL_DISCOVERY,
    RITUAL_FAILURE,
    STUDENT_MISSING,
    SpecialEvent,
)
from app.simulation.policy.models import AgentSnapshot, EffectCandidate, EffectTargetType
from app.simulation.policy.registries.signal_policy import get_state_delta

# 일반 Event Policy Registry — 참여 Agent 대상 기본 효과 (policy-signal-delta.md §7).
EVENT_BASE_EFFECTS: dict[str, tuple[tuple[str, int], ...]] = {
    "CLASS": (("stress", 1),),
    "GROUP_PROJECT": (("stress", 3),),
    "EXAM": (("stress", 8), ("fatigue", 5)),
    "MEETING": (("satisfaction", 2),),
    "MT": (("satisfaction", 5), ("fatigue", 5), ("hunger", 3)),
    "FESTIVAL": (("satisfaction", 6), ("fatigue", 4), ("hunger", 3)),
}

# RANDOM_INCIDENT event_subtype별 등록 효과. 확정된 subtype 규칙이 아직 없어
# 비워둔다 — 미등록 subtype은 효과 없이 거부한다(policy-signal-delta.md §2.2와
# 동일 원칙: "Registry에 등록되지 않은 ... 거부하고 warning을 남긴다").
RANDOM_INCIDENT_EFFECTS: dict[str, tuple[tuple[str, int], ...]] = {}

# Magic Layer 특수 Event → typed state signal 매핑 (slice-5-integration.md §2,
# policy-signal-delta.md §8.1). Magic Layer는 방향/강도만 주고, 실제 delta는
# 아래 signal_policy.get_state_delta로 계산한다.
MagicSignalRule = tuple[StateSignalType, SignalIntensity]

MAGIC_AFFECTED_SIGNALS: dict[str, MagicSignalRule] = {
    STUDENT_MISSING: (StateSignalType.STRESS_UP, SignalIntensity.MEDIUM),
    CURSE_SPREAD: (StateSignalType.MOOD_DOWN, SignalIntensity.HIGH),
    MAGIC_EXPLOSION: (StateSignalType.STRESS_UP, SignalIntensity.HIGH),
    RITUAL_FAILURE: (StateSignalType.STRESS_UP, SignalIntensity.HIGH),
    MAGICAL_DISCOVERY: (StateSignalType.MOOD_UP, SignalIntensity.MEDIUM),
}

# CURSE_SPREAD·MAGIC_EXPLOSION·MAGICAL_DISCOVERY는 확정 표에 두 번째 state 효과가 있다.
MAGIC_SECONDARY_SIGNALS: dict[str, MagicSignalRule] = {
    CURSE_SPREAD: (StateSignalType.SATISFACTION_DOWN, SignalIntensity.HIGH),
    MAGIC_EXPLOSION: (StateSignalType.FATIGUE_UP, SignalIntensity.HIGH),
    MAGICAL_DISCOVERY: (StateSignalType.SATISFACTION_UP, SignalIntensity.HIGH),
}


def _state_value(agent_snapshot: AgentSnapshot, metric: str) -> int:
    return getattr(agent_snapshot, metric)


def build_event_effect_candidates(
    event: Event,
    *,
    run_id: str,
    agent_snapshots: Mapping[str, AgentSnapshot],
    impact_multiplier: float = 1.0,
) -> list[EffectCandidate]:
    """일반 Event(및 RANDOM_INCIDENT)의 참여 Agent 기본 효과를 EffectCandidate로 변환한다.

    ``impact_multiplier``는 ``event_impact``의 효과 강도 배율(low 0.5 / medium 1.0 /
    high 1.5, mvp-tick-event-policy.md §4.4)이다. 기본 delta에 배율을 곱한 뒤
    ``round``로 정수화하며, 최종 범위 clamp는 기존 Conflict Resolver 단계가 담당한다.
    """
    if event.event_type == "RANDOM_INCIDENT":
        rules = RANDOM_INCIDENT_EFFECTS.get(event.event_subtype or "", ())
    else:
        rules = EVENT_BASE_EFFECTS.get(event.event_type, ())
    if not rules:
        return []

    candidates: list[EffectCandidate] = []
    for agent_id in event.participant_agent_ids:
        snapshot = agent_snapshots.get(agent_id)
        if snapshot is None:
            continue
        for metric, delta in rules:
            current = _state_value(snapshot, metric)
            scaled_delta = round(delta * impact_multiplier)
            candidates.append(
                EffectCandidate(
                    effect_id=(
                        f"{run_id}:{event.tick}:{agent_id}:event:"
                        f"{event.event_key}:{metric}"
                    ),
                    target_type=EffectTargetType.AGENT_STATE,
                    source_agent_id=agent_id,
                    target_agent_id=None,
                    metric=metric,
                    delta=scaled_delta,
                    before=current,
                    after_preview=current,
                    rule_id=f"EVENT_{event.event_type}",
                    reason=f"{event.event_type} 참여 기본 효과",
                )
            )
    return candidates


def _build_magic_signal_candidate(
    *,
    run_id: str,
    special_event: SpecialEvent,
    agent_id: str,
    signal_type: StateSignalType,
    intensity: SignalIntensity,
    agent_snapshots: Mapping[str, AgentSnapshot],
) -> EffectCandidate | None:
    snapshot = agent_snapshots.get(agent_id)
    if snapshot is None:
        return None
    metric = {
        StateSignalType.STRESS_UP: "stress",
        StateSignalType.MOOD_DOWN: "mood",
        StateSignalType.MOOD_UP: "mood",
        StateSignalType.SATISFACTION_DOWN: "satisfaction",
        StateSignalType.SATISFACTION_UP: "satisfaction",
        StateSignalType.FATIGUE_UP: "fatigue",
    }[signal_type]
    current = _state_value(snapshot, metric)
    delta = get_state_delta(signal_type, intensity)
    origin = special_event.participant_agent_ids[0] if special_event.participant_agent_ids else "-"
    return EffectCandidate(
        effect_id=(
            f"{run_id}:{special_event.tick}:{agent_id}:magic:"
            f"{special_event.event_subtype}:{origin}:{metric}"
        ),
        target_type=EffectTargetType.AGENT_STATE,
        source_agent_id=agent_id,
        target_agent_id=None,
        metric=metric,
        delta=delta,
        before=current,
        after_preview=current,
        rule_id=f"MAGIC_{special_event.event_subtype}_{signal_type}_{intensity}",
        reason=f"{special_event.event_subtype} 영향",
    )


def build_magic_effect_candidates(
    special_events: Sequence[SpecialEvent],
    *,
    run_id: str,
    agent_snapshots: Mapping[str, AgentSnapshot],
) -> list[EffectCandidate]:
    """Magic Layer 특수 Event의 typed signal을 EffectCandidate로 변환한다.

    STUDENT_MISSING의 MISSING 상태 자체(active_status 전이)는 EffectCandidate로
    표현하지 않는다 — Task 3 persistence(#103)의 missing_agent_ids 경계다.
    """
    candidates: list[EffectCandidate] = []
    for special_event in special_events:
        primary_rule = MAGIC_AFFECTED_SIGNALS.get(special_event.event_subtype)
        secondary_rule = MAGIC_SECONDARY_SIGNALS.get(special_event.event_subtype)
        affected_ids = special_event.affected_agent_ids
        for agent_id in affected_ids:
            if primary_rule is not None:
                candidate = _build_magic_signal_candidate(
                    run_id=run_id,
                    special_event=special_event,
                    agent_id=agent_id,
                    signal_type=primary_rule[0],
                    intensity=primary_rule[1],
                    agent_snapshots=agent_snapshots,
                )
                if candidate is not None:
                    candidates.append(candidate)
            if secondary_rule is not None:
                candidate = _build_magic_signal_candidate(
                    run_id=run_id,
                    special_event=special_event,
                    agent_id=agent_id,
                    signal_type=secondary_rule[0],
                    intensity=secondary_rule[1],
                    agent_snapshots=agent_snapshots,
                )
                if candidate is not None:
                    candidates.append(candidate)
    return candidates
