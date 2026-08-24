from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from app.domain.models import Agent, AgentState, Event, EventParticipant
from app.services.runtime_orchestrator import (
    RuntimeBatchExecutionResult,
    RuntimeOrchestrator,
)
from app.simulation.agent_runtime import (
    AgentContext,
    Block,
    EventSummary,
    ScheduleSummary,
)


ACTIVE_STATUS_VALUES = {
    "active": True,
    "inactive_temporary": False,
}

RUNTIME_AGENT_TYPES = {
    "student": "student",
    "professor": "professor",
    "user_persona": "student",
}


class RuntimeInputAdapter:
    def __init__(self, orchestrator: RuntimeOrchestrator) -> None:
        self._orchestrator = orchestrator

    @staticmethod
    def to_agent_context(agent: Agent, state: AgentState) -> AgentContext:
        if state.agent_id != agent.id:
            raise ValueError("AgentState.agent_id must match Agent.id")
        try:
            agent_type = RUNTIME_AGENT_TYPES[agent.agent_type]
        except KeyError as error:
            raise ValueError(f"unknown agent_type: {agent.agent_type!r}") from error
        try:
            active_status = ACTIVE_STATUS_VALUES[agent.active_status]
        except KeyError as error:
            raise ValueError(f"unknown active_status: {agent.active_status!r}") from error

        return AgentContext(
            agent_id=agent.id,
            fixture_key=agent.fixture_key,
            agent_type=agent_type,
            name=agent.name,
            mbti=agent.mbti_type,
            big_five={
                "openness": agent.openness,
                "conscientiousness": agent.conscientiousness,
                "extraversion": agent.extraversion,
                "agreeableness": agent.agreeableness,
                "emotional_stability": agent.emotional_stability,
            },
            state={
                "hunger": state.hunger,
                "fatigue": state.fatigue,
                "stress": state.stress,
                "satisfaction": state.satisfaction,
                "mood": state.mood,
            },
            current_location_id=state.location_id,
            active_status=active_status,
        )

    @staticmethod
    def to_event_summaries(
        events: Sequence[Event],
        event_participants: Mapping[UUID, Sequence[EventParticipant]],
    ) -> tuple[EventSummary, ...]:
        summaries = []
        for event in events:
            participants = event_participants.get(event.id, ())
            participant_agent_ids = []
            for participant in participants:
                if participant.event_id != event.id:
                    raise ValueError("EventParticipant.event_id must match Event.id")
                participant_agent_ids.append(participant.agent_id)
            summaries.append(
                EventSummary(
                    event_id=event.id,
                    event_type=event.event_type,
                    location_id=event.location_id,
                    participant_agent_ids=participant_agent_ids,
                    title=event.title,
                    description=event.description,
                )
            )
        return tuple(summaries)

    def run(
        self,
        *,
        run_id: str,
        tick_number: int,
        block: Block,
        agents: Sequence[Agent],
        preselected_agent_ids: Sequence[UUID],
        agent_states: Mapping[UUID, AgentState],
        schedule: ScheduleSummary,
        events: Sequence[Event],
        event_participants: Mapping[UUID, Sequence[EventParticipant]],
        valid_agent_ids: Sequence[UUID],
        valid_location_ids: Sequence[UUID],
        memories_by_agent: Mapping[UUID, Sequence[dict[str, Any]]] | None = None,
    ) -> RuntimeBatchExecutionResult:
        self._validate_uuid_sequence("preselected_agent_ids", preselected_agent_ids)
        self._validate_uuid_sequence("valid_agent_ids", valid_agent_ids)
        self._validate_uuid_sequence("valid_location_ids", valid_location_ids)

        agent_candidates = tuple(
            self.to_agent_context(agent, agent_states[agent.id])
            for agent in agents
        )
        event_summaries = self.to_event_summaries(events, event_participants)
        return self._orchestrator.run_preselected(
            run_id=run_id,
            tick_number=tick_number,
            block=block,
            agent_candidates=agent_candidates,
            preselected_agent_ids=preselected_agent_ids,
            schedule=schedule,
            events=event_summaries,
            valid_agent_ids=valid_agent_ids,
            valid_location_ids=valid_location_ids,
            memories_by_agent=memories_by_agent,
        )

    @staticmethod
    def _validate_uuid_sequence(name: str, values: Sequence[UUID]) -> None:
        if any(not isinstance(value, UUID) for value in values):
            raise TypeError(f"{name} must contain only UUID values")
