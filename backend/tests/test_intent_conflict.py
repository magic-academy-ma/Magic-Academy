from uuid import UUID

from app.simulation.agent_runtime import AgentRuntimeResult
from app.simulation.intent_conflict import resolve_talk_conflicts
from app.simulation.policy.engine import evaluate_policy
from app.simulation.policy.models import AgentSnapshot, PolicyEvaluationInput


A = UUID("00000000-0000-0000-0000-00000000000a")
B = UUID("00000000-0000-0000-0000-00000000000b")
C = UUID("00000000-0000-0000-0000-00000000000c")


def talk(agent_id: UUID, target_id: UUID) -> AgentRuntimeResult:
    return AgentRuntimeResult.model_validate(
        {
            "run_id": "talk-run",
            "tick_number": 10,
            "agent_id": agent_id,
            "status": "PROPOSED",
            "intent": {
                "action_type": "TALK",
                "target_agent_id": target_id,
                "target_location_id": None,
                "related_event_id": None,
                "utterance": "대화하자.",
                "motivation_summary": "대화 요청",
                "reaction": {
                    "valence": "POSITIVE",
                    "relationship_signals": [
                        {
                            "signal_type": "TRUST_UP",
                            "intensity": "LOW",
                            "target_agent_id": target_id,
                        }
                    ],
                    "state_signals": [],
                },
                "decision_explanation": {
                    "alternatives": [
                        {
                            "action_type": "TALK",
                            "description": "대화한다.",
                            "relative_priority": "HIGH",
                            "selected": True,
                        }
                    ],
                    "influencing_factors": [],
                },
                "memory_candidates": [],
            },
            "retry_count": 0,
            "failure_reason": None,
            "model": "campaign",
            "prompt_version": "test",
            "idempotency_key": f"talk-run:10:{agent_id}",
        }
    )


def test_mutual_talk_is_kept_and_third_party_becomes_wait_fallback() -> None:
    resolution = resolve_talk_conflicts((talk(A, B), talk(B, A), talk(C, A)))

    assert resolution.mutual_pairs == ((A, B),)
    assert resolution.wait_fallback_agent_ids == (C,)
    assert [result.intent.action_type for result in resolution.runtime_results] == [
        "TALK",
        "TALK",
        "WAIT",
    ]
    fallback = resolution.runtime_results[2]
    assert fallback.status == "FALLBACK"
    assert fallback.failure_reason == "WAIT_FALLBACK"
    assert fallback.intent.reaction.relationship_signals == []


def test_wait_fallback_uses_wait_effect_without_talk_or_relationship_effect() -> None:
    resolved = resolve_talk_conflicts((talk(A, B), talk(B, A), talk(C, A)))
    evaluation = evaluate_policy(
        PolicyEvaluationInput(
            run_id="talk-run",
            tick_number=10,
            policy_version="policy-mvp-0.1",
            agent_snapshots={
                str(agent_id): AgentSnapshot(
                    agent_id=str(agent_id),
                    hunger=10,
                    fatigue=10,
                    stress=10,
                    satisfaction=50,
                )
                for agent_id in (A, B, C)
            },
            relationship_snapshots=[],
            runtime_results=list(resolved.runtime_results),
            valid_agent_ids={str(A), str(B), str(C)},
        )
    )

    c_effects = [
        effect
        for effect in evaluation.effect_candidates
        if effect.source_agent_id == str(C)
    ]
    assert {(effect.metric, effect.delta, effect.rule_id) for effect in c_effects} == {
        ("hunger", 2, "ACTION_WAIT"),
        ("fatigue", 1, "ACTION_WAIT"),
    }
    assert not any(effect.target_agent_id is not None for effect in c_effects)


def test_talk_resolution_is_deterministic() -> None:
    inputs = (talk(A, B), talk(B, A), talk(C, A))
    assert resolve_talk_conflicts(inputs) == resolve_talk_conflicts(inputs)
