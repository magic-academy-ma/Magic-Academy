"""챌린지 3 — 동아리를 폐부에서 구하기 순수 함수 레이어."""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from app.simulation.challenge.forced_events import (
    build_forced_festival,
    build_forced_group_project,
    build_forced_meeting,
)
from app.simulation.event_master import Event, EventMaster, ImpactLevel

CLUB_MIN_MEMBERS = 3
CLUB_REPUTATION_THRESHOLD = 60
CLUB_AFFECTION_AVG_THRESHOLD = 0
CLUB_INITIAL_MEMBERS = 2
CLUB_INITIAL_REPUTATION = 40


class InternalConflictChoice(StrEnum):
    MEDIATE = "MEDIATE"
    REASSIGN_ROLES = "REASSIGN_ROLES"
    OBSERVE = "OBSERVE"


class RecruitmentStrategy(StrEnum):
    PERFORMANCE_PROMOTION = "PERFORMANCE_PROMOTION"
    EXPERIENCE_EVENT = "EXPERIENCE_EVENT"
    PROFESSOR_REFERRAL = "PROFESSOR_REFERRAL"


class FinalStrategy(StrEnum):
    PERFORMANCE_FOCUS = "PERFORMANCE_FOCUS"
    RELATIONSHIP_RECOVERY = "RELATIONSHIP_RECOVERY"
    SAFE_OPERATION = "SAFE_OPERATION"


class ClubEnding(StrEnum):
    REVIVAL = "REVIVAL"
    CONDITIONAL = "CONDITIONAL"
    ONE_MEMBER = "ONE_MEMBER"
    CLOSED = "CLOSED"


RECRUITMENT_EFFECTS: dict[RecruitmentStrategy, tuple[int, int]] = {
    RecruitmentStrategy.PERFORMANCE_PROMOTION: (1, 15),
    RecruitmentStrategy.EXPERIENCE_EVENT: (2, 10),
    RecruitmentStrategy.PROFESSOR_REFERRAL: (1, 20),
}

FINAL_REPUTATION_EFFECTS: dict[FinalStrategy, int] = {
    FinalStrategy.PERFORMANCE_FOCUS: 20,
    FinalStrategy.RELATIONSHIP_RECOVERY: 10,
    FinalStrategy.SAFE_OPERATION: 15,
}


RECRUITMENT_LABELS: dict[RecruitmentStrategy, str] = {
    RecruitmentStrategy.PERFORMANCE_PROMOTION: "공연 홍보",
    RecruitmentStrategy.EXPERIENCE_EVENT: "체험 행사",
    RecruitmentStrategy.PROFESSOR_REFERRAL: "교수 추천 요청",
}


def apply_internal_conflict_choice(
    *, member_count: int, reputation: int, choice: InternalConflictChoice, negative_reaction: bool
) -> tuple[int, int]:
    if choice == InternalConflictChoice.REASSIGN_ROLES:
        reputation += 5
    elif choice == InternalConflictChoice.OBSERVE and negative_reaction:
        member_count -= 1
    return max(0, member_count), max(0, min(100, reputation))


def apply_recruitment_strategy(
    *, member_count: int, reputation: int, strategy: RecruitmentStrategy
) -> tuple[int, int]:
    member_delta, reputation_delta = RECRUITMENT_EFFECTS[strategy]
    return member_count + member_delta, min(100, reputation + reputation_delta)


def apply_final_strategy(*, reputation: int, strategy: FinalStrategy) -> int:
    return min(100, reputation + FINAL_REPUTATION_EFFECTS[strategy])


def build_closure_warning_event(
    *, tick: int, member_ids: Sequence[str], location_id: str
) -> Event:
    """R1 T1 — 전 부원에게 폐부 경고를 전달한다."""
    return EventMaster().build_random_incident(
        tick=tick,
        event_subtype="CLUB_CLOSURE_WARNING",
        participant_agent_ids=member_ids,
        location_id=location_id,
        title="동아리 폐부 경고",
        description="회원 수와 평판이 기준에 미달해 최종 심사가 예정되었다.",
    )


