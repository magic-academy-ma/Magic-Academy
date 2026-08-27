from typing import Protocol
from uuid import UUID


class TickResultPublisher(Protocol):
    async def publish(self, messages: tuple[dict, ...]) -> None: ...


class NullTickResultPublisher:
    async def publish(self, messages: tuple[dict, ...]) -> None:
        return None


tick_result_publisher: TickResultPublisher = NullTickResultPublisher()


def get_tick_result_publisher() -> TickResultPublisher:
    return tick_result_publisher


def build_tick_result_messages(
    simulation_id: UUID,
    result: dict,
    relationship_effects: list[dict],
) -> tuple[dict, ...]:
    """Build Task 4 payloads without owning a WebSocket transport."""
    return (
        {
            "type": "TICK_UPDATED",
            "data": {
                "simulation_id": str(simulation_id),
                "tick_number": result["tick_number"],
                "block": result["block"],
                "resolved_effects": result["resolved_effects"],
            },
        },
        *(
            {
                "type": "EVENT_CREATED",
                "data": {
                    "simulation_id": str(simulation_id),
                    "tick_number": result["tick_number"],
                    "event_id": event["id"],
                    **event,
                },
            }
            for event in result["events"]
        ),
        *(
            {
                "type": "RELATIONSHIP_UPDATED",
                "data": {
                    "simulation_id": str(simulation_id),
                    "tick_number": result["tick_number"],
                    **effect,
                },
            }
            for effect in relationship_effects
        ),
    )
