"""스토리모드 한 학기 진행: CHAPTER 1 → 2 → 3 → 4 → FINAL.

챕터끼리는 독립 run이라 서로의 상황을 바꾸지 않는다. 이 서비스는 순서만 강제하고,
챕터가 끝나면 그 챕터의 활동 기록(ChapterRecord)을 모아 FINAL 엔딩을 정한다.
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

from app.domain.models import StoryRun, User
from app.services import rumor_challenge
from app.services.club_challenge import (
    club_chapter_record,
    get_owned_club_challenge,
    start_club_challenge,
)
from app.services.festival_booth_chapter import (
    festival_booth_record,
    get_festival_booth,
    start_festival_booth,
)
from app.services.team_revival_chapter import (
    get_team_revival,
    start_team_revival,
    team_revival_record,
)
from app.simulation.challenge.record import (
    STORY_CHAPTER_COUNT,
    ChapterGrade,
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


def complete_current_chapter(db: Session, owner: User, story_id: UUID) -> StoryRun:
    story = get_owned_story(db, story_id, owner, for_update=True)
    if story.chapter == FINAL_STAGE:
        return story
    key = str(story.chapter)
    run_id = story.chapter_run_ids.get(key)
    if run_id is None:
        raise HTTPException(409, "아직 이 사건을 맡지 않았습니다.")
    record = _chapter_record(db, owner, story.chapter, UUID(run_id))
    if record is None:
        raise HTTPException(409, "사건이 아직 끝나지 않았습니다.")
    story.records = {**story.records, key: record}
    story.chapter += 1
    if story.chapter == FINAL_STAGE:
        story.final_ending = evaluate_final_ending(
            [ChapterGrade(story.records[str(n)]["grade"]) for n in range(1, FINAL_STAGE)]
        ).value
        story.status = "completed"
        story.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(story)
    return story


def story_response(story: StoryRun) -> dict:
    return {
        "id": str(story.id),
        "chapter": story.chapter,
        "status": story.status,
        "chapter_run_id": story.chapter_run_ids.get(str(story.chapter)),
        "records": [story.records[str(n)] for n in range(1, FINAL_STAGE) if str(n) in story.records],
        "final_ending": story.final_ending,
    }
