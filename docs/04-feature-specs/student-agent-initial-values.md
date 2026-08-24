---
title: Student Agent 초기값
source: confluence/03_REQUIREMENTS/student-agent-initial-values
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/19496962
status: review
visibility: public
updated: 2026-08-25
source_updated: 2026-08-14
---

# Student Agent 초기값

1단계 MVP는 랜덤 생성 대신 `student-fixture-v0.2`의 고정 Student 5명을 사용한다.

| fixture | 이름 | MBTI | 학년 | 성별 | 관심 분야 | 초기 상태 `(hunger/fatigue/stress/satisfaction/mood)` |
| --- | --- | --- | --- | --- | --- | --- |
| student-01 | 아델 | ISTJ | 1 | 여성 | 방어 마법 | 25 / 15 / 20 / 60 / 0 |
| student-02 | 레오 | ESTP | 2 | 남성 | 마법 생물 | 35 / 20 / 15 / 65 / 10 |
| student-03 | 리아 | INFP | 1 | 여성 | 고대 마법 | 20 / 15 / 20 / 55 / 0 |
| student-04 | 카이 | ENTJ | 3 | 남성 | 마법 도구 제작 | 25 / 10 / 25 / 60 / 5 |
| student-05 | 세라 | ESFJ | 4 | 여성 | 마법약 | 30 / 20 / 15 / 65 / 10 |

- 모두 마법공학과 소속이며 기숙사 공간에서 활성 상태로 시작한다.
- Student 간 자기 자신을 제외한 방향성 관계 20개의 모든 척도는 0으로 시작한다.
- 일반 Student는 성격에 맞는 배경 OBSERVATION 2개, User Persona는 최종 설정을 설명하는 OBSERVATION 1개로 시작한다.
- 대표 캠페인은 리아를 User Persona 기본 선택으로 사용한다. 일반 흐름에서는 어느 Student든 선택할 수 있다.
- User Persona 적용 후에도 생활 Agent 수는 변하지 않으며 이름·학년·성별·관심 분야를 유지한다.
- 시작 시 성격 설정을 잠그고 이후 성격 관련 초기 Memory를 사용자 요청으로 다시 작성하지 않는다.

성격 수치와 허용 범위의 단일 기준은 `docs/03-system-design/mbti-big-five-policy.md`다. 구체 저장 구조와 식별자 형식은 비공개 데이터 모델에서 관리한다.

## 검증 기준

- 같은 fixture·성격 규칙 버전은 같은 roster와 초기값을 만든다.
- MBTI 5종이 최초에 하나씩 존재한다.
- Student 간 방향성 관계는 20개이고 자기 관계가 없다.
- User Persona 적용 전후 Agent 수가 같고 정확히 한 명만 User Persona다.
- 설정 후 MBTI 중복과 특정 MBTI 부재를 허용한다.
