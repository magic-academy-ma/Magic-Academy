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


# ─── Slice 3: Memory 타입 ──────────────────────────────────────────────────────

@dataclass
class MemoryItem:
    """MemoryRepository가 생산하고 Runtime에 전달되는 기억 단위."""
    id: str
    content: str
    memory_type: str  # "observation" | "conversation" | "reflection" | "plan"
    importance: int   # 0–100
    created_tick: int
    event_id: str | None


@dataclass
class MemoryCandidateItem:
    """Runtime이 반환하는 기억 후보 — id 없음, 저장은 Tick Engine 담당."""
    content: str
    memory_type: str  # "observation" | "conversation" | "reflection" | "plan"
    importance: int   # 0–100


# ─── Tick 결과 ─────────────────────────────────────────────────────────────────

@dataclass
class TickResult:
    """Tick 실행 결과"""
    status: str  # "completed" | "failed"
    participant_ids: list[str]
    runtime_outputs: dict[str, Any]
    retrieval_traces: dict[str, list[str]] = field(default_factory=dict)
    created_memory_ids: dict[str, list[str]] = field(default_factory=dict)


class TickConflictError(Exception):
    """Tick이 이미 실행 중일 때 발생"""


class TickRollbackError(Exception):
    """Runtime 실패로 Tick 전체가 rollback될 때 발생"""


AgentRuntimeFn = Callable[..., Coroutine[Any, Any, Any]]
PolicyFn = Callable[[list[PolicyInput]], Coroutine[Any, Any, None]]

MemoryRetrieverFn = Callable[
    [str, int, str],  # agent_id, current_tick, query_text
    Coroutine[Any, Any, list[MemoryItem]]
]

MemoryStoreFn = Callable[
    [str, "str | None", MemoryCandidateItem, int],  # agent_id, event_id, candidate, tick
    Coroutine[Any, Any, str]  # 저장된 memory_id
]


class TickEngine:
    def __init__(
        self,
        runtime: AgentRuntimeFn,
        policy: PolicyFn | None = None,
        memory_retriever: MemoryRetrieverFn | None = None,
        memory_store: MemoryStoreFn | None = None,
    ) -> None:
        self._runtime = runtime
        self._policy = policy
        self._memory_retriever = memory_retriever
        self._memory_store = memory_store
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

            # pre-tick: Memory 조회 및 snapshot 주입
            retrieval_traces: dict[str, list[str]] = {}
            if self._memory_retriever:
                all_memories: dict[str, list[MemoryItem]] = {}
                for agent in participants:
                    memories = await self._memory_retriever(
                        agent.id, snapshot.current_tick, event.event_type
                    )
                    all_memories[agent.id] = memories
                    retrieval_traces[agent.id] = [m.id for m in memories]
                snapshot.data["memories"] = all_memories

            runtime_outputs: dict[str, Any] = {}
            for agent in participants:
                result = await self._runtime(agent=agent, event=event, snapshot=snapshot)
                runtime_outputs[agent.id] = result

            if self._policy and runtime_outputs:
                policy_inputs = [
                    PolicyInput(
                        agent_id=agent_id,
                        event_id=event.id,
                        runtime_result=output if isinstance(output, dict) else vars(output),
                    )
                    for agent_id, output in runtime_outputs.items()
                ]
                await self._policy(policy_inputs)

            # post-tick: Memory 저장
            created_memory_ids: dict[str, list[str]] = {}
            if self._memory_store:
                for agent_id, output in runtime_outputs.items():
                    if hasattr(output, "memory_candidate") and output.memory_candidate is not None:
                        mem_id = await self._memory_store(
                            agent_id, event.id, output.memory_candidate, snapshot.current_tick
                        )
                        created_memory_ids[agent_id] = [mem_id]

            return TickResult(
                status="completed",
                participant_ids=[a.id for a in participants],
                runtime_outputs=runtime_outputs,
                retrieval_traces=retrieval_traces,
                created_memory_ids=created_memory_ids,
            )
        except TickConflictError:
            raise
        except Exception as exc:
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
