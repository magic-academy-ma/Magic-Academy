"""스토리모드 CHAPTER 4 — 축제 부스 운영하기.

docs/04-feature-specs/challenge-mode-festival-booth.md: R1 기획·준비 / R2~R3 운영의
9 Tick 강제 Event, 라운드마다 1번씩인 개입 ①~③의 조치, 부스 담당 인원 기록,
부스 성과 계산, 엔딩·챕터 결과 기록·업적 판정을 순수 함수로 구성한다.

CHAPTER 2(controller.py)와 같은 공통 실행 모델을 따른다 — 컨트롤러는 Agent 행동을
정하지 않고 Event 주입·정보 주입(ChallengeLLMOverride가 쓸 injections)·일정 변경
(round_driver에 넘길 non_mandatory_agent_ids)만 만든다. EventMaster/AgentRuntime을
직접 호출하지 않으며, 실제 Tick 실행 연동은 별도 통합 작업의 몫이다.
"""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import combinations

from app.simulation.agent_runtime import ActionType, ReactionValence
from app.simulation.challenge.evaluation import (
    AFFECTION_AVG_THRESHOLD,
    PROJECT_PROGRESS_THRESHOLD,
)
from app.simulation.challenge.forced_events import (
    build_forced_festival,
    build_forced_group_project,
    build_forced_meeting,
)
from app.simulation.challenge.llm_override import (
    Injections,
    build_injected_memory,
    merge_injections,
)
from app.simulation.challenge.progress import (
    DEFAULT_PROGRESS_STEP,
    calculate_project_progress,
)
from app.simulation.challenge.record import (
    WATCH,
    ChapterGrade,
    ChapterRecord,
    InterventionRecord,
)
from app.simulation.event_master import Event, EventMaster, ImpactLevel

# 성과·엔딩 상수 (§4.8/§4.10). 모두 플레이테스트 후 조정 대상인 임시값이다.
BOOTH_PERFORMANCE_STEP = DEFAULT_PROGRESS_STEP  # 임시값 — 집계 건수가 많아 조정 필요
BOOTH_PERFORMANCE_THRESHOLD = PROJECT_PROGRESS_THRESHOLD  # 임시값
BOOTH_VACANCY_PENALTY = BOOTH_PERFORMANCE_STEP  # 임시값 — 공백 Tick 1회당 성과 ↓
BOOTH_VACANCY_LIMIT = 1  # 임시값 — 공백 Tick이 이 값을 넘으면 HALTED
FESTIVAL_AFFECTION_AVG_THRESHOLD = AFFECTION_AVG_THRESHOLD  # 임시값
FESTIVAL_STRESS_LIMIT = 90  # 임시값 — 번아웃 한계값

_PERFORMANCE_MIN = 0


# ─── Tick 계획 (§4.3) ────────────────────────────────────────────────────────

# R1 기획·준비
PLANNING_TICK = 1  # 부스 기획 회의 → 개입 ①
PREPARATION_TICK = 2  # 준비 작업
REHEARSAL_TICK = 3  # 리허설·사전 점검
# R2 운영 첫날
OPENING_TICK = 4  # 별빛제 개장
INCIDENT_TICK = 5  # 돌발 상황 → 개입 ②
INCIDENT_FOLLOWUP_TICK = 6  # 운영 계속 (개입 ② 조치 적용)
# R3 운영 둘째 날
SECOND_DAY_TICK = 7  # 운영 둘째 날
BLAME_TICK = 8  # 책임 공방 → 개입 ③
CLOSING_TICK = 9  # 운영 마무리 (개입 ③ 조치 적용) → 종료 평가

PREPARATION_TICKS: tuple[int, ...] = (PREPARATION_TICK, REHEARSAL_TICK)
OPERATION_TICKS: tuple[int, ...] = (
    OPENING_TICK,
    INCIDENT_TICK,
    INCIDENT_FOLLOWUP_TICK,
    SECOND_DAY_TICK,
    BLAME_TICK,
    CLOSING_TICK,
)
# 역할·컨셉 공지를 매 Tick 주입하는 범위 (R1 T2 이후 전부)
POST_SETUP_TICKS: tuple[int, ...] = (*PREPARATION_TICKS, *OPERATION_TICKS)


