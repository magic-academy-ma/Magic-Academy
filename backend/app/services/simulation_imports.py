import hashlib
import json
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import (
    Agent,
    AgentState,
    Location,
    Organization,
    OrganizationMembership,
    ProfessorProfile,
    Relationship,
    ShareImport,
    Simulation,
    SimulationShare,
    StudentProfile,
    User,
    UserPersonaConfig,
)
from app.repositories.share_imports import get_by_identity
from app.repositories.simulation_shares import get_share_by_id
from app.repositories.simulation_snapshots import SimulationConfigRepository, SimulationSnapshotRepository
from app.services.simulation_shares import SCHEMA_VERSION
from app.services.user_persona import RULE_VERSION

REQUIRED_TOP_LEVEL_KEYS = (
    "schema_version",
    "simulation",
    "locations",
    "organizations",
    "agents",
    "relationships",
    "organization_memberships",
)
REQUIRED_AGENT_KEYS = (
    "fixture_key",
    "fixture_version",
    "agent_type",
    "name",
    "mbti_type",
    "traits",
    "role_profile",
)
REQUIRED_TRAIT_KEYS = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "emotional_stability",
)
REQUIRED_RELATIONSHIP_METRIC_KEYS = (
    "affection",
    "closeness",
    "trust",
    "tension",
    "rivalry",
    "dependency",
)


class ShareImportError(Exception):
    pass


class ShareNotFoundForImportError(ShareImportError):
    pass


class UnsupportedShareSchemaVersionError(ShareImportError):
    pass


class InvalidSharePayloadError(ShareImportError):
    pass


class SharePersonaTargetInvalidError(ShareImportError):
    pass


class ImportIdempotencyConflictError(ShareImportError):
    pass


class ShareImportFailedError(ShareImportError):
    pass


