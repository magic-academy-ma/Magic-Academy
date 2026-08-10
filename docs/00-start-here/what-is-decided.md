---
title: 확정된 사항
status: approved
updated: 2026-08-08
---

# 확정된 사항

---

## 프로젝트 방향

- **한 줄 정의**: 사용자 없이도 자율적으로 돌아가고, 개입 시 결과가 달라지는 사회 실험형 마법 대학교 시뮬레이션
- **사용자 개입 범위**: User Persona Agent 1명의 성격·성향 지정까지로 제한
- **사용자 흐름**: 관찰 → 개입 방식 선택 → User Persona Agent가 개입 스타일 반영 → 시뮬레이션 진행 → 변화 확인

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
