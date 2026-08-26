from uuid import uuid4

from app.services.simulation_events import build_tick_result_messages


def test_persisted_tick_payload_uses_existing_task4_message_contract() -> None:
    simulation_id = uuid4()
    event_id = uuid4()
    result = {
        "tick_number": 10,
        "block": "morning",
        "events": [
            {
                "id": str(event_id),
                "event_type": "MAGIC_EXPLOSION",
                "participant_agent_ids": [str(uuid4())],
            }
        ],
        "resolved_effects": [
            {
                "target_type": "AGENT_STATE",
                "source_agent_id": str(uuid4()),
                "metric": "stress",
                "before": 10,
                "applied_delta": 8,
                "after": 18,
            }
        ],
    }
    relationship_effect = {
        "source_agent_id": str(uuid4()),
        "target_agent_id": str(uuid4()),
        "metric": "trust",
        "before": 1,
        "applied_delta": 3,
        "after": 4,
    }

    messages = build_tick_result_messages(
        simulation_id,
        result,
        [relationship_effect],
    )

    assert [message["type"] for message in messages] == [
        "TICK_UPDATED",
        "EVENT_CREATED",
        "RELATIONSHIP_UPDATED",
    ]
    assert all(
        message["data"]["simulation_id"] == str(simulation_id)
        and message["data"]["tick_number"] == 10
        for message in messages
    )
    assert messages[0]["data"]["resolved_effects"] == result["resolved_effects"]
    assert messages[1]["data"]["event_id"] == str(event_id)
