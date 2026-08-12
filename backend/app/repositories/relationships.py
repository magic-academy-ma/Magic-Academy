from dataclasses import dataclass
from typing import Literal, TypeAlias
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.models import Agent, Relationship


RelationshipMetric: TypeAlias = Literal[
    "affection",
    "closeness",
    "trust",
    "tension",
    "rivalry",
    "dependency",
]
RelationshipRow: TypeAlias = Relationship

METRIC_RANGES: dict[str, tuple[int, int]] = {
    "affection": (-100, 100),
    "closeness": (-100, 100),
    "trust": (-100, 100),
    "tension": (0, 100),
    "rivalry": (0, 100),
    "dependency": (0, 100),
}


class RelationshipNotFoundError(LookupError):
    pass


class StaleRelationshipValueError(RuntimeError):
    pass


class InvalidRelationshipDeltaError(ValueError):
    pass


@dataclass(frozen=True)
class RelationshipDelta:
    source_agent_id: UUID
    target_agent_id: UUID
    metric: RelationshipMetric
    before: int
    requested_total: int
    applied_delta: int
    after: int
    effect_ids: tuple[str, ...]
    policy_version: str
    resolver_version: str
    resolution_id: str


def get_pair(
    session: Session,
    source_agent_id: UUID,
    target_agent_id: UUID,
) -> RelationshipRow | None:
    return session.scalar(
        select(Relationship).where(
            Relationship.source_agent_id == source_agent_id,
            Relationship.target_agent_id == target_agent_id,
        )
    )


def apply_deltas(session: Session, deltas: list[RelationshipDelta]) -> None:
    seen: set[tuple[UUID, UUID, str]] = set()
    pending: list[tuple[Relationship, RelationshipDelta]] = []

    for delta in deltas:
        key = (delta.source_agent_id, delta.target_agent_id, delta.metric)
        if key in seen:
            raise InvalidRelationshipDeltaError(
                f"duplicate resolved relationship metric: {key}"
            )
        seen.add(key)

        bounds = METRIC_RANGES.get(delta.metric)
        if bounds is None:
            raise InvalidRelationshipDeltaError(
                f"unsupported relationship metric: {delta.metric}"
            )
        if not delta.effect_ids:
            raise InvalidRelationshipDeltaError("effect_ids must not be empty")
        if not delta.policy_version or not delta.resolver_version or not delta.resolution_id:
            raise InvalidRelationshipDeltaError(
                "policy_version, resolver_version, and resolution_id are required"
            )
        if abs(delta.applied_delta) > abs(delta.requested_total):
            raise InvalidRelationshipDeltaError(
                "applied_delta cannot exceed requested_total magnitude"
            )
        if delta.requested_total != 0 and delta.applied_delta * delta.requested_total < 0:
            raise InvalidRelationshipDeltaError(
                "applied_delta direction must match requested_total"
            )
        if delta.after != delta.before + delta.applied_delta:
            raise InvalidRelationshipDeltaError(
                "resolved relationship delta must satisfy after = before + applied_delta"
            )
        if not bounds[0] <= delta.after <= bounds[1]:
            raise InvalidRelationshipDeltaError(
                f"resolved {delta.metric} value {delta.after} is outside {bounds}"
            )

        source_simulation_id = session.scalar(
            select(Agent.simulation_id).where(Agent.id == delta.source_agent_id)
        )
        target_simulation_id = session.scalar(
            select(Agent.simulation_id).where(Agent.id == delta.target_agent_id)
        )
        if source_simulation_id is None or target_simulation_id is None:
            raise RelationshipNotFoundError(
                f"relationship agent not found: {delta.source_agent_id} -> {delta.target_agent_id}"
            )
        if source_simulation_id != target_simulation_id:
            raise InvalidRelationshipDeltaError(
                "relationship agents must belong to the same simulation"
            )

        session.execute(
            insert(Relationship)
            .values(
                id=uuid4(),
                simulation_id=source_simulation_id,
                source_agent_id=delta.source_agent_id,
                target_agent_id=delta.target_agent_id,
            )
            .on_conflict_do_nothing(
                constraint="uq_relationships_pair",
            )
        )
        relationship = session.scalar(
            select(Relationship)
            .where(
                Relationship.source_agent_id == delta.source_agent_id,
                Relationship.target_agent_id == delta.target_agent_id,
            )
            .with_for_update()
        )
        if relationship is None:
            raise RelationshipNotFoundError(
                f"relationship not found: {delta.source_agent_id} -> {delta.target_agent_id}"
            )

        current = getattr(relationship, delta.metric)
        if current != delta.before:
            raise StaleRelationshipValueError(
                f"stale {delta.metric}: expected {delta.before}, found {current}"
            )
        pending.append((relationship, delta))

    for relationship, delta in pending:
        setattr(relationship, delta.metric, delta.after)

    # TODO(issue-41-task5): 상위 Tick Commit 경계에서 State, Memory,
    # Event, Outbox 변경과 함께 commit/rollback하도록 통합한다.
    session.flush()
