"""Slice 2 Policy Engine 단위 테스트"""
from uuid import UUID

import pytest
from app.simulation.agent_runtime import (
    ActionAlternative,
    ActionType,
    AgentReaction,
    AgentRuntimeResult,
    DecisionExplanation,
    IntentCandidate,
    ReactionValence,
    RelationshipSignal,
    RelationshipSignalType,
    RelativePriority,
    RuntimeStatus,
    SignalIntensity,
    StateSignal,
    StateSignalType,
)


AGENT_A = UUID("00000000-0000-0000-0000-00000000000a")
AGENT_B = UUID("00000000-0000-0000-0000-00000000000b")
AGENT_X = UUID("00000000-0000-0000-0000-00000000000f")


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


def _make_rel_signal(signal_type, intensity, target_id):
    return RelationshipSignal(signal_type=signal_type, intensity=intensity, target_agent_id=target_id)


def _make_runtime_result(agent_id, target_id, rel_signals=None, state_signals=None):
    action_type = ActionType.TALK if target_id is not None else ActionType.WAIT
    return AgentRuntimeResult(
        run_id="sim-test-1",
        tick_number=1,
        agent_id=agent_id,
        status=RuntimeStatus.PROPOSED,
        intent=IntentCandidate(
            action_type=action_type,
            target_agent_id=target_id,
            target_location_id=None,
            related_event_id=None,
            utterance=None,
            motivation_summary="test",
            reaction=AgentReaction(
                valence=ReactionValence.POSITIVE,
                relationship_signals=rel_signals or [],
                state_signals=state_signals or [],
            ),
            decision_explanation=DecisionExplanation(
                alternatives=[ActionAlternative(
                    action_type=action_type,
                    description="test",
                    relative_priority=RelativePriority.HIGH,
                    selected=True,
                )],
                influencing_factors=[],
            ),
            memory_candidates=[],
        ),
        retry_count=0,
        failure_reason=None,
        model="test-model",
        prompt_version="test-prompt-v1",
        idempotency_key=f"sim-test-1:1:{agent_id}",
    )


# ── engine ─────────────────────────────────────────────────────────────────────

def _make_eval_input(runtime_results, rel_snapshots=None, agent_snapshots=None):
    from app.simulation.policy.models import AgentSnapshot, PolicyEvaluationInput, RelationshipSnapshot
    return PolicyEvaluationInput(
        run_id="sim-test-1",
        tick_number=1,
        policy_version="policy-mvp-0.1",
        agent_snapshots=agent_snapshots if agent_snapshots is not None else {
            str(AGENT_A): AgentSnapshot(agent_id=str(AGENT_A), hunger=50, fatigue=20, stress=10, satisfaction=50),
            str(AGENT_B): AgentSnapshot(agent_id=str(AGENT_B), hunger=50, fatigue=20, stress=10, satisfaction=50),
        },
        relationship_snapshots=rel_snapshots if rel_snapshots is not None else [
            RelationshipSnapshot(source_agent_id=str(AGENT_A), target_agent_id=str(AGENT_B), trust=20, tension=5),
            RelationshipSnapshot(source_agent_id=str(AGENT_B), target_agent_id=str(AGENT_A), trust=15, tension=3),
        ],
        runtime_results=runtime_results,
        valid_agent_ids={str(AGENT_A), str(AGENT_B)},
    )


def test_trust_up_produces_positive_effect_candidate():
    from app.simulation.policy.engine import evaluate_policy
    from app.simulation.policy.models import PolicyStatus

    results = [_make_runtime_result(
        AGENT_A,
        AGENT_B,
        rel_signals=[_make_rel_signal(
            RelationshipSignalType.TRUST_UP, SignalIntensity.MEDIUM, AGENT_B
        )],
    )]
    result = evaluate_policy(_make_eval_input(results))
    assert result.status == PolicyStatus.EVALUATED
    trust_effects = [e for e in result.effect_candidates if e.metric == "trust"]
    assert len(trust_effects) == 1
    assert trust_effects[0].delta == 3
    assert trust_effects[0].source_agent_id == str(AGENT_A)
    assert trust_effects[0].target_agent_id == str(AGENT_B)
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

    results = [_make_runtime_result(
        AGENT_A,
        AGENT_B,
        rel_signals=[_make_rel_signal(
            RelationshipSignalType.TRUST_UP, SignalIntensity.MEDIUM, AGENT_B
        )],
    )]
    result = evaluate_policy(_make_eval_input(results))
    ba_trust = [e for e in result.effect_candidates if e.metric == "trust" and e.source_agent_id == str(AGENT_B)]
    assert len(ba_trust) == 0


