from app.core.config import Settings, get_settings
from app.simulation.agent_runtime import AgentRuntime
from app.simulation.anthropic_llm_client import AnthropicLLMClient


class RuntimeConfigurationError(RuntimeError):
    pass


def create_agent_runtime(settings: Settings) -> AgentRuntime:
    api_key = settings.anthropic_api_key
    if api_key is None or not api_key.strip():
        raise RuntimeConfigurationError(
            "ANTHROPIC_API_KEY must be configured for the Agent Runtime"
        )
    client = AnthropicLLMClient(
        api_key=api_key,
        model=settings.agent_runtime_model,
        max_tokens=settings.agent_runtime_max_tokens,
    )
    return AgentRuntime(client, model=settings.agent_runtime_model)


def get_agent_runtime() -> AgentRuntime:
    return create_agent_runtime(get_settings())
