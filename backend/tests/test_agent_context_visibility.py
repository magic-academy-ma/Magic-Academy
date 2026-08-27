from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID

from app.services.runtime_orchestrator import RuntimeOrchestrator
from app.services.runtime_results import InMemoryRuntimeResultSink
from app.simulation.agent_runtime import (
    AgentContext,
    AgentRuntimeInput,
    AgentRuntimeResult,
    EventSummary,
    RuntimeStatus,
    ScheduleSummary,
    validate_intent_candidate,
)
from app.simulation.anthropic_llm_client import AnthropicLLMClient
from app.simulation.agent_runtime import MockLLMClient


AGENT_A = UUID("00000000-0000-0000-0000-000000000001")
AGENT_B = UUID("00000000-0000-0000-0000-000000000002")
AGENT_C = UUID("00000000-0000-0000-0000-000000000003")
AGENT_D = UUID("00000000-0000-0000-0000-000000000004")
LOCATION_ONE = UUID("10000000-0000-0000-0000-000000000001")
LOCATION_TWO = UUID("10000000-0000-0000-0000-000000000002")
MANDATORY_EVENT = UUID("20000000-0000-0000-0000-000000000001")
PARTICIPANT_EVENT = UUID("20000000-0000-0000-0000-000000000002")
SAME_LOCATION_EVENT = UUID("20000000-0000-0000-0000-000000000003")
UNRELATED_EVENT = UUID("20000000-0000-0000-0000-000000000004")


def make_agent(
    agent_id: UUID,
    *,
    location_id: UUID,
    active: bool = True,
) -> AgentContext:
    return AgentContext(
        agent_id=agent_id,
        fixture_key=f"student-{agent_id.int}",
        agent_type="student",
        name=f"Agent {agent_id.int}",
        mbti="ISTJ",
        big_five={
            "openness": 0,
            "conscientiousness": 0,
            "extraversion": 0,
            "agreeableness": 0,
            "emotional_stability": 0,
        },
        state={
            "hunger": 10,
            "fatigue": agent_id.int,
            "stress": agent_id.int + 10,
            "satisfaction": 50,
            "mood": agent_id.int - 2,
        },
        current_location_id=location_id,
        active_status=active,
    )


def make_event(
    event_id: UUID,
    *,
    location_id: UUID,
    participants: list[UUID] | None = None,
    event_type: str = "meeting",
) -> EventSummary:
    return EventSummary(
        event_id=event_id,
        event_type=event_type,
        location_id=location_id,
        participant_agent_ids=participants or [],
        title=f"Event {event_id.int}",
        description="visible world data",
    )


def make_schedule() -> ScheduleSummary:
    return ScheduleSummary(
        event_id=MANDATORY_EVENT,
        schedule_type="class",
        is_mandatory=True,
        location_id=LOCATION_TWO,
        start_tick=3,
        end_tick=3,
    )


def make_relationship(source: UUID, target: UUID, *, trust: int) -> dict:
    return {
        "source_agent_id": source,
        "target_agent_id": target,
        "affection": 1,
        "closeness": 2,
        "trust": trust,
        "tension": 4,
        "rivalry": 5,
        "dependency": 6,
    }


class RecordingRuntime:
    def __init__(self) -> None:
        self.inputs: list[AgentRuntimeInput] = []

    def run(self, runtime_input: AgentRuntimeInput) -> AgentRuntimeResult:
        self.inputs.append(runtime_input)
        intent = validate_intent_candidate(
            MockLLMClient().generate(runtime_input),
            runtime_input,
        )
        agent_id = runtime_input.agent.agent_id
        return AgentRuntimeResult(
            run_id=runtime_input.run_id,
            tick_number=runtime_input.tick_number,
            agent_id=agent_id,
            status=RuntimeStatus.PROPOSED,
            intent=intent,
            retry_count=0,
            failure_reason=None,
            model="recording-runtime",
            prompt_version="test",
            idempotency_key=f"{runtime_input.run_id}:{runtime_input.tick_number}:{agent_id}",
        )


