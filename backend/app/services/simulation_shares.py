import inspect
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.core.config import get_settings
from app.domain.models import (
    Agent,
    AgentState,
    Location,
    Organization,
    OrganizationMembership,
    ProfessorProfile,
    Relationship,
    Simulation,
    SimulationConfig,
    SimulationShare,
    StudentProfile,
    User,
    UserPersonaConfig,
)
from app.repositories.simulation_shares import (
    get_active_share_by_simulation,
    get_share_by_id,
    list_public_shares,
)
from app.simulation.agent_runtime import AgentRuntime

SCHEMA_VERSION = "slice7-share-v1"
VISIBILITIES = ("private", "unlisted", "public")
# Reproducibility identifier for the prompt template currently used by the
# Agent Runtime, read from its own default so the two never drift apart.
DEFAULT_PROMPT_VERSION = inspect.signature(AgentRuntime.__init__).parameters["prompt_version"].default


class ShareError(Exception):
    """Base class for Slice 7 sharing domain errors."""


class ShareNotFoundError(ShareError):
    pass


class ShareAccessDeniedError(ShareError):
    pass


class SimulationNotReadyForShareError(ShareError):
    pass


def _organization_fixture_key(organization: Organization) -> str:
    # Organization has no dedicated fixture identifier column. `(organization_type,
    # name)` is already unique per Simulation (uq_organizations_simulation_type_name),
    # so it is a stable, non-empty identifier we can derive without a schema change.
    return f"{organization.organization_type}:{organization.name}"


def _agent_role_profile(
    agent: Agent,
    student_profiles: dict[UUID, StudentProfile],
    professor_profiles: dict[UUID, ProfessorProfile],
) -> dict[str, Any]:
    student = student_profiles.get(agent.id)
    if student is not None:
        return {
            "profile_type": "student",
            "grade": student.grade,
            "interest_field": student.interest_field,
        }
    professor = professor_profiles.get(agent.id)
    if professor is not None:
        return {
            "profile_type": "professor",
            "academic_rank": professor.academic_rank,
            "specialty": professor.specialty,
        }
    return {"profile_type": agent.agent_type}


def build_export_payload(
    db: Session, simulation: Simulation, *, title: str, description: str | None
) -> dict[str, Any]:
    """Assemble the immutable `slice7-share-v1` export payload from DB state.

    Only fields explicitly listed in the Slice 7 contract
    (docs/04-feature-specs/slice-7-config-sharing-import-deployment.md §4.2) are
    included. Secrets, prompts, chain-of-thought and execution/replay history are
    never read here.
    """
    config = db.scalar(
        select(SimulationConfig)
        .where(SimulationConfig.simulation_id == simulation.id)
        .order_by(SimulationConfig.version.desc())
        .limit(1)
    )
    persona_config = db.get(UserPersonaConfig, simulation.id)

    agents = list(
        db.scalars(
            select(Agent)
            .where(Agent.simulation_id == simulation.id, Agent.deleted_at.is_(None))
            .order_by(Agent.fixture_key)
        )
    )
    agent_ids = [agent.id for agent in agents]
    agent_fixture_by_id = {agent.id: agent.fixture_key for agent in agents}

    locations = list(
        db.scalars(select(Location).where(Location.simulation_id == simulation.id).order_by(Location.code))
    )
    student_profiles = {
        row.agent_id: row
        for row in db.scalars(select(StudentProfile).where(StudentProfile.agent_id.in_(agent_ids)))
    }
    professor_profiles = {
        row.agent_id: row
        for row in db.scalars(select(ProfessorProfile).where(ProfessorProfile.agent_id.in_(agent_ids)))
    }
    states = {
        row.agent_id: row
        for row in db.scalars(select(AgentState).where(AgentState.simulation_id == simulation.id))
    }
    location_code_by_id = {location.id: location.code for location in locations}

    organizations = list(
        db.scalars(
            select(Organization)
            .where(Organization.simulation_id == simulation.id, Organization.deleted_at.is_(None))
            .order_by(Organization.organization_type, Organization.name)
        )
    )
    organization_fixture_by_id = {org.id: _organization_fixture_key(org) for org in organizations}

    memberships = list(
        db.scalars(
            select(OrganizationMembership)
            .where(
                OrganizationMembership.simulation_id == simulation.id,
                OrganizationMembership.left_at.is_(None),
            )
            .order_by(OrganizationMembership.id)
        )
    )
    relationships = list(
        db.scalars(
            select(Relationship)
            .where(Relationship.simulation_id == simulation.id)
            .order_by(Relationship.source_agent_id, Relationship.target_agent_id)
        )
    )

    persona_fixture_key = None
    if persona_config is not None:
        persona_fixture_key = agent_fixture_by_id.get(persona_config.agent_id)

    settings = get_settings()
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "share": {
            "title": title,
            "description": description,
            "visibility": None,  # filled in by the caller once visibility is known
        },
        "simulation": {
            "name": simulation.name,
            "magic_enabled": simulation.magic_enabled,
            "settings_version": str(config.version) if config is not None else None,
            "execution_seed": uuid7().int & ((1 << 63) - 1),
            "model_version": settings.agent_runtime_model,
            "prompt_version": DEFAULT_PROMPT_VERSION,
            "policy_version": config.policy_version if config is not None else None,
            "resolver_version": config.resolver_version if config is not None else None,
            "user_persona_fixture_key": persona_fixture_key,
        },
        "locations": [
            {"code": location.code, "name": location.name, "is_active": location.is_active}
            for location in locations
        ],
        "organizations": [
            {
                "fixture_key": organization_fixture_by_id[organization.id],
                "organization_type": organization.organization_type,
                "name": organization.name,
                "description": organization.description,
                "is_active": organization.is_active,
            }
            for organization in organizations
        ],
        "agents": [
            {
                "fixture_key": agent.fixture_key,
                "fixture_version": agent.fixture_version,
                "agent_type": agent.agent_type,
                "name": agent.name,
                "gender": agent.gender,
                "personality_type": agent.personality_type,
                "mbti_type": agent.mbti_type,
                "traits": {
                    "openness": agent.openness,
                    "conscientiousness": agent.conscientiousness,
                    "extraversion": agent.extraversion,
                    "agreeableness": agent.agreeableness,
                    "emotional_stability": agent.emotional_stability,
                },
                "role_profile": _agent_role_profile(agent, student_profiles, professor_profiles),
                "state": (
                    {
                        "location_code": (
                            location_code_by_id.get(states[agent.id].location_id)
                            if agent.id in states
                            else None
                        ),
                        "hunger": states[agent.id].hunger,
                        "fatigue": states[agent.id].fatigue,
                        "stress": states[agent.id].stress,
                        "satisfaction": states[agent.id].satisfaction,
                        "mood": states[agent.id].mood,
                        "current_action": states[agent.id].current_action,
                    }
                    if agent.id in states
                    else None
                ),
            }
            for agent in agents
        ],
        "relationships": [
            {
                "source_agent_fixture_key": agent_fixture_by_id.get(relationship.source_agent_id),
                "target_agent_fixture_key": agent_fixture_by_id.get(relationship.target_agent_id),
                "metrics": {
                    "affection": relationship.affection,
                    "closeness": relationship.closeness,
                    "trust": relationship.trust,
                    "tension": relationship.tension,
                    "rivalry": relationship.rivalry,
                    "dependency": relationship.dependency,
                },
            }
            for relationship in relationships
        ],
        "organization_memberships": [
            {
                "organization_fixture_key": organization_fixture_by_id.get(membership.organization_id),
                "agent_fixture_key": agent_fixture_by_id.get(membership.agent_id),
                "membership_role": membership.membership_role,
            }
            for membership in memberships
        ],
    }
    return payload


