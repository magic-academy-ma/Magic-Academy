from datetime import UTC, datetime
from uuid import uuid4

import jwt

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.domain.models import User
from app.services.fixtures import AGENT_FIXTURES, LOCATIONS


def test_fixture_contract_has_exactly_five_students_and_one_professor() -> None:
    students = [fixture for fixture in AGENT_FIXTURES if fixture.agent_type == "student"]
    professors = [fixture for fixture in AGENT_FIXTURES if fixture.agent_type == "professor"]
    assert len(AGENT_FIXTURES) == 6
    assert len(students) == 5
    assert len(professors) == 1
    assert [fixture.key for fixture in AGENT_FIXTURES] == [
        "student-01", "student-02", "student-03", "student-04", "student-05", "professor-01"
    ]
    assert LOCATIONS == {"dormitory": "기숙사", "classroom": "교실"}


def test_password_is_hashed_and_verified() -> None:
    encoded = hash_password("correct-horse")
    assert encoded != "correct-horse"
    assert verify_password("correct-horse", encoded)
    assert not verify_password("wrong-password", encoded)


def test_access_token_contains_required_claims(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-secret-that-is-long-enough-for-tests")
    get_settings.cache_clear()
    user = User(id=uuid4(), username="user-a", display_name="User A", password_hash="unused", roles=["USER"])
    token = create_access_token(user, datetime(2026, 8, 5, tzinfo=UTC))
    settings = get_settings()
    claims = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=["HS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
        options={"verify_exp": False},
    )
    assert {"sub", "roles", "iss", "aud", "iat", "exp", "jti"} <= set(claims)
    assert claims["sub"] == str(user.id)
    assert claims["roles"] == ["USER"]
    get_settings.cache_clear()
