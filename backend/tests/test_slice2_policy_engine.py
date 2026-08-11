"""Slice 2 Policy Engine 단위 테스트"""
import pytest
from app.simulation.policy.types import RelationshipSignalType, SignalIntensity, StateSignalType


# ── signal_policy ──────────────────────────────────────────────────────────────

def test_trust_up_medium_returns_3():
    from app.simulation.policy.registries.signal_policy import get_relationship_delta
    assert get_relationship_delta(RelationshipSignalType.TRUST_UP, SignalIntensity.MEDIUM) == 3


def test_trust_down_medium_returns_negative_3():
    from app.simulation.policy.registries.signal_policy import get_relationship_delta
    assert get_relationship_delta(RelationshipSignalType.TRUST_DOWN, SignalIntensity.MEDIUM) == -3


def test_tension_up_high_returns_5():
    from app.simulation.policy.registries.signal_policy import get_relationship_delta
    assert get_relationship_delta(RelationshipSignalType.TENSION_UP, SignalIntensity.HIGH) == 5


def test_closeness_up_low_returns_1():
    from app.simulation.policy.registries.signal_policy import get_relationship_delta
    assert get_relationship_delta(RelationshipSignalType.CLOSENESS_UP, SignalIntensity.LOW) == 1


def test_rivalry_down_high_returns_negative_5():
    from app.simulation.policy.registries.signal_policy import get_relationship_delta
    assert get_relationship_delta(RelationshipSignalType.RIVALRY_DOWN, SignalIntensity.HIGH) == -5


def test_fatigue_up_low_returns_2():
    from app.simulation.policy.registries.signal_policy import get_state_delta
    assert get_state_delta(StateSignalType.FATIGUE_UP, SignalIntensity.LOW) == 2


def test_stress_down_high_returns_negative_8():
    from app.simulation.policy.registries.signal_policy import get_state_delta
    assert get_state_delta(StateSignalType.STRESS_DOWN, SignalIntensity.HIGH) == -8


def test_mood_up_medium_returns_5():
    from app.simulation.policy.registries.signal_policy import get_state_delta
    assert get_state_delta(StateSignalType.MOOD_UP, SignalIntensity.MEDIUM) == 5


def test_mood_down_low_returns_negative_2():
    from app.simulation.policy.registries.signal_policy import get_state_delta
    assert get_state_delta(StateSignalType.MOOD_DOWN, SignalIntensity.LOW) == -2


# ── validators ─────────────────────────────────────────────────────────────────

def _make_rel_signal(signal_type, intensity, target_id):
    from app.simulation.policy.types import RelationshipSignal
    return RelationshipSignal(signal_type=signal_type, intensity=intensity, target_agent_id=target_id)


def _make_runtime_result(agent_id, target_id, rel_signals=None, state_signals=None):
    from app.simulation.policy.types import AgentReaction, AgentRuntimeResult
    return AgentRuntimeResult(
        agent_id=agent_id,
        action_type="TALK",
        target_agent_id=target_id,
        reaction=AgentReaction(
            valence="POSITIVE",
            relationship_signals=rel_signals or [],
            state_signals=state_signals or [],
        ),
    )


def test_self_target_relationship_signal_is_rejected():
    from app.simulation.policy.validators import validate_runtime_result
    result = _make_runtime_result(
        "agent-a", "agent-a",
        rel_signals=[_make_rel_signal(RelationshipSignalType.TRUST_UP, SignalIntensity.MEDIUM, "agent-a")],
    )
    errors = validate_runtime_result(result, valid_agent_ids={"agent-a", "agent-b"})
    assert any("self" in e.lower() for e in errors)


def test_invalid_target_agent_is_rejected():
    from app.simulation.policy.validators import validate_runtime_result
    result = _make_runtime_result(
        "agent-a", "agent-x",
        rel_signals=[_make_rel_signal(RelationshipSignalType.TRUST_UP, SignalIntensity.MEDIUM, "agent-x")],
    )
    errors = validate_runtime_result(result, valid_agent_ids={"agent-a", "agent-b"})
    assert any("invalid" in e.lower() or "target" in e.lower() for e in errors)


def test_valid_signal_has_no_errors():
    from app.simulation.policy.validators import validate_runtime_result
    result = _make_runtime_result(
        "agent-a", "agent-b",
        rel_signals=[_make_rel_signal(RelationshipSignalType.TRUST_UP, SignalIntensity.MEDIUM, "agent-b")],
    )
    errors = validate_runtime_result(result, valid_agent_ids={"agent-a", "agent-b"})
    assert errors == []


# ── engine ─────────────────────────────────────────────────────────────────────

