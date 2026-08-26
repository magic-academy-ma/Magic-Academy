from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.models import Simulation, UserPersonaConfig
from app.repositories import user_personas


RULE_VERSION = "mbti-big-five-v0.1"
TRAITS = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "emotional_stability",
)
MBTI_RULES = {
    "ISTJ": {
        "openness": {"min": -45, "default": -25, "max": 5},
        "conscientiousness": {"min": -15, "default": 25, "max": 45},
        "extraversion": {"min": -45, "default": -25, "max": 5},
        "agreeableness": {"min": -45, "default": -20, "max": 15},
        "emotional_stability": {"min": -50, "default": 0, "max": 50},
    },
    "INFP": {
        "openness": {"min": -5, "default": 25, "max": 45},
        "conscientiousness": {"min": -45, "default": -25, "max": 15},
        "extraversion": {"min": -45, "default": -25, "max": 5},
        "agreeableness": {"min": -15, "default": 20, "max": 45},
        "emotional_stability": {"min": -50, "default": 0, "max": 50},
    },
    "ENTJ": {
        "openness": {"min": -5, "default": 25, "max": 45},
        "conscientiousness": {"min": -15, "default": 25, "max": 45},
        "extraversion": {"min": -5, "default": 25, "max": 45},
        "agreeableness": {"min": -45, "default": -20, "max": 15},
        "emotional_stability": {"min": -50, "default": 0, "max": 50},
    },
    "ESTP": {
        "openness": {"min": -45, "default": -25, "max": 5},
        "conscientiousness": {"min": -45, "default": -25, "max": 15},
        "extraversion": {"min": -5, "default": 25, "max": 45},
        "agreeableness": {"min": -45, "default": -20, "max": 15},
        "emotional_stability": {"min": -50, "default": 0, "max": 50},
    },
    "ESFJ": {
        "openness": {"min": -45, "default": -25, "max": 5},
        "conscientiousness": {"min": -15, "default": 25, "max": 45},
        "extraversion": {"min": -5, "default": 25, "max": 45},
        "agreeableness": {"min": -15, "default": 20, "max": 45},
        "emotional_stability": {"min": -50, "default": 0, "max": 50},
    },
}


class PersonaError(ValueError):
    pass


class InvalidPersonaAgentError(PersonaError):
    pass


class InvalidPersonalityConfigurationError(PersonaError):
    pass


class PersonaChangeConflictError(PersonaError):
    pass


class PersonaRequiredError(PersonaError):
    pass


@dataclass(frozen=True)
class PersonaInput:
    agent_id: UUID
    mbti_type: str
    personality_rule_version: str
    openness: int
    conscientiousness: int
    extraversion: int
    agreeableness: int
    emotional_stability: int


def personality_config() -> dict:
    return {
        "rule_version": RULE_VERSION,
        "global_min": -50,
        "global_max": 50,
        "step": 5,
        "mbti_rules": MBTI_RULES,
    }


class UserPersonaService:
    def set_persona(
        self,
        session: Session,
        simulation_id: UUID,
        persona: PersonaInput,
    ) -> UserPersonaConfig:
        simulation = self._require_ready_simulation(session, simulation_id)
        if simulation.started_at is not None or simulation.status != "ready":
            raise PersonaChangeConflictError("Persona is locked after Simulation start")
        if user_personas.get_student(session, simulation_id, persona.agent_id) is None:
            raise InvalidPersonaAgentError("Persona must select a Student in this Simulation")
        self._validate(persona)
        values = asdict(persona)
        values.pop("agent_id")
        return user_personas.upsert_config(
            session,
            simulation_id,
            {"agent_id": persona.agent_id, **values},
        )

    def get_persona(
        self, session: Session, simulation_id: UUID
    ) -> UserPersonaConfig | None:
        return user_personas.get_config(session, simulation_id)

    def start(self, session: Session, simulation_id: UUID) -> Simulation:
        simulation = self._require_ready_simulation(session, simulation_id)
        if simulation.started_at is not None or simulation.status != "ready":
            raise PersonaChangeConflictError("Simulation is already started")
        config = user_personas.get_config(session, simulation_id)
        if config is None:
            raise PersonaRequiredError("User Persona must be configured before start")
        agent = user_personas.get_student(session, simulation_id, config.agent_id)
        if agent is None:
            raise InvalidPersonaAgentError("Configured Persona Student is unavailable")
        locked_at = datetime.now(timezone.utc)
        for name in ("mbti_type", *TRAITS):
            setattr(agent, name, getattr(config, name))
        agent.persona_locked_at = locked_at
        simulation.status = "running"
        simulation.started_at = locked_at
        session.flush()
        return simulation

    @staticmethod
    def _require_ready_simulation(
        session: Session, simulation_id: UUID
    ) -> Simulation:
        simulation = user_personas.get_simulation_for_update(session, simulation_id)
        if simulation is None:
            raise PersonaRequiredError("Simulation not found")
        return simulation

    @staticmethod
    def _validate(persona: PersonaInput) -> None:
        if persona.personality_rule_version != RULE_VERSION:
            raise InvalidPersonalityConfigurationError("Unsupported rule version")
        rules = MBTI_RULES.get(persona.mbti_type)
        if rules is None:
            raise InvalidPersonalityConfigurationError("Unsupported MBTI type")
        for trait in TRAITS:
            value = getattr(persona, trait)
            bounds = rules[trait]
            if value % 5 != 0 or not bounds["min"] <= value <= bounds["max"]:
                raise InvalidPersonalityConfigurationError(
                    f"{trait} must follow the {persona.mbti_type} rule"
                )
