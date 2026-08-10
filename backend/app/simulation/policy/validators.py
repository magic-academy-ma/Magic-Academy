from app.simulation.policy.types import AgentRuntimeResult


def validate_runtime_result(
    result: AgentRuntimeResult,
    valid_agent_ids: set[str],
) -> list[str]:
    """AgentRuntimeResult의 유효성을 검증하고 에러 메시지 목록을 반환한다. 빈 목록이면 유효."""
    errors: list[str] = []

    if result.reaction is None:
        return errors

    for signal in result.reaction.relationship_signals:
        if signal.target_agent_id == result.agent_id:
            errors.append(f"self-target relationship signal: agent {result.agent_id} → self")
        elif signal.target_agent_id not in valid_agent_ids:
            errors.append(f"invalid target agent_id: {signal.target_agent_id}")

    return errors
