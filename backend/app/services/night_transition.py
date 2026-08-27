"""야간 전환 서비스.

수동 밤 스킵(``POST /simulations/{id}/night/skip``)과 ``advance_manual_tick``의
야간 통과가 공용으로 사용한다.
계약: ``docs/04-feature-specs/mvp-tick-event-policy.md`` §4.2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.domain.models import Simulation

logger = logging.getLogger(__name__)

_SKIPPABLE_STATUSES = frozenset({"running", "paused"})


class NightSkipNotAllowedError(Exception):
    """status가 밤 스킵을 허용하지 않는 상태(``ready`` / ``completed`` / ``failed``)."""


class NightSkipConflictError(Exception):
    """Tick 실행 중이거나, 야간 대기 상태가 아니며 이미 전환 완료된 상태도 아님."""


@dataclass(frozen=True)
class NightSkipOutcome:
    simulation: Simulation
    transitioned: bool  # True = 실제 전환 수행(WS 발행 대상), False = 멱등(무변경)


def apply_night_transition(db: Session, simulation: Simulation) -> None:
    """EVENING 이후 야간을 건너뛰고 다음 날 MORNING으로 전환한다.

    - ``current_tick``은 변경하지 않는다.
    - ``current_day += 1``.
    - ``night_waiting = False``.
    - 야간 회복(Agent 상태 변경)은 MVP 범위 밖이라 여기서 수행하지 않는다(회복량 0).
      후속 이슈에서 이 함수 안에 회복 단계를 추가한다.
    """
    simulation.current_day += 1
    simulation.night_waiting = False
    db.flush()


def skip_night(db: Session, simulation: Simulation) -> NightSkipOutcome:
    """수동 밤 스킵. 인증·소유권 검사는 호출부(엔드포인트)가 이미 수행한 상태다.

    ``docs/04-feature-specs/mvp-tick-event-policy.md`` §3.1 매트릭스를 구현한다.
    """
    locked = db.scalar(
        select(
            text("pg_try_advisory_xact_lock(hashtextextended(:simulation_id, 0))")
        ).params(simulation_id=str(simulation.id))
    )
    if not locked:
        raise NightSkipConflictError("a tick is currently running for this simulation")

    db.refresh(simulation, with_for_update=True)

    if simulation.status not in _SKIPPABLE_STATUSES:
        raise NightSkipNotAllowedError(
            f"night skip is not allowed while simulation status is {simulation.status}"
        )

    if simulation.night_waiting:
        apply_night_transition(db, simulation)
        return NightSkipOutcome(simulation=simulation, transitioned=True)

    current_tick = simulation.current_tick
    if current_tick > 0 and current_tick % 3 == 0:
        derived_day = ((current_tick - 1) // 3) + 1
        if simulation.current_day == derived_day + 1:
            # 직전 night/skip으로 이미 전환이 완료된 상태 — 멱등 재호출.
            return NightSkipOutcome(simulation=simulation, transitioned=False)
        logger.warning(
            "night/skip on inconsistent state "
            "(simulation_id=%s, current_tick=%s, current_day=%s, night_waiting=False)",
            simulation.id,
            current_tick,
            simulation.current_day,
        )

    raise NightSkipConflictError("simulation is not in a night-waiting state")
