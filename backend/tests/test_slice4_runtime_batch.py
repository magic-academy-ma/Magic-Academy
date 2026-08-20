from copy import deepcopy
from threading import Lock
from uuid import UUID

from app.services.runtime_orchestrator import RuntimeOrchestrator
from app.services.runtime_results import InMemoryRuntimeResultSink
from app.simulation.agent_runtime import (
    AgentRuntime,
    AgentRuntimeInput,
    MockLLMClient,
    RuntimeStatus,
)


STUDENT_IDS = [
    UUID(f"00000000-0000-0000-0000-{index:012d}") for index in range(1, 6)
]
LOCATION_ID = UUID("10000000-0000-0000-0000-000000000001")
CLASS_EVENT_ID = UUID("20000000-0000-0000-0000-000000000001")


def make_student_input(
    index: int,
    *,
    active: bool = True,
    user_persona: bool = False,
) -> AgentRuntimeInput:
    agent_id = STUDENT_IDS[index]
    return AgentRuntimeInput.model_validate(
        {
            "run_id": "slice-4-runtime-batch",
            "tick_number": 1,
            "block": "MORNING",
            "agent": {
                "agent_id": agent_id,
                "fixture_key": "user-persona-01"
                if user_persona
                else f"student-{index + 1:02d}",
                "agent_type": "student",
                "name": f"Student {index + 1}",
                "mbti": "INFP" if user_persona else "ISTJ",
                "big_five": {
                    "openness": 0,
                    "conscientiousness": 0,
                    "extraversion": 0,
                    "agreeableness": 0,
                    "emotional_stability": 0,
                },
                "state": {
                    "hunger": 0,
                    "fatigue": 0,
                    "stress": 0,
                    "satisfaction": 0,
                    "mood": 0,
                },
                "current_location_id": LOCATION_ID,
                "active_status": active,
            },
            "nearby_agents": [],
            "relationships": [],
            "memories": [],
            "events": [
                {
                    "event_id": CLASS_EVENT_ID,
                    "event_type": "class",
                    "location_id": LOCATION_ID,
                    "participant_agent_ids": [agent_id],
                }
            ],
            "schedule": {
                "event_id": CLASS_EVENT_ID,
                "schedule_type": "class",
                "is_mandatory": True,
                "location_id": LOCATION_ID,
                "start_tick": 1,
                "end_tick": 1,
            },
            "valid_agent_ids": STUDENT_IDS,
            "valid_location_ids": [LOCATION_ID],
        }
    )


class RecordingLLMClient:
    def __init__(self) -> None:
        self._lock = Lock()
        self.agent_ids: list[UUID] = []

    def generate(self, runtime_input: AgentRuntimeInput) -> object:
        with self._lock:
            self.agent_ids.append(runtime_input.agent.agent_id)
        mock_input = runtime_input.model_copy(
            update={
                "agent": runtime_input.agent.model_copy(
                    update={"fixture_key": "student-01"}
                )
            }
        )
        response = deepcopy(MockLLMClient().generate(mock_input))
        response["memory_candidates"][0]["content"] = (
            f"{runtime_input.agent.agent_id}의 수업 기억"
        )
        return response


def test_five_students_run_in_one_batch_with_agent_mapping() -> None:
    runtime_inputs = [make_student_input(index) for index in range(5)]
    client = RecordingLLMClient()

    batch = RuntimeOrchestrator(
        AgentRuntime(client), InMemoryRuntimeResultSink()
    ).run_batch(runtime_inputs)

    assert len(batch.results) == 5
    assert set(client.agent_ids) == set(STUDENT_IDS)
    assert [result.agent_id for result in batch.results] == STUDENT_IDS
    assert [
        result.intent.memory_candidates[0].content for result in batch.results
    ] == [f"{agent_id}의 수업 기억" for agent_id in STUDENT_IDS]


def test_user_persona_uses_same_student_runtime() -> None:
    runtime_inputs = [
        make_student_input(index, user_persona=index == 2) for index in range(5)
    ]
    client = RecordingLLMClient()

    batch = RuntimeOrchestrator(
        AgentRuntime(client), InMemoryRuntimeResultSink()
    ).run_batch(runtime_inputs)

    persona_input = runtime_inputs[2]
    persona_result = batch.results[2]
    assert persona_input.agent.fixture_key == "user-persona-01"
    assert persona_input.agent.agent_type == "student"
    assert persona_result.agent_id == persona_input.agent.agent_id
    assert persona_result.status is RuntimeStatus.PROPOSED
    assert persona_input.agent.agent_id in client.agent_ids


def test_inactive_student_is_skipped_without_llm_call() -> None:
    runtime_inputs = [
        make_student_input(index, active=index != 3) for index in range(5)
    ]
    client = RecordingLLMClient()

    batch = RuntimeOrchestrator(
        AgentRuntime(client), InMemoryRuntimeResultSink()
    ).run_batch(runtime_inputs)

    assert batch.results[3].status is RuntimeStatus.SKIPPED
    assert STUDENT_IDS[3] not in client.agent_ids
    assert len(client.agent_ids) == 4
