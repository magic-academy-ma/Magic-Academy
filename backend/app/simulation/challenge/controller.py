"""도전과제 모드 — Round 1~3 진행 컨트롤러.

docs/04-feature-specs/challenge-mode-team-revival.md §4: Round1 갈등 트리거 +
사용자 선택지별 강제 조치, Round2 과로 대응 선택지, Round3 돌발 사건 강제
주입을 순수 함수로 구성한다. 이 모듈은 EventMaster/AgentRuntime을 직접 호출하지
않는다 — build_forced_*()/ChallengeLLMOverride가 쓸 Event·override를 조립하기만
하고, 실제 Tick 실행 연동(Tick Orchestrator와의 배선)은 별도 통합 작업의 몫이다.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from uuid import UUID

from app.simulation.agent_runtime import AgentRuntimeInput
from app.simulation.challenge.forced_events import (
    build_forced_group_project,
    build_forced_meeting,
)
from app.simulation.event_master import Event, EventMaster

ROUND3_INCIDENT_SUBTYPES: tuple[str, ...] = (
    "PRESENTATION_ERROR",
    "MEMBER_DROPOUT",
    "SUPPLY_MISSING",
)


class Round1Choice(StrEnum):
    REASSIGN_ROLES = "REASSIGN_ROLES"
    FORCE_MEETING = "FORCE_MEETING"
    LET_AGENTS_RESOLVE = "LET_AGENTS_RESOLVE"


class Round2Choice(StrEnum):
    LET_REST = "LET_REST"
    REASSIGN_WORKLOAD = "REASSIGN_WORKLOAD"
    PUSH_THROUGH = "PUSH_THROUGH"


# ─── Round 1 — 팀 내 갈등 ───────────────────────────────────────────────────


def build_round1_trigger_event(
    *, tick: int, agent_a_id: str, agent_b_id: str, location_id: str
) -> Event:
    """Round1 Day1 첫 Tick에 선택지와 무관하게 항상 강제 주입되는 A·B 충돌 GROUP_PROJECT."""
    return build_forced_group_project(
        tick=tick,
        participant_agent_ids=[agent_a_id, agent_b_id],
        location_id=location_id,
        title="조별 과제 (A·B 충돌)",
    )


def plan_round1_choice_events(
    *,
    tick: int,
    choice: Round1Choice,
    agent_a_id: str,
    agent_b_id: str,
    agent_c_id: str,
    agent_d_id: str,
    location_id: str,
) -> list[Event]:
    """선택지에 따른 추가 강제 Event. LET_AGENTS_RESOLVE는 추가 주입이 없다."""
    if choice == Round1Choice.REASSIGN_ROLES:
        return [
            build_forced_group_project(
                tick=tick,
                participant_agent_ids=[agent_a_id, agent_c_id],
                location_id=location_id,
                title="조별 과제 (재배정)",
            ),
            build_forced_group_project(
                tick=tick,
                participant_agent_ids=[agent_b_id, agent_d_id],
                location_id=location_id,
                title="조별 과제 (재배정)",
            ),
        ]
    if choice == Round1Choice.FORCE_MEETING:
        return [
            build_forced_meeting(
                tick=tick,
                participant_agent_ids=[agent_a_id, agent_b_id],
                location_id=location_id,
            )
        ]
    if choice == Round1Choice.LET_AGENTS_RESOLVE:
        return []
    raise ValueError(f"unknown Round1Choice: {choice}")


# ─── Round 2 — 과로 문제 ────────────────────────────────────────────────────


def _build_forced_rest_response(runtime_input: AgentRuntimeInput) -> dict:
    return {
        "action_type": "REST",
        "target_agent_id": None,
        "target_location_id": str(runtime_input.agent.current_location_id),
        "related_event_id": None,
        "utterance": None,
        "motivation_summary": "도전과제 개입으로 강제 휴식한다.",
        "reaction": {
            "valence": "NEUTRAL",
            "relationship_signals": [],
            "state_signals": [{"signal_type": "FATIGUE_DOWN", "intensity": "HIGH"}],
        },
        "decision_explanation": {
            "alternatives": [
                {
                    "action_type": "REST",
                    "description": "사용자 개입으로 강제 휴식",
                    "relative_priority": "HIGH",
                    "selected": True,
                }
            ],
            "influencing_factors": [],
        },
        "memory_candidates": [],
    }


def plan_round2_llm_overrides(
    *, tick: int, target_agent_id: UUID, choice: Round2Choice
) -> dict[tuple[int, UUID], object]:
    """LET_REST를 고르면 target_agent_id의 이번 Tick 행동만 REST로 강제한다.
    나머지 선택지는 오버라이드 없음 — Agent Runtime이 그대로 자율 판단한다."""
    if choice == Round2Choice.LET_REST:
        return {(tick, target_agent_id): _build_forced_rest_response}
    return {}


def plan_round2_group_project_participants(
    *,
    original_participants: Sequence[str],
    target_agent_id: str,
    replacement_agent_id: str,
    choice: Round2Choice,
) -> tuple[str, ...]:
    """REASSIGN_WORKLOAD를 고르면 target_agent_id를 participants에서 빼고
    replacement_agent_id로 교체한다. 나머지 선택지는 원래 목록을 그대로 유지한다."""
    if choice == Round2Choice.REASSIGN_WORKLOAD:
        return tuple(
            replacement_agent_id if agent_id == target_agent_id else agent_id
            for agent_id in original_participants
        )
    return tuple(original_participants)


# ─── Round 3 — 마감 직전 위기 ────────────────────────────────────────────────


def build_round3_incident_event(
    *,
    tick: int,
    event_subtype: str,
    participant_agent_ids: Sequence[str],
    location_id: str,
) -> Event:
    """등록된 3종 RANDOM_INCIDENT subtype 중 하나를 강제 주입한다.
    선택지 없이 자율 반응만으로 진행되는 Round이므로 subtype 선택 자체는
    호출자(캠페인 스크립트) 책임이다 — 여기서는 등록된 값인지만 검증한다."""
    if event_subtype not in ROUND3_INCIDENT_SUBTYPES:
        raise ValueError(
            f"event_subtype must be one of {ROUND3_INCIDENT_SUBTYPES}, got {event_subtype!r}"
        )
    return EventMaster().build_random_incident(
        tick=tick,
        event_subtype=event_subtype,
        participant_agent_ids=participant_agent_ids,
        location_id=location_id,
        title="마감 직전 위기",
    )
