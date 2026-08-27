"""Slice 7 Task 6 — 배포 E2E 및 최종 PASS 판정을 위한 사용자 관점 HTTP 인수 테스트.

기준: docs/04-feature-specs/slice-7-config-sharing-import-deployment.md

Railway에서의 실제 Golden Path(#146/#149 Railway 부분)는 사용자 결정에 따라
이 프로젝트 범위에서 실행하지 않는다 — 이 파일은 API/DB 계층에서의 동등한
Golden Path와 완료 기준을 하나의 흐름으로 증명한다.
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
def acceptance_context():
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
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, session_factory
    app.dependency_overrides.clear()
    engine.dispose()


def _register(client: TestClient, username: str) -> dict[str, str]:
    password = "Slice7-acceptance!"
    response = client.post(
        "/v1/auth/register",
        json={"username": username, "display_name": username, "password": password},
    )
    assert response.status_code == 201
    response = client.post("/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_simulation(client: TestClient, headers: dict[str, str], name: str) -> str:
    response = client.post("/v1/simulations", headers=headers, json={"name": name})
    assert response.status_code == 201
    return response.json()["id"]


def test_slice7_golden_path_and_final_pass_criteria(acceptance_context) -> None:
    from app.simulation.instrumentation import get_counts, reset_counters

    client, session_factory = acceptance_context

    # --- Golden Path -------------------------------------------------------
    # 1. 사용자 A가 Simulation 설정을 public으로 공유한다.
    owner_headers = _register(client, "acceptance-owner")
    simulation_id = _create_simulation(client, owner_headers, "Acceptance Simulation")
    share_response = client.post(
        f"/v1/simulations/{simulation_id}/shares",
        headers=owner_headers,
        json={"visibility": "public", "title": "Acceptance Share", "description": "e2e"},
    )
    assert share_response.status_code == 201
    share = share_response.json()

    # 2. 사용자 B가 공개 목록·검색에서 공유를 찾고 상세를 조회한다.
    importer_headers = _register(client, "acceptance-importer")
    listing = client.get("/v1/shares", params={"q": "Acceptance"})
    assert listing.status_code == 200
    assert share["id"] in [item["id"] for item in listing.json()]

    detail = client.get(f"/v1/shares/{share['id']}", headers=importer_headers)
    assert detail.status_code == 200
    assert detail.json()["export_payload"]["schema_version"] == "slice7-share-v1"

    # 3. 사용자 B가 같은 idempotency key로 두 번 가져온다.
    reset_counters()
    first_import = client.post(
        f"/v1/shares/{share['id']}/imports",
        headers={**importer_headers, "Idempotency-Key": "acceptance-key"},
    )
    second_import = client.post(
        f"/v1/shares/{share['id']}/imports",
        headers={**importer_headers, "Idempotency-Key": "acceptance-key"},
    )
    import_call_counts = get_counts()

    # 4. 사용자 B 소유의 새 Simulation이 정확히 하나 생성됐는지 확인한다.
    assert first_import.status_code == 201
    assert second_import.status_code == 201
    assert first_import.json()["id"] == second_import.json()["id"]
    imported_simulation_id = first_import.json()["id"]

    with session_factory() as db:
        importer_id = db.execute(
            text("SELECT id FROM users WHERE username = 'acceptance-importer'")
        ).scalar_one()
        owned_simulation_count = db.execute(
            text("SELECT count(*) FROM simulations WHERE owner_id = :id"), {"id": importer_id}
        ).scalar_one()
    assert owned_simulation_count == 1

    # 5. 설정·roster·Persona·상태 Snapshot이 원본 공유 Snapshot과 일치하는지 확인한다.
    with session_factory() as db:
        agent_count = db.execute(
            text("SELECT count(*) FROM agents WHERE simulation_id = :id"),
            {"id": imported_simulation_id},
        ).scalar_one()
        student_count = db.execute(
            text(
                "SELECT count(*) FROM agents a JOIN student_profiles sp ON sp.agent_id = a.id "
                "WHERE a.simulation_id = :id"
            ),
            {"id": imported_simulation_id},
        ).scalar_one()
        professor_count = db.execute(
            text(
                "SELECT count(*) FROM agents a JOIN professor_profiles pp ON pp.agent_id = a.id "
                "WHERE a.simulation_id = :id"
            ),
            {"id": imported_simulation_id},
        ).scalar_one()
        snapshot_count = db.execute(
            text("SELECT count(*) FROM simulation_snapshots WHERE simulation_id = :id"),
            {"id": imported_simulation_id},
        ).scalar_one()
    assert agent_count == 6
    assert student_count == 5
    assert professor_count == 1
    assert snapshot_count == 1  # Tick 0 initial snapshot only — Replay/Tick never ran

    # 6. 가져온 Simulation을 시작하고 최소 한 Tick 실행 가능한지 확인한다
    #    (import 자체는 Runtime을 호출하지 않지만, 결과물이 실행 가능해야 한다).
    agents = client.get(
        f"/v1/simulations/{imported_simulation_id}/agents", headers=importer_headers
    ).json()
    student = next(a for a in agents if a["agent_type"] == "student")
    persona_response = client.post(
        f"/v1/simulations/{imported_simulation_id}/user-persona",
        headers=importer_headers,
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
    assert persona_response.status_code == 200
    start_response = client.post(
        f"/v1/simulations/{imported_simulation_id}/start", headers=importer_headers
    )
    assert start_response.status_code == 200

    # 7. 원본 Simulation과 공유 Snapshot이 변경되지 않았는지 확인한다.
    with session_factory() as db:
        original = db.execute(
            text("SELECT name, status, current_tick, started_at FROM simulations WHERE id = :id"),
            {"id": simulation_id},
        ).mappings().one()
    assert original["name"] == "Acceptance Simulation"
    assert original["status"] == "ready"
    assert original["current_tick"] == 0
    assert original["started_at"] is None

    unchanged_detail = client.get(f"/v1/shares/{share['id']}", headers=owner_headers)
    assert unchanged_detail.json()["export_payload"] == share["export_payload"]

    # --- 완료 기준: import 중 Runtime·LLM·Tick 호출 0회 ----------------------
    assert import_call_counts == {"llm_calls": 0, "runtime_calls": 0, "tick_calls": 0}

    # --- 완료 기준: private/unlisted 노출 0건 --------------------------------
    private_simulation_id = _create_simulation(client, owner_headers, "Private Simulation")
    private_share = client.post(
        f"/v1/simulations/{private_simulation_id}/shares",
        headers=owner_headers,
        json={"visibility": "private", "title": "hidden", "description": None},
    ).json()
    unlisted_simulation_id = _create_simulation(client, owner_headers, "Unlisted Simulation")
    unlisted_share = client.post(
        f"/v1/simulations/{unlisted_simulation_id}/shares",
        headers=owner_headers,
        json={"visibility": "unlisted", "title": "linkonly", "description": None},
    ).json()

    public_listing = client.get("/v1/shares").json()
    listed_ids = {item["id"] for item in public_listing}
    assert private_share["id"] not in listed_ids
    assert unlisted_share["id"] not in listed_ids

    forbidden_private = client.get(f"/v1/shares/{private_share['id']}", headers=importer_headers)
    assert forbidden_private.status_code == 404

    unlisted_direct = client.get(f"/v1/shares/{unlisted_share['id']}", headers=importer_headers)
    assert unlisted_direct.status_code == 200  # 정확한 ID로는 접근 허용

    # --- 완료 기준: 취소된 공유 접근·가져오기 차단(revoked → 404) -----------
    cancel_response = client.delete(f"/v1/shares/{unlisted_share['id']}", headers=owner_headers)
    assert cancel_response.status_code == 204
    revoked_import = client.post(
        f"/v1/shares/{unlisted_share['id']}/imports",
        headers={**importer_headers, "Idempotency-Key": "revoked-key"},
    )
    assert revoked_import.status_code == 404

    # --- 완료 기준: idempotency 충돌(같은 key, 다른 share) → 409 ------------
    other_simulation_id = _create_simulation(client, owner_headers, "Other Simulation")
    other_share = client.post(
        f"/v1/simulations/{other_simulation_id}/shares",
        headers=owner_headers,
        json={"visibility": "public", "title": "other", "description": None},
    ).json()
    conflicting_import = client.post(
        f"/v1/shares/{other_share['id']}/imports",
        headers={**importer_headers, "Idempotency-Key": "acceptance-key"},
    )
    assert conflicting_import.status_code == 409
    assert conflicting_import.json()["error"]["code"] == "IMPORT_IDEMPOTENCY_CONFLICT"

    # --- 완료 기준: 실행 중 Simulation은 공유 불가(409) ----------------------
    not_ready_share = client.post(
        f"/v1/simulations/{imported_simulation_id}/shares",
        headers=importer_headers,
        json={"visibility": "public", "title": "already running", "description": None},
    )
    assert not_ready_share.status_code == 409
    assert not_ready_share.json()["error"]["code"] == "SIMULATION_SHARE_NOT_READY"
