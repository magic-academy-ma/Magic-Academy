import asyncio
from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import StoryChapterRun, User
from app.services import story_mode
from app.services.festival_booth_chapter import (
    advance_festival_booth,
    festival_booth_record,
    festival_booth_response,
    get_festival_booth,
)
from app.services.runtime_dependency import get_agent_runtime
from app.services.story_chapter_common import (
    StoryChapterChoiceError,
    StoryChapterCompletedError,
    StoryChapterNotFoundError,
    public_results,
    round_of,
)
from app.services.team_revival_chapter import (
    advance_team_revival,
    get_team_revival,
    team_revival_record,
    team_revival_response,
)
from app.simulation.agent_runtime import AgentRuntime

router = APIRouter(prefix="/story", tags=["story-mode"])


class TeamRevivalAdvanceRequest(BaseModel):
    choice: str | None = None


class FestivalBoothAdvanceRequest(BaseModel):
    choice: str | None = None
    concept: str | None = None
    roles: dict[str, str] | None = None
    help_agent_id: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
def start(db: Session = Depends(get_db), owner: User = Depends(require_user_role)) -> dict:
    return {"data": story_mode.story_response(story_mode.start_story(db, owner))}


@router.get("/current")
def current(db: Session = Depends(get_db), owner: User = Depends(require_user_role)) -> dict:
    story = story_mode.current_story(db, owner)
    return {"data": story_mode.story_response(story) if story else None}


@router.post("/{story_id}/chapter/start")
def start_chapter(
    story_id: UUID, db: Session = Depends(get_db), owner: User = Depends(require_user_role)
) -> dict:
    return {"data": story_mode.story_response(story_mode.start_current_chapter(db, owner, story_id))}


@router.post("/{story_id}/chapter/complete")
def complete_chapter(
    story_id: UUID, db: Session = Depends(get_db), owner: User = Depends(require_user_role)
) -> dict:
    story, new_achievements = story_mode.complete_current_chapter(db, owner, story_id)
    return {"data": story_mode.story_response(story, new_achievements)}


def _chapter_response(run: StoryChapterRun, record, extra: dict) -> dict:
    return {
        "id": str(run.id),
        "simulation_id": str(run.simulation_id),
        "chapter": run.chapter,
        "status": run.status,
        "current_tick": run.current_tick,
        "current_round": round_of(run.current_tick),
        "ending": run.ending,
        "chapter_record": asdict(record) if record else None,
        "agent_results": public_results(run),
        **extra,
    }


def _team_revival(run: StoryChapterRun) -> dict:
    return _chapter_response(run, team_revival_record(run), team_revival_response(run))


def _festival_booth(run: StoryChapterRun) -> dict:
    return _chapter_response(run, festival_booth_record(run), festival_booth_response(run))


async def _advance(db: Session, call):
    try:
        return await asyncio.to_thread(call)
    except StoryChapterNotFoundError as exc:
        await asyncio.to_thread(db.rollback)
        raise HTTPException(status_code=404, detail="Story chapter not found") from exc
    except StoryChapterChoiceError as exc:
        await asyncio.to_thread(db.rollback)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StoryChapterCompletedError as exc:
        await asyncio.to_thread(db.rollback)
        raise HTTPException(status_code=409, detail="Story chapter already completed") from exc
    except Exception:
        await asyncio.to_thread(db.rollback)
        raise


@router.get("/chapters/team-revival/{run_id}")
def get_team_revival_chapter(
    run_id: UUID, db: Session = Depends(get_db), owner: User = Depends(require_user_role)
) -> dict:
    try:
        return {"data": _team_revival(get_team_revival(db, run_id, owner))}
    except StoryChapterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Story chapter not found") from exc


@router.post("/chapters/team-revival/{run_id}/advance")
async def advance_team_revival_chapter(
    run_id: UUID,
    request: TeamRevivalAdvanceRequest,
    db: Session = Depends(get_db),
    owner: User = Depends(require_user_role),
    runtime: AgentRuntime = Depends(get_agent_runtime),
) -> dict:
    run = await _advance(
        db,
        lambda: advance_team_revival(
            db, run_id=run_id, owner=owner, runtime=runtime, choice=request.choice
        ),
    )
    return {"data": _team_revival(run)}


@router.get("/chapters/festival-booth/{run_id}")
def get_festival_booth_chapter(
    run_id: UUID, db: Session = Depends(get_db), owner: User = Depends(require_user_role)
) -> dict:
    try:
        return {"data": _festival_booth(get_festival_booth(db, run_id, owner))}
    except StoryChapterNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Story chapter not found") from exc


@router.post("/chapters/festival-booth/{run_id}/advance")
async def advance_festival_booth_chapter(
    run_id: UUID,
    request: FestivalBoothAdvanceRequest,
    db: Session = Depends(get_db),
    owner: User = Depends(require_user_role),
    runtime: AgentRuntime = Depends(get_agent_runtime),
) -> dict:
    run = await _advance(
        db,
        lambda: advance_festival_booth(
            db,
            run_id=run_id,
            owner=owner,
            runtime=runtime,
            choice=request.choice,
            concept=request.concept,
            roles=request.roles,
            help_agent_id=request.help_agent_id,
        ),
    )
    return {"data": _festival_booth(run)}
