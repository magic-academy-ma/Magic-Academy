from collections.abc import Iterable, Sequence
from uuid import UUID

from app.domain.models import Agent
from app.simulation.agent_runtime import AgentContext

# User Persona는 별도 Runtime 없이 기존 Student와 동일하게 편성된다 (Slice 4 Task 0 계약).
STUDENT_AGENT_TYPES = frozenset({"student", "user_persona"})
PROFESSOR_AGENT_TYPE = "professor"


def select_tick_participant_ids(
    agents: Sequence[Agent],
    *,
    event_participant_agent_ids: Iterable[UUID] = (),
    schedule_requires_professor: bool = False,
) -> tuple[UUID, ...]:
    """Tick 실행 대상 Agent.id를 편성한다.

    Student(User Persona 포함)는 항상 포함하고, Professor는 Event 참여자이거나
    Schedule 조건을 충족할 때만 추가한다. 중복 id는 제거하며, 각 그룹 내
    상대 순서는 agents 순서를 보존하되 canonical 순서는 Student 전원 →
    조건부 Professor로 고정한다 (Slice 4 Task 0 계약, Agent 조회 순서인
    fixture_key 정렬 등에 의존하지 않는다).
    """
    participant_event_id_set = set(event_participant_agent_ids)
    seen_ids: set[UUID] = set()
    student_ids: list[UUID] = []
    professor_ids: list[UUID] = []
    for agent in agents:
        if agent.id in seen_ids:
            continue
        if agent.agent_type in STUDENT_AGENT_TYPES:
            seen_ids.add(agent.id)
            student_ids.append(agent.id)
        elif agent.agent_type == PROFESSOR_AGENT_TYPE and not professor_ids:
            if schedule_requires_professor or agent.id in participant_event_id_set:
                seen_ids.add(agent.id)
                professor_ids.append(agent.id)
    return tuple(student_ids) + tuple(professor_ids)


class RuntimeTargetSelector:
    def select(
        self,
        agent_candidates: Sequence[AgentContext],
        *,
        preselected_agent_ids: Sequence[UUID],
    ) -> tuple[AgentContext, ...]:
        candidates_by_id: dict[UUID, AgentContext] = {}
        for candidate in agent_candidates:
            existing = candidates_by_id.get(candidate.agent_id)
            if existing is not None and existing != candidate:
                raise ValueError(f"conflicting agent candidates for {candidate.agent_id}")
            candidates_by_id[candidate.agent_id] = candidate

        if len(set(preselected_agent_ids)) != len(preselected_agent_ids):
            raise ValueError("preselected_agent_ids must not contain duplicates")
        missing_ids = [
            agent_id for agent_id in preselected_agent_ids if agent_id not in candidates_by_id
        ]
        if missing_ids:
            raise ValueError(f"preselected Agent {missing_ids[0]} is not a runtime candidate")
        return tuple(candidates_by_id[agent_id] for agent_id in preselected_agent_ids)
