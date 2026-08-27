from dataclasses import dataclass
from uuid import UUID

from app.simulation.agent_runtime import (
    ActionAlternative,
    ActionType,
    AgentReaction,
    AgentRuntimeResult,
    DecisionExplanation,
    IntentCandidate,
    ReactionValence,
    RelativePriority,
    RuntimeStatus,
)


@dataclass(frozen=True)
class TalkConflictResolution:
    runtime_results: tuple[AgentRuntimeResult, ...]
    mutual_pairs: tuple[tuple[UUID, UUID], ...]
    wait_fallback_agent_ids: tuple[UUID, ...]


def resolve_talk_conflicts(
    runtime_results: tuple[AgentRuntimeResult, ...],
) -> TalkConflictResolution:
    """Accept mutual TALK pairs and convert every unmatched TALK to WAIT."""
    talks = {
        result.agent_id: result.intent.target_agent_id
        for result in runtime_results
        if result.intent.action_type == ActionType.TALK
        and result.intent.target_agent_id is not None
    }
    mutual_agent_ids = {
        source_id
        for source_id, target_id in talks.items()
        if talks.get(target_id) == source_id
    }
    mutual_pairs: list[tuple[UUID, UUID]] = []
    seen: set[UUID] = set()
    for result in runtime_results:
        source_id = result.agent_id
        target_id = talks.get(source_id)
        if source_id in mutual_agent_ids and source_id not in seen and target_id is not None:
            mutual_pairs.append((source_id, target_id))
            seen.update((source_id, target_id))

    fallback_ids: list[UUID] = []
    resolved: list[AgentRuntimeResult] = []
    for result in runtime_results:
        if result.intent.action_type != ActionType.TALK or result.agent_id in mutual_agent_ids:
            resolved.append(result)
            continue
        fallback_ids.append(result.agent_id)
        wait_intent = IntentCandidate(
            action_type=ActionType.WAIT,
            target_agent_id=None,
            target_location_id=None,
            related_event_id=None,
            utterance=None,
            motivation_summary="TALK 충돌로 WAIT_FALLBACK 적용",
            reaction=AgentReaction(
                valence=ReactionValence.NEUTRAL,
                relationship_signals=[],
                state_signals=[],
            ),
            decision_explanation=DecisionExplanation(
                alternatives=[
                    ActionAlternative(
                        action_type=ActionType.WAIT,
                        description="상호 TALK가 성립하지 않아 대기한다.",
                        relative_priority=RelativePriority.HIGH,
                        selected=True,
                    )
                ],
                influencing_factors=[],
            ),
            memory_candidates=[],
        )
        resolved.append(
            result.model_copy(
                update={
                    "status": RuntimeStatus.FALLBACK,
                    "intent": wait_intent,
                    "failure_reason": "WAIT_FALLBACK",
                }
            )
        )
    return TalkConflictResolution(
        runtime_results=tuple(resolved),
        mutual_pairs=tuple(mutual_pairs),
        wait_fallback_agent_ids=tuple(fallback_ids),
    )
