from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.simulations import router as simulations_router
api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(simulations_router)
# TODO(issue-72): 실제 Agent Runtime 및 DB 연동 완료 후 재활성화
# api_router.include_router(make_tick_router(TickEngine(runtime=_stub_runtime)))
