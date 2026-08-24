from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import Agent, User, UserPersonaConfig
from app.services.simulations import require_owned_simulation
from app.services.user_persona import (
    InvalidPersonaAgentError,
    InvalidPersonalityConfigurationError,
    PersonaChangeConflictError,
    PersonaInput,
    PersonaRequiredError,
    UserPersonaService,
    personality_config,
)


router = APIRouter(prefix="/simulations/{simulation_id}", tags=["user-persona"])


class UserPersonaRequest(BaseModel):
    agent_id: UUID
    mbti_type: str
    personality_rule_version: str
    openness: int
    conscientiousness: int
    extraversion: int
    agreeableness: int
    emotional_stability: int


def error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "details": None},
    )


def persona_response(db: Session, config: UserPersonaConfig) -> dict:
    agent = db.get(Agent, config.agent_id)
    locked_at = agent.persona_locked_at if agent is not None else None
    return {
        "agent_id": str(config.agent_id),
        "simulation_id": str(config.simulation_id),
        "agent_type": "USER_PERSONA",
        "mbti_type": config.mbti_type,
        "openness": config.openness,
        "conscientiousness": config.conscientiousness,
        "extraversion": config.extraversion,
        "agreeableness": config.agreeableness,
        "emotional_stability": config.emotional_stability,
        "personality_rule_version": config.personality_rule_version,
        "status": "APPLIED",
        "locked": locked_at is not None,
        "persona_locked_at": locked_at.isoformat() if locked_at else None,
    }


@router.get("/user-persona/config")
def get_config(
    simulation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> dict:
    require_owned_simulation(db, simulation_id, current_user)
    return {"data": personality_config()}


@router.get("/user-persona")
def get_persona(
    simulation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
):
    require_owned_simulation(db, simulation_id, current_user)
    config = UserPersonaService().get_persona(db, simulation_id)
    if config is None:
        return error(404, "RESOURCE_NOT_FOUND", "User Persona is not configured")
    return {"data": persona_response(db, config)}


@router.post("/user-persona")
def set_persona(
    simulation_id: UUID,
    request: UserPersonaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
):
    require_owned_simulation(db, simulation_id, current_user)
    try:
        config = UserPersonaService().set_persona(
            db, simulation_id, PersonaInput(**request.model_dump())
        )
        db.commit()
        db.refresh(config)
    except InvalidPersonalityConfigurationError as exc:
        db.rollback()
        return error(400, "INVALID_PERSONALITY_CONFIGURATION", str(exc))
    except InvalidPersonaAgentError as exc:
        db.rollback()
        return error(400, "INVALID_PERSONA_AGENT", str(exc))
    except PersonaChangeConflictError as exc:
        db.rollback()
        return error(409, "CONFLICT", str(exc))
    except Exception:
        db.rollback()
        raise
    return {"data": persona_response(db, config)}


@router.post("/start")
def start_simulation(
    simulation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
):
    require_owned_simulation(db, simulation_id, current_user)
    try:
        simulation = UserPersonaService().start(db, simulation_id)
        db.commit()
        db.refresh(simulation)
    except PersonaRequiredError as exc:
        db.rollback()
        return error(400, "PERSONA_REQUIRED", str(exc))
    except (PersonaChangeConflictError, InvalidPersonaAgentError) as exc:
        db.rollback()
        return error(409, "CONFLICT", str(exc))
    except Exception:
        db.rollback()
        raise
    return {
        "data": {
            "id": str(simulation.id),
            "status": simulation.status,
            "started_at": simulation.started_at.isoformat(),
        }
    }
