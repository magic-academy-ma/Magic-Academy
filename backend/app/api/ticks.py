from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import User
from app.services.simulations import require_owned_simulation
from app.simulation.tick_engine import (
    TickConflictError,
    TickEngine,
    TickResult,
    TickRollbackError,
)


class TickAdvanceResponse(BaseModel):
    status: str
    participant_ids: list[str]
    runtime_outputs: dict[str, dict]


def make_tick_router(engine: TickEngine) -> APIRouter:
    router = APIRouter(tags=["ticks"])

    @router.post(
        "/simulations/{simulation_id}/ticks/advance",
        response_model=TickAdvanceResponse,
    )
    async def advance_tick(
        simulation_id: UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_user_role),
    ) -> TickAdvanceResponse:
        require_owned_simulation(db, simulation_id, current_user)

        # TODO: PR #39 연결 후 DB에서 agents, events 조회 및 TickEngine 호출
        try:
            result: TickResult = await engine.run_tick(
                agents=[],
                event=None,  # type: ignore[arg-type]
                snapshot=None,  # type: ignore[arg-type]
            )
        except TickConflictError as exc:
            raise HTTPException(status_code=409, detail="Tick is already running") from exc
        except TickRollbackError as exc:
            raise HTTPException(status_code=500, detail="Tick rolled back due to runtime failure") from exc

        return TickAdvanceResponse(
            status=result.status,
            participant_ids=result.participant_ids,
            runtime_outputs=result.runtime_outputs,
        )

    return router
