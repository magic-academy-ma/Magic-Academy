from app.simulation.policy.models import (
    METRIC_RANGE,
    EffectCandidate,
    EffectTargetType,
    PolicyEvaluationInput,
    PolicyEvaluationResult,
    PolicyStatus,
)
from app.simulation.policy.registries.signal_policy import get_relationship_delta, get_state_delta
from app.simulation.policy.types import RelationshipSignalType, StateSignalType
from app.simulation.policy.validators import validate_runtime_result

SUPPORTED_POLICY_VERSIONS = {"policy-mvp-0.1"}

RELATIONSHIP_SIGNAL_TO_METRIC: dict[RelationshipSignalType, str] = {
    RelationshipSignalType.TRUST_UP: "trust",
    RelationshipSignalType.TRUST_DOWN: "trust",
    RelationshipSignalType.TENSION_UP: "tension",
    RelationshipSignalType.TENSION_DOWN: "tension",
    RelationshipSignalType.AFFECTION_UP: "affection",
    RelationshipSignalType.AFFECTION_DOWN: "affection",
    RelationshipSignalType.CLOSENESS_UP: "closeness",
    RelationshipSignalType.CLOSENESS_DOWN: "closeness",
    RelationshipSignalType.RIVALRY_UP: "rivalry",
    RelationshipSignalType.RIVALRY_DOWN: "rivalry",
    RelationshipSignalType.DEPENDENCY_UP: "dependency",
    RelationshipSignalType.DEPENDENCY_DOWN: "dependency",
}

STATE_SIGNAL_TO_METRIC: dict[StateSignalType, str] = {
    StateSignalType.HUNGER_UP: "hunger",
    StateSignalType.HUNGER_DOWN: "hunger",
    StateSignalType.FATIGUE_UP: "fatigue",
    StateSignalType.FATIGUE_DOWN: "fatigue",
    StateSignalType.STRESS_UP: "stress",
    StateSignalType.STRESS_DOWN: "stress",
    StateSignalType.SATISFACTION_UP: "satisfaction",
    StateSignalType.SATISFACTION_DOWN: "satisfaction",
    StateSignalType.MOOD_UP: "mood",
    StateSignalType.MOOD_DOWN: "mood",
}


def _clamp_preview(current: int, delta: int, metric: str) -> int:
    lo, hi = METRIC_RANGE[metric]
    return max(lo, min(hi, current + delta))


def evaluate_policy(inp: PolicyEvaluationInput) -> PolicyEvaluationResult:
    if inp.policy_version not in SUPPORTED_POLICY_VERSIONS:
        return PolicyEvaluationResult(
            run_id=inp.run_id,
            tick_number=inp.tick_number,
            policy_version=inp.policy_version,
            status=PolicyStatus.REJECTED,
            warnings=[f"unsupported policy_version: {inp.policy_version}"],
        )

    rel_index: dict[tuple[str, str], dict[str, int]] = {
        (r.source_agent_id, r.target_agent_id): {
            "trust": r.trust,
            "tension": r.tension,
            "affection": r.affection,
            "closeness": r.closeness,
            "rivalry": r.rivalry,
            "dependency": r.dependency,
        }
        for r in inp.relationship_snapshots
    }
    state_index: dict[str, dict[str, int]] = {
        a.agent_id: {
            "hunger": a.hunger,
            "fatigue": a.fatigue,
            "stress": a.stress,
            "satisfaction": a.satisfaction,
            "mood": a.mood,
        }
        for a in inp.agent_snapshots.values()
    }

    effect_candidates: list[EffectCandidate] = []
    rejected: list[dict] = []
    warnings: list[str] = []
    has_rejection = False

    for runtime_result in inp.runtime_results:
        errors = validate_runtime_result(runtime_result, inp.valid_agent_ids)
        if errors:
            rejected.append({"agent_id": runtime_result.agent_id, "reasons": errors})
            has_rejection = True
            continue

        if runtime_result.reaction is None:
            continue

        for idx, signal in enumerate(runtime_result.reaction.relationship_signals):
            metric = RELATIONSHIP_SIGNAL_TO_METRIC.get(signal.signal_type)
            if metric is None:
                warnings.append(f"unknown relationship signal: {signal.signal_type}")
                continue
            pair_key = (runtime_result.agent_id, signal.target_agent_id)
            rel_snapshot = rel_index.get(pair_key)  # None이면 첫 만남 → 초기값 0
            current = rel_snapshot.get(metric, 0) if rel_snapshot is not None else 0
            delta = get_relationship_delta(signal.signal_type, signal.intensity)
            after_preview = _clamp_preview(current, delta, metric)
            effect_candidates.append(EffectCandidate(
                effect_id=f"{inp.run_id}:{inp.tick_number}:{runtime_result.agent_id}:rel:{signal.signal_type}:{signal.target_agent_id}:{idx}",
                target_type=EffectTargetType.RELATIONSHIP,
                source_agent_id=runtime_result.agent_id,
                target_agent_id=signal.target_agent_id,
                metric=metric,
                delta=delta,
                before=current,
                after_preview=after_preview,
                rule_id=f"REL_{signal.signal_type}_{signal.intensity}",
                reason=f"{runtime_result.action_type}의 {signal.intensity} {signal.signal_type} 반응",
            ))

        for idx, signal in enumerate(runtime_result.reaction.state_signals):
            metric = STATE_SIGNAL_TO_METRIC.get(signal.signal_type)
            if metric is None:
                warnings.append(f"unknown state signal: {signal.signal_type}")
                continue
            current = state_index.get(runtime_result.agent_id, {}).get(metric, 0)
            delta = get_state_delta(signal.signal_type, signal.intensity)
            after_preview = _clamp_preview(current, delta, metric)
            effect_candidates.append(EffectCandidate(
                effect_id=f"{inp.run_id}:{inp.tick_number}:{runtime_result.agent_id}:state:{signal.signal_type}:{idx}",
                target_type=EffectTargetType.AGENT_STATE,
                source_agent_id=runtime_result.agent_id,
                target_agent_id=None,
                metric=metric,
                delta=delta,
                before=current,
                after_preview=after_preview,
                rule_id=f"STATE_{signal.signal_type}_{signal.intensity}",
                reason=f"{signal.intensity} {signal.signal_type} 반응",
            ))

    status = PolicyStatus.PARTIAL if has_rejection else PolicyStatus.EVALUATED
    return PolicyEvaluationResult(
        run_id=inp.run_id,
        tick_number=inp.tick_number,
        policy_version=inp.policy_version,
        status=status,
        effect_candidates=effect_candidates,
        rejected_effects=rejected,
        warnings=warnings,
    )
