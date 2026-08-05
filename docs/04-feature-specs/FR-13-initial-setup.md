---
title: "FR-13 초기 설정 — Slice 0"
status: approved
visibility: public
updated: 2026-08-05
---

# FR-13 초기 설정 — Slice 0

Simulation 생성 transaction에서 `dormitory`, `classroom` Location과 생활 Agent
6명을 upsert한다. 중복 기준은 `(simulation_id, fixture_key)`다.

| fixture_key | version | 이름 | type | MBTI | 학년 | Location |
|---|---|---|---|---|---:|---|
| student-01 | student-fixture-v0.2 | 아델 | student | ISTJ | 1 | dormitory |
| student-02 | student-fixture-v0.2 | 레오 | student | ESTP | 2 | dormitory |
| student-03 | student-fixture-v0.2 | 리아 | student | INFP | 1 | dormitory |
| student-04 | student-fixture-v0.2 | 카이 | student | ENTJ | 3 | dormitory |
| student-05 | student-fixture-v0.2 | 세라 | student | ESFJ | 4 | dormitory |
| professor-01 | professor-fixture-v0.2 | 에단 | professor | ISTJ |  | classroom |

- Agent ID는 UUIDv7이다.
- Big Five는 모두 50으로 시작한다.
- State는 hunger 50, fatigue 0, stress 0, satisfaction 50, mood 0이다.
- 생성 중 실패하면 Simulation을 포함한 전체 transaction을 rollback한다.
- 관계, Memory, User Persona 전환은 Slice 0 범위에서 제외한다.
