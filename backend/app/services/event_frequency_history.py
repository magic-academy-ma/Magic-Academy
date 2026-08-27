"""Tick 시작 시 고정할 Event 파라미터 스냅샷을 구성한다.

``event_frequency`` / ``event_impact`` 정책 (mvp-tick-event-policy.md §4.3–§4.5)에
필요한 값들을 그 Tick에 고정된 ``SimulationConfig``와 기존 ``events`` /
``event_participants`` 기록에서 구한다. 별도 저장소를 추가하지 않는다.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import Event, EventParticipant, SimulationConfig
from app.services.event_magic_phase import EventParameters

# events.event_type은 소문자로 저장된다 (persist_event_batch).
_DYNAMIC_EVENT_TYPES: tuple[str, ...] = ("group_project", "meeting")
_COOLDOWN_TICKS_BY_IMPACT: dict[str, int] = {"low": 0, "medium": 1, "high": 3}
# Magic Layer 특수 사건 (magic_layer.py SPECIAL_EVENT_PRIORITY 와 동일, 소문자).
_MAGIC_EVENT_TYPES: tuple[str, ...] = (
    "student_missing",
    "curse_spread",
    "magic_explosion",
    "ritual_failure",
    "magical_discovery",
)


def build_event_parameters(
    db: Session,
    *,
    simulation_id: UUID,
    current_tick: int,
    current_day: int,
    config: SimulationConfig | None,
) -> EventParameters:
    """이번 Tick에 적용할 ``EventParameters``를 만든다.

    ``config``가 ``None``이면(아직 설정이 없는 시뮬레이션) 빈도 정책을 적용하지
    않는 기본값을 돌려준다 — Event Master는 기존과 동일하게 동작한다.
    """
    if config is None:
        return EventParameters()

    frequency_seed = f"{simulation_id}:{current_tick}:{config.version}"

    daily_dynamic_count = int(
        db.scalar(
            select(func.count())
            .select_from(Event)
            .where(
                Event.simulation_id == simulation_id,
                Event.event_type.in_(_DYNAMIC_EVENT_TYPES),
                Event.simulation_day == current_day,
            )
        )
        or 0
    )

    magic_daily_count = int(
        db.scalar(
            select(func.count())
            .select_from(Event)
            .where(
                Event.simulation_id == simulation_id,
                Event.event_type.in_(_MAGIC_EVENT_TYPES),
                Event.simulation_day == current_day,
            )
        )
        or 0
    )

    rows = db.execute(
        select(
            Event.event_type,
            Event.event_metadata["tick"].astext,
            Event.event_metadata["impact_level"].astext,
            Event.simulation_day,
            EventParticipant.agent_id,
        )
        .join(EventParticipant, EventParticipant.event_id == Event.id)
        .where(
            Event.simulation_id == simulation_id,
            Event.event_type.in_(_DYNAMIC_EVENT_TYPES),
        )
    ).all()

    cooldown_excluded: dict[str, set[str]] = {"GROUP_PROJECT": set(), "MEETING": set()}
    high_impact_today: set[str] = set()
    for event_type, tick_text, impact_level, simulation_day, agent_id in rows:
        impact = (impact_level or "medium").lower()
        agent_str = str(agent_id)
        type_key = event_type.upper()

        try:
            event_tick = int(tick_text) if tick_text is not None else None
        except (TypeError, ValueError):
            event_tick = None

        if event_tick is not None:
            cooldown = _COOLDOWN_TICKS_BY_IMPACT.get(impact, 0)
            if cooldown > 0 and 0 <= current_tick - event_tick < cooldown:
                cooldown_excluded.setdefault(type_key, set()).add(agent_str)

        if impact == "high" and simulation_day == current_day:
            high_impact_today.add(agent_str)

    return EventParameters(
        event_frequency=config.event_frequency,
        event_impact=config.event_impact,
        frequency_seed=frequency_seed,
        daily_dynamic_count=daily_dynamic_count,
        cooldown_excluded_agent_ids={
            key: frozenset(values) for key, values in cooldown_excluded.items()
        },
        high_impact_agent_ids_today=frozenset(high_impact_today),
        magic_enabled=config.magic_enabled,
        magic_frequency=config.magic_layer_frequency,
        magic_impact=config.magic_layer_impact,
        magic_frequency_seed=frequency_seed,
        magic_daily_count=magic_daily_count,
    )
