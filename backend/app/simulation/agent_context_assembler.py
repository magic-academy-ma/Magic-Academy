from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from app.simulation.agent_runtime import (
    AgentContext,
    AgentSummary,
    AgentRuntimeInput,
    AgentStateContext,
    BigFiveContext,
    Block,
    EventSummary,
    MBTI,
    RelationshipSummary,
    ScheduleSummary,
)


class AgentContextAssembler:
    def assemble(
        self,
        *,
        run_id: str,
        tick_number: int,
        block: Block,
        agent_id: UUID,
        fixture_key: str,
        agent_type: Literal["student", "professor"],
        name: str,
        mbti: MBTI | None,
        big_five: BigFiveContext,
        state: AgentStateContext,
        current_location_id: UUID | None,
        active_status: bool,
        events: Sequence[EventSummary],
        schedule: ScheduleSummary,
        valid_agent_ids: Sequence[UUID],
        valid_location_ids: Sequence[UUID],
        agent_candidates: Sequence[AgentContext],
        relationships: Sequence[RelationshipSummary] = (),
    ) -> AgentRuntimeInput:
        observer = AgentContext(
            agent_id=agent_id,
            fixture_key=fixture_key,
            agent_type=agent_type,
            name=name,
            mbti=mbti,
            big_five=big_five,
            state=state,
            current_location_id=current_location_id,
            active_status=active_status,
        )
        nearby_agents = self._nearby_agents(
            observer,
            agent_candidates,
            set(valid_agent_ids),
        )
        observable_agent_ids = {summary.agent_id for summary in nearby_agents}
        visible_events = self._visible_events(
            observer,
            events,
            schedule,
            observable_agent_ids,
        )
        normalized_relationships = tuple(
            RelationshipSummary.model_validate(relationship)
            for relationship in relationships
        )
        visible_relationships = sorted(
            (
                relationship
                for relationship in normalized_relationships
                if relationship.source_agent_id == observer.agent_id
                and relationship.target_agent_id in observable_agent_ids
            ),
            key=lambda relationship: (
                relationship.target_agent_id.int,
                relationship.source_agent_id.int,
            ),
        )
        runtime_valid_agent_ids = sorted(
            observable_agent_ids,
            key=lambda value: value.int,
        )
        return AgentRuntimeInput(
            run_id=run_id,
            tick_number=tick_number,
            block=block,
            agent=observer,
            nearby_agents=nearby_agents,
            relationships=visible_relationships,
            memories=[],
            events=visible_events,
            schedule=schedule,
            valid_agent_ids=runtime_valid_agent_ids,
            valid_location_ids=sorted(set(valid_location_ids), key=lambda value: value.int),
        )

    @staticmethod
    def _nearby_agents(
        observer: AgentContext,
        agent_candidates: Sequence[AgentContext],
        valid_agent_ids: set[UUID],
    ) -> list[AgentSummary]:
        if observer.current_location_id is None:
            return []
        summaries = [
            AgentSummary(
                agent_id=candidate.agent_id,
                name=candidate.name,
                agent_type=candidate.agent_type,
                active_status=candidate.active_status,
                current_location_id=candidate.current_location_id,
                mood=candidate.state.mood,
                stress=candidate.state.stress,
                fatigue=candidate.state.fatigue,
            )
            for candidate in agent_candidates
            if candidate.agent_id != observer.agent_id
            and candidate.agent_id in valid_agent_ids
            and candidate.active_status
            and candidate.current_location_id == observer.current_location_id
        ]
        return sorted(summaries, key=lambda summary: summary.agent_id.int)

    @staticmethod
    def _visible_events(
        observer: AgentContext,
        events: Sequence[EventSummary],
        schedule: ScheduleSummary,
        observable_agent_ids: set[UUID],
    ) -> list[EventSummary]:
        visible_participant_ids = observable_agent_ids | {observer.agent_id}
        visible_events = []
        for event in events:
            if not (
                observer.agent_id in event.participant_agent_ids
                or event.location_id == observer.current_location_id
                or (
                    schedule.is_mandatory
                    and event.event_id == schedule.event_id
                )
            ):
                continue
            visible_events.append(
                event.model_copy(
                    update={
                        "participant_agent_ids": sorted(
                            (
                                participant_id
                                for participant_id in event.participant_agent_ids
                                if participant_id in visible_participant_ids
                            ),
                            key=lambda value: value.int,
                        )
                    }
                )
            )
        return sorted(visible_events, key=lambda event: event.event_id.int)
