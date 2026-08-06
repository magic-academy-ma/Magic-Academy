from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine


class AgentType(str, Enum):
    STUDENT = "student"
    PROFESSOR = "professor"


@dataclass
class Agent:
    id: str
    agent_type: AgentType
    is_active: bool


@dataclass
class Event:
    id: str
    event_type: str
    participant_ids: set[str]


@dataclass
class WorldSnapshot:
    simulation_id: str
    current_tick: int
    data: dict[str, Any] = field(default_factory=dict)


class TickConflictError(Exception):
    """Tick이 이미 실행 중일 때 발생"""


class TickRollbackError(Exception):
    """Runtime 실패로 Tick 전체가 rollback될 때 발생"""


AgentRuntimeFn = Callable[..., Coroutine[Any, Any, dict]]


class TickEngine:
    def __init__(self, runtime: AgentRuntimeFn) -> None:
        self._runtime = runtime
        self._running = False

    async def run_tick(
        self,
        agents: list[Agent],
        event: Event,
        snapshot: WorldSnapshot,
    ) -> list[dict]:
        if self._running:
            raise TickConflictError("Tick is already running")

        self._running = True
        try:
            participants = self._select_participants(agents, event)
            results = []
            for agent in participants:
                result = await self._runtime(agent=agent, event=event, snapshot=snapshot)
                results.append(result)
            return results
        except TickConflictError:
            raise
        except Exception as exc:
            raise TickRollbackError("Tick rolled back due to runtime failure") from exc
        finally:
            self._running = False

    def _select_participants(self, agents: list[Agent], event: Event) -> list[Agent]:
        result = []
        for agent in agents:
            if not agent.is_active:
                continue
            # Professor는 해당 Event 참여자 목록에 있을 때만 실행
            if agent.agent_type == AgentType.PROFESSOR and agent.id not in event.participant_ids:
                continue
            # Student는 Event 참여자 목록에 있을 때만 실행
            if agent.agent_type == AgentType.STUDENT and agent.id not in event.participant_ids:
                continue
            result.append(agent)
        return result
