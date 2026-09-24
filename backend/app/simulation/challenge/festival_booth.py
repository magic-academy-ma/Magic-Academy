"""도전과제 2 — 축제 부스 운영하기.

docs/04-feature-specs/challenge-mode-festival-booth.md: 9개 Tick의 강제 Event,
R1 Tick3 부스 컨셉 선택, R2 Tick2 갈등 쌍 선정, R3 Tick2 돌발 대응 선택,
부스 성과 계산과 엔딩 판정을 순수 함수로 구성한다.

도전과제 1(controller.py)과 마찬가지로 EventMaster/AgentRuntime을 직접 호출하지
않는다 — Event·override를 조립하기만 하고, 실제 Tick 실행 연동은
round_driver.run_forced_event_round() 또는 별도 통합 작업의 몫이다.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from enum import StrEnum
from itertools import combinations
from uuid import UUID

from app.simulation.agent_runtime import ReactionValence
from app.simulation.challenge.controller import _build_forced_rest_response
from app.simulation.challenge.evaluation import (
    AFFECTION_AVG_THRESHOLD,
    PROJECT_PROGRESS_THRESHOLD,
    STRESS_LIMIT,
    ChallengeEnding,
)
from app.simulation.challenge.forced_events import (
    build_forced_festival,
    build_forced_group_project,
    build_forced_meeting,
)
from app.simulation.challenge.progress import (
    DEFAULT_PROGRESS_STEP,
    calculate_project_progress,
)
from app.simulation.event_master import Event, EventMaster, ImpactLevel

BUDGET_RUMOR_SUBTYPE = "BUDGET_RUMOR"

# 성과·엔딩 상수 — 도전과제 1 값을 초기값으로 재사용하되 따로 조정할 수 있게
# 도전과제 2 전용 이름으로 분리한다 (§4.8/§4.9). 모두 플레이테스트 후 조정 대상.
BOOTH_PERFORMANCE_STEP = DEFAULT_PROGRESS_STEP  # 임시값 — 집계 건수가 많아 조정 필요
BOOTH_PERFORMANCE_THRESHOLD = PROJECT_PROGRESS_THRESHOLD  # 임시값
FESTIVAL_AFFECTION_AVG_THRESHOLD = AFFECTION_AVG_THRESHOLD  # 임시값
FESTIVAL_STRESS_LIMIT = STRESS_LIMIT  # 임시값

# 부스 성과 집계 대상 Event 타입 (§4.8). R1 MEETING, R3 RANDOM_INCIDENT,
# R3 T3 긴급 회의 MEETING은 집계하지 않는다.
BOOTH_PERFORMANCE_EVENT_TYPES: frozenset[str] = frozenset({"GROUP_PROJECT", "FESTIVAL"})


class BoothConcept(StrEnum):
    FOOD = "FOOD"
    EXPERIENCE = "EXPERIENCE"
    EXHIBITION = "EXHIBITION"


class IncidentResponse(StrEnum):
    EMERGENCY_MEETING = "EMERGENCY_MEETING"
    ROTATE_REST = "ROTATE_REST"
    PUSH_THROUGH = "PUSH_THROUGH"


CONCEPT_LABELS: dict[BoothConcept, str] = {
    BoothConcept.FOOD: "먹거리 부스",
    BoothConcept.EXPERIENCE: "체험형 부스",
    BoothConcept.EXHIBITION: "전시형 부스",
}

# 컨셉은 수치를 직접 바꾸지 않고 R3 T2 돌발 subtype만 결정한다 (§4.4, 확정적 매핑).
CONCEPT_INCIDENT_SUBTYPES: dict[BoothConcept, str] = {
    BoothConcept.FOOD: "INGREDIENT_SHORTAGE",
    BoothConcept.EXPERIENCE: "CUSTOMER_RUSH",
    BoothConcept.EXHIBITION: "RIVAL_BOOTH_ISSUE",
}


def _concept_description(concept: BoothConcept) -> str:
    return f"동아리 부스 컨셉: {CONCEPT_LABELS[concept]}"


# ─── Round 1 — 부스 기획 ─────────────────────────────────────────────────────


def build_club_meeting_event(
    *, tick: int, agent_ids: Sequence[str], location_id: str
) -> Event:
    """R1 T1 — 축제 부스 기획 동아리 회의."""
    return build_forced_meeting(
        tick=tick,
        participant_agent_ids=agent_ids,
        location_id=location_id,
        impact_level=ImpactLevel.MEDIUM,
        title="동아리 회의 (축제 부스 기획)",
    )


def build_budget_rumor_event(
    *, tick: int, agent_ids: Sequence[str], location_id: str
) -> Event:
    """R1 T2 ★ — 예산·자원 부족 소문."""
    return EventMaster().build_random_incident(
        tick=tick,
        event_subtype=BUDGET_RUMOR_SUBTYPE,
        participant_agent_ids=agent_ids,
        location_id=location_id,
        title="예산·자원 부족 소문",
    )


def build_concept_meeting_event(
    *, tick: int, concept: BoothConcept, agent_ids: Sequence[str], location_id: str
) -> Event:
    """R1 T3 — 사용자가 고른 컨셉으로 최종 결정하는 회의."""
    return build_forced_meeting(
        tick=tick,
        participant_agent_ids=agent_ids,
        location_id=location_id,
        impact_level=ImpactLevel.MEDIUM,
        title=f"부스 컨셉 확정 회의 ({CONCEPT_LABELS[concept]})",
        description=_concept_description(concept),
    )


# ─── Round 2 — 준비 및 역할 분담 ─────────────────────────────────────────────


def build_preparation_event(
    *, tick: int, concept: BoothConcept, agent_ids: Sequence[str], location_id: str
) -> Event:
    """R2 T1 — 재료 조달·디자인 작업."""
    return build_forced_group_project(
        tick=tick,
        participant_agent_ids=agent_ids,
        location_id=location_id,
        impact_level=ImpactLevel.MEDIUM,
        title="부스 준비 (재료 조달·디자인)",
        description=_concept_description(concept),
    )


def select_conflict_pair(
    *,
    agent_ids: Sequence[str],
    directional_affections: Mapping[tuple[str, str], int],
    rng: random.Random,
) -> tuple[str, str]:
    """R2 T2 갈등 쌍 (§4.5): R1 종료 시점 양방향 affection 합이 가장 낮은 쌍.

    동률이면 동률 쌍 중에서 ``rng``로 고른다 — replay 재현성을 위해 호출자는
    run 단위 시드로 만든 Random을 넘겨야 한다. 기록이 없는 edge는 0으로 본다.
    """
    pairs = list(combinations(sorted(dict.fromkeys(agent_ids)), 2))
    if not pairs:
        raise ValueError("select_conflict_pair requires at least 2 agents")

    def mutual(pair: tuple[str, str]) -> int:
        a, b = pair
        return directional_affections.get((a, b), 0) + directional_affections.get((b, a), 0)

    lowest = min(mutual(pair) for pair in pairs)
    return rng.choice([pair for pair in pairs if mutual(pair) == lowest])


def build_role_conflict_event(
    *,
    tick: int,
    concept: BoothConcept,
    conflict_pair: tuple[str, str],
    location_id: str,
) -> Event:
    """R2 T2 ★ — 갈등 쌍 2명만 참여하는 역할 배분 GROUP_PROJECT (Reflection 대상)."""
    return build_forced_group_project(
        tick=tick,
        participant_agent_ids=conflict_pair,
        location_id=location_id,
        impact_level=ImpactLevel.HIGH,
        title="역할 배분 갈등",
        description=_concept_description(concept),
    )


def build_rehearsal_event(
    *, tick: int, concept: BoothConcept, agent_ids: Sequence[str], location_id: str
) -> Event:
    """R2 T3 — 리허설·사전 점검."""
    return build_forced_group_project(
        tick=tick,
        participant_agent_ids=agent_ids,
        location_id=location_id,
        impact_level=ImpactLevel.MEDIUM,
        title="리허설·사전 점검",
        description=_concept_description(concept),
    )


# ─── Round 3 — 축제 당일 운영 및 평가 ────────────────────────────────────────


def build_opening_event(
    *, tick: int, concept: BoothConcept, agent_ids: Sequence[str], location_id: str
) -> Event:
    """R3 T1 — 개장 준비·홍보."""
    return build_forced_festival(
        tick=tick,
        participant_agent_ids=agent_ids,
        location_id=location_id,
        title="부스 개장·홍보",
        description=_concept_description(concept),
    )


def build_festival_incident_event(
    *, tick: int, concept: BoothConcept, agent_ids: Sequence[str], location_id: str
) -> Event:
    """R3 T2 ★ — 컨셉에 매핑된 돌발 상황 (§4.4)."""
    return EventMaster().build_random_incident(
        tick=tick,
        event_subtype=CONCEPT_INCIDENT_SUBTYPES[concept],
        participant_agent_ids=agent_ids,
        location_id=location_id,
        title="축제 당일 돌발 상황",
        description=_concept_description(concept),
    )


def select_rest_target(agent_states: Mapping[str, tuple[int, int]]) -> str:
    """ROTATE_REST 대상: (stress, fatigue) 합이 가장 높은 Agent. 동률은 agent_id 순."""
    if not agent_states:
        raise ValueError("select_rest_target requires at least 1 agent")
    return min(agent_states, key=lambda agent_id: (-sum(agent_states[agent_id]), agent_id))


def plan_final_tick_events(
    *,
    tick: int,
    choice: IncidentResponse,
    concept: BoothConcept,
    agent_ids: Sequence[str],
    location_id: str,
    rest_target_agent_id: str | None = None,
) -> list[Event]:
    """R3 T3 — 돌발 대응 선택에 따른 마지막 Tick Event (§4.6).

    EMERGENCY_MEETING은 FESTIVAL 대신 5명 MEETING(성과 집계 없음), ROTATE_REST는
    rest_target_agent_id를 뺀 FESTIVAL, PUSH_THROUGH는 5명 FESTIVAL.
    """
    if choice == IncidentResponse.EMERGENCY_MEETING:
        return [
            build_forced_meeting(
                tick=tick,
                participant_agent_ids=agent_ids,
                location_id=location_id,
                title="긴급 대책 회의",
                description=_concept_description(concept),
            )
        ]
    if choice == IncidentResponse.ROTATE_REST:
        if rest_target_agent_id is None:
            raise ValueError("ROTATE_REST requires rest_target_agent_id")
        participants = [agent_id for agent_id in agent_ids if agent_id != rest_target_agent_id]
    elif choice == IncidentResponse.PUSH_THROUGH:
        participants = list(agent_ids)
    else:
        raise ValueError(f"unknown IncidentResponse: {choice}")
    return [
        build_forced_festival(
            tick=tick,
            participant_agent_ids=participants,
            location_id=location_id,
            title="부스 운영 마무리",
            description=_concept_description(concept),
        )
    ]


def plan_final_tick_llm_overrides(
    *, tick: int, choice: IncidentResponse, rest_target_agent_id: UUID | None = None
) -> dict[tuple[int, UUID], object]:
    """ROTATE_REST일 때만 대상 Agent의 R3 T3 행동을 REST로 강제한다 (도전과제 1 REST 재사용)."""
    if choice == IncidentResponse.ROTATE_REST:
        if rest_target_agent_id is None:
            raise ValueError("ROTATE_REST requires rest_target_agent_id")
        return {(tick, rest_target_agent_id): _build_forced_rest_response}
    return {}


# ─── 성과·엔딩 ───────────────────────────────────────────────────────────────


def calculate_booth_performance(
    participant_valences: Sequence[tuple[str, ReactionValence]],
    *,
    step: int = BOOTH_PERFORMANCE_STEP,
) -> int:
    """(event_type, reaction.valence) 목록 중 GROUP_PROJECT·FESTIVAL만 집계한다 (§4.8)."""
    return calculate_project_progress(
        [
            valence
            for event_type, valence in participant_valences
            if event_type.upper() in BOOTH_PERFORMANCE_EVENT_TYPES
        ],
        step=step,
    )


def evaluate_festival_ending(
    *,
    booth_performance: int,
    directional_affections: Sequence[int],
    agent_stress_levels: Sequence[int],
    initial_satisfaction_levels: Sequence[int],
    final_satisfaction_levels: Sequence[int],
) -> ChallengeEnding:
    """§4.9: 성과 미달·번아웃이면 BAD, 관계·만족도(시작 대비 평균 상승)까지
    충족하면 PERFECT, 그 외 NORMAL."""
    performance_ok = booth_performance >= BOOTH_PERFORMANCE_THRESHOLD
    stress_ok = all(stress < FESTIVAL_STRESS_LIMIT for stress in agent_stress_levels)
    if not performance_ok or not stress_ok:
        return ChallengeEnding.BAD

    relationship_ok = bool(directional_affections) and (
        sum(directional_affections) / len(directional_affections)
        >= FESTIVAL_AFFECTION_AVG_THRESHOLD
    )
    satisfaction_ok = (
        bool(initial_satisfaction_levels)
        and bool(final_satisfaction_levels)
        and sum(final_satisfaction_levels) / len(final_satisfaction_levels)
        > sum(initial_satisfaction_levels) / len(initial_satisfaction_levels)
    )
    if relationship_ok and satisfaction_ok:
        return ChallengeEnding.PERFECT
    return ChallengeEnding.NORMAL
