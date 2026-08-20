from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.simulations import router as simulations_router
from app.api.ticks import make_tick_router
from app.simulation.tick_engine import TickEngine

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(simulations_router)

# TODO: PR #39 연결 후 실제 runtime 콜백으로 교체
async def _stub_runtime(agents, event, snapshot):  # type: ignore[no-untyped-def]
    return {}

api_router.include_router(make_tick_router(TickEngine(runtime=_stub_runtime)))
