"""Slice 7 Task 4 — 가져오기 Runtime 계약 및 재현성 검증.

기준: docs/04-feature-specs/slice-7-config-sharing-import-deployment.md
관련: #144(import transaction), #147(본 검증)

이 파일은 새 프로덕션 코드를 추가하지 않는다. import 결과가 기존 Slice 4
roster/Persona 계약을 유지하는지, seed/model/prompt/policy/resolver version이
보존되는지, import 과정에서 Runtime·LLM·Tick이 전혀 호출되지 않는지, 원본이
불변인지, 그리고 같은 공유를 두 번 가져와도(기술적 ID는 달라도) 의미상
재현 가능한지를 검증한다.
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")

TABLES = (
    "share_imports",
    "simulation_shares",
    "runtime_executions",
    "runtime_results",
    "simulation_snapshots",
    "simulation_configs",
    "user_persona_configs",
    "relationships",
    "organization_memberships",
    "organizations",
    "agent_states",
    "student_profiles",
    "professor_profiles",
    "agents",
    "locations",
    "simulations",
    "users",
)


@pytest.fixture()
def client():
    from app.core.database import get_db
    from app.main import app

    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))

    def override_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client, session_factory
    app.dependency_overrides.clear()


def register_and_login(client: TestClient, username: str) -> dict[str, str]:
    password = "Slice0-password!"
    register = client.post(
        "/v1/auth/register",
        json={"username": username, "display_name": username, "password": password},
    )
    assert register.status_code == 201
    login = client.post("/v1/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_simulation(client: TestClient, headers: dict[str, str], name: str = "Repro sim") -> str:
    response = client.post("/v1/simulations", headers=headers, json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def set_persona(client: TestClient, headers: dict[str, str], simulation_id: str) -> str:
    agents = client.get(f"/v1/simulations/{simulation_id}/agents", headers=headers).json()
    student = next(a for a in agents if a["agent_type"] == "student")
    response = client.post(
        f"/v1/simulations/{simulation_id}/user-persona",
        headers=headers,
        json={
            "agent_id": student["id"],
            "mbti_type": student["mbti_type"],
            "personality_rule_version": "mbti-big-five-v0.1",
            "openness": student["profile"]["openness"],
            "conscientiousness": student["profile"]["conscientiousness"],
            "extraversion": student["profile"]["extraversion"],
            "agreeableness": student["profile"]["agreeableness"],
            "emotional_stability": student["profile"]["emotional_stability"],
        },
    )
    assert response.status_code == 200, response.text
    return student["fixture_key"]


def create_share(client: TestClient, headers: dict[str, str], simulation_id: str) -> dict:
    response = client.post(
        f"/v1/simulations/{simulation_id}/shares",
        headers=headers,
        json={"visibility": "public", "title": "repro", "description": None},
    )
    assert response.status_code == 201
    return response.json()


def import_share(client: TestClient, headers: dict[str, str], share_id: str, key: str):
    return client.post(
        f"/v1/shares/{share_id}/imports",
        headers={**headers, "Idempotency-Key": key},
    )


def _agent_rows(session_factory, simulation_id: str) -> list[dict]:
    with session_factory() as db:
        rows = db.execute(
            text(
                "SELECT fixture_key, agent_type, name, mbti_type, openness, conscientiousness, "
                "extraversion, agreeableness, emotional_stability FROM agents "
                "WHERE simulation_id = :sid ORDER BY fixture_key"
            ),
            {"sid": simulation_id},
        ).mappings().all()
        return [dict(row) for row in rows]


def test_import_result_matches_roster_and_persona_contract(client) -> None:
    test_client, session_factory = client
    owner_headers = register_and_login(test_client, "owner-r1")
    importer_headers = register_and_login(test_client, "importer-r1")
    simulation_id = create_simulation(test_client, owner_headers)
    persona_key = set_persona(test_client, owner_headers, simulation_id)
    share = create_share(test_client, owner_headers, simulation_id)

    response = import_share(test_client, importer_headers, share["id"], "roster-key")
    assert response.status_code == 201
    new_simulation_id = response.json()["id"]

    rows = _agent_rows(session_factory, new_simulation_id)
    assert len(rows) == 6
    students = [r for r in rows if r["agent_type"] == "student"]
    professors = [r for r in rows if r["agent_type"] == "professor"]
    assert len(students) == 5
    assert len(professors) == 1

    with session_factory() as db:
        persona_row = db.execute(
            text(
                "SELECT a.fixture_key FROM user_persona_configs upc "
                "JOIN agents a ON a.id = upc.agent_id WHERE upc.simulation_id = :sid"
            ),
            {"sid": new_simulation_id},
        ).fetchone()
    assert persona_row is not None
    assert persona_row[0] == persona_key
    assert persona_key in {r["fixture_key"] for r in students}


def test_import_preserves_execution_metadata_identifiers(client) -> None:
    test_client, session_factory = client
    owner_headers = register_and_login(test_client, "owner-r2")
    importer_headers = register_and_login(test_client, "importer-r2")
    simulation_id = create_simulation(test_client, owner_headers)
    share = create_share(test_client, owner_headers, simulation_id)
    shared_sim_data = share["export_payload"]["simulation"]

    response = import_share(test_client, importer_headers, share["id"], "meta-key")
    assert response.status_code == 201
    new_simulation_id = response.json()["id"]

    with session_factory() as db:
        config = db.execute(
            text(
                "SELECT policy_version, resolver_version FROM simulation_configs "
                "WHERE simulation_id = :sid ORDER BY version DESC LIMIT 1"
            ),
            {"sid": new_simulation_id},
        ).mappings().one()

    # seed/model/prompt_version are reproducibility identifiers captured once at
    # share time (the Simulation has never ticked, so there is no RuntimeExecution
    # row yet) — they live only in the frozen export payload, not in a DB column,
    # so "preserved" means every import of this share observes the same values.
    assert shared_sim_data["execution_seed"] is not None
    assert shared_sim_data["model_version"]
    assert shared_sim_data["prompt_version"]
    assert config["policy_version"] == shared_sim_data["policy_version"]
    assert config["resolver_version"] == shared_sim_data["resolver_version"]


def test_import_calls_zero_runtime_llm_tick(client) -> None:
    from app.simulation.instrumentation import get_counts, reset_counters

    test_client, session_factory = client
    owner_headers = register_and_login(test_client, "owner-r3")
    importer_headers = register_and_login(test_client, "importer-r3")
    simulation_id = create_simulation(test_client, owner_headers)
    share = create_share(test_client, owner_headers, simulation_id)

    reset_counters()
    response = import_share(test_client, importer_headers, share["id"], "norun-key")
    assert response.status_code == 201
    assert get_counts() == {"llm_calls": 0, "runtime_calls": 0, "tick_calls": 0}

    with session_factory() as db:
        runtime_result_count = db.execute(text("SELECT count(*) FROM runtime_results")).scalar_one()
        runtime_execution_count = db.execute(
            text("SELECT count(*) FROM runtime_executions")
        ).scalar_one()
    assert runtime_result_count == 0
    assert runtime_execution_count == 0


def test_original_untouched_by_import(client) -> None:
    test_client, session_factory = client
    owner_headers = register_and_login(test_client, "owner-r4")
    importer_headers = register_and_login(test_client, "importer-r4")
    simulation_id = create_simulation(test_client, owner_headers, "Original")
    share = create_share(test_client, owner_headers, simulation_id)

    with session_factory() as db:
        before_agents = db.execute(
            text("SELECT count(*) FROM agents WHERE simulation_id = :sid"), {"sid": simulation_id}
        ).scalar_one()
        before_snapshots = db.execute(
            text("SELECT count(*) FROM simulation_snapshots WHERE simulation_id = :sid"),
            {"sid": simulation_id},
        ).scalar_one()

    import_share(test_client, importer_headers, share["id"], "immut-key")

    with session_factory() as db:
        original = db.execute(
            text("SELECT name, status, current_tick, started_at FROM simulations WHERE id = :sid"),
            {"sid": simulation_id},
        ).mappings().one()
        after_agents = db.execute(
            text("SELECT count(*) FROM agents WHERE simulation_id = :sid"), {"sid": simulation_id}
        ).scalar_one()
        after_snapshots = db.execute(
            text("SELECT count(*) FROM simulation_snapshots WHERE simulation_id = :sid"),
            {"sid": simulation_id},
        ).scalar_one()
        runtime_results_for_original = db.execute(
            text(
                "SELECT count(*) FROM runtime_results rr JOIN agents a ON a.id = rr.agent_id "
                "WHERE a.simulation_id = :sid"
            ),
            {"sid": simulation_id},
        ).scalar_one()

    assert original["name"] == "Original"
    assert original["status"] == "ready"
    assert original["current_tick"] == 0
    assert original["started_at"] is None
    assert after_agents == before_agents
    assert after_snapshots == before_snapshots
    assert runtime_results_for_original == 0


def test_two_imports_of_same_share_are_semantically_reproducible(client) -> None:
    test_client, session_factory = client
    owner_headers = register_and_login(test_client, "owner-r5")
    importer_b_headers = register_and_login(test_client, "importer-r5-b")
    importer_c_headers = register_and_login(test_client, "importer-r5-c")
    simulation_id = create_simulation(test_client, owner_headers)
    set_persona(test_client, owner_headers, simulation_id)
    share = create_share(test_client, owner_headers, simulation_id)

    first = import_share(test_client, importer_b_headers, share["id"], "repro-b")
    second = import_share(test_client, importer_c_headers, share["id"], "repro-c")
    assert first.status_code == 201
    assert second.status_code == 201
    sim_a, sim_b = first.json()["id"], second.json()["id"]
    assert sim_a != sim_b

    def semantic_view(simulation_id: str) -> dict:
        with session_factory() as db:
            agents = [
                {k: v for k, v in dict(row).items() if k != "id"}
                for row in db.execute(
                    text(
                        "SELECT fixture_key, agent_type, name, mbti_type, openness, "
                        "conscientiousness, extraversion, agreeableness, emotional_stability "
                        "FROM agents WHERE simulation_id = :sid ORDER BY fixture_key"
                    ),
                    {"sid": simulation_id},
                ).mappings().all()
            ]
            states = [
                dict(row)
                for row in db.execute(
                    text(
                        "SELECT a.fixture_key, s.hunger, s.fatigue, s.stress, s.satisfaction, "
                        "s.mood, l.code AS location_code FROM agent_states s "
                        "JOIN agents a ON a.id = s.agent_id "
                        "LEFT JOIN locations l ON l.id = s.location_id "
                        "WHERE s.simulation_id = :sid ORDER BY a.fixture_key"
                    ),
                    {"sid": simulation_id},
                ).mappings().all()
            ]
            relationships = [
                dict(row)
                for row in db.execute(
                    text(
                        "SELECT src.fixture_key AS source_key, dst.fixture_key AS target_key, "
                        "r.affection, r.closeness, r.trust, r.tension, r.rivalry, r.dependency "
                        "FROM relationships r "
                        "JOIN agents src ON src.id = r.source_agent_id "
                        "JOIN agents dst ON dst.id = r.target_agent_id "
                        "WHERE r.simulation_id = :sid ORDER BY src.fixture_key, dst.fixture_key"
                    ),
                    {"sid": simulation_id},
                ).mappings().all()
            ]
            memberships = [
                dict(row)
                for row in db.execute(
                    text(
                        "SELECT o.organization_type, o.name AS org_name, a.fixture_key AS agent_key, "
                        "m.membership_role FROM organization_memberships m "
                        "JOIN organizations o ON o.id = m.organization_id "
                        "JOIN agents a ON a.id = m.agent_id "
                        "WHERE m.simulation_id = :sid ORDER BY o.name, a.fixture_key"
                    ),
                    {"sid": simulation_id},
                ).mappings().all()
            ]
            persona = db.execute(
                text(
                    "SELECT a.fixture_key FROM user_persona_configs upc "
                    "JOIN agents a ON a.id = upc.agent_id WHERE upc.simulation_id = :sid"
                ),
                {"sid": simulation_id},
            ).fetchone()
            config = db.execute(
                text(
                    "SELECT event_frequency, event_impact, policy_version, resolver_version "
                    "FROM simulation_configs WHERE simulation_id = :sid ORDER BY version DESC LIMIT 1"
                ),
                {"sid": simulation_id},
            ).mappings().one()
            simulation = db.execute(
                text("SELECT magic_enabled, status, current_tick FROM simulations WHERE id = :sid"),
                {"sid": simulation_id},
            ).mappings().one()
        return {
            "agents": agents,
            "states": states,
            "relationships": relationships,
            "memberships": memberships,
            "persona_fixture_key": persona[0] if persona else None,
            "config": dict(config),
            "simulation": dict(simulation),
        }

    view_a = semantic_view(sim_a)
    view_b = semantic_view(sim_b)
    assert view_a == view_b


def test_imported_agents_are_compatible_with_runtime_input_adapter(client) -> None:
    """Offline structural check only — no orchestrator/LLM call.

    Import itself never touches Runtime, but the resulting Agent/AgentState rows
    must remain shaped the way RuntimeInputAdapter expects so the imported
    Simulation is actually executable later.
    """
    from app.domain.models import Agent, AgentState
    from app.services.runtime_input_adapter import RuntimeInputAdapter

    test_client, session_factory = client
    owner_headers = register_and_login(test_client, "owner-r6")
    importer_headers = register_and_login(test_client, "importer-r6")
    simulation_id = create_simulation(test_client, owner_headers)
    share = create_share(test_client, owner_headers, simulation_id)

    response = import_share(test_client, importer_headers, share["id"], "adapter-key")
    assert response.status_code == 201
    new_simulation_id = response.json()["id"]

    with session_factory() as db:
        agents = db.query(Agent).filter(Agent.simulation_id == new_simulation_id).all()
        states = {
            state.agent_id: state
            for state in db.query(AgentState).filter(AgentState.simulation_id == new_simulation_id)
        }
        assert len(agents) == 6
        for agent in agents:
            state = states[agent.id]
            context = RuntimeInputAdapter.to_agent_context(agent, state)
            assert context.agent_id == agent.id
            assert context.fixture_key == agent.fixture_key
