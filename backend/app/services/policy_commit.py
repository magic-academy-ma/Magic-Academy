from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Agent, AgentState, Relationship
from app.domain.relationship_metrics import RelationshipMetric
from app.repositories.relationships import RelationshipDelta, apply_deltas
from app.simulation.agent_runtime import AgentRuntimeResult, RuntimeStatus
from app.simulation.policy import engine as policy_engine
from app.simulation.policy.conflict import resolve_conflicts
from app.simulation.policy.models import (
    AgentSnapshot,
    EffectCandidate,
    EffectTargetType,
    PolicyEvaluationInput,
    PolicyStatus,
    RelationshipSnapshot,
)

POLICY_VERSION = "policy-mvp-0.1"
RESOLVER_VERSION = "resolver-mvp-0.1"


@dataclass(frozen=True)
class PolicyCommitResult:
    relationship_effects: tuple[EffectCandidate, ...]
    state_effects: tuple[EffectCandidate, ...]


def evaluate_and_apply_policy(
    db: Session,
    *,
    simulation_id: UUID,
    run_id: UUID,
    tick_number: int,
    runtime_results: tuple[AgentRuntimeResult, ...],
) -> PolicyCommitResult:
    agents = list(
        db.scalars(
            select(Agent).where(
                Agent.simulation_id == simulation_id,
                Agent.deleted_at.is_(None),
            )
        )
    )
    agent_ids = {agent.id for agent in agents}
    states = list(
        db.scalars(
            select(AgentState)
            .where(AgentState.agent_id.in_(agent_ids))
            .with_for_update()
        )
    )
    relationships = list(
        db.scalars(
            select(Relationship).where(Relationship.simulation_id == simulation_id)
        )
    )
    evaluation = policy_engine.evaluate_policy(
        PolicyEvaluationInput(
            run_id=str(run_id),
            tick_number=tick_number,
            policy_version=POLICY_VERSION,
            agent_snapshots={
                str(state.agent_id): AgentSnapshot(
                    agent_id=str(state.agent_id),
                    hunger=state.hunger,
                    fatigue=state.fatigue,
                    stress=state.stress,
                    satisfaction=state.satisfaction,
                    mood=state.mood,
                )
                for state in states
            },
            relationship_snapshots=[
                RelationshipSnapshot(
                    source_agent_id=str(relationship.source_agent_id),
                    target_agent_id=str(relationship.target_agent_id),
                    affection=relationship.affection,
                    closeness=relationship.closeness,
                    trust=relationship.trust,
                    tension=relationship.tension,
                    rivalry=relationship.rivalry,
                    dependency=relationship.dependency,
                )
                for relationship in relationships
            ],
            runtime_results=list(runtime_results),
            valid_agent_ids={str(agent_id) for agent_id in agent_ids},
        )
    )
    if evaluation.status == PolicyStatus.REJECTED:
        raise RuntimeError("Policy Engine rejected the Tick")

    resolved = resolve_conflicts(evaluation.effect_candidates)
    relationship_effects = tuple(
        effect
        for effect in resolved
        if effect.target_type == EffectTargetType.RELATIONSHIP
    )
    state_effects = tuple(
        effect
        for effect in resolved
        if effect.target_type == EffectTargetType.AGENT_STATE
    )
    resolution_id = f"{run_id}:{tick_number}"
    apply_deltas(
        db,
        [
            RelationshipDelta(
                source_agent_id=UUID(effect.source_agent_id),
                target_agent_id=UUID(effect.target_agent_id),
                metric=cast(RelationshipMetric, effect.metric),
                before=effect.before,
                requested_total=effect.delta,
                applied_delta=effect.after_preview - effect.before,
                after=effect.after_preview,
                effect_ids=effect.effect_ids or (effect.effect_id,),
                policy_version=POLICY_VERSION,
                resolver_version=RESOLVER_VERSION,
                resolution_id=resolution_id,
            )
            for effect in relationship_effects
            if effect.target_agent_id is not None
        ],
    )

    states_by_agent_id = {str(state.agent_id): state for state in states}
    for effect in state_effects:
        state = states_by_agent_id[effect.source_agent_id]
        current = getattr(state, effect.metric)
        if current != effect.before:
            raise RuntimeError(
                f"stale {effect.metric}: expected {effect.before}, found {current}"
            )
        setattr(state, effect.metric, effect.after_preview)

    # Runtime Intent의 위치/행동도 상태·관계 delta와 같은 Tick transaction에서
    # 저장한다. Fallback/Skipped 결과는 실제로 수행된 행동이 아니므로 반영하지 않는다.
    for runtime_result in runtime_results:
        if runtime_result.status != RuntimeStatus.PROPOSED:
            continue
        state = states_by_agent_id[str(runtime_result.agent_id)]
        state.current_action = runtime_result.intent.action_type.value
        if runtime_result.intent.target_location_id is not None:
            state.location_id = runtime_result.intent.target_location_id
    db.flush()
    return PolicyCommitResult(
        relationship_effects=relationship_effects,
        state_effects=state_effects,
    )
