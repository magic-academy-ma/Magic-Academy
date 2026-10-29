"""도전과제 모드 — Round 1 강제 Event 주입 헬퍼.

docs/04-feature-specs/challenge-mode-team-revival.md §4.3/§6: '역할 재배정'과
'직접 대화시킴' 선택지는 EventMaster의 자동 생성 로직(_generate_group_project /
_generate_meeting)을 거치지 않고, 지정된 참여자로 Event를 직접 구성한다.

'역할 재배정'은 별도 역할/서브그룹 필드 없이, build_forced_group_project()를
서로 다른 참여자 조합으로 두 번 호출해 GROUP_PROJECT를 분리하는 방식으로
구현한다 (GROUP_PROJECT에 역할 필드를 추가하지 않는다).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.simulation.event_master import IMPACT_LEVEL_TO_IMPORTANCE, Event, ImpactLevel


def _forced_event(
    *,
    event_type: str,
    key_prefix: str,
    tick: int,
    participant_agent_ids: Sequence[str],
    location_id: str,
    impact_level: ImpactLevel,
    title: str,
    description: str,
) -> Event:
    participant_ids = tuple(sorted(dict.fromkeys(participant_agent_ids)))
    if len(participant_ids) < 2:
        raise ValueError(f"{event_type} requires at least 2 participants")
    return Event(
        event_key=f"{key_prefix}:{'-'.join(participant_ids)}:{location_id}:{tick}",
        event_type=event_type,
        participant_agent_ids=participant_ids,
        location_id=location_id,
        tick=tick,
        impact_level=impact_level,
        importance=IMPACT_LEVEL_TO_IMPORTANCE[impact_level],
        title=title,
        description=description,
        source="challenge_controller",
    )


def build_forced_group_project(
    *,
    tick: int,
    participant_agent_ids: Sequence[str],
    location_id: str,
    impact_level: ImpactLevel = ImpactLevel.HIGH,
    title: str = "조별 과제",
    description: str = "",
) -> Event:
    return _forced_event(
        event_type="GROUP_PROJECT",
        key_prefix="challenge_group_project",
        tick=tick,
        participant_agent_ids=participant_agent_ids,
        location_id=location_id,
        impact_level=impact_level,
        title=title,
        description=description,
    )


def build_forced_meeting(
    *,
    tick: int,
    participant_agent_ids: Sequence[str],
    location_id: str,
    impact_level: ImpactLevel = ImpactLevel.HIGH,
    title: str = "대화",
    description: str = "",
) -> Event:
    return _forced_event(
        event_type="MEETING",
        key_prefix="challenge_meeting",
        tick=tick,
        participant_agent_ids=participant_agent_ids,
        location_id=location_id,
        impact_level=impact_level,
        title=title,
        description=description,
    )


def build_forced_festival(
    *,
    tick: int,
    participant_agent_ids: Sequence[str],
    location_id: str,
    impact_level: ImpactLevel = ImpactLevel.MEDIUM,
    title: str = "축제",
    description: str = "",
) -> Event:
    """도전과제2(challenge-mode-festival-booth.md §4.3) 축제 당일 부스 운영 Event."""
    return _forced_event(
        event_type="FESTIVAL",
        key_prefix="challenge_festival",
        tick=tick,
        participant_agent_ids=participant_agent_ids,
        location_id=location_id,
        impact_level=impact_level,
        title=title,
        description=description,
    )
