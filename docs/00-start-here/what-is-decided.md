---
title: 확정된 사항
status: approved
updated: 2026-08-25
visibility: public
source:
  - "[Spec] MVP 핵심 설계 기준 (Confluence #6356994)"
  - "2026-07-09 기술 스택 확정 회의 (Confluence #7405620)"
  - "시스템 레이어 구조 (Confluence #6389788)"
  - "Magic Layer 설계 (Confluence #6619141)"
  - "2026-07-18 회의 — 타겟 유저 확정"
  - "2026-07-20 회의 — 프롬프트 캐싱 시점 확정"
  - "시스템 아키텍처 v2.3 (Confluence #8290305) — Agent 수 · Tick 단위 확정"
source_updated: 2026-08-14
---

# 확정된 사항

---

## 프로젝트 방향

- **한 줄 정의**: 사용자 없이도 자율적으로 돌아가고, 개입 시 결과가 달라지는 사회 실험형 마법 대학교 시뮬레이션
- **사용자 개입 범위**: 시작 전 User Persona 성격·성향과 Magic 설정, 실행 중 일반 Event 파라미터 조정으로 제한
- **사용자 흐름**: 초기 설정 → User Persona·Magic 설정 → 실행 시작 및 설정 잠금 → 관찰·제한적 조정 → 변화 확인·Replay
- **Inspector**: 읽기 전용이며 구조화된 Decision Explanation만 표시하고 내부 추론 원문은 저장·노출하지 않음
- **일반 시뮬레이션**: 승패 없이 관찰을 지속하거나 중단
- **대표 캠페인**: Tick 7 고정 종료 후 관계 지표로 결과 판정

---

## Agent 구성 (MVP)

1단계 생활 Agent: Student 5명 (User Persona 1명 포함) + Professor 1명. 시스템 컴포넌트: Event Master Agent · Magic Layer 각 1개.  
상세: `docs/02-domain/agents.md`

---

## 기술 스택

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
- Agent 직접 명령과 실행 중 User Persona 성격 변경
- 내부 chain-of-thought·raw reasoning 노출
