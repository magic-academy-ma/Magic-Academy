"""스토리모드 CHAPTER 2 — 무너진 팀을 다시 살려라: 진행 컨트롤러.

docs/04-feature-specs/challenge-mode-team-revival.md §4.2~§4.6: 역할·속사정 추첨,
Round 1~3의 강제 Event와 개입 선택지별 조치를 순수 함수로 조립한다. 플레이어는
라운드 진행 중 학생들의 대사·행동을 관찰해 속사정을 스스로 짐작한다 — 별도의 파악
판정은 없고, 개입 문구도 속사정을 직접 담지 않는다.
컨트롤러는 Agent 행동을 정하지 않는다 — Event 주입과 정보 주입(ChallengeLLMOverride가
쓸 injections)만 만든다. EventMaster/AgentRuntime을 직접 호출하지 않으며, 실제 Tick
실행 연동은 별도 통합 작업의 몫이다.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.simulation.agent_runtime import ActionType
from app.simulation.challenge.forced_events import (
    build_forced_group_project,
    build_forced_meeting,
)
from app.simulation.challenge.llm_override import (
    Injections,
    build_injected_memory,
    merge_injections,
)
from app.simulation.challenge.record import WATCH
from app.simulation.event_master import Event, EventMaster

ROUND3_INCIDENT_SUBTYPES: tuple[str, ...] = (
    "PRESENTATION_ERROR",
    "MEMBER_DROPOUT",
    "SUPPLY_MISSING",
)


# ─── 역할·초기 상태 (§4.2) ───────────────────────────────────────────────────


class TeamRole(StrEnum):
    LEADER = "LEADER"
    IGNORED_MEMBER = "IGNORED_MEMBER"
    LEAVER = "LEAVER"
    BLAMED_MEMBER = "BLAMED_MEMBER"
    BYSTANDER = "BYSTANDER"


ROLE_LABELS: dict[TeamRole, str] = {
    TeamRole.LEADER: "리더",
    TeamRole.IGNORED_MEMBER: "의견이 무시된다고 느끼는 팀원",
    TeamRole.LEAVER: "탈퇴를 고민하는 팀원",
    TeamRole.BLAMED_MEMBER: "실수 때문에 책임을 추궁받는 팀원",
    TeamRole.BYSTANDER: "갈등에서 거리를 두는 팀원",
}


@dataclass(frozen=True)
class TeamRoster:
    leader: str
    ignored_member: str
    leaver: str
    blamed_member: str
    bystander: str

    def agent_id(self, role: TeamRole) -> str:
        return {
            TeamRole.LEADER: self.leader,
            TeamRole.IGNORED_MEMBER: self.ignored_member,
            TeamRole.LEAVER: self.leaver,
            TeamRole.BLAMED_MEMBER: self.blamed_member,
            TeamRole.BYSTANDER: self.bystander,
        }[role]

    @property
    def all_agent_ids(self) -> tuple[str, ...]:
        return tuple(self.agent_id(role) for role in TeamRole)


class Direction(StrEnum):
    LOW = "LOW"
    HIGH = "HIGH"


@dataclass(frozen=True)
class InitialCondition:
    """시작 시 주입할 초기 상태. 방향만 정하고 수치는 프리셋 적용 시 정한다."""

    role: TeamRole
    metric: str
    direction: Direction
    toward: TeamRole | None = None


INITIAL_CONDITIONS: tuple[InitialCondition, ...] = (
    InitialCondition(TeamRole.LEADER, "affection", Direction.LOW, toward=TeamRole.IGNORED_MEMBER),
    InitialCondition(TeamRole.IGNORED_MEMBER, "affection", Direction.LOW, toward=TeamRole.LEADER),
    InitialCondition(TeamRole.IGNORED_MEMBER, "satisfaction", Direction.LOW),
    InitialCondition(TeamRole.LEAVER, "satisfaction", Direction.LOW),
    InitialCondition(TeamRole.LEAVER, "stress", Direction.HIGH),
    InitialCondition(TeamRole.BLAMED_MEMBER, "stress", Direction.HIGH),
)


# ─── 속사정 (§4.2) ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class HiddenMotive:
    grievance: str
    conflict_target: TeamRole
    desired_role: str


# 문구 초안 — 확정 필요(§9 미정 항목)
MOTIVE_POOLS: dict[TeamRole, tuple[HiddenMotive, ...]] = {
    TeamRole.LEADER: (
        HiddenMotive("팀원들이 연습에 진지하지 않다고 느낀다", TeamRole.IGNORED_MEMBER, "전략을 최종 결정하는 역할"),
        HiddenMotive("실수가 반복되는데 아무도 책임지지 않는다고 느낀다", TeamRole.BLAMED_MEMBER, "팀 전체를 지휘하는 역할"),
    ),
    TeamRole.IGNORED_MEMBER: (
        HiddenMotive("자기 전술 아이디어가 매번 묵살된다", TeamRole.LEADER, "전술 설계 담당"),
        HiddenMotive("회의에서 발언할 기회가 없다", TeamRole.LEADER, "회의 진행 담당"),
    ),
    TeamRole.LEAVER: (
        HiddenMotive("원하는 역할을 맡지 못했다", TeamRole.LEADER, "공격 마법 담당"),
        HiddenMotive("다른 팀원의 실수를 자기가 메우고 있다", TeamRole.BLAMED_MEMBER, "자기 몫만 책임지는 보조 역할"),
        HiddenMotive("리더의 방식이 싫다", TeamRole.LEADER, "의견을 낼 수 있는 역할"),
    ),
    TeamRole.BLAMED_MEMBER: (
        HiddenMotive("실수가 전부 자기 탓으로 몰린다", TeamRole.LEADER, "부담이 덜한 지원 역할"),
        HiddenMotive("맡은 역할이 자기 실력에 맞지 않는다", TeamRole.LEAVER, "방어 마법 담당"),
    ),
    TeamRole.BYSTANDER: (
        HiddenMotive("팀 분위기가 나빠 연습에 집중할 수 없다", TeamRole.LEADER, "지금 역할 유지"),
        HiddenMotive("갈등에 휘말리기 싫다", TeamRole.IGNORED_MEMBER, "조용히 맡은 일만 하는 역할"),
    ),
}


def draw_hidden_motives(rng: random.Random) -> dict[TeamRole, HiddenMotive]:
    """역할마다 후보 풀에서 속사정 하나를 run 시드 RNG로 뽑는다."""
    return {role: rng.choice(MOTIVE_POOLS[role]) for role in TeamRole}


def plan_motive_injections(
    *,
    ticks: Sequence[int],
    roster: TeamRoster,
    motives: dict[TeamRole, HiddenMotive],
) -> Injections:
    """속사정을 해당 Agent의 페르소나 맥락으로 매 Tick 입력에 넣는다."""
    injections: Injections = {}
    for role, motive in motives.items():
        agent_id = roster.agent_id(role)
        content = (
            f"나의 속마음 — 불만: {motive.grievance}. "
            f"가장 부딪히는 상대: {ROLE_LABELS[motive.conflict_target]}. "
            f"팀에서 맡고 싶은 역할: {motive.desired_role}."
        )
        for tick in ticks:
            injections.setdefault((tick, agent_id), []).append(
                build_injected_memory(
                    tick=tick,
                    agent_id=agent_id,
                    kind="motive",
                    content=content,
                    memory_type="reflection",
                )
            )
    return injections


# ─── 개입 결과 ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class InterventionPlan:
    events: tuple[Event, ...] = ()
    injections: Injections = field(default_factory=dict)


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


# ─── Round 1 — 갈등의 표면화 (§4.4) ─────────────────────────────────────────


class Round1Choice(StrEnum):
    REASSIGN_ROLES = "REASSIGN_ROLES"
    MEDIATE = "MEDIATE"
    WATCH = WATCH


def build_round1_trigger_event(
    *, tick: int, agent_a_id: str, agent_b_id: str, location_id: str
) -> Event:
    """Day1 첫 Tick에 항상 주입되는 리더·무시받는 팀원 충돌 GROUP_PROJECT."""
    return build_forced_group_project(
        tick=tick,
        participant_agent_ids=[agent_a_id, agent_b_id],
        location_id=location_id,
        title="전술 연습 (의견 충돌)",
    )


def plan_round1_choice(
    *, tick: int, choice: Round1Choice, roster: TeamRoster, location_id: str
) -> InterventionPlan:
    if choice == Round1Choice.REASSIGN_ROLES:
        groups = (
            (TeamRole.LEADER, TeamRole.LEAVER),
            (TeamRole.IGNORED_MEMBER, TeamRole.BLAMED_MEMBER),
        )
        events = tuple(
            build_forced_group_project(
                tick=tick,
                participant_agent_ids=[roster.agent_id(role) for role in group],
                location_id=location_id,
                title="전술 연습 (역할 재배정)",
            )
            for group in groups
        )
        injections = merge_injections(
            *(
                _notice(tick, roster.agent_id(role), "role_notice", "조정관이 팀의 역할을 다시 나눴다.")
                for group in groups
                for role in group
            )
        )
        return InterventionPlan(events=events, injections=injections)
    if choice == Round1Choice.MEDIATE:
        event = build_forced_meeting(
            tick=tick,
            participant_agent_ids=[roster.leader, roster.ignored_member],
            location_id=location_id,
            title="조정관이 마련한 대화",
            description="조정관이 두 사람이 이야기할 자리를 마련했다.",
        )
        return InterventionPlan(events=(event,))
    if choice == Round1Choice.WATCH:
        return InterventionPlan()
    raise ValueError(f"unknown Round1Choice: {choice}")


def build_leave_declaration_event(*, tick: int, roster: TeamRoster, location_id: str) -> Event:
    """Day1 마지막 Tick — 선택과 무관하게 탈퇴 선언이 일어난다."""
    return build_forced_meeting(
        tick=tick,
        participant_agent_ids=roster.all_agent_ids,
        location_id=location_id,
        title="탈퇴 선언",
        description=f"{ROLE_LABELS[TeamRole.LEAVER]}이(가) 팀을 나가겠다고 선언한다.",
    )


# ─── Round 2 — 책임 공방과 탈퇴 위기 (§4.5) ─────────────────────────────────


class Round2Choice(StrEnum):
    PERSUADE_LEAVER = "PERSUADE_LEAVER"
    TEAM_MEETING = "TEAM_MEETING"
    REDISTRIBUTE = "REDISTRIBUTE"
    WATCH = WATCH


def build_round2_trigger_event(*, tick: int, roster: TeamRoster, location_id: str) -> Event:
    """Day2 첫 Tick — 반복 실수 상황. 책임 떠넘기기 여부는 Agent 자율."""
    return build_forced_group_project(
        tick=tick,
        participant_agent_ids=roster.all_agent_ids,
        location_id=location_id,
        title="전술 연습 (반복되는 실수)",
        description=f"{ROLE_LABELS[TeamRole.BLAMED_MEMBER]}의 실수가 또 나왔다.",
    )


def plan_round2_choice(
    *, ticks: Sequence[int], choice: Round2Choice, roster: TeamRoster, location_id: str
) -> InterventionPlan:
    """ticks는 개입 이후 남은 Day2 Tick이다. Event는 첫 Tick에, 대화 기억은 매 Tick에 넣는다."""
    if not ticks:
        raise ValueError("plan_round2_choice requires at least 1 tick")
    next_tick = ticks[0]
    if choice == Round2Choice.PERSUADE_LEAVER:
        injections = merge_injections(
            *(
                _notice(
                    tick,
                    roster.leaver,
                    "persuade",
                    "조정관이 팀에 남아 달라고 이야기했다.",
                    memory_type="conversation",
                )
                for tick in ticks
            )
        )
        return InterventionPlan(injections=injections)
    if choice == Round2Choice.TEAM_MEETING:
        event = build_forced_meeting(
            tick=next_tick,
            participant_agent_ids=roster.all_agent_ids,
            location_id=location_id,
            title="팀 전체 회의",
        )
        return InterventionPlan(events=(event,))
    if choice == Round2Choice.REDISTRIBUTE:
        groups = (
            (TeamRole.LEAVER, TeamRole.BYSTANDER),
            (TeamRole.LEADER, TeamRole.IGNORED_MEMBER, TeamRole.BLAMED_MEMBER),
        )
        events = tuple(
            build_forced_group_project(
                tick=next_tick,
                participant_agent_ids=[roster.agent_id(role) for role in group],
                location_id=location_id,
                title="전술 연습 (업무 재분배)",
            )
            for group in groups
        )
        injections = merge_injections(
            *(
                _notice(next_tick, roster.agent_id(role), "role_notice", "조정관이 업무를 다시 나눴다.")
                for role in (TeamRole.LEAVER, TeamRole.BLAMED_MEMBER)
            )
        )
        return InterventionPlan(events=events, injections=injections)
    if choice == Round2Choice.WATCH:
        return InterventionPlan()
    raise ValueError(f"unknown Round2Choice: {choice}")


# ─── Round 3 — 대회 직전 (§4.6) ──────────────────────────────────────────────


def draw_round3_incident_subtype(rng: random.Random) -> str:
    return rng.choice(ROUND3_INCIDENT_SUBTYPES)


def build_round3_incident_event(
    *,
    tick: int,
    event_subtype: str,
    participant_agent_ids: Sequence[str],
    location_id: str,
) -> Event:
    """등록된 3종 RANDOM_INCIDENT subtype 중 하나를 주입한다.
    subtype은 draw_round3_incident_subtype()으로 뽑고, 여기서는 등록된 값인지만 검증한다."""
    if event_subtype not in ROUND3_INCIDENT_SUBTYPES:
        raise ValueError(
            f"event_subtype must be one of {ROUND3_INCIDENT_SUBTYPES}, got {event_subtype!r}"
        )
    return EventMaster().build_random_incident(
        tick=tick,
        event_subtype=event_subtype,
        participant_agent_ids=participant_agent_ids,
        location_id=location_id,
        title="대회 직전 위기",
    )


def build_final_preparation_event(*, tick: int, roster: TeamRoster, location_id: str) -> Event:
    """Day3 마지막 Tick — 대회 최종 준비. 탈퇴 선언자의 참여 여부가 팀 존속을 정한다."""
    return build_forced_group_project(
        tick=tick,
        participant_agent_ids=roster.all_agent_ids,
        location_id=location_id,
        title="대회 최종 준비",
    )


def joined_final_preparation(action_type: ActionType) -> bool:
    """최종 준비 Tick에서 AVOID가 아니면 참여한 것으로 본다(§4.6)."""
    return action_type != ActionType.AVOID
