import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from uuid6 import uuid7

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")


@pytest.fixture()
def client(monkeypatch):
    from app.core.database import get_db
    from app.main import app

    engine = create_engine(TEST_DATABASE_URL)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE users, simulations, locations, agents, agent_states, "
                "student_profiles, professor_profiles, organizations, "
                "organization_memberships, relationships, simulation_configs, "
                "simulation_snapshots, simulation_shares RESTART IDENTITY CASCADE"
            )
        )

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


def create_simulation(client: TestClient, headers: dict[str, str], name: str = "Shared sim") -> str:
    response = client.post("/v1/simulations", headers=headers, json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def create_share(
    client: TestClient,
    headers: dict[str, str],
    simulation_id: str,
    *,
    visibility: str = "public",
    title: str = "My share",
    description: str | None = "desc",
):
    return client.post(
        f"/v1/simulations/{simulation_id}/shares",
        headers=headers,
        json={"visibility": visibility, "title": title, "description": description},
    )


def test_owner_can_create_share_from_ready_simulation(client) -> None:
    test_client, _ = client
    owner_headers = register_and_login(test_client, "owner-create")
    simulation_id = create_simulation(test_client, owner_headers)

    response = create_share(test_client, owner_headers, simulation_id, visibility="public")

    assert response.status_code == 201
    body = response.json()
    assert body["visibility"] == "public"
    assert body["export_schema_version"] == "slice7-share-v1"
    assert body["title"] == "My share"


def test_non_owner_cannot_create_or_cancel_share(client) -> None:
    test_client, _ = client
    owner_headers = register_and_login(test_client, "owner-perm")
    other_headers = register_and_login(test_client, "other-perm")
    simulation_id = create_simulation(test_client, owner_headers)

    forbidden_create = create_share(test_client, other_headers, simulation_id)
    assert forbidden_create.status_code == 403
    assert forbidden_create.json()["error"]["code"] == "SHARE_ACCESS_DENIED"

    share_id = create_share(test_client, owner_headers, simulation_id).json()["id"]
    forbidden_cancel = test_client.delete(f"/v1/shares/{share_id}", headers=other_headers)
    assert forbidden_cancel.status_code == 403


def test_invalid_visibility_is_rejected(client) -> None:
    test_client, _ = client
    owner_headers = register_and_login(test_client, "owner-invalid-vis")
    simulation_id = create_simulation(test_client, owner_headers)

    response = test_client.post(
        f"/v1/simulations/{simulation_id}/shares",
        headers=owner_headers,
        json={"visibility": "hidden"},
    )
    assert response.status_code == 422


def test_running_simulation_cannot_be_shared(client) -> None:
    test_client, session_factory = client
    owner_headers = register_and_login(test_client, "owner-running")
    simulation_id = create_simulation(test_client, owner_headers)

    with session_factory() as db:
        db.execute(
            text(
                "UPDATE simulations SET status = 'running', started_at = now(), "
                "current_tick = 1 WHERE id = :id"
            ),
            {"id": simulation_id},
        )
        db.commit()

    response = create_share(test_client, owner_headers, simulation_id)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SIMULATION_SHARE_NOT_READY"


def test_public_list_and_search(client) -> None:
    test_client, _ = client
    owner_headers = register_and_login(test_client, "owner-search")
    sim_a = create_simulation(test_client, owner_headers, "Sim A")
    sim_b = create_simulation(test_client, owner_headers, "Sim B")
    share_a = create_share(
        test_client, owner_headers, sim_a, visibility="public", title="Magic Academy Alpha"
    ).json()
    share_b = create_share(
        test_client, owner_headers, sim_b, visibility="public", title="Something else"
    ).json()

    listing = test_client.get("/v1/shares")
    assert listing.status_code == 200
    ids = [item["id"] for item in listing.json()]
    assert share_a["id"] in ids
    assert share_b["id"] in ids
    # list items must not leak the full export payload
    assert "export_payload" not in listing.json()[0]

    filtered = test_client.get("/v1/shares", params={"q": "Alpha"})
    assert filtered.status_code == 200
    filtered_ids = [item["id"] for item in filtered.json()]
    assert share_a["id"] in filtered_ids
    assert share_b["id"] not in filtered_ids


def test_unlisted_hidden_from_list_but_reachable_by_id(client) -> None:
    test_client, _ = client
    owner_headers = register_and_login(test_client, "owner-unlisted")
    viewer_headers = register_and_login(test_client, "viewer-unlisted")
    simulation_id = create_simulation(test_client, owner_headers)
    share = create_share(test_client, owner_headers, simulation_id, visibility="unlisted").json()

    listing = test_client.get("/v1/shares")
    assert share["id"] not in [item["id"] for item in listing.json()]

    detail = test_client.get(f"/v1/shares/{share['id']}", headers=viewer_headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == share["id"]

    anonymous_detail = test_client.get(f"/v1/shares/{share['id']}")
    assert anonymous_detail.status_code == 200


def test_private_hidden_from_others_but_visible_to_owner(client) -> None:
    test_client, _ = client
    owner_headers = register_and_login(test_client, "owner-private")
    viewer_headers = register_and_login(test_client, "viewer-private")
    simulation_id = create_simulation(test_client, owner_headers)
    share = create_share(test_client, owner_headers, simulation_id, visibility="private").json()

    assert share["id"] not in [item["id"] for item in test_client.get("/v1/shares").json()]

    forbidden = test_client.get(f"/v1/shares/{share['id']}", headers=viewer_headers)
    assert forbidden.status_code == 404

    anonymous = test_client.get(f"/v1/shares/{share['id']}")
    assert anonymous.status_code == 404

    owner_detail = test_client.get(f"/v1/shares/{share['id']}", headers=owner_headers)
    assert owner_detail.status_code == 200


def test_revoked_share_is_404_for_detail_and_cancel_is_idempotent_failure(client) -> None:
    test_client, _ = client
    owner_headers = register_and_login(test_client, "owner-revoke")
    simulation_id = create_simulation(test_client, owner_headers)
    share = create_share(test_client, owner_headers, simulation_id, visibility="public").json()

    cancel_response = test_client.delete(f"/v1/shares/{share['id']}", headers=owner_headers)
    assert cancel_response.status_code == 204

    detail_after_cancel = test_client.get(f"/v1/shares/{share['id']}", headers=owner_headers)
    assert detail_after_cancel.status_code == 404

    listing = test_client.get("/v1/shares")
    assert share["id"] not in [item["id"] for item in listing.json()]

    second_cancel = test_client.delete(f"/v1/shares/{share['id']}", headers=owner_headers)
    assert second_cancel.status_code == 404


def test_simulation_can_be_re_shared_after_cancellation(client) -> None:
    test_client, _ = client
    owner_headers = register_and_login(test_client, "owner-reshare")
    simulation_id = create_simulation(test_client, owner_headers)

    first = create_share(test_client, owner_headers, simulation_id)
    assert first.status_code == 201
    test_client.delete(f"/v1/shares/{first.json()['id']}", headers=owner_headers)

    second = create_share(test_client, owner_headers, simulation_id)
    assert second.status_code == 201
    assert second.json()["id"] != first.json()["id"]


def test_export_payload_is_immutable_after_source_simulation_changes(client) -> None:
    test_client, session_factory = client
    owner_headers = register_and_login(test_client, "owner-immutable")
    simulation_id = create_simulation(test_client, owner_headers, "Snapshot sim")

    share = create_share(test_client, owner_headers, simulation_id, title="frozen-name").json()

    with session_factory() as db:
        db.execute(
            text("UPDATE simulations SET name = :new_name WHERE id = :id"),
            {"id": simulation_id, "new_name": "mutated-name"},
        )
        db.commit()

    detail = test_client.get(f"/v1/shares/{share['id']}", headers=owner_headers).json()
    assert detail["export_payload"]["simulation"]["name"] == "Snapshot sim"


def test_export_payload_roster_and_no_sensitive_fields(client) -> None:
    test_client, _ = client
    owner_headers = register_and_login(test_client, "owner-roster")
    simulation_id = create_simulation(test_client, owner_headers)

    share = create_share(test_client, owner_headers, simulation_id).json()
    payload = share["export_payload"]

    assert payload["schema_version"] == "slice7-share-v1"
    agents = payload["agents"]
    assert len(agents) == 6
    student_count = sum(1 for agent in agents if agent["role_profile"]["profile_type"] == "student")
    professor_count = sum(1 for agent in agents if agent["role_profile"]["profile_type"] == "professor")
    assert student_count == 5
    assert professor_count == 1
    for agent in agents:
        assert set(agent["fixture_key"] for agent in agents) == {a["fixture_key"] for a in agents}
        assert "traits" in agent and "state" in agent

    serialized = str(payload)
    for forbidden in ("password", "jwt", "secret", "Authorization", "access_token"):
        assert forbidden not in serialized


def test_export_payload_maps_organizations_and_relationships_by_fixture_key(client) -> None:
    test_client, session_factory = client
    owner_headers = register_and_login(test_client, "owner-org")
    simulation_id = create_simulation(test_client, owner_headers)

    with session_factory() as db:
        agent_rows = db.execute(
            text(
                "SELECT id, fixture_key FROM agents WHERE simulation_id = :sid ORDER BY fixture_key"
            ),
            {"sid": simulation_id},
        ).fetchall()
        student_a_id, student_a_key = agent_rows[0]
        student_b_id, student_b_key = agent_rows[1]

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

    share = create_share(test_client, owner_headers, simulation_id).json()
    payload = share["export_payload"]

    assert len(payload["organizations"]) == 1
    org_fixture_key = payload["organizations"][0]["fixture_key"]
    assert org_fixture_key

    assert len(payload["organization_memberships"]) == 1
    membership = payload["organization_memberships"][0]
    assert membership["organization_fixture_key"] == org_fixture_key
    assert membership["agent_fixture_key"] == student_a_key

    assert len(payload["relationships"]) == 1
    relationship = payload["relationships"][0]
    assert relationship["source_agent_fixture_key"] == student_a_key
    assert relationship["target_agent_fixture_key"] == student_b_key


def test_share_not_found_for_unknown_id(client) -> None:
    test_client, _ = client
    response = test_client.get(f"/v1/shares/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "SHARE_NOT_FOUND"


def test_create_share_for_missing_simulation_is_404(client) -> None:
    test_client, _ = client
    owner_headers = register_and_login(test_client, "owner-missing-sim")
    response = create_share(test_client, owner_headers, str(uuid4()))
    assert response.status_code == 404
