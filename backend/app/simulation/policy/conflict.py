from app.simulation.policy.models import EffectCandidate

METRIC_RANGE: dict[str, tuple[int, int]] = {
    "trust": (-100, 100),
    "affection": (-100, 100),
    "mood": (-100, 100),
    "tension": (0, 100),
    "closeness": (0, 100),
    "rivalry": (0, 100),
    "dependency": (0, 100),
    "hunger": (0, 100),
    "fatigue": (0, 100),
    "stress": (0, 100),
    "satisfaction": (0, 100),
}


def resolve_conflicts(candidates: list[EffectCandidate]) -> list[EffectCandidate]:
    """같은 (source, target, metric) 쌍의 delta를 합산하고 clamp한다. (MVP: 단순 가산)"""
    groups: dict[tuple, EffectCandidate] = {}

    for c in candidates:
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
        groups[key].delta += c.delta

    result = []
    for resolved in groups.values():
        lo, hi = METRIC_RANGE.get(resolved.metric, (0, 100))
        resolved.after_preview = max(lo, min(hi, resolved.before + resolved.delta))
        result.append(resolved)

    return result
