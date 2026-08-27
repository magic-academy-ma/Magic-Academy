"""Slice 5 Task 1 — Event Master: deterministic general Event generation.

Contract source: docs/04-feature-specs/slice-5-integration.md §1, §3 (Task 0
confirmed). The LLM-narration design in docs/03-system-design/event-master.md
is superseded for Task 1 by the integration doc's deterministic requirement
(Issue #101: "동일 입력/seed/상태에서 결과가 흔들리면 안 됩니다") — Event Master
here is pure system logic, no LLM call.

Event Master's L1 ``AgentSummary`` is a distinct contract from Agent Runtime's
``nearby_agents`` (``app.simulation.agent_runtime.AgentSummary``): this one is
the full participant-candidate snapshot used to pick Event participants, not a
per-observer visibility subset.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

# 예정 Event(schedule 기반)와 동적 Event(조건 기반) 구분. RANDOM_INCIDENT는
# 동적 Event의 한 형태로, event_subtype이 실제 효과를 결정한다 (§1).
SCHEDULED_EVENT_TYPES: frozenset[str] = frozenset(
    {"CLASS", "EXAM", "MT", "FESTIVAL", "STUDENT_COUNCIL"}
)


class ImpactLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# 확정된 매핑 (slice-5-integration.md §1). 반드시 이 값만 사용한다.
IMPACT_LEVEL_TO_IMPORTANCE: dict[ImpactLevel, int] = {
    ImpactLevel.LOW: 30,
    ImpactLevel.MEDIUM: 50,
    ImpactLevel.HIGH: 80,
}


@dataclass(frozen=True)
class AgentSummary:
    """Event Master L1 참여 후보 snapshot (§3 L1 필드).

    Agent Runtime의 nearby_agents(관찰 가능한 부분집합)와 혼동하지 말 것 — 이
    summary는 전체 Event 참여 후보 목록이다.
    """

    agent_id: str
    name: str
    role: str  # "student" | "professor" | "user_persona"
    major_id: str | None
    year: int | None
    active_status: bool
    current_location_id: str | None
    mood: int
    stress: int
    fatigue: int


@dataclass(frozen=True)
class RelationshipSummary:
    """MEETING 후보 선정 전용 관계 요약 (§3: MEETING 후보 선정에만 사용)."""

    source_agent_id: str
    target_agent_id: str
    affection: int
    closeness: int


@dataclass(frozen=True)
class ScheduledEventInput:
    """기존 Schedule/Event 구조에서 이미 활성화된 예정 Event를 그대로 재사용하는 입력.

    Event Master는 예정 Event를 새로 생성하지 않고 변환만 한다.
    """

    event_id: str
    event_type: str  # SCHEDULED_EVENT_TYPES 중 하나
    location_id: str
    participant_agent_ids: tuple[str, ...]
    title: str = ""
    description: str = ""
    impact_level: ImpactLevel = ImpactLevel.MEDIUM


@dataclass(frozen=True)
class Event:
    """Event Master 출력 계약 (§1)."""

    event_key: str  # 결정론적 canonical 식별자 (effect_id 생성용, DB UUID 아님)
    event_type: str
    participant_agent_ids: tuple[str, ...]
    location_id: str
    tick: int
    impact_level: ImpactLevel
    importance: int
    title: str
    description: str
    source: str = "event_master"
    event_subtype: str | None = None
    expected_effects: dict = field(default_factory=dict)


def _importance_for(impact_level: ImpactLevel) -> int:
    return IMPACT_LEVEL_TO_IMPORTANCE[impact_level]


class EventMaster:
    """Tick당 예정/동적 일반 Event를 결정론적으로 생성한다."""

    def generate(
        self,
        *,
        tick: int,
        agent_summaries: Sequence[AgentSummary],
        scheduled_events: Sequence[ScheduledEventInput] = (),
        relationship_summaries: Sequence[RelationshipSummary] = (),
    ) -> list[Event]:
        active_by_id = {
            summary.agent_id: summary for summary in agent_summaries if summary.active_status
        }

        events: list[Event] = []
        events.extend(self._convert_scheduled(tick, active_by_id, scheduled_events))
        events.extend(self._generate_group_project(tick, active_by_id))
        events.extend(self._generate_meeting(tick, active_by_id, relationship_summaries))
        return events

    def build_random_incident(
        self,
        *,
        tick: int,
        event_subtype: str,
        participant_agent_ids: Sequence[str],
        location_id: str,
        impact_level: ImpactLevel = ImpactLevel.MEDIUM,
        title: str = "돌발 사건",
        description: str = "",
    ) -> Event:
        """RANDOM_INCIDENT는 반드시 event_subtype을 가진다 (§1).

        실제 효과는 Event Policy Registry의 event_subtype 규칙으로 결정되며,
        Magic Layer의 special_events(마법 특수 사건)와는 별도 경로다.
        """
        if not event_subtype:
            raise ValueError("RANDOM_INCIDENT requires event_subtype")
        participant_ids = tuple(sorted(dict.fromkeys(participant_agent_ids)))
        if not participant_ids:
            raise ValueError("RANDOM_INCIDENT requires at least one participant")
        return Event(
            event_key=f"random_incident:{event_subtype}:{location_id}:{tick}",
            event_type="RANDOM_INCIDENT",
            event_subtype=event_subtype,
            participant_agent_ids=participant_ids,
            location_id=location_id,
            tick=tick,
            impact_level=impact_level,
            importance=_importance_for(impact_level),
            title=title,
            description=description,
        )

    # ------------------------------------------------------------------
    # 예정 Event 변환
    # ------------------------------------------------------------------
    def _convert_scheduled(
        self,
        tick: int,
        active_by_id: dict[str, AgentSummary],
        scheduled_events: Sequence[ScheduledEventInput],
    ) -> list[Event]:
        events: list[Event] = []
        for scheduled in sorted(scheduled_events, key=lambda item: item.event_id):
            if scheduled.event_type not in SCHEDULED_EVENT_TYPES:
                continue
            participant_ids = tuple(
                sorted(
                    agent_id
                    for agent_id in scheduled.participant_agent_ids
                    if agent_id in active_by_id
                )
            )
            if not participant_ids:
                continue
            events.append(
                Event(
                    event_key=f"scheduled:{scheduled.event_id}",
                    event_type=scheduled.event_type,
                    participant_agent_ids=participant_ids,
                    location_id=scheduled.location_id,
                    tick=tick,
                    impact_level=scheduled.impact_level,
                    importance=_importance_for(scheduled.impact_level),
                    title=scheduled.title or scheduled.event_type,
                    description=scheduled.description,
                )
            )
        return events

    # ------------------------------------------------------------------
    # 동적 Event: GROUP_PROJECT (같은 major_id 수강 Agent 우선, 2~4명)
    # ------------------------------------------------------------------
    def _generate_group_project(
        self, tick: int, active_by_id: dict[str, AgentSummary]
    ) -> list[Event]:
        groups: dict[tuple[str, str], list[AgentSummary]] = {}
        for summary in active_by_id.values():
            if summary.role != "student" or not summary.major_id or not summary.current_location_id:
                continue
            key = (summary.major_id, summary.current_location_id)
            groups.setdefault(key, []).append(summary)

        events: list[Event] = []
        for (major_id, location_id), members in sorted(groups.items()):
            if len(members) < 2:
                continue
            participant_ids = tuple(
                sorted(member.agent_id for member in members)[:4]
            )
            events.append(
                Event(
                    event_key=f"group_project:{major_id}:{location_id}:{tick}",
                    event_type="GROUP_PROJECT",
                    participant_agent_ids=participant_ids,
                    location_id=location_id,
                    tick=tick,
                    impact_level=ImpactLevel.MEDIUM,
                    importance=_importance_for(ImpactLevel.MEDIUM),
                    title="조별 과제",
                    description=f"{major_id} 전공 Student들이 조별 과제를 진행한다.",
                )
            )
        return events

    # ------------------------------------------------------------------
    # 동적 Event: MEETING (같은 위치 + 기존 우호 관계, 2~5명)
    # ------------------------------------------------------------------
    def _generate_meeting(
        self,
        tick: int,
        active_by_id: dict[str, AgentSummary],
        relationship_summaries: Sequence[RelationshipSummary],
    ) -> list[Event]:
        # 우호적인 관계(affection+closeness 평균 > 0)만 MEETING 후보로 인정한다.
        friendly_pairs = {
            (rel.source_agent_id, rel.target_agent_id)
            for rel in relationship_summaries
            if (rel.affection + rel.closeness) / 2 > 0
            and rel.source_agent_id in active_by_id
            and rel.target_agent_id in active_by_id
        }
        if not friendly_pairs:
            return []

        groups: dict[str, set[str]] = {}
        for source_id, target_id in friendly_pairs:
            source = active_by_id[source_id]
            target = active_by_id[target_id]
            if (
                source.current_location_id is None
                or source.current_location_id != target.current_location_id
            ):
                continue
            groups.setdefault(source.current_location_id, set()).update(
                {source_id, target_id}
            )

        events: list[Event] = []
        for location_id, members in sorted(groups.items()):
            if len(members) < 2:
                continue
            participant_ids = tuple(sorted(members)[:5])
            events.append(
                Event(
                    event_key=f"meeting:{location_id}:{tick}",
                    event_type="MEETING",
                    participant_agent_ids=participant_ids,
                    location_id=location_id,
                    tick=tick,
                    impact_level=ImpactLevel.MEDIUM,
                    importance=_importance_for(ImpactLevel.MEDIUM),
                    title="친목 모임",
                    description="친한 Agent들이 함께 모인다.",
                )
            )
        return events
