from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine


class AgentType(str, Enum):
    STUDENT = "student"
    PROFESSOR = "professor"


@dataclass
class TickAgent:
    id: str
    agent_type: AgentType
    is_active: bool


@dataclass
class TickEvent:
    id: str
    event_type: str
    participant_ids: set[str]


@dataclass
class WorldSnapshot:
    simulation_id: str
    current_tick: int
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class PolicyInput:
    """Runtime 결과를 Policy로 전달하는 단위"""
    agent_id: str
    event_id: str
    runtime_result: dict[str, Any]


@dataclass
class TickResult:
    """Tick 실행 결과"""
    status: str  # "completed" | "failed"
    participant_ids: list[str]
    runtime_outputs: dict[str, dict[str, Any]]


class TickConflictError(Exception):
    """Tick이 이미 실행 중일 때 발생"""


class RuntimeExecutionError(Exception):
    """Runtime 콜백의 예상된 실패 (타임아웃, LLM 오류 등)"""


class TickRollbackError(Exception):
    """RuntimeExecutionError로 Tick 전체가 rollback될 때 발생"""


AgentRuntimeFn = Callable[..., Coroutine[Any, Any, dict]]
PolicyFn = Callable[[list[PolicyInput]], Coroutine[Any, Any, None]]


class TickEngine:
    def __init__(
        self,
        runtime: AgentRuntimeFn,
        policy: PolicyFn | None = None,
    ) -> None:
        self._runtime = runtime
        self._policy = policy
        self._running = False

    async def run_tick(
        self,
        agents: list[TickAgent],
        event: TickEvent,
        snapshot: WorldSnapshot,
    ) -> TickResult:
        if self._running:
            raise TickConflictError("Tick is already running")

        self._running = True
        try:
            participants = self._select_participants(agents, event)
            runtime_outputs: dict[str, dict] = {}

            for agent in participants:
                result = await self._runtime(agent=agent, event=event, snapshot=snapshot)
                runtime_outputs[agent.id] = result

            if self._policy and runtime_outputs:
                policy_inputs = [
                    PolicyInput(
                        agent_id=agent_id,
                        event_id=event.id,
                        runtime_result=output,
                    )
                    for agent_id, output in runtime_outputs.items()
                ]
                await self._policy(policy_inputs)

            return TickResult(
                status="completed",
                participant_ids=[a.id for a in participants],
                runtime_outputs=runtime_outputs,
            )
        except TickConflictError:
            raise
        except RuntimeExecutionError as exc:
            raise TickRollbackError("Tick rolled back due to runtime failure") from exc
        finally:
            self._running = False

    def _select_participants(self, agents: list[TickAgent], event: TickEvent) -> list[TickAgent]:
        result = []
        for agent in agents:
            if not agent.is_active:
                continue
            if agent.id not in event.participant_ids:
                continue
            result.append(agent)
        return result
