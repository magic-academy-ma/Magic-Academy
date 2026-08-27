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

import hashlib
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

# 예정 Event(schedule 기반)와 동적 Event(조건 기반) 구분. RANDOM_INCIDENT는
# 동적 Event의 한 형태로, event_subtype이 실제 효과를 결정한다 (§1).
SCHEDULED_EVENT_TYPES: frozenset[str] = frozenset(
    {"CLASS", "EXAM", "MT", "FESTIVAL", "STUDENT_COUNCIL"}
)

DYNAMIC_EVENT_TYPES: frozenset[str] = frozenset({"GROUP_PROJECT", "MEETING"})


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

# event_impact / event_frequency 정책 (mvp-tick-event-policy.md §4.3, §4.4).
IMPACT_LEVEL_BY_NAME: dict[str, ImpactLevel] = {
    "low": ImpactLevel.LOW,
    "medium": ImpactLevel.MEDIUM,
    "high": ImpactLevel.HIGH,
}
DYNAMIC_FREQUENCY_PROBABILITY: dict[str, float] = {
    "low": 0.25,
    "medium": 0.50,
    "high": 0.75,
}
DYNAMIC_DAILY_MAX: dict[str, int] = {"low": 1, "medium": 2, "high": 2}
DYNAMIC_PARTICIPANT_CAP_BY_IMPACT: dict[str, int] = {"low": 2, "medium": 4, "high": 5}
_LEGACY_GROUP_PROJECT_CAP = 4
_LEGACY_MEETING_CAP = 5


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


def _dynamic_frequency_allows(
    *,
    scheduled_count: int,
    event_frequency: str,
    frequency_seed: str,
    daily_dynamic_count: int,
) -> bool:
    """동적 Event 후보를 이번 Tick에 생성할지 결정론적으로 판정한다 (§4.3).

    시드는 ``f"{simulation_id}:{tick_number}:{config_version}"``이며, 같은 시드는
    항상 같은 결과를 낸다 (프로세스 간 불안정한 내장 ``hash()``는 쓰지 않는다).
    """
    if scheduled_count >= 3:
        return False
    if daily_dynamic_count >= DYNAMIC_DAILY_MAX.get(event_frequency, 2):
        return False
    probability = DYNAMIC_FREQUENCY_PROBABILITY.get(event_frequency, 0.50)
    digest = hashlib.sha256(frequency_seed.encode("utf-8")).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    return rng.random() < probability


