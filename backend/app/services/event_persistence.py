"""Task 3 persistence; the caller owns the complete Tick transaction."""

from copy import deepcopy

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.event_persistence import EventBatch
from app.domain.models import Agent, AgentMemory, AgentState, Event, EventBatchResult, EventParticipant, Location, Simulation
from app.repositories.memory_repository import MemoryCreateInput, MemoryRepository

DURATION_TICKS = 3


def persist_event_batch(session: Session, batch: EventBatch) -> dict:
    """Flush final results atomically with caller writes; never commit or rollback.

    The caller MUST roll back its whole Tick on any error. The returned payload
    is not publishable until that enclosing transaction has committed.
    """
    batch = EventBatch.model_validate(batch.model_dump())
    session.flush()
    simulation = session.scalar(select(Simulation).where(
        Simulation.id == batch.simulation_id, Simulation.deleted_at.is_(None)
    ).with_for_update().execution_options(populate_existing=True))
    if simulation is None:
        raise ValueError("Simulation not found")
    payload = batch.model_dump(mode="json")
    existing = session.get(EventBatchResult, (batch.simulation_id, batch.tick_number))
    if existing is not None:
        if existing.input_payload != payload:
            raise ValueError("different result already stored for this Tick")
        return deepcopy(existing.result_payload)
    if batch.tick_number != simulation.current_tick + 1:
        raise ValueError("stale or out-of-order Tick")

    agents = {agent.id: agent for agent in session.scalars(select(Agent).where(
        Agent.simulation_id == batch.simulation_id, Agent.deleted_at.is_(None)
    ).order_by(Agent.id).with_for_update().execution_options(populate_existing=True))}
    locations = {location.id: location for location in session.scalars(select(Location).where(
        Location.simulation_id == batch.simulation_id
    ))}
    states = {state.agent_id: state for state in session.scalars(select(AgentState).where(
        AgentState.simulation_id == batch.simulation_id
    ).order_by(AgentState.agent_id).with_for_update().execution_options(populate_existing=True))}
    events = {event.id: event for event in batch.events}
    for event in batch.events:
        if not set(event.participant_agent_ids) <= agents.keys():
            raise ValueError("Event Agent is outside Simulation")
        if event.location_id not in locations:
            raise ValueError("Event Location is outside Simulation")
        if session.get(Event, event.id) is not None:
            raise ValueError("Event ID already exists")
    for memory in batch.memories:
        event = events.get(memory.event_id)
        if event is None or memory.agent_id not in event.participant_agent_ids:
            raise ValueError("Memory must reference a participating Event Agent")
    missing_candidates = {agent_id for event in batch.events if event.event_type == "STUDENT_MISSING" for agent_id in event.participant_agent_ids}
    if not set(batch.missing_agent_ids) <= missing_candidates:
        raise ValueError("missing status requires STUDENT_MISSING Event")
    if any(agents[agent_id].agent_type not in ("student", "user_persona") for agent_id in batch.missing_agent_ids):
        raise ValueError("STUDENT_MISSING requires a Student")
    for effect in batch.resolved_effects:
        state = states.get(effect.source_agent_id)
        if effect.source_agent_id not in agents or state is None:
            raise ValueError("State Agent is outside Simulation")
        if getattr(state, effect.metric) != effect.before:
            raise ValueError("stale State delta")

    # Expiration runs before new effects. No LLM or probability is involved.
    for agent in agents.values():
        if agent.active_status == "inactive_temporary" and agent.inactive_until_tick is not None and agent.inactive_until_tick <= batch.tick_number:
            expiry = agent.inactive_until_tick
            agent.active_status = "active"
            agent.inactive_until_tick = None
            agent.cursed_until_tick = expiry + DURATION_TICKS
        if agent.cursed_until_tick is not None and agent.cursed_until_tick <= batch.tick_number:
            agent.cursed_until_tick = None
    for agent_id in batch.missing_agent_ids:
        agent = agents[agent_id]
        if agent.active_status != "active":
            raise ValueError("missing Agent is not active")
        agent.active_status = "inactive_temporary"
        agent.inactive_until_tick = batch.tick_number + DURATION_TICKS

    saved_events = []
    for event in batch.events:
        data = event.model_dump(mode="json")
        data.update(tick=batch.tick_number, location=locations[event.location_id].name)
        session.add(Event(
            id=event.id, simulation_id=batch.simulation_id, location_id=event.location_id,
            event_type=event.event_type.lower(), title=event.title, description=event.description,
            status="completed", simulation_day=(batch.tick_number - 1) // 3 + 1,
            event_metadata=data,
        ))
        saved_events.append(data)
    session.flush()
    for event in batch.events:
        for agent_id in event.participant_agent_ids:
            session.add(EventParticipant(id=uuid7(), event_id=event.id, agent_id=agent_id))
    for effect in batch.resolved_effects:
        setattr(states[effect.source_agent_id], effect.metric, effect.after)
    session.flush()

    repository = MemoryRepository()
    saved_memories = []
    for memory in batch.memories:
        row = repository.create(session, MemoryCreateInput(
            **memory.model_dump(), created_tick=batch.tick_number,
        ))
        saved_memories.append({**memory.model_dump(mode="json"), "id": str(row.id), "created_tick": batch.tick_number})
    for agent_id in {memory.agent_id for memory in batch.memories}:
        repository.enforce_cap(session, agent_id)
    retained_ids = {str(value) for value in session.scalars(select(AgentMemory.id).where(
        AgentMemory.event_id.in_(events)
    ))}
    saved_memories = [memory for memory in saved_memories if memory["id"] in retained_ids]

    result = {
        "simulation_id": str(batch.simulation_id), "run_id": batch.run_id,
        "tick_number": batch.tick_number,
        "block": ("morning", "afternoon", "evening")[(batch.tick_number - 1) % 3],
        "policy_version": batch.policy_version, "resolver_version": batch.resolver_version,
        "resolution_id": batch.resolution_id, "events": saved_events,
        "resolved_effects": [effect.model_dump(mode="json") for effect in batch.resolved_effects],
        "memories": saved_memories,
        "agent_statuses": [{"agent_id": str(agent.id), "active_status": agent.active_status,
                            "inactive_until_tick": agent.inactive_until_tick,
                            "cursed_until_tick": agent.cursed_until_tick} for agent in agents.values()],
    }
    session.add(EventBatchResult(simulation_id=batch.simulation_id, tick_number=batch.tick_number,
                                 input_payload=payload, result_payload=result))
    session.flush()
    # TODO(#105): invoke inside the fenced Tick commit alongside Runtime/relationships;
    # advance current_tick there, and publish get_event_result() only after commit.
    return deepcopy(result)
