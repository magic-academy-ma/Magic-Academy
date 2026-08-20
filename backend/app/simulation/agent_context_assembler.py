from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from app.simulation.agent_runtime import (
    AgentContext,
    AgentRuntimeInput,
    AgentStateContext,
    BigFiveContext,
    Block,
    EventSummary,
    MBTI,
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
    ) -> AgentRuntimeInput:
        return AgentRuntimeInput(
            run_id=run_id,
            tick_number=tick_number,
            block=block,
            agent=AgentContext(
                agent_id=agent_id,
                fixture_key=fixture_key,
                agent_type=agent_type,
                name=name,
                mbti=mbti,
                big_five=big_five,
                state=state,
                current_location_id=current_location_id,
                active_status=active_status,
            ),
            nearby_agents=[],
            relationships=[],
            memories=[],
            events=list(events),
            schedule=schedule,
            valid_agent_ids=list(valid_agent_ids),
            valid_location_ids=list(valid_location_ids),
        )