class InterventionPoint(StrEnum):
    BOOTH_SETUP = "BOOTH_SETUP"  # 개입 ① 컨셉·역할 배정
    INCIDENT_RESPONSE = "INCIDENT_RESPONSE"  # 개입 ② 돌발 대응
    STAFFING_ADJUSTMENT = "STAFFING_ADJUSTMENT"  # 개입 ③ 인력 조정


# ─── 컨셉·역할 (§4.2/§4.4) ──────────────────────────────────────────────────


class BoothConcept(StrEnum):
    FOOD = "FOOD"
    EXPERIENCE = "EXPERIENCE"
    EXHIBITION = "EXHIBITION"


CONCEPT_LABELS: dict[BoothConcept, str] = {
    BoothConcept.FOOD: "먹거리 부스",
    BoothConcept.EXPERIENCE: "체험형 부스",
    BoothConcept.EXHIBITION: "전시형 부스",
}

# 컨셉은 수치를 바꾸지 않고 R2 T2 돌발의 후보 풀만 바꾼다. 실제 돌발은 run 시드로 뽑는다.
CONCEPT_INCIDENT_POOLS: dict[BoothConcept, tuple[str, ...]] = {
    BoothConcept.FOOD: ("INGREDIENT_SHORTAGE", "CUSTOMER_RUSH"),
    BoothConcept.EXPERIENCE: ("CUSTOMER_RUSH", "RIVAL_BOOTH_ISSUE"),
    BoothConcept.EXHIBITION: ("RIVAL_BOOTH_ISSUE", "INGREDIENT_SHORTAGE"),
}

INCIDENT_LABELS: dict[str, str] = {
    "INGREDIENT_SHORTAGE": "재료 부족",
    "CUSTOMER_RUSH": "손님 폭주",
    "RIVAL_BOOTH_ISSUE": "옆 부스와의 문제",
}


class BoothRole(StrEnum):
    COUNTER = "COUNTER"
    PRODUCTION = "PRODUCTION"
    SUPPLY = "SUPPLY"
    PROMOTION = "PROMOTION"


ROLE_LABELS: dict[BoothRole, str] = {
    BoothRole.COUNTER: "부스 담당",
    BoothRole.PRODUCTION: "제작·진행",
    BoothRole.SUPPLY: "조달",
    BoothRole.PROMOTION: "홍보",
}

RoleAssignment = Mapping[str, BoothRole]


def _concept_description(concept: BoothConcept) -> str:
    return f"별빛제 부스 컨셉: {CONCEPT_LABELS[concept]}"


# ─── 개입 결과 ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BoothInterventionPlan:
    """개입 조치. 행동은 지정하지 않고 Event·정보 주입·일정 변경만 담는다.

    non_mandatory_agent_ids는 해당 Tick의 일정을 비필수로 바꿀 Agent다 —
    round_driver.run_forced_event_round(non_mandatory_agent_ids=...)로 넘긴다.
    roles는 개입 이후 유효한 역할 배정이다(역할 배정을 생략했으면 None).
    """

    events: tuple[Event, ...] = ()
    injections: Injections = field(default_factory=dict)
    non_mandatory_agent_ids: frozenset[str] = frozenset()
    roles: dict[str, BoothRole] | None = None


def _notice(
    tick: int, agent_id: str, kind: str, content: str, memory_type: str = "observation"
) -> Injections:
    return {
        (tick, agent_id): [
            build_injected_memory(
                tick=tick, agent_id=agent_id, kind=kind, content=content, memory_type=memory_type
            )
        ]
    }


def _festival(
    *, tick: int, concept: BoothConcept, agent_ids: Sequence[str], location_id: str, title: str
) -> Event:
    return build_forced_festival(
        tick=tick,
        participant_agent_ids=agent_ids,
        location_id=location_id,
        title=title,
        description=_concept_description(concept),
    )


