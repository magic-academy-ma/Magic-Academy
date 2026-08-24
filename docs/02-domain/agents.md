---
title: Agent 정의
status: draft
updated: 2026-08-25
visibility: public
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
source_updated: 2026-08-14
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
| Magic Layer | 1 | 마법 세계관 변환 + 조건 기반 특수 사건 후보 서술 | Magic Layer 설계 |

> **User Persona**: 별도 Agent 아님. Student 5명 중 1명을 사용자가 지정하며, 해당 Agent의 성격·성향(Big Five)을 수정할 수 있다. 직접 조종 불가.

---

## 공통 내부 상태

모든 Agent는 아래 내부 상태를 보유하며, 이 상태가 행동과 관계 변화의 입력이 된다.

| 상태 | 범위 | 설명 |
|------|------|------|
| 배고픔 | 0~100 | 식사 이벤트로 감소 |
| 피로도 | 0~100 | Tick 경과·수업·활동으로 누적, 수면(밤 스킵) 시 감소 |
| 스트레스 | 0~100 | 시험·갈등·과제로 누적 |
| 만족도 | 0~100 | 긍정 사건·관계 호전으로 상승 |
| 기분 | -100~100 | 위 4개 상태와 관계 변화의 복합 결과 |

---

## Student Agent

- **memory 보유 상한**: 최대 10개 — Spec §FR-02
- **MVP 소속**: 단일 전공. 기숙사는 생활 공간이며 공식 조직이 아니다.
- **초기 성격 슬롯**: ISTJ·ESTP·INFP·ENTJ·ESFJ 각 1명
- **Big Five 성격**: 5개 축을 -50~+50 범위에서 사용하며 MBTI별 허용 범위 안에서 5단위로 설정
- **User Persona 지정**: 기존 Student 5명 중 1명을 선택한다. 시작 전에 MBTI와 Big Five를 설정하고 시작 후 잠근다.

### Student Runtime 기준

- Slice 1은 지정 Student 1명, 확장 단계는 Student 5명을 실행 대상으로 편성한다.
- preselected Student가 비활성이면 Runtime은 LLM 호출 없이 SKIPPED 결과를 반환한다.
- Agent는 Intent·Decision Explanation·Memory 후보·정성적 Reaction만 반환하고 수치 효과나 저장을 담당하지 않는다.
- 상태·일정·위치·관계·Memory·관찰 가능한 Event를 종합해 Tick당 대표 행동 하나를 선택한다.

## Professor Agent

- MVP 전공 교수 1명이며 Student와 같은 Runtime·상태·관계·Memory 계약을 사용한다.
- 현재 schedule에 교수 역할이 있거나 최종 Event 참여자로 지정된 Tick에만 실행 대상에 포함한다.
- 조건을 만족한 비활성 Professor는 SKIPPED 결과를 반환하고, 조건이 없는 Tick에는 Runtime 결과를 만들지 않는다.
- 수업·시험 감독·상담·연구·학생 관찰을 우선 행동 맥락으로 사용한다.

## Event Master Agent (시스템 컴포넌트)

- 하루 1~2회 특별 사건 생성
- 모델: Sonnet 4.6 (서사 품질 중요)

## Magic Layer (시스템 컴포넌트)

- 모델: Haiku 4.5
