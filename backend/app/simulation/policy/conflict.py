from app.simulation.policy.models import METRIC_RANGE, EffectCandidate


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
                effect_ids=c.effect_ids or (c.effect_id,),
            )
        else:
            groups[key].rule_id = f"{groups[key].rule_id}|{c.rule_id}"
            groups[key].reason = f"{groups[key].reason} + {c.reason}"
            groups[key].effect_ids += c.effect_ids or (c.effect_id,)
        groups[key].delta += c.delta

    result = []
    for resolved in groups.values():
        lo, hi = METRIC_RANGE[resolved.metric]
        resolved.after_preview = max(lo, min(hi, resolved.before + resolved.delta))
        result.append(resolved)

    return result
