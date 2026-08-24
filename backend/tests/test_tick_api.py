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
    from app.api.ticks import (
        AgentTickResultResponse,
        DecisionExplanationResponse,
        RelationshipDeltaResponse,
        StateDeltaResponse,
        TickAdvanceResponse,
    )

    response = TickAdvanceResponse(
        simulation_id=uuid4(),
        previous_tick=0,
        current_tick=1,
        current_day=1,
        status="COMPLETED",
        state_deltas=[
            StateDeltaResponse(
                effect_id="run:1:a:state:FATIGUE_UP",
                rule_id="STATE_FATIGUE_UP_MEDIUM",
                agent_id=uuid4(),
                agent_name="아델",
                metric="fatigue",
                delta=5,
                before=10,
                after=15,
                reason="수업 참여 후 피로 상승",
            )
        ],
        relationship_deltas=[
            RelationshipDeltaResponse(
                effect_id="run:1:a:rel:TRUST_UP:b",
                rule_id="REL_TRUST_UP_MEDIUM",
                source_agent_id=uuid4(),
                target_agent_id=uuid4(),
                metric="trust",
                delta=3,
                before=0,
                after=3,
                reason="대화 후 신뢰 상승",
            )
        ],
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
    assert response["relationship_deltas"][0]["delta"] == 3
    assert response["relationship_deltas"][0]["after"] == 3
    assert "after_preview" not in response["relationship_deltas"][0]
    assert response["state_deltas"][0]["after"] == 15
    assert response["retrieved_memories"] == []
    assert "participant_ids" not in response
    assert "runtime_outputs" not in response
