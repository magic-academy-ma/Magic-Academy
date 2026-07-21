---
title: 확정된 사항
status: approved
visibility: public
updated: 2026-07-20
source:
  - "[Spec] MVP 핵심 설계 기준 (Confluence #6356994)"
  - "2026-07-09 기술 스택 확정 회의 (Confluence #7405620)"
  - "시스템 레이어 구조 (Confluence #6389788)"
  - "Magic Layer 설계 (Confluence #6619141)"
  - "2026-07-18 회의 — 타겟 유저 확정"
  - "2026-07-20 회의 — 프롬프트 캐싱 시점 확정"
---

# 확정된 사항

> 출처: 2차 회의 (2026-07-07) · [Spec] MVP 핵심 설계 기준 (Confluence #6356994) · 2026-07-09 기술 스택 확정 회의 (Confluence #7405620)

---

## 프로젝트 방향

- **한 줄 정의**: 사용자 없이도 자율적으로 돌아가고, 개입 시 결과가 달라지는 사회 실험형 마법 대학교 시뮬레이션
- **사용자 개입 범위**: User Persona Agent 1명의 성격·성향 지정까지로 제한
- **사용자 흐름**: 관찰 → 개입 방식 선택 → User Persona Agent가 개입 스타일 반영 → 시뮬레이션 진행 → 변화 확인

---

## Agent 구성 (MVP)

> 출처: [Spec] MVP 핵심 설계 기준 §FR-01~FR-09 · Magic Layer 설계 (Confluence #6619141)

| Agent | 수량 | 비고 |
|-------|------|------|
| Student Agent | 초기 5 / MVP 8~10 | 초기 구현은 단일 전공 5명, MVP는 8~10명 — §FR-01 |
| Professor Agent | 5 | 교양 1 + 전공 4 — §FR-01 |
| Event Master Agent | 1 | 매 Tick 사건 생성 오케스트레이터 — §FR-05, FR-09 |
| Magic Agent | 1 | 마법 세계 특화 사건 생성 · Magic Layer 운영 |

- **User Persona**: 별도 Agent 아님. Student 중 1명을 지정하며 성격·성향 수정 가능. 직접 조종 불가.
- **Student Agent memory 상한**: 최대 10 — §FR-02
- **Magic Layer 실행 위치**: Event Master → Magic Layer → Agent Runtime

---

## 세계관 카테고리

시간 / 공간 / 조직 / 관계 / 사건 / 배경

### 시간

- **Time Tick**: 24분 = 1일
- 수업 시간·점심 시간 구분, 밤 시간은 스킵 가능
- 시뮬레이션은 입학 시점부터 Tick 기반으로 진행

### 공간

교실 · 식당 · 도서관 · 연구실 · 기숙사

### 조직

- 기숙사 2개
- 동아리 3개
- 전공 4개 × 학생 5명 = 20명, 학년 4학년까지 전공별 랜덤 배정
- 총학생회 4~5명
- **규칙**: 소속이 같으면 친밀도 UP

### 관계

| 구분 | 목록 |
|------|------|
| 척도 | 호감도 · 친밀도 · 신뢰도 · 긴장도(갈등) · 경쟁 · 의존도 |
| 유형 | 친구 · 선후배 · 라이벌 · 고백 · 배신 · 화해 |

### 사건 (MVP 포함)

수업(시간표) · 조별 과제 · 과팅/미팅 · MT · 중간·기말고사(→장학금) · 축제 · 교수님 납치(→대학원 직행) · 랜덤 날씨(이벤트 전 징조)

### 배경

랜덤 날씨, 한국식 학기제, 장학금·상/벌점 기반 학교 운영

---

## 기술 스택

> 출처: 2026-07-09 기술 스택 확정 회의 (Confluence #7405620)

| 계층 | 기술 |
|------|------|
| 백엔드 | FastAPI |
| 에이전트 오케스트레이션 | LangGraph |
| DB | PostgreSQL + pgvector |
| 프론트엔드 | React |
| 인프라 | Docker Compose |

---

## 개발 환경

- **GitHub Actions CI**: 구축 완료
- **CodeRabbit**: AI PR 리뷰어 설치 완료
- **docs/ 구조**: 확정 (`docs/README.md` 참조)
- **SYNC.md**: Confluence → docs/ 이관 정책·큐 (`docs/_meta/SYNC.md`)

---

## MVP 제외 확정

- 단과대학 확장
- 인간-동물 관계 확장
- Agent/조직 수 확장
- 사건 규모 확장
