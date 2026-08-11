---
title: Agent 정의
source:
  - "[Spec] MVP 핵심 설계 기준 (Confluence #6356994)"
  - "Magic Layer 설계 (Confluence #6619141)"
  - "2026-07-09 기술 스택 확정 회의 (Confluence #7405620)"
  - "시스템 아키텍처 v2.3 (Confluence #8290305)"
  - "Agent Runtime 설계 (Confluence #11894790)"
canonical:
  - https://jehye.atlassian.net/wiki/spaces/MA/pages/6356994
  - https://jehye.atlassian.net/wiki/spaces/MA/pages/6619141
  - https://jehye.atlassian.net/wiki/spaces/MA/pages/8290305
  - https://jehye.atlassian.net/wiki/spaces/MA/pages/11894790
status: approved
updated: 2026-07-28
---

# Agent 정의

## Agent 구성

### 생활 Agent (1단계 MVP: 6명)

| Agent 종류 | 1단계 | 역할 | 출처 |
|-----------|-------|------|------|
| Student Agent | 5명 (User Persona 1명 포함) | 시뮬레이션의 주체. 관계·조직·사건의 중심 | Spec §FR-01, 아키텍처 v2.3 |
| Professor Agent | 1명 | 수업·시험·조별과제 등 학사 사건의 진행자 | Spec §FR-01, 아키텍처 v2.3 |

2단계 13명, 3단계 25명으로 확장 예정.

### 시스템 컴포넌트 (생활 Agent 수 제외)

| 컴포넌트 | 수량 | 역할 | 출처 |
|---------|------|------|------|
| Event Master Agent | 1 | 매 Tick 사건 생성 오케스트레이터 | Spec §FR-05, FR-09 |
| Magic Layer | 1 | 마법 세계관 변환 + 30% 특수 사건 생성 | Magic Layer 설계 (Confluence #6619141) |

> **User Persona**: 별도 Agent 아님. Student 5명 중 1명을 사용자가 지정하며, 해당 Agent의 성격·성향(Big Five)을 수정할 수 있다. 직접 조종 불가.

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

- **1단계 수량**: 5명 (User Persona 1명 포함) — 아키텍처 v2.3 (Confluence #8290305)
- **memory 보유 상한**: 최대 10개 — Spec §FR-02
- **조직 소속**: 전공 1개 + 기숙사 1개 + 동아리 0~1개 + 총학생회(선택)
- **학년**: 1~4학년 중 전공별 랜덤 배정
- **Big Five 성격**: openness, conscientiousness, extraversion, agreeableness, emotional_stability (각 0~100 SMALLINT)
- **User Persona 지정**: 5명 중 1명을 사용자가 지정. Big Five 성향만 수정 가능. 직접 조종 불가.

## Professor Agent

- **1단계 수량**: 1명 — 아키텍처 v2.3 (Confluence #8290305)
- 담당 과목의 수업·시험·조별과제 사건을 진행
- 학생 Agent와 관계(신뢰도·의존도 등)를 형성할 수 있음

## Event Master Agent (시스템 컴포넌트)

- **수량**: 1 — 생활 Agent 수에서 제외
- **MVP 포함**: 확정 — Spec §FR-05, FR-09
- 역할: 매 Tick 사건을 생성하는 오케스트레이터 (하루 1~2회 특별 사건 생성)
- 모델: Sonnet 4.6 (서사 품질 중요)

## Magic Layer (시스템 컴포넌트)

- **수량**: 1 — 생활 Agent 수에서 제외
- **MVP 포함**: 확정 — Magic Layer 설계 (Confluence #6619141)
- 역할: ① Event Master 이벤트 마법 세계관 변환 (매 Tick) ② 30% 확률 마법 특수 사건 생성
- 모델: Haiku 4.5
