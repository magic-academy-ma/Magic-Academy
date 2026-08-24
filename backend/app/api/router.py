from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.simulations import router as simulations_router
from app.api.ticks import router as ticks_router
from app.api.user_persona import router as user_persona_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(simulations_router)
api_router.include_router(ticks_router)
api_router.include_router(user_persona_router)
