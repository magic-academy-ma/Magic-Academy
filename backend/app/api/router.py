from fastapi import APIRouter

from app.api.agents import router as agents_router
from app.api.auth import router as auth_router
from app.api.dialogues import router as dialogues_router
from app.api.events import router as events_router
from app.api.simulation_history import router as simulation_history_router
from app.api.simulation_imports import router as simulation_imports_router
from app.api.simulation_logs import router as simulation_logs_router
from app.api.simulation_shares import router as simulation_shares_router
from app.api.simulations import router as simulations_router
from app.api.ticks import router as ticks_router
from app.api.user_persona import router as user_persona_router
from app.api.websockets import router as websockets_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(events_router)
api_router.include_router(agents_router)
api_router.include_router(simulations_router)
api_router.include_router(simulation_history_router)
api_router.include_router(simulation_shares_router)
api_router.include_router(simulation_imports_router)
api_router.include_router(simulation_logs_router)
api_router.include_router(dialogues_router)
api_router.include_router(ticks_router)
api_router.include_router(user_persona_router)
api_router.include_router(websockets_router)
