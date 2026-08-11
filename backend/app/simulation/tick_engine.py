import asyncio
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


class TickRollbackError(Exception):
    """Runtime 실패로 Tick 전체가 rollback될 때 발생"""


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
        self._running: set[str] = set()  # 실행 중인 simulation_id 집합

    async def run_tick(
        self,
        agents: list[TickAgent],
        event: TickEvent,
        snapshot: WorldSnapshot,
    ) -> TickResult:
        simulation_id = snapshot.simulation_id
        if simulation_id in self._running:
            raise TickConflictError(f"Tick is already running for simulation {simulation_id}")

        self._running.add(simulation_id)
        try:
            participants = self._select_participants(agents, event)

            async def _run_one(agent: TickAgent) -> tuple[str, dict]:
                return agent.id, await self._runtime(agent=agent, event=event, snapshot=snapshot)

            pairs = await asyncio.gather(*[_run_one(a) for a in participants])
            runtime_outputs: dict[str, dict] = dict(pairs)

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
        except Exception as exc:
            raise TickRollbackError("Tick rolled back due to runtime failure") from exc
        finally:
            self._running.discard(simulation_id)

    def _select_participants(self, agents: list[TickAgent], event: TickEvent) -> list[TickAgent]:
        result = []
        for agent in agents:
            if not agent.is_active:
                continue
            if agent.id not in event.participant_ids:
                continue
            result.append(agent)
        return result
