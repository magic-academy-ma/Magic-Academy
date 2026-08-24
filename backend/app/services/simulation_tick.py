from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.models import Agent, AgentState, Event, EventParticipant
from app.repositories.simulations import (
    list_active_runtime_location_ids,
    list_runtime_agents,
    list_runtime_agent_states,
)
from app.services.runtime_input_adapter import RuntimeInputAdapter
from app.services.runtime_orchestrator import RuntimeBatchExecutionResult
from app.services.runtime_target_selection import select_tick_participant_ids
from app.simulation.agent_runtime import Block, ScheduleSummary


class RuntimeSnapshotError(ValueError):
    pass


class SimulationTickService:
    def __init__(self, runtime_input_adapter: RuntimeInputAdapter) -> None:
        self._runtime_input_adapter = runtime_input_adapter

    def run_runtime_phase(
        self,
        db: Session,
        *,
        simulation_id: UUID,
        run_id: UUID,
        tick_number: int,
        seed: int = 0,
        block: Block,
        preselected_agent_ids: Sequence[UUID] | None = None,
        schedule_requires_professor: bool = False,
        schedule: ScheduleSummary,
        events: Sequence[Event],
        event_participants: Mapping[UUID, Sequence[EventParticipant]],
    ) -> RuntimeBatchExecutionResult:
        agents = list_runtime_agents(db, simulation_id)
        agent_ids = self._validate_unique_agents(agents)
        states = list_runtime_agent_states(db, agent_ids)
        agent_states = self._validate_agent_states(agent_ids, states)
        valid_location_ids = list_active_runtime_location_ids(db, simulation_id)
        self._validate_events(
            simulation_id=simulation_id,
            events=events,
            event_participants=event_participants,
            valid_agent_ids=agent_ids,
            valid_location_ids=valid_location_ids,
        )

        if preselected_agent_ids is None:
            # Student(User Persona 포함)를 기본 편성하고, Event 참여자이거나
            # Schedule 조건을 충족하는 Professor만 추가한다 (Slice 4 Task 0 계약).
            preselected_agent_ids = select_tick_participant_ids(
                agents,
                event_participant_agent_ids=self._flatten_event_participant_agent_ids(
                    event_participants
                ),
                schedule_requires_professor=schedule_requires_professor,
            )

        return self._runtime_input_adapter.run(
            run_id=str(run_id),
            tick_number=tick_number,
            seed=seed,
            block=block,
            agents=agents,
            preselected_agent_ids=preselected_agent_ids,
            agent_states=agent_states,
            schedule=schedule,
            events=events,
            event_participants=event_participants,
            valid_agent_ids=agent_ids,
            valid_location_ids=valid_location_ids,
        )

    @staticmethod
    def _flatten_event_participant_agent_ids(
        event_participants: Mapping[UUID, Sequence[EventParticipant]],
    ) -> tuple[UUID, ...]:
        return tuple(
            participant.agent_id
            for participants in event_participants.values()
            for participant in participants
        )

    @staticmethod
    def _validate_unique_agents(agents: Sequence[Agent]) -> list[UUID]:
        agent_ids = [agent.id for agent in agents]
        if len(set(agent_ids)) != len(agent_ids):
            raise RuntimeSnapshotError("duplicate Agent.id in runtime snapshot")
        return agent_ids

    @staticmethod
    def _validate_agent_states(
        agent_ids: Sequence[UUID],
        states: Sequence[AgentState],
    ) -> dict[UUID, AgentState]:
        expected_agent_ids = set(agent_ids)
        states_by_agent_id: dict[UUID, AgentState] = {}
        for state in states:
            if state.agent_id not in expected_agent_ids:
                raise RuntimeSnapshotError("AgentState.agent_id does not match a runtime Agent")
            if state.agent_id in states_by_agent_id:
                raise RuntimeSnapshotError(f"duplicate AgentState for Agent {state.agent_id}")
            if state.location_id is None:
                raise RuntimeSnapshotError(
                    f"AgentState.location_id is required for Agent {state.agent_id}"
                )
            states_by_agent_id[state.agent_id] = state

        missing_ids = [agent_id for agent_id in agent_ids if agent_id not in states_by_agent_id]
        if missing_ids:
            raise RuntimeSnapshotError(f"missing AgentState for Agent {missing_ids[0]}")
        return states_by_agent_id

    @staticmethod
    def _validate_events(
        *,
        simulation_id: UUID,
        events: Sequence[Event],
        event_participants: Mapping[UUID, Sequence[EventParticipant]],
        valid_agent_ids: Sequence[UUID],
        valid_location_ids: Sequence[UUID],
    ) -> None:
        event_ids = [event.id for event in events]
        if len(set(event_ids)) != len(event_ids):
            raise RuntimeSnapshotError("duplicate Event.id in runtime snapshot")

        events_by_id = {event.id: event for event in events}
        unknown_mapping_ids = [
            event_id for event_id in event_participants if event_id not in events_by_id
        ]
        if unknown_mapping_ids:
            raise RuntimeSnapshotError(
                f"event_participants contains unknown Event {unknown_mapping_ids[0]}"
            )

        valid_agent_id_set = set(valid_agent_ids)
        valid_location_id_set = set(valid_location_ids)
        for event in events:
            if event.simulation_id != simulation_id:
                raise RuntimeSnapshotError(
                    f"Event {event.id} does not belong to Simulation {simulation_id}"
                )
            if event.location_id not in valid_location_id_set:
                raise RuntimeSnapshotError(
                    f"Event {event.id} has an invalid runtime Location"
                )
            for participant in event_participants.get(event.id, ()):
                if participant.event_id != event.id:
                    raise RuntimeSnapshotError(
                        f"EventParticipant.event_id does not match Event {event.id}"
                    )
                if participant.agent_id not in valid_agent_id_set:
                    raise RuntimeSnapshotError(
                        f"EventParticipant Agent {participant.agent_id} is not valid"
                    )