# ─── Round 1 — 기획·준비 ─────────────────────────────────────────────────────


def build_planning_meeting_event(
    *, agent_ids: Sequence[str], location_id: str, tick: int = PLANNING_TICK
) -> Event:
    """R1 T1 — 부스 기획 회의. 직후 개입 ①."""
    return build_forced_meeting(
        tick=tick,
        participant_agent_ids=agent_ids,
        location_id=location_id,
        impact_level=ImpactLevel.MEDIUM,
        title="별빛제 부스 기획 회의",
    )


def setup_choice(roles: RoleAssignment | None) -> str:
    """개입 ① 기록값: 역할 배정을 생략하면 WATCH."""
    return WATCH if roles is None else "ASSIGN_ROLES"


def plan_booth_setup(
    *,
    concept: BoothConcept,
    agent_ids: Sequence[str],
    roles: RoleAssignment | None,
    ticks: Sequence[int] = POST_SETUP_TICKS,
) -> BoothInterventionPlan:
    """개입 ① — 역할을 배정했으면 각 Agent에게 자기 역할 공지를 ``ticks``마다 주입한다.

    역할 배정을 생략하면(WATCH) 공지를 주입하지 않고 학생들이 스스로 나눈다.
    컨셉은 공지가 아니라 R1 T2 이후 Event description으로 전달된다.
    """
    if roles is None:
        return BoothInterventionPlan()
    if set(roles) != set(agent_ids):
        raise ValueError("roles must assign exactly one role to every agent")
    roles = {agent_id: BoothRole(role) for agent_id, role in roles.items()}
    return BoothInterventionPlan(
        injections=_role_notices(concept=concept, roles=roles, ticks=ticks),
        roles=roles,
    )


def _role_notices(
    *, concept: BoothConcept, roles: Mapping[str, BoothRole], ticks: Sequence[int]
) -> Injections:
    return merge_injections(
        *(
            _notice(
                tick,
                agent_id,
                "booth_role",
                f"조정관 공지: 너는 {CONCEPT_LABELS[concept]}에서 "
                f"{ROLE_LABELS[role]}({role.value}) 담당이다.",
            )
            for agent_id, role in roles.items()
            for tick in ticks
        )
    )


def build_preparation_event(
    *, concept: BoothConcept, agent_ids: Sequence[str], location_id: str, tick: int = PREPARATION_TICK
) -> Event:
    """R1 T2 — 준비 작업(컨셉·역할 반영)."""
    return build_forced_group_project(
        tick=tick,
        participant_agent_ids=agent_ids,
        location_id=location_id,
        impact_level=ImpactLevel.MEDIUM,
        title="부스 준비 작업",
        description=_concept_description(concept),
    )


def build_rehearsal_event(
    *, concept: BoothConcept, agent_ids: Sequence[str], location_id: str, tick: int = REHEARSAL_TICK
) -> Event:
    """R1 T3 — 리허설·사전 점검."""
    return build_forced_group_project(
        tick=tick,
        participant_agent_ids=agent_ids,
        location_id=location_id,
        impact_level=ImpactLevel.MEDIUM,
        title="리허설·사전 점검",
        description=_concept_description(concept),
    )


# ─── Round 2 — 운영 첫날 ─────────────────────────────────────────────────────


def build_opening_event(
    *, concept: BoothConcept, agent_ids: Sequence[str], location_id: str, tick: int = OPENING_TICK
) -> Event:
    """R2 T1 — 별빛제 개장."""
    return _festival(
        tick=tick, concept=concept, agent_ids=agent_ids, location_id=location_id, title="별빛제 개장"
    )


def draw_festival_incident_subtype(concept: BoothConcept, rng: random.Random) -> str:
    """컨셉의 돌발 후보 풀에서 run 시드 RNG로 하나를 뽑는다 (§4.4)."""
    return rng.choice(CONCEPT_INCIDENT_POOLS[concept])


