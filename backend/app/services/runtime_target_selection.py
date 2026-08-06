from collections.abc import Sequence
from uuid import UUID

from app.simulation.agent_runtime import AgentContext, EventSummary


class RuntimeTargetSelector:
    def select(
        self,
        agent_candidates: Sequence[AgentContext],
        *,
        schedule_requires_professor: bool,
        events: Sequence[EventSummary],
    ) -> tuple[AgentContext, ...]:
        if type(schedule_requires_professor) is not bool:
            raise TypeError("schedule_requires_professor must be a bool")

        candidates_by_id: dict[UUID, AgentContext] = {}
        for candidate in agent_candidates:
            existing = candidates_by_id.get(candidate.agent_id)
            if existing is not None and existing != candidate:
                raise ValueError(f"conflicting agent candidates for {candidate.agent_id}")
            candidates_by_id[candidate.agent_id] = candidate

        event_participant_ids = {
            participant_id
            for event in events
            for participant_id in event.participant_agent_ids
        }
        selected = [
            candidate
            for candidate in candidates_by_id.values()
            if (
                candidate.agent_type == "student"
                and candidate.active_status
            )
            or (
                candidate.agent_type == "professor"
                and (
                    schedule_requires_professor
                    or candidate.agent_id in event_participant_ids
                )
            )
        ]
        return tuple(sorted(selected, key=lambda candidate: str(candidate.agent_id)))
