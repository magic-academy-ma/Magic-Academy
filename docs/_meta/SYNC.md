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
`04-feature-specs/`는 Confluence 이관(#16777778, #12582917)과 신규 작성으로 구분됨. 이관 항목은 §이관 큐 참조.

---

## 이관 큐

### 01-product/

| 상태 | Confluence 문서 | docs/ 파일 | 추가일 |
|------|----------------|------------|--------|
| ✅ | 02. Product Planning / MVP 범위 (#17989637) | `01-product/mvp-scope.md` | 2026-07-29 |
| ✅ | 02. Product Planning / 기능 우선순위 (#17956886) | `01-product/mvp-scope.md` (병합) | 2026-07-29 |
| ✅ | 03. Requirements / 핵심 기능 정의 (#16777846) | `01-product/functional-requirements.md` | 2026-07-29 |
| — | 02. Product Planning / 프로젝트 개요 | 이관 제외 — `what-is-decided.md`에 포함 | 2026-07-13 |
| — | 02. Product Planning / 문제 정의 | 이관 제외 — `what-is-decided.md`에 포함 | 2026-07-13 |
| — | 02. Product Planning / 타겟 사용자 | 이관 제외 — 구현 AI context 불필요 | 2026-07-13 |
| — | 02. Product Planning / 사용자 시나리오 | 이관 제외 — 구현 AI context 불필요 | 2026-07-13 |
| — | 03. Requirements / 비기능 요구사항 | 이관 불가 — Confluence 미존재 | 2026-07-13 |
| ✅ | 03. Requirements / [요구사항] 시뮬레이션 파라미터 설정 (#21364758) | `01-product/simulation-parameters.md` | 2026-08-05 |
| — | [Spec] 대표 캠페인 — 첫 학기, 다섯 명의 마법사 (#13533186) | 미이관 — 사용자 시나리오 계열 | 2026-08-05 |
| — | [Scenario] 대표 캠페인 데모 — 설정 생성부터 시점 복원까지 (#13402116) | 미이관 — 사용자 시나리오 계열 | 2026-08-05 |
| ✅ | MVP 범위 (#17989637) — drift | `01-product/mvp-scope.md` 재동기화 | 2026-08-05 |
| ✅ | 핵심 기능 정의 (#16777846) — drift | `01-product/functional-requirements.md` 재동기화 | 2026-08-05 |

### 03-system-design/

| 상태 | Confluence 문서 | docs/ 파일 | 추가일 |
|------|----------------|------------|--------|
| ✅ | 05. Tech / 시스템 아키텍처 (#8290305, v2.3) | `03-system-design/architecture.md` | 2026-07-13 |
| ✅ | 05. Tech / 기술 스택 | `03-system-design/tech-stack.md` | 2026-07-13 |
| ✅ | 05. Tech / ERD·데이터 모델 | `03-system-design/data-model.md` | 2026-07-13 |
| ✅ | 05. Tech / API 명세 (#12451842, v1.1, 구 #10911849 trashed) | `03-system-design/api-spec.md` | 2026-07-13 |
| ✅ | 05. Tech / 배포·인프라 | `03-system-design/infra.md` | 2026-07-13 |
| ✅ | 05. Tech / Tick Engine 스펙 (#12910622) | `03-system-design/tick-engine.md` | 2026-07-28 |
| ✅ | 05. Tech / Agent Runtime 설계 (#11894790) | `03-system-design/agent-runtime.md` | 2026-07-28 |
| ✅ | 05. Tech / Policy Engine 설계 (#14090319) | `03-system-design/policy-engine.md` | 2026-07-28 |
| ✅ | 05. Tech / Magic Layer Agent 설계 (#9371768) | `03-system-design/magic-layer.md` | 2026-07-28 |
| ✅ | 05. Tech / User Flow (#17367076) | `03-system-design/user-flow.md` | 2026-07-28 |
| ✅ | 05. Tech / Event Master Agent 설계 (#10878982) | `03-system-design/event-master.md` | 2026-08-06 |
| ✅ | 05. Tech / 인증·접근 제어 설계 (#23888013) | `03-system-design/auth.md` | 2026-08-06 |
| ✅ | 05. Tech / [Policy] Signal → Delta 규칙 (#19628033) | `03-system-design/policy-signal-delta.md` | 2026-08-06 |
| ✅ | Tick Engine 스펙 (#12910622) — drift | `03-system-design/tick-engine.md` 재동기화 | 2026-08-05 |
| ✅ | Policy Engine 설계 (#14090319) — drift | `03-system-design/policy-engine.md` 재동기화 | 2026-08-05 |

### 05-team-rules/

| 상태 | Confluence 문서 | docs/ 파일 | 추가일 |
|------|----------------|------------|--------|
| ✅ | 09_CONVENTIONS / 1. 브랜치 컨벤션 | `05-team-rules/git-workflow-commit.md` | 2026-07-21 |
| ✅ | 09_CONVENTIONS / 2. Issue 라벨·제목 컨벤션 | `05-team-rules/git-workflow-pr.md` | 2026-07-21 |
| ✅ | 09_CONVENTIONS / 3. PR 크기·리뷰 컨벤션 | `05-team-rules/git-workflow-pr.md` (병합) | 2026-07-21 |
| ✅ | 09_CONVENTIONS / 4. 코드 스타일·폴더 구조 컨벤션 | `05-team-rules/conventions.md` | 2026-07-13 |
| ✅ | 09_CONVENTIONS / 8. AI 사용 컨벤션 | `05-team-rules/ai-usage.md` | 2026-07-13 |
| ✅ | 09_CONVENTIONS / 11. Definition of Done | `05-team-rules/definition-of-done.md` | 2026-07-13 |

### 04-feature-specs/

| 상태 | Confluence 문서 | docs/ 파일 | 추가일 |
|------|----------------|------------|--------|
| ✅ | [기능 명세서] 1단계 Magic Academy MVP (#16777778) | `04-feature-specs/mvp-feature-spec.md` | 2026-08-05 |
| ✅ | [Spec] Inspector 기능 정의 (#12582917) | `04-feature-specs/inspector.md` | 2026-08-05 |

---

### 02-domain/ (새로 작성 — Confluence 직접 매핑 없음)

| 상태 | 작성 기준 | docs/ 파일 | 추가일 |
|------|----------|------------|--------|
| ✅ | PRD 부록 A + local/CLAUDE.md | `02-domain/overview.md` | 2026-07-13 |
| ✅ | PRD 부록 A (Agent 정의) | `02-domain/agents.md` | 2026-07-13 |
| ✅ | PRD 부록 A (관계 축) | `02-domain/relationships.md` | 2026-07-13 |
| ✅ | PRD 부록 A (조직 축) | `02-domain/organizations.md` | 2026-07-13 |
| ✅ | PRD 부록 A (사건 축) | `02-domain/events.md` | 2026-07-13 |
| ✅ | PRD 부록 A (배경) | `02-domain/time-and-space.md` | 2026-07-13 |
| ❌ 폐기 | 전체 문서 취합 | `02-domain/glossary.md` (2026-08-13 폐기 — 각 도메인 파일에 통합) | 2026-07-13 |
| ✅ | 05. Tech / [전제 조건] Magic Academy 세계관 설정 (#10911745) | `02-domain/world-setting.md` | 2026-08-06 |

---

### 명시적 미이관

> 이관 결정이 내려진 항목. 이관 큐에 추가하지 않는다.

| 상태 | Confluence 문서 | 이유 | 결정일 |
|------|----------------|------|--------|
| — | [Plan] 1단계 수직 Slice 0~7 (#19202077) | INTERNAL — 팀 내부 계획 | 2026-08-05 |
| — | [Sprint] 1단계 개발 5영업일 스프린트 (#19169283) | INTERNAL — 스프린트 계획 | 2026-08-05 |
| — | [Branding] Magic Academy 브랜딩 (#24281259) | 구현 AI context 불필요 | 2026-08-05 |
| — | [Test] * 4종 + Magic Academy 테스트 문서 범위 및 담당 (#22544473 등) | 테스트 문서 — 07 QA & Test 스코프 제외 결정 | 2026-08-05 |
| — | 05. Tech / 인증·접근 제어 설계 (#23888013) | INTERNAL — 변경 이력 팀원 실명(PII) + 내부 API 경로 노출 | 2026-08-07 |
