from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.simulations import router as simulations_router
from app.api.ticks import make_tick_router
from app.simulation.tick_engine import TickEngine


async def _stub_runtime(agent, event, snapshot):
    # TODO(issue-72): Task 3 완료 후 실제 Agent Runtime으로 교체
    return {}


_tick_engine = TickEngine(runtime=_stub_runtime)

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(simulations_router)
api_router.include_router(make_tick_router(_tick_engine))