def compute_fingerprint(share_id: UUID) -> str:
    canonical = json.dumps({"share_id": str(share_id)}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _get_importable_share(db: Session, share_id: UUID, viewer: User) -> SimulationShare:
    share = get_share_by_id(db, share_id)
    if share is None or share.revoked_at is not None:
        raise ShareNotFoundForImportError("Shared simulation not found")
    is_owner = viewer.id == share.owner_id
    if share.visibility == "private" and not is_owner:
        raise ShareNotFoundForImportError("Shared simulation not found")
    return share


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidSharePayloadError(message)


def _validate_payload(payload: dict) -> None:
    for key in REQUIRED_TOP_LEVEL_KEYS:
        _require(key in payload, f"missing top-level field: {key}")

    simulation = payload["simulation"]
    _require(isinstance(simulation, dict), "simulation must be an object")
    _require(bool(simulation.get("name")), "simulation.name is required")

    locations = payload["locations"]
    _require(isinstance(locations, list), "locations must be a list")
    location_codes: set[str] = set()
    for location in locations:
        _require(bool(location.get("code")), "location.code is required")
        _require(location["code"] not in location_codes, "duplicate location code")
        location_codes.add(location["code"])

    organizations = payload["organizations"]
    _require(isinstance(organizations, list), "organizations must be a list")
    organization_keys: set[str] = set()
    for organization in organizations:
        key = organization.get("fixture_key")
        _require(bool(key), "organization.fixture_key is required")
        _require(key not in organization_keys, "duplicate organization fixture_key")
        organization_keys.add(key)

    agents = payload["agents"]
    _require(isinstance(agents, list) and len(agents) > 0, "agents must be a non-empty list")
    agent_keys: set[str] = set()
    for agent in agents:
        for key in REQUIRED_AGENT_KEYS:
            _require(key in agent, f"agent missing field: {key}")
        _require(agent["fixture_key"] not in agent_keys, "duplicate agent fixture_key")
        agent_keys.add(agent["fixture_key"])
        _require(agent["agent_type"] in ("student", "professor"), "invalid agent_type")
        traits = agent["traits"]
        for trait_key in REQUIRED_TRAIT_KEYS:
            _require(trait_key in traits, f"agent traits missing field: {trait_key}")
        role = agent["role_profile"]
        profile_type = role.get("profile_type")
        if profile_type == "student":
            _require("grade" in role and "interest_field" in role, "student role_profile incomplete")
        elif profile_type == "professor":
            _require("academic_rank" in role and "specialty" in role, "professor role_profile incomplete")
        else:
            raise InvalidSharePayloadError("unsupported role_profile.profile_type")
        state = agent.get("state")
        if state is not None:
            location_code = state.get("location_code")
            _require(
                location_code is None or location_code in location_codes,
                "agent state references unknown location_code",
            )

    for relationship in payload["relationships"]:
        _require(
            relationship.get("source_agent_fixture_key") in agent_keys,
            "relationship references unknown source agent",
        )
        _require(
            relationship.get("target_agent_fixture_key") in agent_keys,
            "relationship references unknown target agent",
        )
        metrics = relationship.get("metrics", {})
        for metric_key in REQUIRED_RELATIONSHIP_METRIC_KEYS:
            _require(metric_key in metrics, f"relationship metrics missing field: {metric_key}")

    for membership in payload["organization_memberships"]:
        _require(
            membership.get("organization_fixture_key") in organization_keys,
            "membership references unknown organization",
        )
        _require(
            membership.get("agent_fixture_key") in agent_keys,
            "membership references unknown agent",
        )

    persona_key = simulation.get("user_persona_fixture_key")
    if persona_key is not None and persona_key not in agent_keys:
        raise SharePersonaTargetInvalidError("user_persona_fixture_key does not match any agent in roster")


def _build_simulation(db: Session, owner: User, payload: dict) -> Simulation:
    sim_data = payload["simulation"]
    simulation = Simulation(
        id=uuid7(),
        owner_id=owner.id,
        name=sim_data["name"],
        magic_enabled=bool(sim_data.get("magic_enabled", True)),
    )
    db.add(simulation)
    db.flush()

    location_id_by_code: dict[str, UUID] = {}
    for location_data in payload["locations"]:
        location = Location(
            id=uuid7(),
            simulation_id=simulation.id,
            code=location_data["code"],
            name=location_data.get("name", location_data["code"]),
            is_active=bool(location_data.get("is_active", True)),
        )
        db.add(location)
        db.flush()
        location_id_by_code[location_data["code"]] = location.id

    organization_id_by_fixture: dict[str, UUID] = {}
    for organization_data in payload["organizations"]:
        organization = Organization(
            id=uuid7(),
            simulation_id=simulation.id,
            organization_type=organization_data["organization_type"],
            name=organization_data["name"],
            description=organization_data.get("description"),
            is_active=bool(organization_data.get("is_active", True)),
        )
        db.add(organization)
        db.flush()
        organization_id_by_fixture[organization_data["fixture_key"]] = organization.id

    agent_id_by_fixture: dict[str, UUID] = {}
    persona_agent_id: UUID | None = None
    persona_fixture_key = sim_data.get("user_persona_fixture_key")
    for agent_data in payload["agents"]:
        traits = agent_data["traits"]
        agent = Agent(
            id=uuid7(),
            simulation_id=simulation.id,
            fixture_key=agent_data["fixture_key"],
            fixture_version=agent_data["fixture_version"],
            agent_type=agent_data["agent_type"],
            name=agent_data["name"],
            gender=agent_data.get("gender"),
            personality_type=agent_data.get("personality_type"),
            mbti_type=agent_data["mbti_type"],
            openness=traits["openness"],
            conscientiousness=traits["conscientiousness"],
            extraversion=traits["extraversion"],
            agreeableness=traits["agreeableness"],
            emotional_stability=traits["emotional_stability"],
        )
        db.add(agent)
        db.flush()
        agent_id_by_fixture[agent_data["fixture_key"]] = agent.id

        role = agent_data["role_profile"]
        if role["profile_type"] == "student":
            db.add(
                StudentProfile(
                    agent_id=agent.id, grade=role["grade"], interest_field=role["interest_field"]
                )
            )
        else:
            db.add(
                ProfessorProfile(
                    agent_id=agent.id, academic_rank=role["academic_rank"], specialty=role["specialty"]
                )
            )

        state = agent_data.get("state")
        if state is not None:
            location_id = location_id_by_code.get(state.get("location_code"))
            db.add(
                AgentState(
                    id=uuid7(),
                    simulation_id=simulation.id,
                    agent_id=agent.id,
                    location_id=location_id,
                    hunger=state["hunger"],
                    fatigue=state["fatigue"],
                    stress=state["stress"],
                    satisfaction=state["satisfaction"],
                    mood=state["mood"],
                    current_action=state.get("current_action"),
                )
            )

        if persona_fixture_key is not None and agent_data["fixture_key"] == persona_fixture_key:
            persona_agent_id = agent.id

    for membership_data in payload["organization_memberships"]:
        db.add(
            OrganizationMembership(
                id=uuid7(),
                simulation_id=simulation.id,
                organization_id=organization_id_by_fixture[membership_data["organization_fixture_key"]],
                agent_id=agent_id_by_fixture[membership_data["agent_fixture_key"]],
                membership_role=membership_data.get("membership_role"),
            )
        )

    for relationship_data in payload["relationships"]:
        metrics = relationship_data["metrics"]
        db.add(
            Relationship(
                id=uuid7(),
                simulation_id=simulation.id,
                source_agent_id=agent_id_by_fixture[relationship_data["source_agent_fixture_key"]],
                target_agent_id=agent_id_by_fixture[relationship_data["target_agent_fixture_key"]],
                affection=metrics["affection"],
                closeness=metrics["closeness"],
                trust=metrics["trust"],
                tension=metrics["tension"],
                rivalry=metrics["rivalry"],
                dependency=metrics["dependency"],
            )
        )

    db.flush()

    config_repository = SimulationConfigRepository()
    config = config_repository.create_version(
        db,
        simulation,
        event_frequency="medium",
        event_impact="medium",
        magic_enabled=simulation.magic_enabled,
        user_persona_settings={},
        policy_version=sim_data.get("policy_version"),
        resolver_version=sim_data.get("resolver_version"),
    )

    if persona_agent_id is not None:
        persona_agent = db.get(Agent, persona_agent_id)
        db.add(
            UserPersonaConfig(
                simulation_id=simulation.id,
                agent_id=persona_agent_id,
                mbti_type=persona_agent.mbti_type,
                personality_rule_version=RULE_VERSION,
                openness=persona_agent.openness,
                conscientiousness=persona_agent.conscientiousness,
                extraversion=persona_agent.extraversion,
                agreeableness=persona_agent.agreeableness,
                emotional_stability=persona_agent.emotional_stability,
            )
        )
        db.flush()

    SimulationSnapshotRepository().create(db, simulation, config)
    db.flush()
    return simulation


def import_share(
    db: Session,
    request_user: User,
    share_id: UUID,
    idempotency_key: str,
) -> Simulation:
    """Create a new owned Simulation from a share's immutable Snapshot.

    Never calls TickEngine, AgentRuntime, RuntimeOrchestrator or any LLM
    client — import is a pure data-copy transaction.
    """
    fingerprint = compute_fingerprint(share_id)

    existing = get_by_identity(db, request_user.id, idempotency_key)
    if existing is not None:
        if existing.fingerprint != fingerprint:
            raise ImportIdempotencyConflictError(
                "idempotency key already used for a different share"
            )
        simulation = db.get(Simulation, existing.simulation_id)
        if simulation is None:
            raise ShareImportFailedError("recorded import result is missing")
        return simulation

    share = _get_importable_share(db, share_id, request_user)
    if share.export_schema_version != SCHEMA_VERSION:
        raise UnsupportedShareSchemaVersionError(
            f"unsupported schema_version: {share.export_schema_version}"
        )
    payload = share.export_payload
    _validate_payload(payload)

    try:
        simulation = _build_simulation(db, request_user, payload)
        db.add(
            ShareImport(
                id=uuid7(),
                request_user_id=request_user.id,
                idempotency_key=idempotency_key,
                share_id=share_id,
                fingerprint=fingerprint,
                simulation_id=simulation.id,
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        winner = get_by_identity(db, request_user.id, idempotency_key)
        if winner is None or winner.fingerprint != fingerprint:
            raise ImportIdempotencyConflictError(
                "concurrent import used this idempotency key for a different share"
            ) from None
        simulation = db.get(Simulation, winner.simulation_id)
        if simulation is None:
            raise ShareImportFailedError("recorded import result is missing") from None
        return simulation
    except ShareImportError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise ShareImportFailedError(str(exc)) from exc

    db.refresh(simulation)
    return simulation