def create_simulation_share(
    db: Session,
    owner: User,
    simulation_id: UUID,
    *,
    visibility: str,
    title: str = "",
    description: str | None = None,
) -> SimulationShare:
    simulation = db.get(Simulation, simulation_id)
    if simulation is None:
        raise ShareNotFoundError("Simulation not found")
    if simulation.owner_id != owner.id:
        raise ShareAccessDeniedError("Simulation access denied")
    if simulation.status != "ready" or simulation.started_at is not None or simulation.current_tick != 0:
        raise SimulationNotReadyForShareError(
            "Simulation must be status=ready, started_at=null, current_tick=0 to share"
        )

    payload = build_export_payload(db, simulation, title=title, description=description)
    payload["share"]["visibility"] = visibility

    existing = get_active_share_by_simulation(db, simulation_id)
    if existing is not None:
        existing.revoked_at = datetime.now(UTC)
        db.flush()

    share = SimulationShare(
        id=uuid7(),
        simulation_id=simulation_id,
        owner_id=owner.id,
        title=title,
        description=description,
        visibility=visibility,
        export_schema_version=SCHEMA_VERSION,
        export_payload=deepcopy(payload),
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return share


def cancel_simulation_share(db: Session, owner: User, share_id: UUID) -> None:
    share = get_share_by_id(db, share_id)
    if share is None or share.revoked_at is not None:
        raise ShareNotFoundError("Shared simulation not found")
    if share.owner_id != owner.id:
        raise ShareAccessDeniedError("Simulation access denied")

    share.revoked_at = datetime.now(UTC)
    db.commit()


def get_public_simulation_shares(
    db: Session, *, query: str | None = None, limit: int = 20, offset: int = 0
) -> list[SimulationShare]:
    return list_public_shares(db, query=query, limit=limit, offset=offset)


def get_simulation_share_detail(db: Session, share_id: UUID, viewer: User | None) -> SimulationShare:
    share = get_share_by_id(db, share_id)
    if share is None or share.revoked_at is not None:
        raise ShareNotFoundError("Shared simulation not found")

    is_owner = viewer is not None and viewer.id == share.owner_id
    if share.visibility == "private" and not is_owner:
        raise ShareNotFoundError("Shared simulation not found")
    # `unlisted` and `public` are both reachable by exact share_id; only public
    # is additionally surfaced through listing/search (enforced in the repository).
    return share