def assemble_visibility_inputs() -> tuple[list[AgentRuntimeInput], tuple[object, ...]]:
    agents = [
        make_agent(AGENT_D, location_id=LOCATION_TWO),
        make_agent(AGENT_C, location_id=LOCATION_ONE, active=False),
        make_agent(AGENT_B, location_id=LOCATION_ONE),
        make_agent(AGENT_A, location_id=LOCATION_ONE),
    ]
    events = [
        make_event(UNRELATED_EVENT, location_id=LOCATION_TWO),
        make_event(SAME_LOCATION_EVENT, location_id=LOCATION_ONE),
        make_event(
            PARTICIPANT_EVENT,
            location_id=LOCATION_TWO,
            participants=[AGENT_D, AGENT_A],
        ),
        make_event(
            MANDATORY_EVENT,
            location_id=LOCATION_TWO,
            participants=[AGENT_D],
            event_type="class",
        ),
    ]
    relationships = [
        make_relationship(AGENT_B, AGENT_A, trust=90),
        make_relationship(AGENT_A, AGENT_D, trust=80),
        make_relationship(AGENT_A, AGENT_B, trust=70),
    ]
    original = deepcopy((agents, events, relationships))
    runtime = RecordingRuntime()
    RuntimeOrchestrator(runtime, InMemoryRuntimeResultSink()).run_preselected(
        run_id="slice-5-run",
        tick_number=3,
        block="MORNING",
        agent_candidates=agents,
        preselected_agent_ids=[AGENT_A, AGENT_D],
        schedule=make_schedule(),
        events=events,
        relationships=relationships,
        valid_agent_ids=[AGENT_D, AGENT_C, AGENT_B, AGENT_A],
        valid_location_ids=[LOCATION_TWO, LOCATION_ONE],
    )
    return runtime.inputs, (agents, events, relationships, original)


def test_orchestrator_builds_independent_agent_visibility_contexts() -> None:
    runtime_inputs, _ = assemble_visibility_inputs()

    assert len(runtime_inputs) == 2
    assert runtime_inputs[0] is not runtime_inputs[1]
    by_agent = {item.agent.agent_id: item for item in runtime_inputs}
    observer = by_agent[AGENT_A]

    assert [event.event_id for event in observer.events] == [
        MANDATORY_EVENT,
        PARTICIPANT_EVENT,
        SAME_LOCATION_EVENT,
    ]
    assert [summary.agent_id for summary in observer.nearby_agents] == [AGENT_B]
    assert observer.nearby_agents[0].active_status is True
    assert observer.nearby_agents[0].current_location_id == LOCATION_ONE
    assert observer.nearby_agents[0].mood == 0
    assert observer.nearby_agents[0].stress == 12
    assert observer.nearby_agents[0].fatigue == 2
    assert [relationship.target_agent_id for relationship in observer.relationships] == [
        AGENT_B
    ]
    assert observer.relationships[0].source_agent_id == AGENT_A
    assert observer.relationships[0].trust == 70
    assert observer.valid_agent_ids == [AGENT_B]
    assert observer.agent.active_status is True
    assert observer.agent.current_location_id == LOCATION_ONE
    assert observer.agent.state.model_dump()["mood"] == -1
    assert observer.agent.state.model_dump()["stress"] == 11
    assert observer.agent.state.model_dump()["fatigue"] == 1


def test_context_filters_hidden_ids_and_is_stably_sorted_without_mutation() -> None:
    runtime_inputs, values = assemble_visibility_inputs()
    agents, events, relationships, original = values
    observer = next(item for item in runtime_inputs if item.agent.agent_id == AGENT_A)
    payload = observer.model_dump(mode="json")
    serialized = str(payload)

    assert str(AGENT_C) not in serialized
    assert str(AGENT_D) not in serialized
    assert observer.events[0].participant_agent_ids == []
    assert observer.events[1].participant_agent_ids == [AGENT_A]
    assert [location for location in observer.valid_location_ids] == [
        LOCATION_ONE,
        LOCATION_TWO,
    ]
    assert (agents, events, relationships) == original


class FakeMessages:
    def __init__(self, parsed_output: object) -> None:
        self.parsed_output = parsed_output
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed_output=self.parsed_output)


def test_hidden_agent_ids_are_not_serialized_into_anthropic_request() -> None:
    runtime_inputs, _ = assemble_visibility_inputs()
    observer = next(item for item in runtime_inputs if item.agent.agent_id == AGENT_A)
    candidate = validate_intent_candidate(MockLLMClient().generate(observer), observer)
    messages = FakeMessages(candidate)
    client = AnthropicLLMClient(
        client=SimpleNamespace(messages=messages),
        model="test-model",
        max_tokens=100,
    )

    client.generate(observer)

    content = messages.calls[0]["messages"][0]["content"]
    assert str(AGENT_B) in content
    assert str(AGENT_C) not in content
    assert str(AGENT_D) not in content
