from uuid import uuid4

import pytest

from app.services.manual_tick import tick_position


@pytest.mark.parametrize(
    ("tick", "day", "block"),
    [
        (1, 1, "MORNING"),
        (2, 1, "AFTERNOON"),
        (3, 1, "EVENING"),
        (4, 2, "MORNING"),
        (6, 2, "EVENING"),
        (7, 3, "MORNING"),
    ],
)
def test_tick_position_boundaries(tick, day, block):
    assert tick_position(tick) == (day, block)


def test_tick_position_rejects_non_positive_tick():
    with pytest.raises(ValueError, match="positive"):
        tick_position(0)


def test_tick_response_contract_does_not_expose_internal_fields():
    from app.api.ticks import AgentTickResultResponse, TickAdvanceResponse
    from app.api.ticks import DecisionExplanationResponse

    response = TickAdvanceResponse(
        simulation_id=uuid4(),
        previous_tick=0,
        current_tick=1,
        current_day=1,
        status="COMPLETED",
        agent_results=[
            AgentTickResultResponse(
                agent_id=uuid4(),
                agent_name="아델",
                runtime_status="PROPOSED",
                action_type="ATTEND_CLASS",
                utterance=None,
                motivation_summary="수업에 참석한다.",
                decision_explanation=DecisionExplanationResponse(
                    alternatives=[], influencing_factors=[]
                ),
                retry_count=0,
                failure_reason=None,
            )
        ],
    ).model_dump(mode="json")

    assert response["status"] == "COMPLETED"
    assert response["agent_results"][0]["runtime_status"] == "PROPOSED"
    assert "participant_ids" not in response
    assert "runtime_outputs" not in response
