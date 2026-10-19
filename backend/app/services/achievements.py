"""계정별 업적 지급과 조회.

지급은 호출한 쪽의 트랜잭션 안에서 이뤄진다(commit하지 않는다). 챕터 결과 저장과
업적 지급이 함께 commit되거나 함께 rollback되게 하기 위해서다.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.achievements import ACHIEVEMENTS, ACHIEVEMENTS_BY_ID
from app.domain.models import User, UserAchievement


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
