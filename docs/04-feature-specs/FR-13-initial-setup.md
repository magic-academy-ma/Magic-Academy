---
title: "FR-13 초기 설정 — Slice 0"
status: approved
updated: 2026-08-06
---

# FR-13 초기 설정 — Slice 0

Simulation 생성 transaction에서 `dormitory`, `classroom` Location과 생활 Agent
6명을 upsert한다. 중복 기준은 `(simulation_id, fixture_key)`다.

| fixture_key | version | 이름 | type | MBTI | 역할 Profile | Location |
|---|---|---|---|---|---|---|
| student-01 | student-fixture-v0.2 | 아델 | student | ISTJ | 1학년 / 방어 마법 | dormitory |
| student-02 | student-fixture-v0.2 | 레오 | student | ESTP | 2학년 / 마법 생물 | dormitory |
| student-03 | student-fixture-v0.2 | 리아 | student | INFP | 1학년 / 고대 마법 | dormitory |
| student-04 | student-fixture-v0.2 | 카이 | student | ENTJ | 3학년 / 마법 도구 제작 | dormitory |
| student-05 | student-fixture-v0.2 | 세라 | student | ESFJ | 4학년 / 마법약 | dormitory |
| professor-01 | professor-fixture-v0.2 | 에단 | professor | ISTJ | 통합 교수 / 통합마법학과 수업·시험·학생 지도 | classroom |

| fixture_key | openness | conscientiousness | extraversion | agreeableness | emotional_stability |
|---|---:|---:|---:|---:|---:|
| student-01 | -25 | 25 | -25 | -20 | 0 |
| student-02 | -25 | -25 | 25 | -20 | 0 |
| student-03 | 25 | -25 | -25 | 20 | 0 |
| student-04 | 25 | 25 | 25 | -20 | 0 |
| student-05 | -25 | 25 | 25 | 20 | 0 |
| professor-01 | -20 | 40 | -25 | 10 | 35 |

| fixture_key | hunger | fatigue | stress | satisfaction | mood |
|---|---:|---:|---:|---:|---:|
| student-01 | 25 | 15 | 20 | 60 | 0 |
| student-02 | 35 | 20 | 15 | 65 | 10 |
| student-03 | 20 | 15 | 20 | 55 | 0 |
| student-04 | 25 | 10 | 25 | 60 | 5 |
| student-05 | 30 | 20 | 15 | 65 | 10 |
| professor-01 | 20 | 15 | 20 | 70 | 20 |

- Agent ID는 UUIDv7이다.
- Big Five는 `-50~50` 범위의 5단위 값이며 위 Agent별 값을 명시적으로 저장한다.
- State는 DB 기본값에 의존하지 않고 위 Agent별 값을 명시적으로 저장한다.
- Student 역할 정보는 `student_profiles`, Professor 역할 정보는 `professor_profiles`에 저장한다.
- 생성 중 실패하면 Simulation을 포함한 전체 transaction을 rollback한다.
- 관계, Memory, User Persona 전환은 Slice 0 범위에서 제외한다.
