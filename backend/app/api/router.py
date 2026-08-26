from fastapi import APIRouter

from app.api.agents import router as agents_router
from app.api.auth import router as auth_router
from app.api.events import router as events_router
from app.api.simulations import router as simulations_router
from app.api.ticks import router as ticks_router
from app.api.websockets import router as websockets_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(events_router)
api_router.include_router(agents_router)
api_router.include_router(simulations_router)
api_router.include_router(ticks_router)
api_router.include_router(websockets_router)
