import asyncio
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
from app.simulation.replay_guard import assert_not_replay
from app.simulation.instrumentation import increment_tick, increment_runtime


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
    runtime_outputs: dict[str, AgentRuntimeResult]
    retrieval_traces: dict[str, list[str]] = field(default_factory=dict)
    created_memory_ids: dict[str, list[str]] = field(default_factory=dict)


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
        self._running: set[str] = set()  # 실행 중인 simulation_id 집합

    async def run_tick(
        self,
        agents: list[TickAgent],
        event: TickEvent,
        snapshot: WorldSnapshot,
        *,
        schedule_requires_professor: bool = False,
    ) -> TickResult:
        simulation_id = snapshot.simulation_id
        if simulation_id in self._running:
            raise TickConflictError(f"Tick is already running for simulation {simulation_id}")

        self._running.add(simulation_id)
        try:
            participants = self._select_participants(
                agents, event, schedule_requires_professor=schedule_requires_professor
            )
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

            # Prevent runtime invocation and tick creation during replay, and instrument when allowed
            from app.simulation.replay_guard import assert_not_replay

            runtime_outputs: dict[str, AgentRuntimeResult] = {}
            if participants:
                # If replay mode is active, abort before creating or running ticks
                assert_not_replay("Runtime invocation attempted during replay")
                # instrument tick and runtime only when not in replay
                increment_tick()
                increment_runtime()
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

            # post-tick: Memory 저장
            created_memory_ids: dict[str, list[str]] = {}
            if self._memory_store:
                for agent_id, output in runtime_outputs.items():
                    for candidate in output.intent.memory_candidates:
                        memory_candidate = MemoryCandidateItem(
                            content=candidate.content,
                            memory_type=candidate.memory_type.value.lower(),
                            importance=candidate.importance * 10,
                        )
                        mem_id = await self._memory_store(
                            agent_id, event.id, memory_candidate, snapshot.current_tick
                        )
                        created_memory_ids.setdefault(agent_id, []).append(mem_id)

            return TickResult(
                status="completed",
                participant_ids=[a.id for a in participants],
                runtime_outputs=runtime_outputs,
                retrieval_traces=retrieval_traces,
                created_memory_ids=created_memory_ids,
            )
        except TickConflictError:
            raise
        except RuntimeExecutionError as exc:
            raise TickRollbackError("Tick rolled back due to runtime failure") from exc
        finally:
            self._running.discard(simulation_id)

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