def test_trust_preview_clamped_at_100():
    from app.simulation.policy.engine import evaluate_policy
    from app.simulation.policy.models import RelationshipSnapshot

    results = [_make_runtime_result(
        AGENT_A,
        AGENT_B,
        rel_signals=[_make_rel_signal(
            RelationshipSignalType.TRUST_UP, SignalIntensity.HIGH, AGENT_B
        )],
    )]
    rel_snapshots = [
        RelationshipSnapshot(source_agent_id=str(AGENT_A), target_agent_id=str(AGENT_B), trust=98, tension=0),
        RelationshipSnapshot(source_agent_id=str(AGENT_B), target_agent_id=str(AGENT_A), trust=0, tension=0),
    ]
    result = evaluate_policy(_make_eval_input(results, rel_snapshots=rel_snapshots))
    trust_effect = next(e for e in result.effect_candidates if e.metric == "trust")
    assert trust_effect.after_preview == 100
    assert trust_effect.delta == 5  # delta는 그대로, clamp는 Commit에서


def test_mood_up_produces_state_effect():
    from app.simulation.policy.engine import evaluate_policy

    results = [_make_runtime_result(
        AGENT_A,
        None,
        state_signals=[StateSignal(
            signal_type=StateSignalType.MOOD_UP, intensity=SignalIntensity.MEDIUM
        )],
    )]
    result = evaluate_policy(_make_eval_input(results))
    mood_effects = [e for e in result.effect_candidates if e.metric == "mood"]
    assert len(mood_effects) == 1
    assert mood_effects[0].delta == 5
    assert mood_effects[0].source_agent_id == str(AGENT_A)
    assert mood_effects[0].target_agent_id is None


def test_invalid_relationship_signal_keeps_valid_effects():
    from app.simulation.policy.engine import evaluate_policy
    from app.simulation.policy.models import PolicyStatus

    results = [_make_runtime_result(
        AGENT_A,
        AGENT_B,
        rel_signals=[
            _make_rel_signal(RelationshipSignalType.TRUST_UP, SignalIntensity.MEDIUM, AGENT_B),
            _make_rel_signal(RelationshipSignalType.TRUST_UP, SignalIntensity.MEDIUM, AGENT_X),
        ],
        state_signals=[StateSignal(
            signal_type=StateSignalType.MOOD_UP, intensity=SignalIntensity.LOW
        )],
    )]

    result = evaluate_policy(_make_eval_input(results))

    assert result.status == PolicyStatus.PARTIAL
    assert {(effect.metric, effect.target_agent_id) for effect in result.effect_candidates} == {
        ("trust", str(AGENT_B)),
        ("mood", None),
        ("fatigue", None),
    }
    assert result.rejected_effects[0]["reason"] == "INVALID_RELATIONSHIP_TARGET"


def test_closeness_preview_allows_negative_value():
    from app.simulation.policy.engine import evaluate_policy
    from app.simulation.policy.models import RelationshipSnapshot

    results = [_make_runtime_result(
        AGENT_A,
        AGENT_B,
        rel_signals=[_make_rel_signal(
            RelationshipSignalType.CLOSENESS_DOWN, SignalIntensity.HIGH, AGENT_B
        )],
    )]
    relationships = [RelationshipSnapshot(
        source_agent_id=str(AGENT_A),
        target_agent_id=str(AGENT_B),
        trust=0,
        tension=0,
        closeness=0,
    )]

    result = evaluate_policy(_make_eval_input(results, rel_snapshots=relationships))

    closeness_effect = next(effect for effect in result.effect_candidates if effect.metric == "closeness")
    assert closeness_effect.after_preview == -5


def test_conflicting_relationship_signals_are_both_rejected():
    from app.simulation.policy.engine import evaluate_policy
    from app.simulation.policy.models import PolicyStatus

    results = [_make_runtime_result(
        AGENT_A,
        AGENT_B,
        rel_signals=[
            _make_rel_signal(RelationshipSignalType.TRUST_UP, SignalIntensity.MEDIUM, AGENT_B),
            _make_rel_signal(RelationshipSignalType.TRUST_DOWN, SignalIntensity.MEDIUM, AGENT_B),
        ],
    )]

    result = evaluate_policy(_make_eval_input(results))

    assert result.status == PolicyStatus.PARTIAL
    assert [effect for effect in result.effect_candidates if effect.metric == "trust"] == []
    assert len(result.rejected_effects) == 2
    assert any("conflicting" in warning for warning in result.warnings)


