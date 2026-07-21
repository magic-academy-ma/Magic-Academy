# SYNC.md — Confluence → docs/ 이관 정책

## 워크플로우

```
[주 2회] 담당자가 Confluence 업데이트 확인
      ↓
이관 필요 문서 → 아래 이관 큐에 추가 (⬜)
      ↓
이관 작업: docs/ 반영 + frontmatter 갱신
      ↓
PR → 리뷰 → main 머지
      ↓
이관 큐 완료 표시 (⬜ → ✅)
```

**주기**: 주 2회  
**원칙**: 재정렬은 판단이 필요하므로 수동 큐레이션. 단 drift는 이 큐로 추적.

---

## 공개 / 내부 분류 정책

| 구분 | 처리 | 예시 |
|------|------|------|
| PUBLIC | `docs/`에 이관 | 제품 컨셉 · 도메인 모델 · 기능/비기능 요구사항 · 아키텍처 · 용어집 · 컨벤션 |
| INTERNAL | 미이관, `canonical` 링크로만 참조 | 팀원 실명·연락처(PII) · 회의록 · 배포 시크릿 · 내부 KPI |

---

## frontmatter 스키마

모든 `docs/` 파일에 아래 frontmatter를 부여한다.

```yaml
---
title:
source: confluence/XX_SECTION/파일명    # 원본 Confluence 섹션 경로
canonical:                              # Confluence 실제 URL
status: draft | review | approved
visibility: public
updated: YYYY-MM-DD                     # docs/ 파일 갱신일
source_updated: YYYY-MM-DD             # 원본 마지막 반영일 (drift 판정 기준)
---
```

---

## Confluence → docs/ 매핑

| Confluence | docs/ | 비고 |
|------------|-------|------|
| 02. Product Planning | `01-product/` | PUBLIC |
| 03. Requirements | `01-product/` 하위 또는 별도 | PUBLIC |
| 05. Tech | `03-system-design/` | PUBLIC (시크릿 제외) |
| 09_CONVENTIONS | `05-team-rules/` | PUBLIC |
| 00. Home | 미이관 | INTERNAL (PII) |
| 01. Meeting Notes | 미이관 | INTERNAL |
| 04. Design | 미이관 (초기) | 추후 필요 시 편입 |
| 07. QA & Test | 미이관 (초기) | 추후 필요 시 편입 |
| 08. Release | 미이관 (초기) | 추후 필요 시 편입 |
| 99. Archive | 미이관 | 불필요 |

`02-domain/`은 Confluence 직접 매핑 없음 → PRD 부록 A + `local/CLAUDE.md` 도메인 모델 기반으로 새로 작성.  
`04-feature-specs/`는 구현 직전 새로 작성 (Confluence 매핑 없음).

---

## 이관 큐

### 01-product/

| 상태 | Confluence 문서 | docs/ 파일 | 추가일 |
|------|----------------|------------|--------|
| ⬜ | 02. Product Planning / 프로젝트 개요 | `01-product/overview.md` | 2026-07-13 |
| ⬜ | 02. Product Planning / 문제 정의 | `01-product/overview.md` (병합) | 2026-07-13 |
| ⬜ | 02. Product Planning / 타겟 사용자 | `01-product/target-users.md` | 2026-07-13 |
| ⬜ | 02. Product Planning / MVP 범위 | `01-product/mvp-scope.md` | 2026-07-13 |
| ⬜ | 02. Product Planning / 기능 우선순위 | `01-product/mvp-scope.md` (병합) | 2026-07-13 |
| ⬜ | 02. Product Planning / 사용자 시나리오 | `01-product/user-scenarios.md` | 2026-07-13 |
| ⬜ | 03. Requirements / 기능 요구사항 | `01-product/functional-requirements.md` | 2026-07-13 |
| ⬜ | 03. Requirements / 비기능 요구사항 | `01-product/non-functional-requirements.md` | 2026-07-13 |

### 03-system-design/

| 상태 | Confluence 문서 | docs/ 파일 | 추가일 |
|------|----------------|------------|--------|
| ✅ | 05. Tech / 시스템 아키텍처 | `03-system-design/architecture.md` | 2026-07-13 |
| ✅ | 05. Tech / 기술 스택 | `03-system-design/tech-stack.md` | 2026-07-13 |
| ✅ | 05. Tech / ERD·데이터 모델 | `03-system-design/data-model.md` | 2026-07-13 |
| ✅ | 05. Tech / API 명세 | `03-system-design/api-spec.md` | 2026-07-13 |
| ✅ | 05. Tech / 배포·인프라 | `03-system-design/infra.md` | 2026-07-13 |

### 05-team-rules/

| 상태 | Confluence 문서 | docs/ 파일 | 추가일 |
|------|----------------|------------|--------|
| ✅ | 09_CONVENTIONS / 1. 브랜치 컨벤션 | `05-team-rules/git-workflow-commit.md` | 2026-07-21 |
| ✅ | 09_CONVENTIONS / 2. Issue 라벨·제목 컨벤션 | `05-team-rules/git-workflow-pr.md` | 2026-07-21 |
| ✅ | 09_CONVENTIONS / 3. PR 크기·리뷰 컨벤션 | `05-team-rules/git-workflow-pr.md` (병합) | 2026-07-21 |
| ✅ | 09_CONVENTIONS / 4. 코드 스타일·폴더 구조 컨벤션 | `05-team-rules/conventions.md` | 2026-07-13 |
| ✅ | 09_CONVENTIONS / 8. AI 사용 컨벤션 | `05-team-rules/ai-usage.md` | 2026-07-13 |
| ✅ | 09_CONVENTIONS / 11. Definition of Done | `05-team-rules/definition-of-done.md` | 2026-07-13 |

### 02-domain/ (새로 작성 — Confluence 직접 매핑 없음)

| 상태 | 작성 기준 | docs/ 파일 | 추가일 |
|------|----------|------------|--------|
| ✅ | PRD 부록 A + local/CLAUDE.md | `02-domain/overview.md` | 2026-07-13 |
| ✅ | PRD 부록 A (Agent 정의) | `02-domain/agents.md` | 2026-07-13 |
| ✅ | PRD 부록 A (관계 축) | `02-domain/relationships.md` | 2026-07-13 |
| ✅ | PRD 부록 A (조직 축) | `02-domain/organizations.md` | 2026-07-13 |
| ✅ | PRD 부록 A (사건 축) | `02-domain/events.md` | 2026-07-13 |
| ✅ | PRD 부록 A (배경) | `02-domain/time-and-space.md` | 2026-07-13 |
| ✅ | 전체 문서 취합 | `02-domain/glossary.md` | 2026-07-13 |
