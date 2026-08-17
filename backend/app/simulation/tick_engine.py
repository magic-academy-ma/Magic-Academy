from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine

from app.simulation.agent_runtime import (
    AgentReaction,
    AgentRuntimeResult,
    RelationshipSignal,
    RelationshipSignalType,
    SignalIntensity,
    StateSignal,
    StateSignalType,
)


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
    runtime_result: AgentRuntimeResult


@dataclass
class TickResult:
    """Tick 실행 결과"""
    status: str  # "completed" | "failed"
    participant_ids: list[str]
    runtime_outputs: dict[str, AgentRuntimeResult]


class TickConflictError(Exception):
    """Tick이 이미 실행 중일 때 발생"""


class RuntimeExecutionError(Exception):
    """Runtime 콜백의 예상된 실패 (타임아웃, LLM 오류 등)"""


class TickRollbackError(Exception):
    """RuntimeExecutionError로 Tick 전체가 rollback될 때 발생"""


# (agents, event, snapshot) → {agent_id: result} batch 방식 1회 호출
AgentRuntimeFn = Callable[
    [list[TickAgent], TickEvent, WorldSnapshot],
    Coroutine[Any, Any, dict[str, AgentRuntimeResult]],
]
PolicyFn = Callable[[list[PolicyInput]], Coroutine[Any, Any, None]]


class TickEngine:
    def __init__(
        self,
        runtime: AgentRuntimeFn,
        policy: PolicyFn | None = None,
    ) -> None:
        self._runtime = runtime
        self._policy = policy
        # TODO: PR #60 연결 후 DB 기반 상태 전이로 교체
        self._running = False

    async def run_tick(
        self,
        agents: list[TickAgent],
        event: TickEvent,
        snapshot: WorldSnapshot,
        *,
        schedule_requires_professor: bool = False,
    ) -> TickResult:
        if self._running:
            raise TickConflictError("Tick is already running")

        self._running = True
        try:
            participants = self._select_participants(
                agents, event, schedule_requires_professor=schedule_requires_professor
            )
            runtime_outputs: dict[str, AgentRuntimeResult] = {}

            if participants:
                runtime_outputs = await self._runtime(participants, event, snapshot)

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

    def _select_participants(
        self,
        agents: list[TickAgent],
        event: TickEvent,
        *,
        schedule_requires_professor: bool = False,
    ) -> list[TickAgent]:
        """
        실행 대상 선정. is_active 여부와 무관하게 선정하고 Runtime에 전달.
        비활성 Agent는 Runtime이 LLM 호출 없이 SKIPPED 결과를 반환.
        """
        result = []
        for agent in agents:
            if agent.agent_type == AgentType.STUDENT:
                result.append(agent)
            elif agent.agent_type == AgentType.PROFESSOR:
                if schedule_requires_professor or agent.id in event.participant_ids:
                    result.append(agent)
        return result
