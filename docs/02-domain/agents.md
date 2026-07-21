---
title: Agent 정의
source:
  - "[Spec] MVP 핵심 설계 기준 (Confluence #6356994)"
  - "Magic Layer 설계 (Confluence #6619141)"
  - "2026-07-09 기술 스택 확정 회의 (Confluence #7405620)"
canonical:
  - https://jehye.atlassian.net/wiki/spaces/MA/pages/6356994
  - https://jehye.atlassian.net/wiki/spaces/MA/pages/6619141
status: approved
visibility: public
updated: 2026-07-13
---

# Agent 정의

## MVP Agent 구성

| Agent 종류 | 수량 | 역할 | 출처 |
|-----------|------|------|------|
| Student Agent | 20 | 시뮬레이션의 주체. 관계·조직·사건의 중심 | Spec §FR-01 |
| Professor Agent | 5 | 수업·시험·조별과제 등 학사 사건의 진행자 | Spec §FR-01 |
| Event Master Agent | 1 | 매 Tick 사건 생성 오케스트레이터 | Spec §FR-05, FR-09 |
| Magic Agent | 1 | 마법 세계 특화 사건 생성 · Magic Layer 운영 | Magic Layer 설계 |

> **User Persona**: 별도 Agent 아님. Student 20명 중 1명을 사용자가 지정하며, 해당 Agent의 성격·성향을 수정할 수 있다. 직접 조종은 MVP 제외.

---

## 공통 내부 상태

모든 Agent는 아래 내부 상태를 보유하며, 이 상태가 행동과 관계 변화의 입력이 된다.

| 상태 | 설명 |
|------|------|
| 배고픔 | 식사 이벤트로 감소 |
| 피로도 | Tick 경과·수업·활동으로 누적, 수면(밤 스킵) 시 감소 |
| 스트레스 | 시험·갈등·과제로 누적 |
| 만족도 | 긍정 사건·관계 호전으로 상승 |
| 기분 | 위 4개 상태와 관계 변화의 복합 결과 |

---

## Student Agent

- **수량**: 20명 (한 반 기준) — Spec §FR-01
- **memory 상한**: 최대 10 (핵심 리스크: 토큰 비용) — Spec §FR-02
- **조직 소속**: 전공 1개 + 기숙사 1개 + 동아리 0~1개 + 총학생회(선택)
- **학년**: 1~4학년 중 전공별 랜덤 배정
- 성격·성향을 개별 부여할 수 있으며, 주인공적 성격 부여 가능
- **User Persona 지정**: 20명 중 1명을 사용자가 지정. 해당 Agent의 성격·성향만 수정 가능. 직접 조종 불가 (MVP 제외)

## Professor Agent

- **수량**: 5명 (교양 교수 1 + 전공 교수 4) — Spec §FR-01
- 담당 과목의 수업·시험·조별과제 사건을 진행
- 학생 Agent와 관계(신뢰도·의존도 등)를 형성할 수 있음

## Event Master Agent

- **수량**: 1
- **MVP 포함**: 확정 — Spec §FR-05, FR-09
- 역할: 매 Tick 사건을 생성하는 오케스트레이터 (하루 1~2회 특별 사건 생성)
- 모델: Sonnet (서사 품질 중요)

## Magic Agent

- **수량**: 1
- **MVP 포함**: 확정 — Magic Layer 설계 (Confluence #6619141)
- 역할: 마법 세계 특화 사건 생성 (마법 실험 폭발·저주·실종 등 RANDOM_INCIDENT 분기)
