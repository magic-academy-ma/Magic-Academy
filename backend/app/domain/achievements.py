"""업적 카탈로그 — docs/04-feature-specs/achievements.md의 업적 목록.

목록 순서는 문서 순서를 따르고, 업적 화면도 이 순서로 보여 준다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AchievementMode(StrEnum):
    STORY = "STORY"
    FREE = "FREE"


class AchievementKind(StrEnum):
    PROGRESS = "PROGRESS"  # 진행
    OBSERVATION = "OBSERVATION"  # 관찰
    INTERVENTION = "INTERVENTION"  # 개입
    OUTCOME = "OUTCOME"  # 결과


@dataclass(frozen=True)
class Achievement:
    id: str
    name: str
    mode: AchievementMode
    group: str
    kind: AchievementKind
    condition: str


_STORY = AchievementMode.STORY
_FREE = AchievementMode.FREE
_PROGRESS = AchievementKind.PROGRESS
_OBSERVATION = AchievementKind.OBSERVATION
_INTERVENTION = AchievementKind.INTERVENTION
_OUTCOME = AchievementKind.OUTCOME

_CHAPTER1 = "CHAPTER 1 거짓 소문의 확산을 막아라"
_CHAPTER2 = "CHAPTER 2 무너진 팀을 다시 살려라"
_CHAPTER3 = "CHAPTER 3 동아리를 폐부에서 구하기"
_CHAPTER4 = "CHAPTER 4 축제 부스 운영하기"
_ENDING = "엔딩 스토리"
_STORY_COMMON = "스토리모드 공통"
_FREE_MODE = "자유 모드"

ACHIEVEMENTS: tuple[Achievement, ...] = (
    Achievement("CHAPTER1_CLEAR", "CHAPTER 1 클리어", _STORY, _CHAPTER1, _PROGRESS,
                "CHAPTER 1을 끝까지 진행한다"),
    Achievement("FIRST_SENTENCE", "소문의 첫 문장", _STORY, _CHAPTER1, _OBSERVATION,
                "학생들과의 대화를 통해 소문을 처음 전한 학생을 찾아낸다"),
    Achievement("HEARD_AND_SEEN", "들은 것과 본 것", _STORY, _CHAPTER1, _INTERVENTION,
                "서로 다른 학생의 이야기를 비교하고, 당사자나 교수에게 사실을 확인한 뒤 대응한다"),
    Achievement("FAN_THE_FLAME", "불씨를 키운 사람", _STORY, _CHAPTER1, _INTERVENTION,
                "확인되지 않은 이야기를 플레이어가 전달해 소문을 더 퍼뜨린다"),
    Achievement("SILENT_WITNESS", "침묵을 깬 증인", _STORY, _CHAPTER1, _INTERVENTION,
                "진실을 알지만 사건에 휘말리기 싫어하던 학생이 스스로 사실을 말하도록 이끈다"),
    Achievement("THREE_RUMORS", "말이 말을 낳고", _STORY, _CHAPTER1, _OBSERVATION,
                "같은 사건에 관한 서로 다른 소문 3가지를 듣는다"),
    Achievement("AHEAD_OF_RUMOR", "소문보다 한발 먼저", _STORY, _CHAPTER1, _INTERVENTION,
                "소문이 학교 전체로 퍼지기 전에 사실을 확인하고 확산을 막는다"),
    Achievement("SELF_CORRECTION", "되돌리는 한마디", _STORY, _CHAPTER1, _INTERVENTION,
                "소문을 퍼뜨렸던 학생이 자신의 말을 스스로 정정한다"),
    Achievement("CHAPTER2_CLEAR", "CHAPTER 2 클리어", _STORY, _CHAPTER2, _PROGRESS,
                "CHAPTER 2를 끝까지 진행한다"),
    Achievement("WORSENED_RELATIONS", "마이너스의 손", _STORY, _CHAPTER2, _INTERVENTION,
                "팀원들끼리의 관계를 더 악화시킨다"),
    Achievement("HANDS_OFF_REVIVAL", "다 계획이 있구나!", _STORY, _CHAPTER2, _INTERVENTION,
                "한 번도 손대지 않고 팀을 살려낸다"),
    Achievement("ENEMIES_TO_ALLIES", "원수에서 전우로", _STORY, _CHAPTER2, _OUTCOME,
                "학생들이 모두 서로에게 호감을 가진 채로 마감을 맞는다"),
    Achievement("CHAPTER3_CLEAR", "CHAPTER 3 클리어", _STORY, _CHAPTER3, _PROGRESS,
                "CHAPTER 3을 끝까지 진행한다"),
    Achievement("GLORY_DAYS", "다시 전성기다!", _STORY, _CHAPTER3, _OUTCOME,
                "동아리 부활 엔딩을 맞는다"),
    Achievement("CATASTROPHE", "파국이다!", _STORY, _CHAPTER3, _INTERVENTION,
                "시작 시점보다 회원 관계를 악화시킨다"),
    Achievement("MEMBERS_FIRST", "일단 사람부터 모아", _STORY, _CHAPTER3, _OUTCOME,
                "회원 수만 채워 조건부로 동아리를 유지한다"),
    Achievement("CLUB_OF_ONE", "나 홀로 동아리", _STORY, _CHAPTER3, _OUTCOME,
                "회원이 1명만 남은 채로 챕터를 끝낸다"),
    Achievement("CHAPTER4_CLEAR", "CHAPTER 4 클리어", _STORY, _CHAPTER4, _PROGRESS,
                "CHAPTER 4를 끝까지 진행한다"),
    Achievement("SHOW_MUST_GO_ON", "쇼는 계속되어야 한다", _STORY, _CHAPTER4, _INTERVENTION,
                "돌발 상황에서도 부스를 멈추지 않고 최고의 축제를 만든다"),
    Achievement("BOOTH_LEFT_EMPTY", "여기 비었잖아", _STORY, _CHAPTER4, _INTERVENTION,
                "어떤 이유로든 잠시라도 부스를 비운다"),
    Achievement("FESTIVAL_IS_OVER", "축제는 끝났다", _STORY, _CHAPTER4, _OUTCOME,
                "스트레스 한계값 초과자가 발생한다"),
    Achievement("ENDING_UNLOCKED", "엔딩 스토리 해금", _STORY, _ENDING, _PROGRESS,
                "CHAPTER 1~4를 모두 클리어한다"),
    Achievement("ENDING_CLEAR", "엔딩 스토리 클리어", _STORY, _ENDING, _PROGRESS,
                "엔딩 스토리를 끝까지 본다"),
    Achievement("INDECISIVE", "우유부단하시네요", _STORY, _STORY_COMMON, _INTERVENTION,
                "사용자 개입에서 결정에 오랜 시간(5분 이상)을 사용한다"),
    Achievement("MISSING_STUDENT_RETURN", "실종된 학생의 귀환 목격", _FREE, _FREE_MODE, _OBSERVATION,
                "돌아온 학생의 Inspector를 연다"),
    Achievement("MAGIC_DISCOVERY", "마법 발견 목격", _FREE, _FREE_MODE, _OBSERVATION,
                "마법 발견 이벤트를 목격한다"),
    Achievement("CURSE_TRIGGERED", "저주 이벤트 발생", _FREE, _FREE_MODE, _OBSERVATION,
                "저주 이벤트를 발생시킨다"),
    Achievement("CURSE_SPREAD", "저주 확산", _FREE, _FREE_MODE, _OBSERVATION,
                "3명 이상이 저주에 감염된다"),
    Achievement("CURSE_LIFTED", "저주 해결", _FREE, _FREE_MODE, _OBSERVATION,
                "저주를 해결한다"),
)

ACHIEVEMENTS_BY_ID: dict[str, Achievement] = {achievement.id: achievement for achievement in ACHIEVEMENTS}
