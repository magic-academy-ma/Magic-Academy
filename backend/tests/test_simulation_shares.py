import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

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
                "TRUNCATE users, simulations, locations, agents, agent_states, simulation_shares RESTART IDENTITY CASCADE"
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


def test_share_owner_and_visibility_rules(client) -> None:
    test_client, _ = client
    owner_headers = register_and_login(test_client, "owner-share")
    viewer_headers = register_and_login(test_client, "viewer-share")

    simulation_id = create_simulation(test_client, owner_headers, "Public share")
    create_response = test_client.post(
        f"/v1/simulations/{simulation_id}/share",
        headers=owner_headers,
        json={"visibility": "public", "export_payload": {"schema_version": "1", "name": "initial"}},
    )
    assert create_response.status_code == 201
    share_id = create_response.json()["id"]

    list_response = test_client.get("/v1/shares", headers=viewer_headers)
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [share_id]

    private_response = test_client.post(
        f"/v1/simulations/{simulation_id}/share",
        headers=owner_headers,
        json={"visibility": "private", "export_payload": {"schema_version": "1", "name": "hidden"}},
    )
    assert private_response.status_code == 409

    unlisted_response = test_client.post(
        f"/v1/simulations/{uuid4()}/share",
        headers=owner_headers,
        json={"visibility": "unlisted", "export_payload": {"schema_version": "1", "name": "secret"}},
    )
    assert unlisted_response.status_code == 201
    unlisted_id = unlisted_response.json()["id"]

    list_response = test_client.get("/v1/shares", headers=viewer_headers)
    assert list_response.status_code == 200
    listed_ids = [item["id"] for item in list_response.json()]
    assert share_id in listed_ids
    assert unlisted_id not in listed_ids

    detail_response = test_client.get(f"/v1/shares/{unlisted_id}", headers=viewer_headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == str(unlisted_id)

    private_simulation_id = create_simulation(test_client, owner_headers, "Private share")
    create_private = test_client.post(
        f"/v1/simulations/{private_simulation_id}/share",
        headers=owner_headers,
        json={"visibility": "private", "export_payload": {"schema_version": "1", "name": "private"}},
    )
    private_share_id = create_private.json()["id"]

    private_list = test_client.get("/v1/shares", headers=viewer_headers)
    assert private_share_id not in [item["id"] for item in private_list.json()]

    private_detail = test_client.get(f"/v1/shares/{private_share_id}", headers=viewer_headers)
    assert private_detail.status_code == 404


def test_share_snapshot_is_frozen_after_simulation_changes(client) -> None:
    test_client, session_factory = client
    owner_headers = register_and_login(test_client, "snapshot-owner")
    simulation_id = create_simulation(test_client, owner_headers, "Snapshot sim")

    creation = test_client.post(
        f"/v1/simulations/{simulation_id}/share",
        headers=owner_headers,
        json={"visibility": "public", "export_payload": {"schema_version": "1", "name": "snapshot-name"}},
    )
    assert creation.status_code == 201
    share_id = creation.json()["id"]

    with session_factory() as db:
        simulation = db.execute(text("SELECT id, name FROM simulations WHERE id = :simulation_id")).fetchone()
        assert simulation is not None
        db.execute(text("UPDATE simulations SET name = :new_name WHERE id = :simulation_id"), {"simulation_id": simulation[0], "new_name": "mutated-name"})
        db.commit()

    detail = test_client.get(f"/v1/shares/{share_id}", headers=owner_headers)
    assert detail.status_code == 200
    payload = detail.json()["export_payload"]
    assert payload["simulation"]["name"] == "snapshot-name"


def test_owner_only_create_and_cancel_share(client) -> None:
    test_client, _ = client

    owner_headers = register_and_login(test_client, "share-owner")
    viewer_headers = register_and_login(test_client, "share-viewer")
    simulation_id = create_simulation(test_client, owner_headers, "Owner only")

    forbidden_create = test_client.post(
        f"/v1/simulations/{simulation_id}/share",
        headers=viewer_headers,
        json={"visibility": "public", "export_payload": {"schema_version": "1", "owner": "other"}},
    )
    assert forbidden_create.status_code == 403

    valid_create = test_client.post(
        f"/v1/simulations/{simulation_id}/share",
        headers=owner_headers,
        json={"visibility": "public", "export_payload": {"schema_version": "1", "owner": "me"}},
    )
    assert valid_create.status_code == 201
    share_id = valid_create.json()["id"]

    forbidden_cancel = test_client.delete(
        f"/v1/simulations/{simulation_id}/share",
        headers=viewer_headers,
    )
    assert forbidden_cancel.status_code == 403

    cancel_response = test_client.delete(
        f"/v1/simulations/{simulation_id}/share",
        headers=owner_headers,
    )
    assert cancel_response.status_code == 204

    detail_response = test_client.get(f"/v1/shares/{share_id}", headers=viewer_headers)
    assert detail_response.status_code == 404
