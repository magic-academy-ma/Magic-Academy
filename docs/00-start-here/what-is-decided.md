---
title: 확정된 사항
status: approved
visibility: internal
updated: 2026-07-28
source:
  - "[Spec] MVP 핵심 설계 기준 (Confluence #6356994)"
  - "2026-07-09 기술 스택 확정 회의 (Confluence #7405620)"
  - "시스템 레이어 구조 (Confluence #6389788)"
  - "Magic Layer 설계 (Confluence #6619141)"
  - "2026-07-18 회의 — 타겟 유저 확정"
  - "2026-07-20 회의 — 프롬프트 캐싱 시점 확정"
  - "시스템 아키텍처 v2.3 (Confluence #8290305) — Agent 수 · Tick 단위 확정"
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
| Student Agent | 1단계 5명 (User Persona 1명 포함) | 2단계 이상 확장 예정 — §FR-01 |
| Professor Agent | 1단계 1명 | 2단계 이상 확장 예정 — §FR-01 |
| Event Master Agent | 1 | 시스템 컴포넌트 (생활 Agent 수 제외) — §FR-05, FR-09 |
| Magic Layer | 1 | 시스템 컴포넌트 (생활 Agent 수 제외), Magic Layer 운영 |

- **1단계 생활 Agent**: Student 5명 + Professor 1명 = 총 6명

- **User Persona**: 별도 Agent 아님. Student 중 1명을 지정하며 성격·성향 수정 가능. 직접 조종 불가.
- **Student Agent memory 상한**: 최대 10 — §FR-02
- **Magic Layer 실행 위치**: Event Master → Magic Layer → Agent Runtime

---

## MVP 제외 확정

- 단과대학 확장
- 인간-동물 관계 확장
- Agent/조직 수 확장
- 사건 규모 확장
