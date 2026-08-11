---
title: AI Context 로딩 범위
status: approved
visibility: internal
updated: 2026-08-10
---

# AI Context 로딩 범위

> 이 파일은 AI 에이전트가 작업 유형별로 어떤 파일을 로드해야 하는지 정의한다.  
> 불필요한 파일을 제거해 토큰 예산을 절약하고, 필요한 문맥을 빠뜨리지 않도록 가이드한다.

---

## 파일별 토큰 예산

> 측정 기준: `wc -m`(실제 문자 수) ÷ 4 = 예상 토큰

### Always Load (~970 tokens)

| 파일 | 예상 토큰 |
|------|----------:|
| `00-start-here/index.md` | ~290 |
| `00-start-here/what-is-decided.md` | ~441 |
| `00-start-here/what-is-pending.md` | ~239 |
| **소계** | **~970** |

### Task-Specific

| 파일 | 예상 토큰 | 로드 시점 |
|------|----------:|----------|
| `02-domain/agents.md` | ~600 | feature 구현·도메인 수정 시 |
| `02-domain/relationships.md` | ~305 | feature 구현·도메인 수정 시 |
| `02-domain/organizations.md` | ~240 | feature 구현·도메인 수정 시 |
| `02-domain/events.md` | ~320 | feature 구현·도메인 수정 시 |
| `02-domain/time-and-space.md` | ~275 | feature 구현·도메인 수정 시 |
| `02-domain/glossary.md` | ~378 | feature 구현·도메인 수정 시 |
| `03-system-design/architecture.md` | ~997 | 시스템 전체 파악 시 |
| `03-system-design/agent-runtime.md` | ~3,588 | Agent Runtime 구현 시 |
| `03-system-design/agent-runtime-prompt.md` | ~785 | 프롬프트 수정·튜닝 시 |
| `03-system-design/policy-engine.md` | ~2,220 | Policy Engine 구현 시 |
| `03-system-design/magic-layer.md` | ~1,934 | Magic Layer 구현 시 |
| `03-system-design/tick-engine.md` | ~1,029 | Tick Engine 구현 시 |
| `03-system-design/infra.md` | ~1,012 | Docker·배포 작업 시 |
| `03-system-design/tech-stack.md` | ~822 | 기술 선택 검토 시 |
| `03-system-design/user-flow.md` | ~382 | 프론트엔드 작업 시 |
| `00-start-here/context-quality.md` | ~223 | AI context 충분성 판단 필요 시 |
| `01-product/mvp-scope.md` | ~708 | 기능 범위·우선순위 확인 시 |
| `04-feature-specs/<기능명>.md` | ~117~480 | 해당 기능 구현 직전 |
| `05-team-rules/conventions.md` | ~316 | 구현 작업 시 |
| `05-team-rules/definition-of-done.md` | ~281 | PR 작성 시 |
| `05-team-rules/git-workflow-commit.md` | ~368 | 커밋 시 |
| `05-team-rules/git-workflow-pr.md` | ~652 | PR 작성·리뷰 시 |
| `05-team-rules/ai-usage.md` | ~332 | AI 사용 기록 작성 시 |

**전체 docs/ 토큰 (2026-08-11 기준)**: ~20,645 토큰  
**DB 스키마**: `docs/03-system-design/data-model.md` 삭제됨 → `backend/app/domain/models.py` 직접 참조

---

## Always Load (모든 작업)

모든 작업 시작 시 아래 파일을 로드한다.

```
docs/00-start-here/index.md
docs/00-start-here/what-is-decided.md
docs/00-start-here/what-is-pending.md
```

**이유**:
- 프로젝트 방향과 확정/미정 경계를 모르면 임의 결정이 발생한다.
- `02-domain/` 6종은 feature 구현·도메인 수정 작업에서만 Task-Specific 로드한다. PR·커밋·인프라 작업에는 불필요.

---

## Task-Specific Load

### 도메인 로직 구현 (새 기능)

Always Load 전체 + 아래 추가:

```
docs/02-domain/agents.md
docs/02-domain/relationships.md
docs/02-domain/organizations.md
docs/02-domain/events.md
docs/02-domain/time-and-space.md
docs/02-domain/glossary.md
docs/05-team-rules/conventions.md
docs/05-team-rules/definition-of-done.md
docs/05-team-rules/git-workflow-commit.md
docs/03-system-design/architecture.md        ← 전체 흐름 파악 시
docs/03-system-design/<해당 컴포넌트>.md     ← 구현 대상 컴포넌트
```

해당 기능 스펙이 있으면 `docs/04-feature-specs/<기능명>.md`도 필수 로드 (구현 직전).

### DB 스키마 확인

`docs/03-system-design/data-model.md`는 삭제됨. DB 스키마는 코드를 직접 읽는다.

```
backend/app/domain/models.py          ← 테이블·컬럼·제약 전체 (ground truth)
backend/app/simulation/policy/models.py ← Policy 관련 모델
```

### 버그 수정

Always Load 전체 + 아래 추가:

```
docs/05-team-rules/conventions.md
docs/05-team-rules/git-workflow-commit.md
docs/03-system-design/<버그 발생 컴포넌트>.md
```

### 문서 작업·이관

Always Load 중 `02-domain/` 6종 + 아래:

```
docs/00-start-here/index.md
docs/00-start-here/what-is-decided.md
docs/00-start-here/what-is-pending.md
docs/00-start-here/context-quality.md
docs/05-team-rules/ai-usage.md
docs/05-team-rules/definition-of-done.md
```

참고: `_meta/SYNC.md`는 이관 담당자가 직접 확인하는 운영 문서. AI가 이관 작업 자체를 수행하는 경우에만 로드.

### PR 작성·리뷰

Always Load 중 `00-start-here/` 4종 + 아래:

```
docs/05-team-rules/git-workflow-pr.md
docs/05-team-rules/definition-of-done.md
docs/05-team-rules/ai-usage.md
```

---

## 로드하지 않는 파일

| 파일 | 이유 |
|------|------|
| ~~`docs/decisions/README.md`~~ | **삭제됨** (2026-08-12). ADR은 Confluence에 작성. |
| ~~`docs/README.md`~~ | **삭제됨** (2026-08-10). `index.md`와 중복. 사람용 안내 파일. |
| ~~`docs/_meta/SYNC.md`~~ | **삭제됨** (2026-08-10). Confluence 이관 큐·운영 정책. ~1,155 토큰. |
| ~~`docs/_meta/ai-native-env-design.md`~~ | **삭제됨** (2026-08-10). 설계 과정 ADR. 결과는 다른 파일에 반영. ~1,055 토큰. |
| ~~`docs/superpowers/` 2종~~ | **삭제됨** (2026-08-10). 프로세스 문서. AI context 가치 없음. ~2,391 토큰. |
| ~~`docs/04-feature-specs/README.md`~~ | **삭제됨** (2026-08-10). 기능 스펙 인덱스. 불필요한 메타 파일. |
| ~~`docs/03-system-design/data-model.md`~~ | **삭제됨** (2026-08-10). 실제 스키마와 diverge 발생. `models.py` 사용. |
| ~~`docs/01-product/functional-requirements.md`~~ | **삭제됨** (2026-08-10). 내용이 각 설계 문서에 분산·반영됨. |
| ~~`docs/02-domain/overview.md`~~ | **삭제됨** (2026-08-10). `index.md`에 도메인 파일 목록으로 흡수. |
