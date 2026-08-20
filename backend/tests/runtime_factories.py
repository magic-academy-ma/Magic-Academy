from uuid import NAMESPACE_URL, uuid5

from app.simulation.agent_runtime import AgentRuntimeResult


def make_runtime_result(
    agent_id: str,
    *,
    action_type: str = "STUDY",
    memory_candidate: object | None = None,
    status: str = "PROPOSED",
) -> AgentRuntimeResult:
    runtime_agent_id = uuid5(NAMESPACE_URL, agent_id)
    memory_candidates = []
    if memory_candidate is not None:
        memory_candidates.append(
            {
                "memory_type": str(getattr(memory_candidate, "memory_type")).upper(),
                "content": getattr(memory_candidate, "content"),
                "importance": getattr(memory_candidate, "importance"),
                "related_agent_ids": [],
                "related_event_id": None,
            }
        )

    return AgentRuntimeResult.model_validate(
        {
            "run_id": "tick-test-run",
            "tick_number": 0,
            "agent_id": runtime_agent_id,
            "status": status,
            "intent": {
                "action_type": action_type,
                "target_agent_id": None,
                "target_location_id": None,
                "related_event_id": None,
                "utterance": None,
                "motivation_summary": "테스트 Runtime 결과",
                "reaction": {"valence": "NEUTRAL"},
                "decision_explanation": {
                    "alternatives": [
                        {
                            "action_type": action_type,
                            "description": "테스트 행동",
                            "relative_priority": "HIGH",
                            "selected": True,
                        }
                    ],
                    "influencing_factors": [],
                },
                "memory_candidates": memory_candidates,
            },
            "retry_count": 0,
            "failure_reason": None,
            "model": "mock-llm",
            "prompt_version": "test",
            "idempotency_key": f"tick-test-run:0:{runtime_agent_id}",
        }
    )
