import os
import threading
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from uuid6 import uuid7

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")

TABLES = (
    "share_imports",
    "simulation_shares",
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
        yield test_client, session_factory, engine
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


def create_simulation(client: TestClient, headers: dict[str, str], name: str = "Shared sim") -> str:
    response = client.post("/v1/simulations", headers=headers, json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def create_share(
    client: TestClient, headers: dict[str, str], simulation_id: str, visibility: str = "public"
) -> dict:
    response = client.post(
        f"/v1/simulations/{simulation_id}/shares",
        headers=headers,
        json={"visibility": visibility, "title": "share", "description": None},
    )
    assert response.status_code == 201
    return response.json()


def import_share(
    client: TestClient, headers: dict[str, str], share_id: str, idempotency_key: str
):
    return client.post(
        f"/v1/shares/{share_id}/imports",
        headers={**headers, "Idempotency-Key": idempotency_key},
    )


def _seed_org_and_relationship(session_factory, simulation_id: str) -> None:
    with session_factory() as db:
        agent_rows = db.execute(
            text("SELECT id, fixture_key FROM agents WHERE simulation_id = :sid ORDER BY fixture_key"),
            {"sid": simulation_id},
        ).fetchall()
        student_a_id, _ = agent_rows[0]
        student_b_id, _ = agent_rows[1]
        org_id = uuid7()
        db.execute(
            text(
                "INSERT INTO organizations (id, simulation_id, organization_type, name, "
                "description, is_active, created_at, updated_at) VALUES "
                "(:id, :sid, 'club', 'Magic Club', 'desc', true, now(), now())"
            ),
            {"id": org_id, "sid": simulation_id},
        )
        db.execute(
            text(
                "INSERT INTO organization_memberships (id, simulation_id, organization_id, "
                "agent_id, membership_role, joined_at, created_at, updated_at) VALUES "
                "(:id, :sid, :org_id, :agent_id, 'member', now(), now(), now())"
            ),
            {"id": uuid7(), "sid": simulation_id, "org_id": org_id, "agent_id": student_a_id},
        )
        db.execute(
            text(
                "INSERT INTO relationships (id, simulation_id, source_agent_id, target_agent_id, "
                "affection, closeness, trust, tension, rivalry, dependency, created_at, updated_at) "
                "VALUES (:id, :sid, :src, :dst, 10, 5, 0, 0, 0, 0, now(), now())"
            ),
            {"id": uuid7(), "sid": simulation_id, "src": student_a_id, "dst": student_b_id},
        )
        db.commit()


def test_import_creates_owned_simulation_with_full_roster(client) -> None:
    from app.simulation.instrumentation import get_counts, reset_counters

    test_client, session_factory, _ = client
    owner_headers = register_and_login(test_client, "owner-imp")
    importer_headers = register_and_login(test_client, "importer-imp")
    simulation_id = create_simulation(test_client, owner_headers)
    _seed_org_and_relationship(session_factory, simulation_id)
    share = create_share(test_client, owner_headers, simulation_id, visibility="public")

    reset_counters()
    response = import_share(test_client, importer_headers, share["id"], "key-1")
    counts = get_counts()

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ready"
    assert body["current_tick"] == 0
    new_simulation_id = body["id"]
    assert new_simulation_id != simulation_id
    assert counts == {"llm_calls": 0, "runtime_calls": 0, "tick_calls": 0}

    with session_factory() as db:
        owner_row = db.execute(
            text("SELECT owner_id FROM simulations WHERE id = :id"), {"id": new_simulation_id}
        ).fetchone()
        importer_id = db.execute(
            text("SELECT id FROM users WHERE username = 'importer-imp'")
        ).scalar_one()
        assert str(owner_row[0]) == str(importer_id)

        agent_count = db.execute(
            text("SELECT count(*) FROM agents WHERE simulation_id = :id"), {"id": new_simulation_id}
        ).scalar_one()
        assert agent_count == 6
        student_count = db.execute(
            text(
                "SELECT count(*) FROM agents a JOIN student_profiles sp ON sp.agent_id = a.id "
                "WHERE a.simulation_id = :id"
            ),
            {"id": new_simulation_id},
        ).scalar_one()
        assert student_count == 5
        professor_count = db.execute(
            text(
                "SELECT count(*) FROM agents a JOIN professor_profiles pp ON pp.agent_id = a.id "
                "WHERE a.simulation_id = :id"
            ),
            {"id": new_simulation_id},
        ).scalar_one()
        assert professor_count == 1
        org_count = db.execute(
            text("SELECT count(*) FROM organizations WHERE simulation_id = :id"),
            {"id": new_simulation_id},
        ).scalar_one()
        assert org_count == 1
        membership_count = db.execute(
            text("SELECT count(*) FROM organization_memberships WHERE simulation_id = :id"),
            {"id": new_simulation_id},
        ).scalar_one()
        assert membership_count == 1
        relationship_count = db.execute(
            text("SELECT count(*) FROM relationships WHERE simulation_id = :id"),
            {"id": new_simulation_id},
        ).scalar_one()
        assert relationship_count == 1
        snapshot_count = db.execute(
            text("SELECT count(*) FROM simulation_snapshots WHERE simulation_id = :id"),
            {"id": new_simulation_id},
        ).scalar_one()
        assert snapshot_count == 1


def test_import_maps_user_persona_to_new_agent(client) -> None:
    test_client, session_factory, _ = client
    owner_headers = register_and_login(test_client, "owner-persona")
    importer_headers = register_and_login(test_client, "importer-persona")
    simulation_id = create_simulation(test_client, owner_headers)

    with session_factory() as db:
        student = db.execute(
            text(
                "SELECT id FROM agents WHERE simulation_id = :sid AND agent_type = 'student' "
                "ORDER BY fixture_key LIMIT 1"
            ),
            {"sid": simulation_id},
        ).scalar_one()
        db.commit()
    set_persona = test_client.post(
        f"/v1/simulations/{simulation_id}/user-persona",
        headers=owner_headers,
        json={
            "agent_id": str(student),
            "mbti_type": "ISTJ",
            "personality_rule_version": "mbti-big-five-v0.1",
            "openness": -25,
            "conscientiousness": 25,
            "extraversion": -25,
            "agreeableness": -20,
            "emotional_stability": 0,
        },
    )
    assert set_persona.status_code == 200, set_persona.text

    share = create_share(test_client, owner_headers, simulation_id, visibility="public")
    assert share["export_payload"]["simulation"]["user_persona_fixture_key"] is not None

    response = import_share(test_client, importer_headers, share["id"], "key-persona")
    assert response.status_code == 201
    new_simulation_id = response.json()["id"]

    with session_factory() as db:
        persona_row = db.execute(
            text("SELECT agent_id FROM user_persona_configs WHERE simulation_id = :id"),
            {"id": new_simulation_id},
        ).fetchone()
        assert persona_row is not None
        agent_type = db.execute(
            text("SELECT agent_type FROM agents WHERE id = :id"), {"id": persona_row[0]}
        ).scalar_one()
        assert agent_type == "student"


def test_import_rejects_private_share_for_non_owner(client) -> None:
    test_client, _, _ = client
    owner_headers = register_and_login(test_client, "owner-priv-imp")
    importer_headers = register_and_login(test_client, "importer-priv-imp")
    simulation_id = create_simulation(test_client, owner_headers)
    share = create_share(test_client, owner_headers, simulation_id, visibility="private")

    response = import_share(test_client, importer_headers, share["id"], "key-priv")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SHARE_NOT_FOUND"


def test_import_owner_can_import_own_private_share(client) -> None:
    test_client, _, _ = client
    owner_headers = register_and_login(test_client, "owner-self-imp")
    simulation_id = create_simulation(test_client, owner_headers)
    share = create_share(test_client, owner_headers, simulation_id, visibility="private")

    response = import_share(test_client, owner_headers, share["id"], "key-self")
    assert response.status_code == 201


def test_import_rejects_revoked_share(client) -> None:
    test_client, _, _ = client
    owner_headers = register_and_login(test_client, "owner-revoked-imp")
    importer_headers = register_and_login(test_client, "importer-revoked-imp")
    simulation_id = create_simulation(test_client, owner_headers)
    share = create_share(test_client, owner_headers, simulation_id, visibility="public")
    test_client.delete(f"/v1/shares/{share['id']}", headers=owner_headers)

    response = import_share(test_client, importer_headers, share["id"], "key-revoked")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SHARE_NOT_FOUND"


def test_import_requires_idempotency_key_header(client) -> None:
    test_client, _, _ = client
    owner_headers = register_and_login(test_client, "owner-noheader")
    simulation_id = create_simulation(test_client, owner_headers)
    share = create_share(test_client, owner_headers, simulation_id, visibility="public")

    response = test_client.post(f"/v1/shares/{share['id']}/imports", headers=owner_headers)
    assert response.status_code == 422


def test_import_same_key_same_share_is_idempotent(client) -> None:
    test_client, session_factory, _ = client
    owner_headers = register_and_login(test_client, "owner-idem")
    importer_headers = register_and_login(test_client, "importer-idem")
    simulation_id = create_simulation(test_client, owner_headers)
    share = create_share(test_client, owner_headers, simulation_id, visibility="public")

    first = import_share(test_client, importer_headers, share["id"], "same-key")
    second = import_share(test_client, importer_headers, share["id"], "same-key")

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    with session_factory() as db:
        importer_id = db.execute(
            text("SELECT id FROM users WHERE username = 'importer-idem'")
        ).scalar_one()
        count = db.execute(
            text("SELECT count(*) FROM simulations WHERE owner_id = :id"), {"id": importer_id}
        ).scalar_one()
        assert count == 1


def test_import_same_key_different_share_is_conflict(client) -> None:
    test_client, _, _ = client
    owner_headers = register_and_login(test_client, "owner-conflict")
    importer_headers = register_and_login(test_client, "importer-conflict")
    sim_a = create_simulation(test_client, owner_headers, "A")
    sim_b = create_simulation(test_client, owner_headers, "B")
    share_a = create_share(test_client, owner_headers, sim_a, visibility="public")
    share_b = create_share(test_client, owner_headers, sim_b, visibility="public")

    first = import_share(test_client, importer_headers, share_a["id"], "shared-key")
    assert first.status_code == 201

    second = import_share(test_client, importer_headers, share_b["id"], "shared-key")
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "IMPORT_IDEMPOTENCY_CONFLICT"


def test_import_rollback_on_injected_failure_leaves_no_partial_state(client, monkeypatch) -> None:
    test_client, session_factory, _ = client
    owner_headers = register_and_login(test_client, "owner-rollback")
    importer_headers = register_and_login(test_client, "importer-rollback")
    simulation_id = create_simulation(test_client, owner_headers)
    share = create_share(test_client, owner_headers, simulation_id, visibility="public")

    import app.services.simulation_imports as imports_module

    def _boom(*args, **kwargs):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(
        imports_module.SimulationSnapshotRepository, "create", _boom
    )

    response = import_share(test_client, importer_headers, share["id"], "key-rollback")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "SHARE_IMPORT_FAILED"

    with session_factory() as db:
        importer_id = db.execute(
            text("SELECT id FROM users WHERE username = 'importer-rollback'")
        ).scalar_one()
        sim_count = db.execute(
            text("SELECT count(*) FROM simulations WHERE owner_id = :id"), {"id": importer_id}
        ).scalar_one()
        assert sim_count == 0
        agent_count = db.execute(text("SELECT count(*) FROM agents")).scalar_one()
        # only the original owner's 6 agents exist; nothing extra was created
        assert agent_count == 6
        idempotency_count = db.execute(text("SELECT count(*) FROM share_imports")).scalar_one()
        assert idempotency_count == 0

    # original untouched
    with session_factory() as db:
        original_status = db.execute(
            text("SELECT status, current_tick FROM simulations WHERE id = :id"),
            {"id": simulation_id},
        ).fetchone()
        assert original_status == ("ready", 0)


def test_original_simulation_and_share_payload_are_immutable_after_import(client) -> None:
    test_client, session_factory, _ = client
    owner_headers = register_and_login(test_client, "owner-immutable-imp")
    importer_headers = register_and_login(test_client, "importer-immutable-imp")
    simulation_id = create_simulation(test_client, owner_headers, "Original name")
    share = create_share(test_client, owner_headers, simulation_id, visibility="public")

    before_payload = share["export_payload"]

    import_share(test_client, importer_headers, share["id"], "key-immutable")

    with session_factory() as db:
        original = db.execute(
            text("SELECT name, status, current_tick FROM simulations WHERE id = :id"),
            {"id": simulation_id},
        ).fetchone()
        assert original == ("Original name", "ready", 0)

    after_detail = test_client.get(f"/v1/shares/{share['id']}", headers=owner_headers).json()
    assert after_detail["export_payload"] == before_payload


def test_concurrent_imports_with_same_key_create_exactly_one_simulation(client) -> None:
    test_client, session_factory, engine = client
    owner_headers = register_and_login(test_client, "owner-race")
    importer_headers = register_and_login(test_client, "importer-race")
    simulation_id = create_simulation(test_client, owner_headers)
    share = create_share(test_client, owner_headers, simulation_id, visibility="public")

    from app.core.security import authenticate_access_token
    from app.domain.models import User
    from app.services.simulation_imports import import_share as import_share_service
    from uuid import UUID as PyUUID

    importer_token = importer_headers["Authorization"].split(" ")[1]

    results: list[object] = []
    barrier = threading.Barrier(2)

    def worker():
        session_factory_local = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with session_factory_local() as db:
            user = authenticate_access_token(db, importer_token)
            barrier.wait()
            try:
                simulation = import_share_service(db, user, PyUUID(share["id"]), "race-key")
                results.append(("ok", simulation.id))
            except Exception as exc:  # noqa: BLE001
                results.append(("error", exc))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 2
    ok_results = [r for r in results if r[0] == "ok"]
    assert len(ok_results) == 2
    assert ok_results[0][1] == ok_results[1][1]

    with session_factory() as db:
        importer_id = db.execute(
            text("SELECT id FROM users WHERE username = 'importer-race'")
        ).scalar_one()
        count = db.execute(
            text("SELECT count(*) FROM simulations WHERE owner_id = :id"), {"id": importer_id}
        ).scalar_one()
        assert count == 1


def test_import_unsupported_schema_version_is_422(client) -> None:
    test_client, session_factory, _ = client
    owner_headers = register_and_login(test_client, "owner-schema")
    importer_headers = register_and_login(test_client, "importer-schema")
    simulation_id = create_simulation(test_client, owner_headers)
    share = create_share(test_client, owner_headers, simulation_id, visibility="public")

    with session_factory() as db:
        db.execute(
            text("UPDATE simulation_shares SET export_schema_version = 'legacy-v0' WHERE id = :id"),
            {"id": share["id"]},
        )
        db.commit()

    response = import_share(test_client, importer_headers, share["id"], "key-schema")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_SHARE_SCHEMA_VERSION"


def test_import_unknown_share_is_404(client) -> None:
    test_client, _, _ = client
    importer_headers = register_and_login(test_client, "importer-unknown")
    response = import_share(test_client, importer_headers, str(uuid4()), "key-unknown")
    assert response.status_code == 404
