"""계정별 업적 지급과 조회.

지급은 호출한 쪽의 트랜잭션 안에서 이뤄진다(commit하지 않는다). 챕터 결과 저장과
업적 지급이 함께 commit되거나 함께 rollback되게 하기 위해서다.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.achievements import ACHIEVEMENTS, ACHIEVEMENTS_BY_ID
from app.domain.models import (
    Agent,
    Event,
    EventParticipant,
    RumorChallengeRun,
    Simulation,
    User,
    UserAchievement,
)
from app.services.simulations import require_owned_simulation
from app.simulation.free_mode_achievements import (
    AgentStatus,
    event_witness_achievements,
    inspector_achievements,
    tick_achievements,
)


def grant_achievements(db: Session, owner: User, achievement_ids: Iterable[str]) -> set[str]:
    """업적을 지급하고, 이번에 처음 달성한 업적 ID만 돌려준다. 이미 달성한 업적은 무시한다."""
    ids = set(achievement_ids)
    unknown = ids - ACHIEVEMENTS_BY_ID.keys()
    if unknown:
        raise ValueError(f"unknown achievement ids: {sorted(unknown)}")
    if not ids:
        return set()
    statement = (
        insert(UserAchievement)
        .values([{"id": uuid4(), "user_id": owner.id, "achievement_id": i} for i in sorted(ids)])
        .on_conflict_do_nothing(constraint="uq_user_achievements_user_achievement")
        .returning(UserAchievement.achievement_id)
    )
    return set(db.scalars(statement).all())


def _is_story_simulation(db: Session, simulation_id: UUID) -> bool:
    return db.scalar(
        select(RumorChallengeRun.id).where(RumorChallengeRun.simulation_id == simulation_id)
    ) is not None


def grant_free_tick_achievements(
    db: Session,
    simulation: Simulation,
    before: Mapping[str, AgentStatus],
    agent_statuses: Iterable[dict],
) -> set[str]:
    """자유 모드 Tick 저장 직후 저주 업적을 판정해 지급한다 (achievements.md §5.1)."""
    if _is_story_simulation(db, simulation.id):
        return set()
    after = {
        item["agent_id"]: AgentStatus(item["active_status"], item["cursed_until_tick"] is not None)
        for item in agent_statuses
    }
    achieved = tick_achievements({k: v for k, v in before.items() if k in after}, after)
    if not achieved:
        return set()
    return grant_achievements(db, db.get(User, simulation.owner_id), achieved)


def grant_inspector_achievements(
    db: Session, owner: User, simulation_id: UUID, agent_id: UUID
) -> set[str]:
    """플레이어가 Inspector를 연 Agent가 돌아온 학생이면 귀환 목격 업적을 지급한다."""
    simulation = require_owned_simulation(db, simulation_id, owner)
    agent = db.get(Agent, agent_id)
    if agent is None or agent.simulation_id != simulation.id or _is_story_simulation(db, simulation.id):
        return set()
    was_missing = db.scalar(
        select(EventParticipant.id)
        .join(Event, Event.id == EventParticipant.event_id)
        .where(
            Event.simulation_id == simulation.id,
            Event.event_type == "student_missing",
            EventParticipant.agent_id == agent.id,
        )
        .limit(1)
    ) is not None
    return grant_achievements(
        db, owner, inspector_achievements(was_missing=was_missing, active_status=agent.active_status)
    )


def grant_event_witness_achievements(
    db: Session, owner: User, simulation_id: UUID, event_id: UUID
) -> set[str]:
    """플레이어가 Event Log에서 누른 이벤트가 마법 발견이면 발견 목격 업적을 지급한다."""
    simulation = require_owned_simulation(db, simulation_id, owner)
    event = db.get(Event, event_id)
    if event is None or event.simulation_id != simulation.id or _is_story_simulation(db, simulation.id):
        return set()
    return grant_achievements(db, owner, event_witness_achievements(event.event_type))


def list_achievements(db: Session, owner: User) -> list[dict]:
    """카탈로그 순서대로 전체 업적과 이 계정의 달성 여부를 돌려준다."""
    achieved_at = dict(
        db.execute(
            select(UserAchievement.achievement_id, UserAchievement.achieved_at).where(
                UserAchievement.user_id == owner.id
            )
        ).all()
    )
    return [
        {
            "id": achievement.id,
            "name": achievement.name,
            "mode": achievement.mode.value,
            "group": achievement.group,
            "kind": achievement.kind.value,
            "condition": achievement.condition,
            "achieved": achievement.id in achieved_at,
            "achieved_at": achieved_at[achievement.id].isoformat() if achievement.id in achieved_at else None,
        }
        for achievement in ACHIEVEMENTS
    ]
