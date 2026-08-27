from datetime import UTC, datetime
from uuid import uuid4

import jwt

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.domain.models import User
from app.services.fixtures import AGENT_FIXTURES, LOCATIONS, MVP_MAJOR_NAME


def test_fixture_contract_has_exactly_five_students_and_one_professor() -> None:
    students = [fixture for fixture in AGENT_FIXTURES if fixture.agent_type == "student"]
    professors = [fixture for fixture in AGENT_FIXTURES if fixture.agent_type == "professor"]
    assert len(AGENT_FIXTURES) == 6
    assert len(students) == 5
    assert len(professors) == 1
    assert [fixture.key for fixture in AGENT_FIXTURES] == [
        "student-01", "student-02", "student-03", "student-04", "student-05", "professor-01"
    ]
    # MVP 공간 6종 (mvp-feature-spec.md §2.5). code는 소문자 snake_case 컨벤션.
    assert LOCATIONS == {
        "classroom": "교실",
        "restaurant": "식당",
        "library": "도서관",
        "lab": "연구실",
        "dormitory": "기숙사",
        "central_square": "중앙광장",
    }
    # MVP 단일 전공.
    assert MVP_MAJOR_NAME == "마법공학과"


def test_each_fixture_matches_the_confluence_v02_contract() -> None:
    expected = {
        "student-01": ("student-fixture-v0.2", "아델", "student", "ISTJ", "female", -25, 25, -25, -20, 0, 25, 15, 20, 60, 0, 1, "방어 마법", None, None, "dormitory"),
        "student-02": ("student-fixture-v0.2", "레오", "student", "ESTP", "male", -25, -25, 25, -20, 0, 35, 20, 15, 65, 10, 2, "마법 생물", None, None, "dormitory"),
        "student-03": ("student-fixture-v0.2", "리아", "student", "INFP", "female", 25, -25, -25, 20, 0, 20, 15, 20, 55, 0, 1, "고대 마법", None, None, "dormitory"),
        "student-04": ("student-fixture-v0.2", "카이", "student", "ENTJ", "male", 25, 25, 25, -20, 0, 25, 10, 25, 60, 5, 3, "마법 도구 제작", None, None, "dormitory"),
        "student-05": ("student-fixture-v0.2", "세라", "student", "ESFJ", "female", -25, 25, 25, 20, 0, 30, 20, 15, 65, 10, 4, "마법약", None, None, "dormitory"),
        "professor-01": ("professor-fixture-v0.2", "에단", "professor", "ISTJ", "male", -20, 40, -25, 10, 35, 20, 15, 20, 70, 20, None, None, "통합 교수", "통합마법학과 수업·시험·학생 지도", "classroom"),
    }
    for fixture in AGENT_FIXTURES:
        assert (
            fixture.version,
            fixture.name,
            fixture.agent_type,
            fixture.mbti_type,
            fixture.gender,
            fixture.openness,
            fixture.conscientiousness,
            fixture.extraversion,
            fixture.agreeableness,
            fixture.emotional_stability,
            fixture.hunger,
            fixture.fatigue,
            fixture.stress,
            fixture.satisfaction,
            fixture.mood,
            fixture.grade,
            fixture.interest_field,
            fixture.academic_rank,
            fixture.specialty,
            fixture.location_code,
        ) == expected[fixture.key]


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