def _make_eval_input(runtime_results, rel_snapshots=None, agent_snapshots=None):
    from app.simulation.policy.models import AgentSnapshot, PolicyEvaluationInput, RelationshipSnapshot
    return PolicyEvaluationInput(
        run_id="sim-test-1",
        tick_number=1,
        policy_version="policy-mvp-0.1",
        agent_snapshots=agent_snapshots if agent_snapshots is not None else {
            "agent-a": AgentSnapshot(agent_id="agent-a", hunger=50, fatigue=20, stress=10, satisfaction=50),
            "agent-b": AgentSnapshot(agent_id="agent-b", hunger=50, fatigue=20, stress=10, satisfaction=50),
        },
        relationship_snapshots=rel_snapshots if rel_snapshots is not None else [
            RelationshipSnapshot(source_agent_id="agent-a", target_agent_id="agent-b", trust=20, tension=5),
            RelationshipSnapshot(source_agent_id="agent-b", target_agent_id="agent-a", trust=15, tension=3),
        ],
        runtime_results=runtime_results,
        valid_agent_ids={"agent-a", "agent-b"},
    )


def test_trust_up_produces_positive_effect_candidate():
    from app.simulation.policy.engine import evaluate_policy
    from app.simulation.policy.models import PolicyStatus
    from app.simulation.policy.types import AgentReaction, AgentRuntimeResult, RelationshipSignal

    results = [AgentRuntimeResult(
        agent_id="agent-a", action_type="TALK", target_agent_id="agent-b",
        reaction=AgentReaction(
            valence="POSITIVE",
            relationship_signals=[RelationshipSignal(
                signal_type=RelationshipSignalType.TRUST_UP,
                intensity=SignalIntensity.MEDIUM,
                target_agent_id="agent-b",
            )],
        ),
    )]
    result = evaluate_policy(_make_eval_input(results))
    assert result.status == PolicyStatus.EVALUATED
    trust_effects = [e for e in result.effect_candidates if e.metric == "trust"]
    assert len(trust_effects) == 1
    assert trust_effects[0].delta == 3
    assert trust_effects[0].source_agent_id == "agent-a"
    assert trust_effects[0].target_agent_id == "agent-b"
    assert trust_effects[0].before == 20
    assert trust_effects[0].after_preview == 23


def test_unknown_policy_version_is_rejected():
    from app.simulation.policy.engine import evaluate_policy
    from app.simulation.policy.models import PolicyStatus
    inp = _make_eval_input([])
    inp.policy_version = "policy-unknown-99.9"
    result = evaluate_policy(inp)
    assert result.status == PolicyStatus.REJECTED


def test_ab_signal_does_not_affect_ba():
    from app.simulation.policy.engine import evaluate_policy
    from app.simulation.policy.types import AgentReaction, AgentRuntimeResult, RelationshipSignal

    results = [AgentRuntimeResult(
        agent_id="agent-a", action_type="TALK", target_agent_id="agent-b",
        reaction=AgentReaction(
            valence="POSITIVE",
            relationship_signals=[RelationshipSignal(
                signal_type=RelationshipSignalType.TRUST_UP,
                intensity=SignalIntensity.MEDIUM,
                target_agent_id="agent-b",
            )],
        ),
    )]
    result = evaluate_policy(_make_eval_input(results))
    ba_trust = [e for e in result.effect_candidates if e.metric == "trust" and e.source_agent_id == "agent-b"]
    assert len(ba_trust) == 0


def test_trust_preview_clamped_at_100():
    from app.simulation.policy.engine import evaluate_policy
    from app.simulation.policy.models import RelationshipSnapshot
    from app.simulation.policy.types import AgentReaction, AgentRuntimeResult, RelationshipSignal

    results = [AgentRuntimeResult(
        agent_id="agent-a", action_type="TALK", target_agent_id="agent-b",
        reaction=AgentReaction(
            valence="POSITIVE",
            relationship_signals=[RelationshipSignal(
                signal_type=RelationshipSignalType.TRUST_UP,
                intensity=SignalIntensity.HIGH,  # delta +5
                target_agent_id="agent-b",
            )],
        ),
    )]
    rel_snapshots = [
        RelationshipSnapshot(source_agent_id="agent-a", target_agent_id="agent-b", trust=98, tension=0),
        RelationshipSnapshot(source_agent_id="agent-b", target_agent_id="agent-a", trust=0, tension=0),
    ]
    result = evaluate_policy(_make_eval_input(results, rel_snapshots=rel_snapshots))
    trust_effect = next(e for e in result.effect_candidates if e.metric == "trust")
    assert trust_effect.after_preview == 100
    assert trust_effect.delta == 5  # delta는 그대로, clamp는 Commit에서


