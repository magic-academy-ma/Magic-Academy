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
        block: Block,
        schedule: ScheduleSummary,
        schedule_requires_professor: bool,
        events: Sequence[Event],
        event_participants: Mapping[UUID, Sequence[EventParticipant]],
    ) -> RuntimeBatchExecutionResult:
        agents = list_runtime_agents(db, simulation_id)
        agent_ids = self._validate_unique_agents(agents)
        states = list_runtime_agent_states(db, agent_ids)
        agent_states = self._validate_agent_states(agent_ids, states)
        valid_location_ids = list_active_runtime_location_ids(db, simulation_id)

        return self._runtime_input_adapter.run(
            run_id=str(run_id),
            tick_number=tick_number,
            block=block,
            agents=agents,
            agent_states=agent_states,
            schedule=schedule,
            schedule_requires_professor=schedule_requires_professor,
            events=events,
            event_participants=event_participants,
            valid_agent_ids=agent_ids,
            valid_location_ids=valid_location_ids,
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