def plan_internal_conflict_events(
    *,
    tick: int,
    choice: InternalConflictChoice,
    conflict_pair: tuple[str, str],
    other_member_ids: Sequence[str],
    location_id: str,
) -> list[Event]:
    """R1 T3 — 내부 갈등에 대한 사용자 개입을 Event로 변환한다."""
    agent_a_id, agent_b_id = conflict_pair
    if choice == InternalConflictChoice.MEDIATE:
        return [
            build_forced_meeting(
                tick=tick,
                participant_agent_ids=conflict_pair,
                location_id=location_id,
                title="동아리 내부 갈등 중재",
            )
        ]
    if choice == InternalConflictChoice.REASSIGN_ROLES:
        return [
            build_forced_group_project(
                tick=tick,
                participant_agent_ids=[agent_a_id, agent_b_id, *other_member_ids],
                location_id=location_id,
                title="동아리 역할 재배정",
            )
        ]
    if choice == InternalConflictChoice.OBSERVE:
        return []
    raise ValueError(f"unknown InternalConflictChoice: {choice}")


def plan_recruitment_event(
    *,
    tick: int,
    strategy: RecruitmentStrategy,
    member_ids: Sequence[str],
    location_id: str,
    professor_id: str | None = None,
) -> Event:
    """R2 T3 — 선택한 모집 전략을 하나의 강제 Event로 계획한다."""
    label = RECRUITMENT_LABELS[strategy]
    description = f"신입 회원 모집 전략: {strategy.value}"
    if strategy == RecruitmentStrategy.PERFORMANCE_PROMOTION:
        return build_forced_festival(
            tick=tick,
            participant_agent_ids=member_ids,
            location_id=location_id,
            title=f"동아리 {label}",
            description=description,
        )
    participants = list(member_ids)
    if strategy == RecruitmentStrategy.PROFESSOR_REFERRAL:
        if professor_id is None:
            raise ValueError("PROFESSOR_REFERRAL requires professor_id")
        participants.append(professor_id)
    return build_forced_meeting(
        tick=tick,
        participant_agent_ids=participants,
        location_id=location_id,
        impact_level=ImpactLevel.MEDIUM,
        title=f"동아리 {label}",
        description=description,
    )


def plan_final_event(
    *,
    tick: int,
    strategy: FinalStrategy,
    member_ids: Sequence[str],
    location_id: str,
) -> Event:
    """R3 T3 — 최종 행사 전략에 맞는 Event를 계획한다."""
    description = f"최종 행사 전략: {strategy.value}"
    if strategy == FinalStrategy.RELATIONSHIP_RECOVERY:
        return build_forced_meeting(
            tick=tick,
            participant_agent_ids=member_ids,
            location_id=location_id,
            title="최종 심사 전 관계 회복 회의",
            description=description,
        )
    impact_level = (
        ImpactLevel.HIGH
        if strategy == FinalStrategy.PERFORMANCE_FOCUS
        else ImpactLevel.MEDIUM
    )
    return build_forced_festival(
        tick=tick,
        participant_agent_ids=member_ids,
        location_id=location_id,
        impact_level=impact_level,
        title=(
            "동아리 성과 발표"
            if strategy == FinalStrategy.PERFORMANCE_FOCUS
            else "동아리 안전 운영 행사"
        ),
        description=description,
    )


def evaluate_club_ending(
    *,
    member_count: int,
    reputation: int,
    directional_affections: Sequence[int],
) -> ClubEnding:
    """회원 수·평판·부원 관계를 기준으로 네 가지 엔딩을 판정한다."""
    if member_count == 1:
        return ClubEnding.ONE_MEMBER
    if member_count < CLUB_MIN_MEMBERS:
        return ClubEnding.CLOSED

    relationship_ok = bool(directional_affections) and (
        sum(directional_affections) / len(directional_affections)
        >= CLUB_AFFECTION_AVG_THRESHOLD
    )
    if reputation >= CLUB_REPUTATION_THRESHOLD and relationship_ok:
        return ClubEnding.REVIVAL
    return ClubEnding.CONDITIONAL
