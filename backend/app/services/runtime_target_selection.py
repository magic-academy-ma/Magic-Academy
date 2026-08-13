from collections.abc import Sequence
from uuid import UUID

from app.simulation.agent_runtime import AgentContext


class RuntimeTargetSelector:
    def select(
        self,
        agent_candidates: Sequence[AgentContext],
        *,
        preselected_agent_ids: Sequence[UUID],
    ) -> tuple[AgentContext, ...]:
        candidates_by_id: dict[UUID, AgentContext] = {}
        for candidate in agent_candidates:
            existing = candidates_by_id.get(candidate.agent_id)
            if existing is not None and existing != candidate:
                raise ValueError(f"conflicting agent candidates for {candidate.agent_id}")
            candidates_by_id[candidate.agent_id] = candidate

        if len(set(preselected_agent_ids)) != len(preselected_agent_ids):
            raise ValueError("preselected_agent_ids must not contain duplicates")
        missing_ids = [
            agent_id for agent_id in preselected_agent_ids if agent_id not in candidates_by_id
        ]
        if missing_ids:
            raise ValueError(f"preselected Agent {missing_ids[0]} is not a runtime candidate")
        return tuple(candidates_by_id[agent_id] for agent_id in preselected_agent_ids)
