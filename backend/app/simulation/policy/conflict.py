from app.simulation.policy.models import METRIC_RANGE, EffectCandidate


class ConflictingEffectIdError(ValueError):
    pass


def resolve_conflicts(candidates: list[EffectCandidate]) -> list[EffectCandidate]:
    """같은 (source, target, metric) 쌍의 delta를 합산하고 clamp한다. (MVP: 단순 가산)"""
    groups: dict[tuple, EffectCandidate] = {}
    unique_candidates = _deduplicate_effect_ids(candidates)

    for c in unique_candidates:
        key = (c.source_agent_id, c.target_agent_id, c.metric)
        if key not in groups:
            groups[key] = EffectCandidate(
                effect_id=c.effect_id,
                target_type=c.target_type,
                source_agent_id=c.source_agent_id,
                target_agent_id=c.target_agent_id,
                metric=c.metric,
                delta=0,
                before=c.before,
                after_preview=c.before,
                rule_id=c.rule_id,
                reason=c.reason,
            )
        else:
            groups[key].rule_id = f"{groups[key].rule_id}|{c.rule_id}"
            groups[key].reason = f"{groups[key].reason} + {c.reason}"
        groups[key].delta += c.delta

    result = []
    for resolved in groups.values():
        lo, hi = METRIC_RANGE[resolved.metric]
        resolved.after_preview = max(lo, min(hi, resolved.before + resolved.delta))
        result.append(resolved)

    return result


def _deduplicate_effect_ids(
    candidates: list[EffectCandidate],
) -> list[EffectCandidate]:
    seen_by_effect_id: dict[str, EffectCandidate] = {}
    unique_candidates = []
    for candidate in candidates:
        existing = seen_by_effect_id.get(candidate.effect_id)
        if existing is None:
            seen_by_effect_id[candidate.effect_id] = candidate
            unique_candidates.append(candidate)
            continue
        if existing != candidate:
            raise ConflictingEffectIdError(
                f"conflicting payloads for effect_id {candidate.effect_id}"
            )
    return unique_candidates
