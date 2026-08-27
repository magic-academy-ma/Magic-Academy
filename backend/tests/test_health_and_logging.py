"""Slice 7 Task 3 — /health migration readiness and structured request logging.

기준: docs/04-feature-specs/slice-7-config-sharing-import-deployment.md §6
"""

import json
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL is required")


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


def test_health_reports_ok_when_migrations_are_up_to_date(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "database": "ok", "migration": "ok"}


def test_health_returns_503_when_db_revision_is_stale(client) -> None:
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as connection:
        original = connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        connection.execute(text("DELETE FROM alembic_version"))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('stale-revision')")
        )
    try:
        response = client.get("/health")
        assert response.status_code == 503
    finally:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM alembic_version"))
            for row in original:
                connection.execute(
                    text("INSERT INTO alembic_version (version_num) VALUES (:v)"),
                    {"v": row[0]},
                )


def test_structured_request_log_has_required_fields_and_no_secrets(client, caplog) -> None:
    import logging

    caplog.set_level(logging.INFO, logger="magic_academy.request")
    response = client.get("/health", headers={"Authorization": "Bearer super-secret-token"})
    assert response.status_code == 200

    records = [r for r in caplog.records if r.name == "magic_academy.request"]
    assert len(records) == 1
    payload = json.loads(records[0].message)

    for field in (
        "timestamp",
        "level",
        "service",
        "environment",
        "trace_id",
        "request_id",
        "operation",
        "result",
        "duration_ms",
    ):
        assert field in payload

    assert payload["operation"] == "GET /health"
    assert payload["result"] == 200

    serialized = json.dumps(payload)
    assert "super-secret-token" not in serialized
    assert "authorization" not in serialized.lower()
    assert "bearer" not in serialized.lower()


def test_structured_request_log_includes_allowed_path_params(client, caplog) -> None:
    import logging

    caplog.set_level(logging.INFO, logger="magic_academy.request")
    client.get("/v1/shares/00000000-0000-0000-0000-000000000000")

    records = [r for r in caplog.records if r.name == "magic_academy.request"]
    payload = json.loads(records[-1].message)
    assert payload["operation"] == "GET /shares/{share_id}"
    assert payload["share_id"] == "00000000-0000-0000-0000-000000000000"