class EventMaster:
    """Tick당 예정/동적 일반 Event를 결정론적으로 생성한다."""

    def generate(
        self,
        *,
        tick: int,
        agent_summaries: Sequence[AgentSummary],
        scheduled_events: Sequence[ScheduledEventInput] = (),
        relationship_summaries: Sequence[RelationshipSummary] = (),
        event_frequency: str = "medium",
        event_impact: str = "medium",
        frequency_seed: str | None = None,
        daily_dynamic_count: int = 0,
        cooldown_excluded_agent_ids: Mapping[str, frozenset[str]] | None = None,
        high_impact_agent_ids_today: frozenset[str] = frozenset(),
    ) -> list[Event]:
        """예정 Event를 변환하고 동적 Event 후보를 생성한다.

        ``frequency_seed``가 ``None``이면 빈도 정책 없이 모든 동적 후보를 생성한다
        (Slice 5 기존 동작). ``frequency_seed``가 주어지면
        ``docs/04-feature-specs/mvp-tick-event-policy.md`` §4.3 · §4.4 정책을 적용한다:
        확률 판정 · Tick당 동적 Event 1개 상한 · 참여 Agent 상한 · 쿨다운 ·
        당일 high 참여 제외.
        """
        active_by_id = {
            summary.agent_id: summary for summary in agent_summaries if summary.active_status
        }

        events: list[Event] = list(
            self._convert_scheduled(tick, active_by_id, scheduled_events)
        )

        if frequency_seed is None:
            events.extend(self._generate_group_project(tick, active_by_id))
            events.extend(
                self._generate_meeting(tick, active_by_id, relationship_summaries)
            )
            return events

        if not _dynamic_frequency_allows(
            scheduled_count=len(events),
            event_frequency=event_frequency,
            frequency_seed=frequency_seed,
            daily_dynamic_count=daily_dynamic_count,
        ):
            return events

        impact_level = IMPACT_LEVEL_BY_NAME.get(event_impact, ImpactLevel.MEDIUM)
        participant_cap = DYNAMIC_PARTICIPANT_CAP_BY_IMPACT.get(event_impact, 4)
        excluded = cooldown_excluded_agent_ids or {}
        dynamic = self._generate_group_project(
            tick,
            active_by_id,
            impact_level=impact_level,
            participant_cap=participant_cap,
            excluded_agent_ids=excluded.get("GROUP_PROJECT", frozenset()),
            high_impact_agent_ids_today=high_impact_agent_ids_today,
        )
        if not dynamic:
            dynamic = self._generate_meeting(
                tick,
                active_by_id,
                relationship_summaries,
                impact_level=impact_level,
                participant_cap=participant_cap,
                excluded_agent_ids=excluded.get("MEETING", frozenset()),
                high_impact_agent_ids_today=high_impact_agent_ids_today,
            )
        # Tick당 동적 Event는 최대 1개 (§4.3).
        events.extend(dynamic[:1])
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
    # 동적 Event: GROUP_PROJECT (같은 major_id 수강 Agent 우선)
    # ------------------------------------------------------------------
    def _generate_group_project(
        self,
        tick: int,
        active_by_id: dict[str, AgentSummary],
        *,
        impact_level: ImpactLevel = ImpactLevel.MEDIUM,
        participant_cap: int | None = None,
        excluded_agent_ids: frozenset[str] = frozenset(),
        high_impact_agent_ids_today: frozenset[str] = frozenset(),
    ) -> list[Event]:
        cap = participant_cap if participant_cap is not None else _LEGACY_GROUP_PROJECT_CAP
        exclude_high = impact_level == ImpactLevel.HIGH
        groups: dict[tuple[str, str], list[AgentSummary]] = {}
        for summary in active_by_id.values():
            if summary.role != "student" or not summary.major_id or not summary.current_location_id:
                continue
            if summary.agent_id in excluded_agent_ids:
                continue
            if exclude_high and summary.agent_id in high_impact_agent_ids_today:
                continue
            key = (summary.major_id, summary.current_location_id)
            groups.setdefault(key, []).append(summary)

        events: list[Event] = []
        for (major_id, location_id), members in sorted(groups.items()):
            if len(members) < 2:
                continue
            participant_ids = tuple(
                sorted(member.agent_id for member in members)[:cap]
            )
            events.append(
                Event(
                    event_key=f"group_project:{major_id}:{location_id}:{tick}",
                    event_type="GROUP_PROJECT",
                    participant_agent_ids=participant_ids,
                    location_id=location_id,
                    tick=tick,
                    impact_level=impact_level,
                    importance=_importance_for(impact_level),
                    title="조별 과제",
                    description=f"{major_id} 전공 Student들이 조별 과제를 진행한다.",
                )
            )
        return events

    # ------------------------------------------------------------------
    # 동적 Event: MEETING (같은 위치 + 기존 우호 관계)
    # ------------------------------------------------------------------
    def _generate_meeting(
        self,
        tick: int,
        active_by_id: dict[str, AgentSummary],
        relationship_summaries: Sequence[RelationshipSummary],
        *,
        impact_level: ImpactLevel = ImpactLevel.MEDIUM,
        participant_cap: int | None = None,
        excluded_agent_ids: frozenset[str] = frozenset(),
        high_impact_agent_ids_today: frozenset[str] = frozenset(),
    ) -> list[Event]:
        cap = participant_cap if participant_cap is not None else _LEGACY_MEETING_CAP
        exclude_high = impact_level == ImpactLevel.HIGH

        def _blocked(agent_id: str) -> bool:
            if agent_id in excluded_agent_ids:
                return True
            return exclude_high and agent_id in high_impact_agent_ids_today

        # 우호적인 관계(affection+closeness 평균 > 0)만 MEETING 후보로 인정한다.
        friendly_pairs = {
            (rel.source_agent_id, rel.target_agent_id)
            for rel in relationship_summaries
            if (rel.affection + rel.closeness) / 2 > 0
            and rel.source_agent_id in active_by_id
            and rel.target_agent_id in active_by_id
            and not _blocked(rel.source_agent_id)
            and not _blocked(rel.target_agent_id)
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
            participant_ids = tuple(sorted(members)[:cap])
            events.append(
                Event(
                    event_key=f"meeting:{location_id}:{tick}",
                    event_type="MEETING",
                    participant_agent_ids=participant_ids,
                    location_id=location_id,
                    tick=tick,
                    impact_level=impact_level,
                    importance=_importance_for(impact_level),
                    title="친목 모임",
                    description="친한 Agent들이 함께 모인다.",
                )
            )
        return events