def build_festival_incident_event(
    *,
    event_subtype: str,
    concept: BoothConcept,
    agent_ids: Sequence[str],
    location_id: str,
    tick: int = INCIDENT_TICK,
) -> Event:
    """R2 T2 ★ — 돌발 상황. subtype은 draw_festival_incident_subtype()으로 뽑는다."""
    if event_subtype not in CONCEPT_INCIDENT_POOLS[concept]:
        raise ValueError(
            f"event_subtype must be one of {CONCEPT_INCIDENT_POOLS[concept]}, got {event_subtype!r}"
        )
    return EventMaster().build_random_incident(
        tick=tick,
        event_subtype=event_subtype,
        participant_agent_ids=agent_ids,
        location_id=location_id,
        title=f"별빛제 돌발 상황 ({INCIDENT_LABELS[event_subtype]})",
        description=_concept_description(concept),
    )


class IncidentResponse(StrEnum):
    SEND_HELP = "SEND_HELP"
    KEEP_BOOTH = "KEEP_BOOTH"
    EMERGENCY_MEETING = "EMERGENCY_MEETING"
    WATCH = WATCH


def plan_incident_response(
    *,
    choice: IncidentResponse,
    incident_subtype: str,
    concept: BoothConcept,
    agent_ids: Sequence[str],
    location_id: str,
    help_agent_id: str | None = None,
    tick: int = INCIDENT_FOLLOWUP_TICK,
) -> BoothInterventionPlan:
    """개입 ② — R2 T3에 적용할 조치 (§4.5).

    SEND_HELP는 5명 FESTIVAL을 유지한다. ``help_agent_id``를 지목하면 그 학생에게
    부탁을 주입하고 일정을 비필수로 바꾸며, 지목하지 않으면 5명 모두에게 공지만
    주입한다. 실제로 부스를 떠날지는 Agent가 정한다.
    """
    if help_agent_id is not None and choice != IncidentResponse.SEND_HELP:
        raise ValueError("help_agent_id is only valid for SEND_HELP")
    incident = INCIDENT_LABELS[incident_subtype]
    if choice == IncidentResponse.EMERGENCY_MEETING:
        event = build_forced_meeting(
            tick=tick,
            participant_agent_ids=agent_ids,
            location_id=location_id,
            title="긴급 대책 회의",
            description=f"{_concept_description(concept)} / 돌발: {incident}",
        )
        return BoothInterventionPlan(events=(event,))

    festival = _festival(
        tick=tick, concept=concept, agent_ids=agent_ids, location_id=location_id, title="부스 운영 계속"
    )
    if choice == IncidentResponse.SEND_HELP:
        if help_agent_id is None:
            injections = merge_injections(
                *(
                    _notice(
                        tick,
                        agent_id,
                        "send_help",
                        f"조정관 공지: 누군가 부스를 잠시 떠나 '{incident}' 문제를 처리해 줬으면 한다. "
                        "누가 갈지는 너희가 정한다.",
                    )
                    for agent_id in agent_ids
                )
            )
            return BoothInterventionPlan(events=(festival,), injections=injections)
        if help_agent_id not in agent_ids:
            raise ValueError(f"help_agent_id {help_agent_id!r} is not a booth member")
        return BoothInterventionPlan(
            events=(festival,),
            injections=_notice(
                tick,
                help_agent_id,
                "send_help",
                f"조정관이 너에게 부스를 잠시 떠나 '{incident}' 문제를 처리해 달라고 부탁했다. "
                "갈지는 네가 정한다.",
            ),
            non_mandatory_agent_ids=frozenset({help_agent_id}),
        )
    if choice == IncidentResponse.KEEP_BOOTH:
        injections = merge_injections(
            *(
                _notice(
                    tick,
                    agent_id,
                    "keep_booth",
                    f"조정관 공지: '{incident}' 문제는 나중에 처리하고 지금은 부스 운영에 집중한다.",
                )
                for agent_id in agent_ids
            )
        )
        return BoothInterventionPlan(events=(festival,), injections=injections)
    if choice == IncidentResponse.WATCH:
        return BoothInterventionPlan(events=(festival,))
    raise ValueError(f"unknown IncidentResponse: {choice}")


