from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/students", tags=["students"])


class Student(BaseModel):
    id: int
    name: str
    grade: int
    major: str
    dormitory: str
    is_user_persona: bool


# 임시 더미 데이터 — Agent 초기값 배정 방식 확정 후 교체 예정 (Issue #11)
_MAJORS = ["마법공학", "마법생물학", "마법역사학", "마법약학"]
_DORMS = ["그리폰관", "피닉스관"]

DUMMY_STUDENTS: list[Student] = [
    Student(id=1,  name="김지우", grade=1, major="마법공학",   dormitory="그리폰관", is_user_persona=True),
    Student(id=2,  name="이하늘", grade=2, major="마법생물학", dormitory="피닉스관", is_user_persona=False),
    Student(id=3,  name="박서준", grade=3, major="마법역사학", dormitory="그리폰관", is_user_persona=False),
    Student(id=4,  name="최아린", grade=1, major="마법약학",   dormitory="피닉스관", is_user_persona=False),
    Student(id=5,  name="정민준", grade=4, major="마법공학",   dormitory="그리폰관", is_user_persona=False),
    Student(id=6,  name="강유진", grade=2, major="마법생물학", dormitory="피닉스관", is_user_persona=False),
    Student(id=7,  name="윤서연", grade=3, major="마법역사학", dormitory="그리폰관", is_user_persona=False),
    Student(id=8,  name="임채원", grade=1, major="마법약학",   dormitory="피닉스관", is_user_persona=False),
    Student(id=9,  name="한도윤", grade=4, major="마법공학",   dormitory="그리폰관", is_user_persona=False),
    Student(id=10, name="오지현", grade=2, major="마법생물학", dormitory="피닉스관", is_user_persona=False),
    Student(id=11, name="신예은", grade=3, major="마법역사학", dormitory="그리폰관", is_user_persona=False),
    Student(id=12, name="배현우", grade=1, major="마법약학",   dormitory="피닉스관", is_user_persona=False),
    Student(id=13, name="권나연", grade=4, major="마법공학",   dormitory="그리폰관", is_user_persona=False),
    Student(id=14, name="유승호", grade=2, major="마법생물학", dormitory="피닉스관", is_user_persona=False),
    Student(id=15, name="안지수", grade=3, major="마법역사학", dormitory="그리폰관", is_user_persona=False),
    Student(id=16, name="전민서", grade=1, major="마법약학",   dormitory="피닉스관", is_user_persona=False),
    Student(id=17, name="조은찬", grade=4, major="마법공학",   dormitory="그리폰관", is_user_persona=False),
    Student(id=18, name="황소율", grade=2, major="마법생물학", dormitory="피닉스관", is_user_persona=False),
    Student(id=19, name="서지호", grade=3, major="마법역사학", dormitory="그리폰관", is_user_persona=False),
    Student(id=20, name="문가영", grade=1, major="마법약학",   dormitory="피닉스관", is_user_persona=False),
]


@router.get("/", response_model=list[Student])
async def list_students() -> list[Student]:
    return DUMMY_STUDENTS
