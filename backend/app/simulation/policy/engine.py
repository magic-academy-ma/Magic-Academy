from app.simulation.agent_runtime import RelationshipSignalType, StateSignalType
from app.simulation.policy.models import (
    METRIC_RANGE,
    EffectCandidate,
    EffectTargetType,
    PolicyEvaluationInput,
    PolicyEvaluationResult,
    PolicyStatus,
)
from app.simulation.policy.registries.signal_policy import (
    get_relationship_delta,
    get_state_delta,
)

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
        source_agent_id = str(runtime_result.agent_id)
        reaction = runtime_result.intent.reaction
        action_type = runtime_result.intent.action_type
        seen_effect_source_keys: set[tuple[str, ...]] = set()

        relationship_directions: dict[tuple[str, str], set[int]] = {}
        for signal in reaction.relationship_signals:
            metric = RELATIONSHIP_SIGNAL_TO_METRIC.get(signal.signal_type)
            if metric is not None:
                key = (metric, str(signal.target_agent_id))
                relationship_directions.setdefault(key, set()).add(
                    1 if signal.signal_type.value.endswith("_UP") else -1
                )

        conflicting_relationship_keys = {
            key
            for key, directions in relationship_directions.items()
            if len(directions) > 1
        }
        for metric, target_agent_id in sorted(conflicting_relationship_keys):
            warnings.append(
                f"conflicting relationship signals: {source_agent_id} → "
                f"{target_agent_id} {metric}"
            )

        state_directions: dict[str, set[int]] = {}
        for signal in reaction.state_signals:
            metric = STATE_SIGNAL_TO_METRIC.get(signal.signal_type)
            if metric is not None:
                state_directions.setdefault(metric, set()).add(
                    1 if signal.signal_type.value.endswith("_UP") else -1
                )
        conflicting_state_metrics = {
            metric
            for metric, directions in state_directions.items()
            if len(directions) > 1
        }
        for metric in sorted(conflicting_state_metrics):
            warnings.append(f"conflicting state signals: {source_agent_id} {metric}")

        for signal in reaction.relationship_signals:
            metric = RELATIONSHIP_SIGNAL_TO_METRIC.get(signal.signal_type)
            target_agent_id = str(signal.target_agent_id)
            if metric is None:
                warnings.append(f"unknown relationship signal: {signal.signal_type}")
                continue
            if (
                signal.target_agent_id == runtime_result.agent_id
                or target_agent_id not in inp.valid_agent_ids
            ):
                rejected.append(
                    {
                        "agent_id": source_agent_id,
                        "target_agent_id": target_agent_id,
                        "signal_type": signal.signal_type,
                        "reason": "INVALID_RELATIONSHIP_TARGET",
                    }
                )
                has_rejection = True
                continue
            if (metric, target_agent_id) in conflicting_relationship_keys:
                rejected.append(
                    {
                        "agent_id": source_agent_id,
                        "target_agent_id": target_agent_id,
                        "signal_type": signal.signal_type,
                        "reason": "CONFLICTING_DUPLICATE_EFFECT",
                    }
                )
                has_rejection = True
                continue
            rule_id = f"REL_{signal.signal_type}_{signal.intensity}"
            relationship_effect_source_key = (
                runtime_result.idempotency_key,
                "RELATIONSHIP",
                source_agent_id,
                target_agent_id,
                metric,
                rule_id,
            )
            if relationship_effect_source_key in seen_effect_source_keys:
                continue
            seen_effect_source_keys.add(relationship_effect_source_key)
            pair_key = (source_agent_id, target_agent_id)
            rel_snapshot = rel_index.get(pair_key)  # None이면 첫 만남 → 초기값 0
            current = rel_snapshot.get(metric, 0) if rel_snapshot is not None else 0
            delta = get_relationship_delta(signal.signal_type, signal.intensity)
            after_preview = _clamp_preview(current, delta, metric)
            effect_candidates.append(
                EffectCandidate(
                    effect_id=f"{inp.run_id}:{inp.tick_number}:{source_agent_id}:rel:{signal.signal_type}:{target_agent_id}",
                    target_type=EffectTargetType.RELATIONSHIP,
                    source_agent_id=source_agent_id,
                    target_agent_id=target_agent_id,
                    metric=metric,
                    delta=delta,
                    before=current,
                    after_preview=after_preview,
                    rule_id=rule_id,
                    reason=f"{action_type}의 {signal.intensity} {signal.signal_type} 반응",
                )
            )

        for signal in reaction.state_signals:
            metric = STATE_SIGNAL_TO_METRIC.get(signal.signal_type)
            if metric is None:
                warnings.append(f"unknown state signal: {signal.signal_type}")
                continue
            if metric in conflicting_state_metrics:
                rejected.append(
                    {
                        "agent_id": source_agent_id,
                        "signal_type": signal.signal_type,
                        "reason": "CONFLICTING_DUPLICATE_EFFECT",
                    }
                )
                has_rejection = True
                continue
            rule_id = f"STATE_{signal.signal_type}_{signal.intensity}"
            state_effect_source_key = (
                runtime_result.idempotency_key,
                "AGENT_STATE",
                source_agent_id,
                metric,
                rule_id,
            )
            if state_effect_source_key in seen_effect_source_keys:
                continue
            seen_effect_source_keys.add(state_effect_source_key)
            current = state_index.get(source_agent_id, {}).get(metric, 0)
            delta = get_state_delta(signal.signal_type, signal.intensity)
            after_preview = _clamp_preview(current, delta, metric)
            effect_candidates.append(
                EffectCandidate(
                    effect_id=f"{inp.run_id}:{inp.tick_number}:{source_agent_id}:state:{signal.signal_type}",
                    target_type=EffectTargetType.AGENT_STATE,
                    source_agent_id=source_agent_id,
                    target_agent_id=None,
                    metric=metric,
                    delta=delta,
                    before=current,
                    after_preview=after_preview,
                    rule_id=rule_id,
                    reason=f"{signal.intensity} {signal.signal_type} 반응",
                )
            )

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
