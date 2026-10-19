import asyncio
from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import Agent, ClubChallengeRun, User
from app.services.club_challenge import (
    ClubChallengeChoiceError,
    ClubChallengeCompletedError,
    ClubChallengeNotFoundError,
    advance_club_challenge,
    club_chapter_record,
    club_member_agents,
    get_owned_club_challenge,
    start_club_challenge,
)
from app.services.runtime_dependency import get_agent_runtime
from app.simulation.agent_runtime import AgentRuntime
from app.simulation.challenge.club_revival import (
    FinalStrategy,
    InternalConflictChoice,
    RecruitmentStrategy,
)

router = APIRouter(prefix="/challenges/club-revival", tags=["club-challenge"])


class ClubChallengeAdvanceRequest(BaseModel):
    choice: str | None = None


def _choice_options(next_tick: int) -> list[dict[str, str]]:
    choices = {
        3: [
            (InternalConflictChoice.MEDIATE, "중재하기", "두 회원이 직접 대화하도록 돕습니다."),
            (InternalConflictChoice.REASSIGN_ROLES, "역할 재배정", "강점에 맞게 업무를 다시 나눕니다."),
            (InternalConflictChoice.OBSERVE, "지켜보기", "개입하지 않고 두 회원의 선택을 지켜봅니다."),
        ],
        6: [
            (RecruitmentStrategy.PERFORMANCE_PROMOTION, "공연 홍보", "화려한 공연으로 후보들의 관심과 평판을 높입니다."),
            (RecruitmentStrategy.EXPERIENCE_EVENT, "체험 행사", "후보들이 직접 활동을 경험하게 해 더 많은 회원을 모집합니다."),
            (RecruitmentStrategy.PROFESSOR_REFERRAL, "교수 추천 요청", "에단 교수의 신뢰를 빌려 후보 한 명을 설득합니다."),
        ],
        9: [
            (FinalStrategy.PERFORMANCE_FOCUS, "성과 집중", "눈에 띄는 결과를 보여 최종 심사의 평판을 끌어올립니다."),
            (FinalStrategy.RELATIONSHIP_RECOVERY, "관계 회복", "회원 사이의 신뢰를 회복해 함께 심사에 나섭니다."),
            (FinalStrategy.SAFE_OPERATION, "안전 운영", "무리하지 않고 안정적인 행사 운영으로 심사를 준비합니다."),
        ],
    }.get(next_tick, [])
    return [
        {"value": value.value, "label": label, "description": description}
        for value, label, description in choices
    ]


def _story(next_tick: int) -> str | None:
    return {
        3: "두 회원의 갈등이 깊어졌습니다. 아델과 레오가 다시 힘을 합칠 수 있도록 개입 방식을 선택하세요.",
        6: "갈등은 일단락됐지만 두 명만으로는 동아리를 유지할 수 없습니다. 리아·카이·세라를 설득할 모집 전략을 선택하세요.",
        9: "새 회원들과 준비한 최종 심사가 다가왔습니다. 동아리의 마지막 인상을 결정할 운영 전략을 선택하세요.",
    }.get(next_tick)


def _response(db: Session, run: ClubChallengeRun, runtime_results=()) -> dict:
    current_round = min(3, (max(1, run.current_tick) - 1) // 3 + 1)
    tick_in_round = 0 if run.current_tick == 0 else (run.current_tick - 1) % 3 + 1
    next_tick = run.current_tick + 1
    students = list(
        db.scalars(
            select(Agent)
            .where(Agent.simulation_id == run.simulation_id, Agent.agent_type == "student")
            .order_by(Agent.fixture_key)
        )
    )
    chapter_record = club_chapter_record(run)
    return {
        "id": str(run.id),
        "simulation_id": str(run.simulation_id),
        "status": run.status,
        "current_tick": run.current_tick,
        "current_round": current_round,
        "tick_in_round": tick_in_round,
        "member_count": run.member_count,
        "reputation": run.reputation,
        "choices": run.choices,
        "ending": run.ending,
        "chapter_record": asdict(chapter_record) if chapter_record else None,
        "next_choice_options": _choice_options(next_tick),
        "next_story": _story(next_tick),
        "member_agent_ids": [
            str(agent.id) for agent in club_member_agents(students, run.member_count)
        ],
        "agent_results": [
            {
                "agent_id": str(item.agent_id),
                "status": item.status,
                "action_type": item.intent.action_type,
                "motivation_summary": item.intent.motivation_summary,
            }
            for item in runtime_results
        ],
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def start(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> dict:
    _, run = start_club_challenge(db, current_user)
    return {"data": _response(db, run)}


@router.get("/{run_id}")
def get_one(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> dict:
    try:
        run = get_owned_club_challenge(db, run_id, current_user)
    except ClubChallengeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Club challenge not found") from exc
    return {"data": _response(db, run)}


@router.post("/{run_id}/advance")
async def advance(
    run_id: UUID,
    request: ClubChallengeAdvanceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
    runtime: AgentRuntime = Depends(get_agent_runtime),
) -> dict:
    try:
        run, result = await asyncio.to_thread(
            advance_club_challenge,
            db,
            run_id=run_id,
            owner=current_user,
            runtime=runtime,
            choice=request.choice,
        )
    except ClubChallengeNotFoundError as exc:
        await asyncio.to_thread(db.rollback)
        raise HTTPException(status_code=404, detail="Club challenge not found") from exc
    except ClubChallengeChoiceError as exc:
        await asyncio.to_thread(db.rollback)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ClubChallengeCompletedError as exc:
        await asyncio.to_thread(db.rollback)
        raise HTTPException(status_code=409, detail="Club challenge already completed") from exc
    except Exception:
        await asyncio.to_thread(db.rollback)
        raise
    return {
        "data": _response(db, run, result.runtime_results)
    }