# ─── Round 3 — 운영 둘째 날 ──────────────────────────────────────────────────


def build_second_day_event(
    *, concept: BoothConcept, agent_ids: Sequence[str], location_id: str, tick: int = SECOND_DAY_TICK
) -> Event:
    """R3 T1 — 운영 둘째 날."""
    return _festival(
        tick=tick, concept=concept, agent_ids=agent_ids, location_id=location_id, title="별빛제 운영 둘째 날"
    )


def select_conflict_pair(
    *,
    agent_ids: Sequence[str],
    directional_affections: Mapping[tuple[str, str], int],
    rng: random.Random,
) -> tuple[str, str]:
    """R3 T2 갈등 쌍 (§4.6): R2 종료 시점 양방향 affection 합이 가장 낮은 쌍.

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


def build_blame_event(
    *,
    concept: BoothConcept,
    conflict_pair: tuple[str, str],
    location_id: str,
    tick: int = BLAME_TICK,
) -> Event:
    """R3 T2 ★ — 갈등 쌍 2명만 참여하는 책임 공방 GROUP_PROJECT (importance high)."""
    return build_forced_group_project(
        tick=tick,
        participant_agent_ids=conflict_pair,
        location_id=location_id,
        impact_level=ImpactLevel.HIGH,
        title="책임 공방",
        description=f"{_concept_description(concept)} / 작은 실수를 두고 책임을 따진다.",
    )


class StaffingAdjustment(StrEnum):
    SUGGEST_REST = "SUGGEST_REST"
    SWAP_ROLES = "SWAP_ROLES"
    MEDIATE = "MEDIATE"
    WATCH = WATCH


def select_rest_target(agent_states: Mapping[str, tuple[int, int]]) -> str:
    """SUGGEST_REST 대상: (stress, fatigue) 합이 가장 높은 Agent. 동률은 agent_id 순."""
    if not agent_states:
        raise ValueError("select_rest_target requires at least 1 agent")
    return min(agent_states, key=lambda agent_id: (-sum(agent_states[agent_id]), agent_id))


def swap_conflict_roles(
    *, roles: RoleAssignment | None, conflict_pair: tuple[str, str], rng: random.Random
) -> dict[str, BoothRole]:
    """SWAP_ROLES로 바뀌는 역할만 돌려준다 (§4.6).

    두 사람의 역할이 다르면 맞바꾼다. 같거나 역할 배정을 생략했으면 갈등 쌍 중
    1명(``rng``)을 PROMOTION으로, 이미 PROMOTION이면 COUNTER로 옮긴다.
    """
    a, b = conflict_pair
    if roles is not None and roles[a] != roles[b]:
        return {a: roles[b], b: roles[a]}
    mover = rng.choice(sorted(conflict_pair))
    current = roles[mover] if roles is not None else None
    return {mover: BoothRole.COUNTER if current == BoothRole.PROMOTION else BoothRole.PROMOTION}


def plan_staffing_adjustment(
    *,
    choice: StaffingAdjustment,
    concept: BoothConcept,
    agent_ids: Sequence[str],
    location_id: str,
    conflict_pair: tuple[str, str],
    roles: RoleAssignment | None,
    agent_states: Mapping[str, tuple[int, int]],
    rng: random.Random,
    tick: int = CLOSING_TICK,
) -> BoothInterventionPlan:
    """개입 ③ — R3 T3에 적용할 조치 (§4.6). R3 T3은 항상 5명 FESTIVAL이다.

    ``agent_states``는 SUGGEST_REST 대상 선정용 (stress, fatigue)이다.
    """
    festival = _festival(
        tick=tick, concept=concept, agent_ids=agent_ids, location_id=location_id, title="부스 운영 마무리"
    )
    current_roles = None if roles is None else dict(roles)
    if choice == StaffingAdjustment.SUGGEST_REST:
        target = select_rest_target(agent_states)
        return BoothInterventionPlan(
            events=(festival,),
            injections=_notice(
                tick,
                target,
                "suggest_rest",
                "조정관이 너에게 지쳤으면 이번에는 쉬어도 된다고 했다. 쉴지는 네가 정한다.",
            ),
            non_mandatory_agent_ids=frozenset({target}),
            roles=current_roles,
        )
    if choice == StaffingAdjustment.SWAP_ROLES:
        changes = swap_conflict_roles(roles=roles, conflict_pair=conflict_pair, rng=rng)
        injections = merge_injections(
            *(
                _notice(
                    tick,
                    agent_id,
                    "booth_role",
                    f"조정관 공지: 지금부터 너는 {ROLE_LABELS[role]}({role.value}) 담당이다.",
                )
                for agent_id, role in changes.items()
            )
        )
        new_roles = None if current_roles is None else {**current_roles, **changes}
        return BoothInterventionPlan(events=(festival,), injections=injections, roles=new_roles)
    if choice == StaffingAdjustment.MEDIATE:
        injections = merge_injections(
            *(
                _notice(
                    tick,
                    agent_id,
                    "mediate",
                    "조정관이 책임 공방을 벌인 두 사람 사이를 중재하며, 책임을 따지기보다 "
                    "남은 운영을 함께 마무리하자고 이야기했다.",
                    memory_type="conversation",
                )
                for agent_id in conflict_pair
            )
        )
        return BoothInterventionPlan(events=(festival,), injections=injections, roles=current_roles)
    if choice == StaffingAdjustment.WATCH:
        return BoothInterventionPlan(events=(festival,), roles=current_roles)
    raise ValueError(f"unknown StaffingAdjustment: {choice}")


# ─── 부스 담당 인원 (§4.7) ───────────────────────────────────────────────────


@dataclass(frozen=True)
class BoothStaffingRecord:
    tick: int
    staff_count: int
    vacant: bool


def record_booth_staffing(
    *, tick: int, event_type: str, action_types: Mapping[str, ActionType]
) -> BoothStaffingRecord | None:
    """운영 Tick의 부스 담당 인원을 기록한다. 기록 대상이 아니면 None.

    ``action_types``는 그 Tick Event 참여자의 행동이다. FESTIVAL이면 AVOID가 아닌
    인원을 부스 담당 인원으로 세고, 0명이면 공백이다. MEETING으로 바뀐 운영 Tick은
    공백이다. 그 외(R2 T2 돌발, R3 T2 공방)는 기록하지 않는다.
    """
    if tick not in OPERATION_TICKS:
        return None
    kind = event_type.upper()
    if kind == "MEETING":
        return BoothStaffingRecord(tick=tick, staff_count=0, vacant=True)
    if kind != "FESTIVAL":
        return None
    staff = sum(1 for action in action_types.values() if action != ActionType.AVOID)
    return BoothStaffingRecord(tick=tick, staff_count=staff, vacant=staff == 0)


def count_vacant_ticks(records: Sequence[BoothStaffingRecord]) -> int:
    return sum(1 for record in records if record.vacant)


# ─── 성과 (§4.8) ────────────────────────────────────────────────────────────


def _counts_toward_performance(tick: int, event_type: str) -> bool:
    kind = event_type.upper()
    return (tick in PREPARATION_TICKS and kind == "GROUP_PROJECT") or (
        tick in OPERATION_TICKS and kind == "FESTIVAL"
    )


def calculate_booth_performance(
    participant_valences: Sequence[tuple[int, str, ReactionValence]],
    *,
    vacant_tick_count: int,
    step: int = BOOTH_PERFORMANCE_STEP,
    vacancy_penalty: int = BOOTH_VACANCY_PENALTY,
) -> int:
    """(tick, event_type, reaction.valence) 중 R1 준비 GROUP_PROJECT와 운영 FESTIVAL만
    집계하고, 부스 공백 Tick마다 성과를 낮춘다. 회의·돌발·책임 공방은 집계하지 않는다."""
    progress = calculate_project_progress(
        [
            valence
            for tick, event_type, valence in participant_valences
            if _counts_toward_performance(tick, event_type)
        ],
        step=step,
    )
    return max(_PERFORMANCE_MIN, progress - vacant_tick_count * vacancy_penalty)


# ─── 엔딩·챕터 기록 (§4.10) ─────────────────────────────────────────────────


class FestivalEnding(StrEnum):
    POPULAR = "POPULAR"
    COMPLETED = "COMPLETED"
    HALTED = "HALTED"


ENDING_GRADES: dict[FestivalEnding, ChapterGrade] = {
    FestivalEnding.POPULAR: ChapterGrade.GOOD,
    FestivalEnding.COMPLETED: ChapterGrade.MIXED,
    FestivalEnding.HALTED: ChapterGrade.BAD,
}


def _mean(values: Sequence[int]) -> float:
    if not values:
        raise ValueError("values must not be empty")
    return sum(values) / len(values)


def evaluate_festival_ending(
    *,
    booth_performance: int,
    vacant_tick_count: int,
    directional_affections: Sequence[int],
    agent_stress_levels: Sequence[int],
    initial_satisfaction_levels: Sequence[int],
    final_satisfaction_levels: Sequence[int],
) -> FestivalEnding:
    """성과 미달·공백 초과면 HALTED. 번아웃 없음·관계·만족도 상승까지 충족하면 POPULAR.
    번아웃은 HALTED가 아니라 POPULAR만 막는다."""
    if booth_performance < BOOTH_PERFORMANCE_THRESHOLD or vacant_tick_count > BOOTH_VACANCY_LIMIT:
        return FestivalEnding.HALTED
    no_burnout = all(stress < FESTIVAL_STRESS_LIMIT for stress in agent_stress_levels)
    relationship_ok = _mean(directional_affections) >= FESTIVAL_AFFECTION_AVG_THRESHOLD
    satisfaction_rose = _mean(final_satisfaction_levels) > _mean(initial_satisfaction_levels)
    if no_burnout and relationship_ok and satisfaction_rose:
        return FestivalEnding.POPULAR
    return FestivalEnding.COMPLETED


def build_festival_record(
    *, ending: FestivalEnding, interventions: Sequence[InterventionRecord]
) -> ChapterRecord:
    return ChapterRecord(
        chapter=4,
        ending=ending.value,
        grade=ENDING_GRADES[ending],
        interventions=tuple(interventions),
    )


# ─── 업적 (§4.11, 기획 확정분만) ─────────────────────────────────────────────


class FestivalAchievement(StrEnum):
    SHOW_MUST_GO_ON = "SHOW_MUST_GO_ON"  # 쇼는 계속 되어야 한다
    BOOTH_LEFT_EMPTY = "BOOTH_LEFT_EMPTY"  # 여기 비었잖아
    FESTIVAL_IS_OVER = "FESTIVAL_IS_OVER"  # 축제는 끝났다


def evaluate_festival_achievements(
    *,
    ending: FestivalEnding,
    vacant_tick_count: int,
    peak_stress_levels: Sequence[int],
) -> frozenset[FestivalAchievement]:
    """``peak_stress_levels``는 run 동안 Agent별 stress 최대값이다.

    R2 T2 돌발과 R3 T2 공방은 Tick 계획상 항상 주입되므로, 「쇼는 계속 되어야 한다」는
    정상 종료된 run에서 공백 0회 + POPULAR로 판정한다.
    """
    achieved: set[FestivalAchievement] = set()
    if vacant_tick_count == 0 and ending == FestivalEnding.POPULAR:
        achieved.add(FestivalAchievement.SHOW_MUST_GO_ON)
    if vacant_tick_count >= 1:
        achieved.add(FestivalAchievement.BOOTH_LEFT_EMPTY)
    if any(stress >= FESTIVAL_STRESS_LIMIT for stress in peak_stress_levels):
        achieved.add(FestivalAchievement.FESTIVAL_IS_OVER)
    return frozenset(achieved)