def test_mood_up_produces_state_effect():
    from app.simulation.policy.engine import evaluate_policy
    from app.simulation.policy.types import AgentReaction, AgentRuntimeResult, StateSignal

    results = [AgentRuntimeResult(
        agent_id="agent-a", action_type="REST", target_agent_id=None,
        reaction=AgentReaction(
            valence="POSITIVE",
            state_signals=[StateSignal(signal_type=StateSignalType.MOOD_UP, intensity=SignalIntensity.MEDIUM)],
        ),
    )]
    result = evaluate_policy(_make_eval_input(results))
    mood_effects = [e for e in result.effect_candidates if e.metric == "mood"]
    assert len(mood_effects) == 1
    assert mood_effects[0].delta == 5
    assert mood_effects[0].source_agent_id == "agent-a"
    assert mood_effects[0].target_agent_id is None


# ── conflict ───────────────────────────────────────────────────────────────────

def _rel_effect(source, target, metric, delta, before):
    from app.simulation.policy.models import EffectCandidate, EffectTargetType
    lo, hi = (-100, 100) if metric in {"trust", "affection", "mood"} else (0, 100)
    return EffectCandidate(
        effect_id=f"test:{source}:{target}:{metric}",
        target_type=EffectTargetType.RELATIONSHIP,
        source_agent_id=source,
        target_agent_id=target,
        metric=metric,
        delta=delta,
        before=before,
        after_preview=max(lo, min(hi, before + delta)),
        rule_id="TEST",
        reason="test",
    )


def test_multiple_deltas_on_same_pair_are_summed():
    from app.simulation.policy.conflict import resolve_conflicts
    candidates = [
        _rel_effect("a", "b", "trust", 3, 20),
        _rel_effect("a", "b", "trust", 2, 20),
    ]
    committed = resolve_conflicts(candidates)
    ab_trust = [c for c in committed if c.source_agent_id == "a" and c.metric == "trust"]
    assert len(ab_trust) == 1
    assert ab_trust[0].delta == 5
    assert ab_trust[0].after_preview == 25


def test_ab_and_ba_are_independent_in_conflict():
    from app.simulation.policy.conflict import resolve_conflicts
    candidates = [
        _rel_effect("a", "b", "trust", 3, 20),
        _rel_effect("b", "a", "trust", 2, 15),
    ]
    committed = resolve_conflicts(candidates)
    assert len(committed) == 2
    ab = next(c for c in committed if c.source_agent_id == "a")
    ba = next(c for c in committed if c.source_agent_id == "b")
    assert ab.delta == 3
    assert ba.delta == 2


def test_summed_delta_clamped_at_range():
    from app.simulation.policy.conflict import resolve_conflicts
    candidates = [
        _rel_effect("a", "b", "trust", 5, 97),
        _rel_effect("a", "b", "trust", 5, 97),
    ]
    committed = resolve_conflicts(candidates)
    assert committed[0].after_preview == 100


def test_merged_candidates_join_rule_id_and_reason():
    from app.simulation.policy.conflict import resolve_conflicts
    from app.simulation.policy.models import EffectCandidate, EffectTargetType
    c1 = EffectCandidate(
        effect_id="e1", target_type=EffectTargetType.RELATIONSHIP,
        source_agent_id="a", target_agent_id="b", metric="trust",
        delta=3, before=20, after_preview=23,
        rule_id="REL_TRUST_UP_MEDIUM", reason="MEDIUM 반응",
    )
    c2 = EffectCandidate(
        effect_id="e2", target_type=EffectTargetType.RELATIONSHIP,
        source_agent_id="a", target_agent_id="b", metric="trust",
        delta=5, before=20, after_preview=25,
        rule_id="REL_TRUST_UP_HIGH", reason="HIGH 반응",
    )
    committed = resolve_conflicts([c1, c2])
    assert len(committed) == 1
    assert committed[0].delta == 8
    assert "REL_TRUST_UP_MEDIUM" in committed[0].rule_id
    assert "REL_TRUST_UP_HIGH" in committed[0].rule_id
    assert "MEDIUM 반응" in committed[0].reason
    assert "HIGH 반응" in committed[0].reason


def test_missing_relationship_snapshot_treats_as_neutral_zero():
    from app.simulation.policy.engine import evaluate_policy
    from app.simulation.policy.types import AgentReaction, AgentRuntimeResult, RelationshipSignal

    results = [AgentRuntimeResult(
        agent_id="agent-a", action_type="TALK", target_agent_id="agent-b",
        reaction=AgentReaction(
            valence="POSITIVE",
            relationship_signals=[RelationshipSignal(
                signal_type=RelationshipSignalType.TRUST_UP,
                intensity=SignalIntensity.MEDIUM,
                target_agent_id="agent-b",
            )],
        ),
    )]
    # 첫 만남 — relationship snapshot 없음
    result = evaluate_policy(_make_eval_input(results, rel_snapshots=[]))
    trust_effects = [e for e in result.effect_candidates if e.metric == "trust"]
    assert len(trust_effects) == 1
    assert trust_effects[0].before == 0
