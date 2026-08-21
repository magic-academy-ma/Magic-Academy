"""Slice 4 Task 2 — 5-Student·조건부 Professor Tick orchestration.

Runtime·Persistence 통합(Task 1, Task 3)이 base에 병합되기 전에도 검증 가능한
Student/Professor 실행 대상 편성 로직을 다룬다. 통합 인수 테스트는
test_slice4_acceptance.py(Task 5)에서 다룬다.
"""

from uuid import UUID

import pytest

from app.domain.models import Agent
from app.services.runtime_target_selection import select_tick_participant_ids

SIMULATION_ID = UUID("40000000-0000-0000-0000-000000000001")
STUDENT_IDS = [UUID(f"00000000-0000-0000-0000-{index:012d}") for index in range(1, 6)]
USER_PERSONA_ID = STUDENT_IDS[0]
PROFESSOR_ID = UUID("00000000-0000-0000-0000-000000000010")
CLASS_EVENT_ID = UUID("20000000-0000-0000-0000-000000000001")


def make_agent(agent_id: UUID, agent_type: str) -> Agent:
    return Agent(
        id=agent_id,
        simulation_id=SIMULATION_ID,
        fixture_key=str(agent_id),
        fixture_version="test",
        agent_type=agent_type,
        name=str(agent_id),
        mbti_type="ISTJ",
    )


def make_students(*, user_persona_id: UUID | None = None) -> list[Agent]:
    return [
        make_agent(
            agent_id,
            "user_persona" if agent_id == user_persona_id else "student",
        )
        for agent_id in STUDENT_IDS
    ]


def make_professor(agent_id: UUID = PROFESSOR_ID) -> Agent:
    return make_agent(agent_id, "professor")


class TestDefaultStudentFiveOrchestration:
    def test_student_five_only_by_default(self) -> None:
        """일반 Tick에서는 Student 5명만 실행 대상이 된다."""
        agents = make_students() + [make_professor()]

        selected = select_tick_participant_ids(agents)

        assert selected == tuple(STUDENT_IDS)

    def test_user_persona_included_as_ordinary_student(self) -> None:
        """User Persona는 별도 Runtime 없이 기존 Student와 동일하게 편성된다."""
        agents = make_students(user_persona_id=USER_PERSONA_ID) + [make_professor()]

        selected = select_tick_participant_ids(agents)

        assert selected == tuple(STUDENT_IDS)


class TestConditionalProfessorOrchestration:
    def test_professor_added_when_event_participant(self) -> None:
        """Professor가 Event 참여자면 6명이 실행 대상이 된다."""
        agents = make_students() + [make_professor()]

        selected = select_tick_participant_ids(
            agents, event_participant_agent_ids=[PROFESSOR_ID]
        )

        assert selected == (*STUDENT_IDS, PROFESSOR_ID)

    def test_professor_added_when_schedule_requires(self) -> None:
        """Schedule 조건 충족 시 Event 미참여 Professor도 추가된다."""
        agents = make_students() + [make_professor()]

        selected = select_tick_participant_ids(
            agents, schedule_requires_professor=True
        )

        assert selected == (*STUDENT_IDS, PROFESSOR_ID)

    def test_professor_not_added_without_condition(self) -> None:
        """Event 참여자도 아니고 Schedule 조건도 없으면 Professor는 제외된다."""
        agents = make_students() + [make_professor()]

        selected = select_tick_participant_ids(agents)

        assert PROFESSOR_ID not in selected
        assert len(selected) == 5


class TestSelectionInvariants:
    def test_duplicate_agent_id_is_deduplicated(self) -> None:
        """같은 Agent.id가 중복 전달돼도 결과는 한 번만 포함한다."""
        agents = make_students() + make_students()

        selected = select_tick_participant_ids(agents)

        assert selected == tuple(STUDENT_IDS)

    def test_selection_order_follows_agent_snapshot_order(self) -> None:
        """반환 순서는 Agent 목록 순서를 그대로 보존한다."""
        reversed_students = list(reversed(make_students()))
        agents = reversed_students + [make_professor()]

        selected = select_tick_participant_ids(
            agents, schedule_requires_professor=True
        )

        assert selected == (*reversed(STUDENT_IDS), PROFESSOR_ID)

    def test_non_runtime_agent_type_is_excluded(self) -> None:
        """student/professor/user_persona 이외 agent_type은 실행 대상에서 제외된다."""
        agents = make_students() + [make_agent(PROFESSOR_ID, "unknown")]

        selected = select_tick_participant_ids(
            agents,
            event_participant_agent_ids=[PROFESSOR_ID],
            schedule_requires_professor=True,
        )

        assert selected == tuple(STUDENT_IDS)

    def test_empty_agents_returns_empty_selection(self) -> None:
        assert select_tick_participant_ids([]) == ()


# ── SimulationTickService 연동 뼈대 ────────────────────────────────────────
# 실제 DB(Agent/Event/EventParticipant) 연동 시나리오는 Task 1·3 결과를 반영해
# test_simulation_tick_runtime.py에서 검증한다. 아래는 통합 지점만 표시하는 뼈대다.


@pytest.mark.skip(
    reason="Task 1(Runtime batch)·Task 3(저장·rollback) 병합 후 실제 Runtime 연결"
)
def test_tick_calls_runtime_batch_exactly_once_per_tick() -> None:
    """Tick당 Runtime batch가 정확히 1회 호출된다."""


@pytest.mark.skip(
    reason="Task 1(Runtime batch)·Task 3(저장·rollback) 병합 후 실제 Runtime 연결"
)
def test_all_agents_receive_identical_world_snapshot() -> None:
    """5/6명 모든 Agent가 동일한 World Snapshot을 전달받는다."""