def test_duplicate_relationship_signals_are_deduplicated():
    from app.simulation.policy.engine import evaluate_policy

    signal = _make_rel_signal(
        RelationshipSignalType.TRUST_UP, SignalIntensity.MEDIUM, AGENT_B
    )
    results = [_make_runtime_result(AGENT_A, AGENT_B, rel_signals=[signal, signal])]

    result = evaluate_policy(_make_eval_input(results))

    trust_effects = [effect for effect in result.effect_candidates if effect.metric == "trust"]
    assert len(trust_effects) == 1
    assert trust_effects[0].delta == 3


# ── conflict ───────────────────────────────────────────────────────────────────

def _rel_effect(source, target, metric, delta, before, *, effect_id=None):
    from app.simulation.policy.models import EffectCandidate, EffectTargetType
    lo, hi = (-100, 100) if metric in {"trust", "affection", "mood"} else (0, 100)
    return EffectCandidate(
        effect_id=effect_id or f"test:{source}:{target}:{metric}",
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
        _rel_effect("a", "b", "trust", 3, 20, effect_id="effect-1"),
        _rel_effect("a", "b", "trust", 2, 20, effect_id="effect-2"),
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
        _rel_effect("a", "b", "trust", 5, 97, effect_id="effect-1"),
        _rel_effect("a", "b", "trust", 5, 97, effect_id="effect-2"),
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


def test_identical_effect_id_and_payload_is_applied_once():
    from copy import deepcopy

    from app.simulation.policy.conflict import resolve_conflicts

    event_effect = _rel_effect(
        "a", "b", "trust", 3, 20, effect_id="canonical-event-effect"
    )
    magic_effect = deepcopy(event_effect)

    committed = resolve_conflicts([event_effect, magic_effect])

    assert len(committed) == 1
    assert committed[0].delta == 3
    assert committed[0].effect_id == "canonical-event-effect"


def test_same_effect_id_with_different_payload_raises_error():
    from app.simulation.policy.conflict import resolve_conflicts

    candidates = [
        _rel_effect("a", "b", "trust", 3, 20, effect_id="same-effect"),
        _rel_effect("a", "b", "trust", 5, 20, effect_id="same-effect"),
    ]

    with pytest.raises(ValueError, match="conflicting payloads.*same-effect"):
        resolve_conflicts(candidates)


def test_distinct_effect_ids_for_same_metric_sum_in_first_seen_order():
    from copy import deepcopy

    from app.simulation.policy.conflict import resolve_conflicts

    candidates = [
        _rel_effect("a", "b", "affection", 2, 10, effect_id="first"),
        _rel_effect("a", "b", "trust", 3, 20, effect_id="second"),
        _rel_effect("a", "b", "affection", 4, 10, effect_id="third"),
    ]
    original = deepcopy(candidates)

    committed = resolve_conflicts(candidates)

    assert [(effect.metric, effect.delta) for effect in committed] == [
        ("affection", 6),
        ("trust", 3),
    ]
    assert candidates == original


def test_missing_relationship_snapshot_treats_as_neutral_zero():
    from app.simulation.policy.engine import evaluate_policy

    results = [_make_runtime_result(
        AGENT_A,
        AGENT_B,
        rel_signals=[_make_rel_signal(
            RelationshipSignalType.TRUST_UP, SignalIntensity.MEDIUM, AGENT_B
        )],
    )]
    # 첫 만남 — relationship snapshot 없음
    result = evaluate_policy(_make_eval_input(results, rel_snapshots=[]))
    trust_effects = [e for e in result.effect_candidates if e.metric == "trust"]
    assert len(trust_effects) == 1
    assert trust_effects[0].before == 0


def test_duplicate_state_signals_are_deduplicated():
    from app.simulation.policy.engine import evaluate_policy

    signal = StateSignal(signal_type=StateSignalType.STRESS_DOWN, intensity=SignalIntensity.LOW)
    results = [_make_runtime_result(AGENT_A, None, state_signals=[signal, signal])]
    result = evaluate_policy(_make_eval_input(results))
    stress_effects = [e for e in result.effect_candidates if e.metric == "stress"]
    assert len(stress_effects) == 1


def test_resolve_conflicts_raises_key_error_for_unknown_metric():
    from app.simulation.policy.conflict import resolve_conflicts
    from app.simulation.policy.models import EffectCandidate, EffectTargetType

    candidates = [
        EffectCandidate(
            effect_id="test:a:b:unknown_metric",
            target_type=EffectTargetType.RELATIONSHIP,
            source_agent_id="a",
            target_agent_id="b",
            metric="unknown_metric",
            delta=5,
            before=10,
            after_preview=15,
            rule_id="TEST",
            reason="test",
        )
    ]
    with pytest.raises(KeyError):
        resolve_conflicts(candidates)
