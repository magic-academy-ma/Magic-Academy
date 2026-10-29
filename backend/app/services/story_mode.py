"""스토리모드 한 학기 진행: CHAPTER 1 → 2 → 3 → 4 → FINAL.

챕터끼리는 독립 run이라 서로의 상황을 바꾸지 않는다. 이 서비스는 순서만 강제하고,
챕터가 끝나면 그 챕터의 활동 기록(ChapterRecord)을 모아 FINAL 엔딩을 정하고,
그 챕터에서 달성한 업적을 계정에 지급한다.
"""

from __future__ import annotations

import random
from dataclasses import asdict
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.achievements import ACHIEVEMENTS
from app.domain.models import StoryRun, User
from app.services import rumor_challenge
from app.services.achievements import grant_achievements
from app.services.club_challenge import (
    club_achievements,
    club_chapter_record,
    get_owned_club_challenge,
    start_club_challenge,
)
from app.services.festival_booth_chapter import (
    festival_booth_achievements,
    festival_booth_record,
    get_festival_booth,
    start_festival_booth,
)
from app.services.team_revival_chapter import (
    get_team_revival,
    start_team_revival,
    team_revival_achievements,
    team_revival_record,
)
from app.simulation.challenge.record import (
    STORY_CHAPTER_COUNT,
    ChapterGrade,
    ending_achievements,
    evaluate_final_ending,
)

FINAL_STAGE = STORY_CHAPTER_COUNT + 1


def get_owned_story(db: Session, story_id: UUID, owner: User, *, for_update: bool = False) -> StoryRun:
    query = select(StoryRun).where(StoryRun.id == story_id, StoryRun.owner_id == owner.id)
    if for_update:
        query = query.with_for_update()
    story = db.scalar(query)
    if story is None:
        raise HTTPException(404, "스토리 기록을 찾을 수 없습니다.")
    return story


def current_story(db: Session, owner: User) -> StoryRun | None:
    return db.scalar(
        select(StoryRun)
        .where(StoryRun.owner_id == owner.id)
        .order_by(StoryRun.created_at.desc())
        .limit(1)
    )


def start_story(db: Session, owner: User) -> StoryRun:
    story = StoryRun(id=uuid7(), owner_id=owner.id, chapter=1, chapter_run_ids={}, records={})
    db.add(story)
    db.commit()
    db.refresh(story)
    return story


def _start_chapter_run(db: Session, owner: User, chapter: int) -> UUID:
    if chapter == 1:
        data = rumor_challenge.start(
            db, owner, uuid7(), random.SystemRandom().randrange(2**63)
        )
        return UUID(data["id"])
    if chapter == 2:
        return start_team_revival(db, owner).id
    if chapter == 3:
        _, run = start_club_challenge(db, owner)
        return run.id
    return start_festival_booth(db, owner).id


def start_current_chapter(db: Session, owner: User, story_id: UUID) -> StoryRun:
    story = get_owned_story(db, story_id, owner, for_update=True)
    if story.chapter == FINAL_STAGE:
        raise HTTPException(409, "네 사건을 모두 마쳤습니다.")
    key = str(story.chapter)
    if key not in story.chapter_run_ids:
        run_id = _start_chapter_run(db, owner, story.chapter)
        # 챕터 시작 서비스가 commit하므로 잠금을 다시 잡고 이어서 기록한다.
        story = get_owned_story(db, story_id, owner, for_update=True)
        story.chapter_run_ids = {**story.chapter_run_ids, key: str(run_id)}
        db.commit()
        db.refresh(story)
    return story


def _chapter_record(db: Session, owner: User, chapter: int, run_id: UUID) -> dict | None:
    if chapter == 1:
        return rumor_challenge.owned(db, run_id, owner).private_state.get("chapter_record")
    if chapter == 2:
        record = team_revival_record(get_team_revival(db, run_id, owner))
    elif chapter == 3:
        record = club_chapter_record(get_owned_club_challenge(db, run_id, owner))
    else:
        record = festival_booth_record(get_festival_booth(db, run_id, owner))
    return asdict(record) if record else None


def _chapter_achievements(db: Session, owner: User, chapter: int, run_id: UUID) -> frozenset[str]:
    if chapter == 1:
        state = rumor_challenge.owned(db, run_id, owner).private_state
        return frozenset(state.get("achievements", []))
    if chapter == 2:
        return team_revival_achievements(db, get_team_revival(db, run_id, owner))
    if chapter == 3:
        return club_achievements(db, get_owned_club_challenge(db, run_id, owner))
    return festival_booth_achievements(get_festival_booth(db, run_id, owner))


def complete_current_chapter(
    db: Session, owner: User, story_id: UUID
) -> tuple[StoryRun, frozenset[str]]:
    """끝난 챕터의 기록을 남기고 다음 챕터로 넘긴다. 이번에 처음 달성한 업적 ID를 함께 돌려준다."""
    story = get_owned_story(db, story_id, owner, for_update=True)
    if story.chapter == FINAL_STAGE:
        return story, frozenset()
    key = str(story.chapter)
    run_id = story.chapter_run_ids.get(key)
    if run_id is None:
        raise HTTPException(409, "아직 이 사건을 맡지 않았습니다.")
    record = _chapter_record(db, owner, story.chapter, UUID(run_id))
    if record is None:
        raise HTTPException(409, "사건이 아직 끝나지 않았습니다.")
    achieved = set(_chapter_achievements(db, owner, story.chapter, UUID(run_id)))
    story.records = {**story.records, key: record}
    story.chapter += 1
    if story.chapter == FINAL_STAGE:
        story.final_ending = evaluate_final_ending(
            [ChapterGrade(story.records[str(n)]["grade"]) for n in range(1, FINAL_STAGE)]
        ).value
        story.status = "completed"
        story.completed_at = datetime.now(timezone.utc)
    achieved |= ending_achievements(
        cleared_chapters=len(story.records), semester_completed=story.status == "completed"
    )
    # 기록 저장과 업적 지급을 한 transaction으로 commit한다.
    granted = grant_achievements(db, owner, achieved)
    db.commit()
    db.refresh(story)
    return story, frozenset(granted)


def story_response(story: StoryRun, new_achievements: frozenset[str] = frozenset()) -> dict:
    return {
        "id": str(story.id),
        "chapter": story.chapter,
        "status": story.status,
        "chapter_run_id": story.chapter_run_ids.get(str(story.chapter)),
        "records": [story.records[str(n)] for n in range(1, FINAL_STAGE) if str(n) in story.records],
        "final_ending": story.final_ending,
        "new_achievements": [
            {"id": achievement.id, "name": achievement.name}
            for achievement in ACHIEVEMENTS
            if achievement.id in new_achievements
        ],
    }
