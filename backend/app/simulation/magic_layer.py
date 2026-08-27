"""Slice 5 Task 1 — Magic Layer: deterministic special-Event condition judgment.

Contract source: docs/04-feature-specs/slice-5-integration.md §2 (Task 0
confirmed thresholds/priority) and docs/03-system-design/magic-layer.md §3.2.1
(condition shape). No LLM narration in Task 1 — condition judgment is system
logic only ("2026-07-24 확정: ... 고정 확률 기반 생성은 사용하지 않는다").

Magic Layer never computes numeric deltas (magic-layer.md §2.1: "방향 정보만
제공"). It only decides *which* special Event fires and *who/where*; the
typed direction/intensity signals it emits are converted to canonical
EffectCandidates by the Event Policy Registry (app.simulation.policy.registries
.event_policy), reusing the existing Signal → Delta rules.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.simulation.event_master import Event
from app.simulation.policy.models import RelationshipSnapshot

# magic-layer.md §3.2.1, §3.2.2 확정 우선순위.
STUDENT_MISSING = "STUDENT_MISSING"
CURSE_SPREAD = "CURSE_SPREAD"
MAGIC_EXPLOSION = "MAGIC_EXPLOSION"
RITUAL_FAILURE = "RITUAL_FAILURE"
MAGICAL_DISCOVERY = "MAGICAL_DISCOVERY"

SPECIAL_EVENT_PRIORITY: tuple[str, ...] = (
    STUDENT_MISSING,
    CURSE_SPREAD,
    MAGIC_EXPLOSION,
    RITUAL_FAILURE,
    MAGICAL_DISCOVERY,
)

# 확정 threshold (slice-5-integration.md §2).
STUDENT_MISSING_STRESS_THRESHOLD = 90
STUDENT_MISSING_STREAK_TICKS = 10
STUDENT_MISSING_STREAK_REQUIRED = 10
MAGIC_EXPLOSION_MIN_STUDENTS = 3
MAGIC_EXPLOSION_FATIGUE_THRESHOLD = 80
MAGIC_EXPLOSION_RATIO_THRESHOLD = 0.8
RITUAL_FAILURE_MIN_PARTICIPANTS = 4

# "나쁜 관계" threshold: 이 정확한 수치를 확정한 기존 문서/코드가 없어
# (magic-layer.md §3.2.1은 "평균 trust 낮음 OR tension 높음"이라고만 서술),
# app.domain.relationship_metrics.RELATIONSHIP_METRIC_RANGES의 기존 범위
# (trust: -100~100, tension: 0~100) 중간값을 기준으로 결정한다. 새 수치
# 체계를 만들지 않고 기존 range의 중립점을 그대로 재사용한 것이다.
RITUAL_FAILURE_TRUST_THRESHOLD = 0
RITUAL_FAILURE_TENSION_THRESHOLD = 50


@dataclass(frozen=True)
class AgentSnapshot:
    """Magic Layer용 world_state Agent snapshot."""

    agent_id: str
    agent_type: str  # "student" | "professor" | "user_persona"
    active_status: bool
    current_location_id: str | None
    fatigue: int
    is_cursed: bool
    # 최근 tick의 stress 값(오래된 → 최신 순). STUDENT_MISSING 스트릭 판정용.
    recent_stress: tuple[int, ...] = ()


@dataclass(frozen=True)
class SpecialEvent:
    """Magic Layer 특수 Event 후보 (source=magic_layer)."""

    event_subtype: str
    participant_agent_ids: tuple[str, ...]
    location_id: str | None
    tick: int
    title: str
    description: str = ""
    # STUDENT_MISSING 전용: 실종 후보(Student만). Task 3 persistence 입력의
    # missing_agent_ids로 그대로 전달 가능하도록 별도 보관한다 (§2 계약).
    missing_agent_ids: tuple[str, ...] = ()
    # CURSE_SPREAD 전용: 저주가 새로 전파되는 대상.
    newly_cursed_agent_ids: tuple[str, ...] = ()
    # 주변/영향 Agent (예: STUDENT_MISSING 주변 stress 상승 대상).
    affected_agent_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class MagicLayerResult:
    converted_events: tuple[Event, ...]
    special_events: tuple[SpecialEvent, ...]


def _is_missing_candidate(snapshot: AgentSnapshot) -> bool:
    if snapshot.agent_type != "student" or not snapshot.active_status:
        return False
    if len(snapshot.recent_stress) < STUDENT_MISSING_STREAK_TICKS:
        return False
    recent = snapshot.recent_stress[-STUDENT_MISSING_STREAK_TICKS:]
    hits = sum(1 for value in recent if value >= STUDENT_MISSING_STRESS_THRESHOLD)
    return hits >= STUDENT_MISSING_STREAK_REQUIRED


def _same_location_others(
    agent_id: str, location_id: str | None, snapshots: Sequence[AgentSnapshot]
) -> list[str]:
    if location_id is None:
        return []
    return sorted(
        snapshot.agent_id
        for snapshot in snapshots
        if snapshot.agent_id != agent_id
        and snapshot.active_status
        and snapshot.current_location_id == location_id
    )


class MagicLayer:
    """converted_events + special_events를 결정론적으로 생성한다."""

    def evaluate(
        self,
        *,
        tick: int,
        regular_events: Sequence[Event],
        agent_snapshots: Sequence[AgentSnapshot],
        relationship_snapshots: Sequence[RelationshipSnapshot] = (),
        lab_location_ids: frozenset[str] = frozenset(),
    ) -> MagicLayerResult:
        converted = tuple(self._convert(event) for event in regular_events)
        candidates = self._collect_candidates(
            tick=tick,
            agent_snapshots=agent_snapshots,
            relationship_snapshots=relationship_snapshots,
            lab_location_ids=lab_location_ids,
        )
        selected = self._select_by_priority(candidates)
        return MagicLayerResult(
            converted_events=converted,
            special_events=tuple(selected) if selected is not None else (),
        )

    @staticmethod
    def _convert(event: Event) -> Event:
        # Task 1 범위에서는 세계관 텍스트 변환(LLM)을 생략하고 원본 Event를
        # 그대로 전달한다 (magic-layer.md §4.2: LLM 실패 시 원본 반환과 동일한
        # 형태). source/effect 계약은 event_master 그대로 유지된다.
        return event

    def _collect_candidates(
        self,
        *,
        tick: int,
        agent_snapshots: Sequence[AgentSnapshot],
        relationship_snapshots: Sequence[RelationshipSnapshot],
        lab_location_ids: frozenset[str],
    ) -> dict[str, list[SpecialEvent]]:
        by_subtype: dict[str, list[SpecialEvent]] = {}
        by_subtype[STUDENT_MISSING] = self._student_missing_candidates(tick, agent_snapshots)
        by_subtype[CURSE_SPREAD] = self._curse_spread_candidates(tick, agent_snapshots)
        by_subtype[MAGIC_EXPLOSION] = self._magic_explosion_candidates(tick, agent_snapshots)
        by_subtype[RITUAL_FAILURE] = self._ritual_failure_candidates(
            tick, agent_snapshots, relationship_snapshots
        )
        by_subtype[MAGICAL_DISCOVERY] = self._magical_discovery_candidates(
            tick, agent_snapshots, lab_location_ids
        )
        return by_subtype

    @staticmethod
    def _select_by_priority(
        candidates: dict[str, list[SpecialEvent]],
    ) -> list[SpecialEvent] | None:
        for event_subtype in SPECIAL_EVENT_PRIORITY:
            found = candidates.get(event_subtype) or []
            if found:
                return found
        return None

    # ------------------------------------------------------------------
    # 1) STUDENT_MISSING
    # ------------------------------------------------------------------
    def _student_missing_candidates(
        self, tick: int, snapshots: Sequence[AgentSnapshot]
    ) -> list[SpecialEvent]:
        events: list[SpecialEvent] = []
        for snapshot in sorted(snapshots, key=lambda item: item.agent_id):
            if not _is_missing_candidate(snapshot):
                continue
            affected = _same_location_others(
                snapshot.agent_id, snapshot.current_location_id, snapshots
            )
            events.append(
                SpecialEvent(
                    event_subtype=STUDENT_MISSING,
                    participant_agent_ids=(snapshot.agent_id,),
                    location_id=snapshot.current_location_id,
                    tick=tick,
                    title="학생 실종",
                    missing_agent_ids=(snapshot.agent_id,),
                    affected_agent_ids=tuple(affected),
                )
            )
        return events

    # ------------------------------------------------------------------
    # 2) CURSE_SPREAD
    # ------------------------------------------------------------------
    def _curse_spread_candidates(
        self, tick: int, snapshots: Sequence[AgentSnapshot]
    ) -> list[SpecialEvent]:
        cursed_ids = {s.agent_id for s in snapshots if s.is_cursed}
        if not cursed_ids:
            return []
        events: list[SpecialEvent] = []
        for snapshot in sorted(snapshots, key=lambda item: item.agent_id):
            if snapshot.agent_id not in cursed_ids:
                continue
            contacts = [
                other_id
                for other_id in _same_location_others(
                    snapshot.agent_id, snapshot.current_location_id, snapshots
                )
                # 접촉했지만 이미 저주 상태인 대상은 새로 전파되지 않음 —
                # CURSED source 자체와 이미 CURSED인 대상에 중복 적용하지 않는다.
                if other_id not in cursed_ids
            ]
            if not contacts:
                continue
            events.append(
                SpecialEvent(
                    event_subtype=CURSE_SPREAD,
                    participant_agent_ids=(snapshot.agent_id, *contacts),
                    location_id=snapshot.current_location_id,
                    tick=tick,
                    title="저주 전파",
                    newly_cursed_agent_ids=tuple(contacts),
                    affected_agent_ids=tuple(contacts),
                )
            )
        return events

    # ------------------------------------------------------------------
    # 3) MAGIC_EXPLOSION
    # ------------------------------------------------------------------
    def _magic_explosion_candidates(
        self, tick: int, snapshots: Sequence[AgentSnapshot]
    ) -> list[SpecialEvent]:
        by_location: dict[str, list[AgentSnapshot]] = {}
        for snapshot in snapshots:
            if (
                snapshot.agent_type != "student"
                or not snapshot.active_status
                or snapshot.current_location_id is None
            ):
                continue
            by_location.setdefault(snapshot.current_location_id, []).append(snapshot)

        events: list[SpecialEvent] = []
        for location_id, students in sorted(by_location.items()):
            if len(students) < MAGIC_EXPLOSION_MIN_STUDENTS:
                continue
            high_fatigue = sum(
                1 for s in students if s.fatigue >= MAGIC_EXPLOSION_FATIGUE_THRESHOLD
            )
            if high_fatigue / len(students) < MAGIC_EXPLOSION_RATIO_THRESHOLD:
                continue
            participant_ids = tuple(sorted(s.agent_id for s in students))
            events.append(
                SpecialEvent(
                    event_subtype=MAGIC_EXPLOSION,
                    participant_agent_ids=participant_ids,
                    location_id=location_id,
                    tick=tick,
                    title="마법 폭발",
                    affected_agent_ids=participant_ids,
                )
            )
        return events

    # ------------------------------------------------------------------
    # 4) RITUAL_FAILURE
    # ------------------------------------------------------------------
    def _ritual_failure_candidates(
        self,
        tick: int,
        snapshots: Sequence[AgentSnapshot],
        relationship_snapshots: Sequence[RelationshipSnapshot],
    ) -> list[SpecialEvent]:
        by_location: dict[str, list[AgentSnapshot]] = {}
        for snapshot in snapshots:
            if not snapshot.active_status or snapshot.current_location_id is None:
                continue
            by_location.setdefault(snapshot.current_location_id, []).append(snapshot)

        events: list[SpecialEvent] = []
        for location_id, members in sorted(by_location.items()):
            if len(members) < RITUAL_FAILURE_MIN_PARTICIPANTS:
                continue
            member_ids = {m.agent_id for m in members}
            pair_metrics = [
                rel
                for rel in relationship_snapshots
                if rel.source_agent_id in member_ids and rel.target_agent_id in member_ids
            ]
            if not pair_metrics:
                continue
            avg_trust = sum(rel.trust for rel in pair_metrics) / len(pair_metrics)
            avg_tension = sum(rel.tension for rel in pair_metrics) / len(pair_metrics)
            bad_relationship = (
                avg_trust < RITUAL_FAILURE_TRUST_THRESHOLD
                or avg_tension > RITUAL_FAILURE_TENSION_THRESHOLD
            )
            if not bad_relationship:
                continue
            participant_ids = tuple(sorted(member_ids))
            events.append(
                SpecialEvent(
                    event_subtype=RITUAL_FAILURE,
                    participant_agent_ids=participant_ids,
                    location_id=location_id,
                    tick=tick,
                    title="의식 실패",
                    affected_agent_ids=participant_ids,
                )
            )
        return events

    # ------------------------------------------------------------------
    # 5) MAGICAL_DISCOVERY (다른 후보가 전혀 없을 때만 — 우선순위로 선택되므로
    #    여기서는 후보 존재 여부만 판정한다)
    # ------------------------------------------------------------------
    def _magical_discovery_candidates(
        self,
        tick: int,
        snapshots: Sequence[AgentSnapshot],
        lab_location_ids: frozenset[str],
    ) -> list[SpecialEvent]:
        if not lab_location_ids:
            return []
        by_location: dict[str, list[AgentSnapshot]] = {}
        for snapshot in snapshots:
            if (
                not snapshot.active_status
                or snapshot.current_location_id not in lab_location_ids
            ):
                continue
            by_location.setdefault(snapshot.current_location_id, []).append(snapshot)

        events: list[SpecialEvent] = []
        for location_id, members in sorted(by_location.items()):
            has_professor = any(m.agent_type == "professor" for m in members)
            has_student = any(m.agent_type == "student" for m in members)
            if not (has_professor and has_student):
                continue
            participant_ids = tuple(sorted(m.agent_id for m in members))
            events.append(
                SpecialEvent(
                    event_subtype=MAGICAL_DISCOVERY,
                    participant_agent_ids=participant_ids,
                    location_id=location_id,
                    tick=tick,
                    title="마법 발견",
                    affected_agent_ids=participant_ids,
                )
            )
        return events
