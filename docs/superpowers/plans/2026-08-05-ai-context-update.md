# AI Context Update 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude 5 시대 context engineering 원칙에 맞춰 AI context 파일을 개선하고, SYNC.md 이관 큐의 Confluence 문서를 docs/에 반영한다.

**Architecture:** 모두 마크다운 문서 작업이다. 코드 없음. 각 태스크는 독립적으로 검증 가능하고, 태스크 완료 시 커밋한다.

**Tech Stack:** Markdown, Git, Atlassian MCP (Confluence 조회)

## Global Constraints

- 저장소 루트: `/Users/User/src/Magic_Academy/repo/`
- 작업 브랜치: `feature/issue-34-ai-context-update` (develop 기반, main 직접 push 금지)
- PUBLIC 저장소 — 팀원 실명·시크릿·내부 KPI 포함 금지
- `repo/docs/` 수정은 사용자 승인 후 실행 (CLAUDE.md 정책)
- Confluence cloudId: `jehye.atlassian.net`
- frontmatter 필수 필드: `title`, `source`, `canonical`, `status`, `visibility`, `updated`, `source_updated`
- 신규 docs/ 파일: `status: draft`, `visibility: public`
- 이관 완료 후 SYNC.md 해당 항목 `⬜ → ✅`로 업데이트
- 관련 Issue: #34

---

### Task 1: 브랜치 생성

**Files:**
- Git branch: `feature/issue-34-ai-context-update`

- [ ] **Step 1: 브랜치 생성 및 확인**

```bash
git -C /Users/User/src/Magic_Academy/repo checkout develop
git -C /Users/User/src/Magic_Academy/repo pull
git -C /Users/User/src/Magic_Academy/repo checkout -b feature/issue-34-ai-context-update
git -C /Users/User/src/Magic_Academy/repo branch
```

Expected: `* feature/issue-34-ai-context-update` 출력

---

### Task 2: AGENTS.md 점검 및 최소화

**Files:**
- Modify: `AGENTS.md`

**원칙:**
- 삭제 기준: docs/ 파일에 이미 있는 내용, 지나치게 제약적인 예시, 동일 규칙 반복
- 보존 기준: 프로젝트 고유 규칙, 3축 프레임, 페르소나 정의
- 한 번에 삭제하지 말고 항목별로 확인 후 처리

- [ ] **Step 1: AGENTS.md 읽기**

`AGENTS.md` 전체를 읽는다.

- [ ] **Step 2: 반복·과잉 항목 식별**

아래 기준으로 후보를 식별한다:

1. **반복 제거 대상**: 동일 내용이 `docs/05-team-rules/`에 이미 있는 항목
   - 코딩 원칙 → `docs/05-team-rules/conventions.md`와 중복 여부 확인
   - 디버깅 절차 → 전역 CLAUDE.md와 동일하면 링크로 대체 가능

2. **예시 최소화 대상**: "나쁜 예/좋은 예" 형태의 예시 블록
   - 예시가 모델을 그 범위에 가두므로 규칙 한 줄로 대체

3. **규칙 완화 대상**: "절대 금지" 등 강한 제약 → 상황 판단 위임 가능한 것

- [ ] **Step 3: 최소 변경 적용**

변경 전 사용자에게 구체적인 변경 내용을 보여주고 승인을 받는다.

승인 후 편집. 삭제보다는 링크 대체를 우선한다:
```markdown
<!-- 상세 내용: docs/05-team-rules/conventions.md 참조 -->
```

- [ ] **Step 4: self-review**

변경 후 확인:
- [ ] 3축 프레임 (관계·조직·사건) 설명 보존
- [ ] 페르소나 정의 보존
- [ ] 미정 항목 확인 규칙 보존
- [ ] 요청하지 않은 작업 금지 규칙 보존

- [ ] **Step 5: 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add AGENTS.md
git -C /Users/User/src/Magic_Academy/repo diff --staged
# 사용자 승인 후:
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: AGENTS.md 반복 제거 및 규칙 최소화 (#34)"
```

---

### Task 3: docs/superpowers/ 구축

**Files:**
- Create: `docs/superpowers/README.md`
- Create: `docs/superpowers/ai-workflow.md`

**Interfaces:**
- Produces: @ai-native 페르소나 자동 로딩 문서 (`docs/superpowers/` 전체)

- [ ] **Step 1: README.md 생성**

`docs/superpowers/README.md` 를 아래 내용으로 생성한다.

```markdown
---
title: Superpowers — Magic Academy AI 협업 가이드
status: approved
visibility: public
updated: 2026-08-05
---

# Superpowers — Magic Academy AI 협업 가이드

> @ai-native 페르소나 세션 시작 시 이 파일을 로드한다.

Magic Academy에서 사용하는 Claude Code superpowers 스킬과 AI 협업 워크플로우를 정리한다.

---

## 스킬 라우팅 (Magic Academy 맥락)

| 상황 | 스킬 |
|------|------|
| 새 기능·시스템 설계 시작 | `superpowers:brainstorming` |
| 설계 확정 후 구현 계획 | `superpowers:writing-plans` |
| Issue·스펙 작성 | `issue-writer`, `spec-draft` |
| 구현 단계 | `superpowers:executing-plans` 또는 `superpowers:subagent-driven-development` |
| 버그·예상 외 동작 | `superpowers:systematic-debugging` |
| 구현 완료 후 검증 | `superpowers:verification-before-completion` |
| PR 리뷰 | `pr-review` |
| AI context 업데이트 | `docs/superpowers/ai-workflow.md` 참조 |
| Agent 설계 초안 | `agent-spec` |
| Confluence 페이지 생성 | `confluence-post` |
| 작업 상태 정리 | `briefing` |

---

## 문서 구조

```
docs/superpowers/
├── README.md          # 이 파일 — 스킬 라우팅 가이드
├── ai-workflow.md     # AI context 관리 운영 가이드
├── plans/             # 구현 계획 (writing-plans 출력물)
└── specs/             # 설계 스펙 (brainstorming 출력물)
```

---

## 관련 링크

- 컨텍스트 로딩 범위: `docs/00-start-here/context-scope.md`
- 팀 AI 사용 컨벤션: `docs/05-team-rules/ai-usage.md`
- AI context 설계 기록: `docs/_meta/ai-native-env-design.md`
```

- [ ] **Step 2: ai-workflow.md 생성**

`docs/superpowers/ai-workflow.md` 를 아래 내용으로 생성한다.

```markdown
---
title: Magic Academy AI 워크플로우 운영 가이드
status: approved
visibility: public
updated: 2026-08-05
---

# Magic Academy AI 워크플로우 운영 가이드

> @ai-native 페르소나 담당: 은혜

---

## 1. Confluence → docs/ 동기화

**원칙**: Confluence(원본) → docs/(AI 개발용 스냅샷). 원본은 Confluence.

**주기**: 주 2회 또는 Confluence 주요 변경 시

**절차**:
1. `docs/_meta/SYNC.md` 이관 큐에서 ⬜ 항목 확인
2. Atlassian MCP로 해당 Confluence 페이지 조회
3. docs/ 파일 생성 또는 업데이트 (frontmatter 포함)
4. SYNC.md 해당 항목 `⬜ → ✅`로 업데이트
5. PR을 통해 develop에 머지

**drift 감지**: ✅ 항목 중 Confluence 수정일이 `source_updated`보다 최신이면 drift 상태.
drift 항목은 SYNC.md에 `⬜ [파일명] — drift` 행으로 재등록한다.

---

## 2. AI context 파일 관리

| 파일 | 역할 | 수정 기준 |
|------|------|----------|
| `AGENTS.md` | 전체 팀 AI 진입점 | 프로젝트 규칙·페르소나 변경 시 |
| `docs/00-start-here/context-scope.md` | 작업별 로딩 범위 | 파일 추가·삭제 시, 토큰 수 변경 시 |
| `docs/00-start-here/context-quality.md` | AI 자가 점검 기준 | 품질 기준 변경 시 |
| `docs/05-team-rules/ai-usage.md` | AI 사용 컨벤션 | Confluence 원본 갱신 시 |
| `docs/_meta/SYNC.md` | 이관 큐 | Confluence 변경 감지 시 |

---

## 3. context-scope.md 토큰 예산 업데이트

파일 변경 후 토큰 예산을 재측정한다.

```bash
# 문자 수 측정 (한국어 포함 파일은 chars ÷ 4 = 예상 토큰)
wc -m docs/00-start-here/*.md docs/02-domain/*.md docs/05-team-rules/*.md
```

측정 후 `context-scope.md`의 파일별 토큰 수치와 총합을 업데이트한다.

---

## 4. Claude 5 시대 context engineering 원칙

출처: https://yozm.wishket.com/magazine/detail/3875/

| 원칙 | 적용 방식 |
|------|----------|
| 규칙 최소화 | AGENTS.md에서 강한 제약 대신 판단 위임 |
| 반복 제거 | 동일 규칙은 한 파일에만, 다른 파일은 링크 |
| 점진적 공개 | context-scope.md로 작업별 필요 파일만 로드 |
| 예시 제한 | "나쁜 예/좋은 예" 대신 규칙 한 줄로 표현 |
| 풍부한 참조 | 텍스트 설명보다 Confluence URL·파일 링크 |
```

- [ ] **Step 3: 검증**

```bash
ls /Users/User/src/Magic_Academy/repo/docs/superpowers/
# Expected: README.md  ai-workflow.md  plans/  specs/
```

- [ ] **Step 4: 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add docs/superpowers/README.md docs/superpowers/ai-workflow.md
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: superpowers/ 구축 — @ai-native 자동 로딩 문서 추가 (#34)"
```

---

### Task 4: ai-usage.md 업데이트 + context-scope.md 재측정

**Files:**
- Modify: `docs/05-team-rules/ai-usage.md`
- Modify: `docs/00-start-here/context-scope.md`

- [ ] **Step 1: ai-usage.md frontmatter 갱신**

`docs/05-team-rules/ai-usage.md` frontmatter를 수정한다:
- `updated: 2026-07-13` → `updated: 2026-08-05`
- `source_updated: 2026-07-09` → Confluence 원본 최신 수정일로 갱신

Confluence 원본 확인:
- canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/4521997/8.+AI
- Atlassian MCP `getConfluencePage` 로 현재 버전·수정일 확인 후 반영

- [ ] **Step 2: context-scope.md 토큰 예산 재측정**

아래 측정값(2026-08-05 기준)으로 `context-scope.md` 파일별 토큰 수와 총합을 업데이트한다:

| 파일 | 문자 수 | 예상 토큰 |
|------|------:|----------:|
| `00-start-here/index.md` | 898 | ~225 |
| `00-start-here/what-is-decided.md` | 2448 | ~612 |
| `00-start-here/what-is-pending.md` | 959 | ~240 |
| `00-start-here/context-quality.md` | 895 | ~224 |
| `02-domain/overview.md` | 913 | ~228 |
| `02-domain/agents.md` | 2403 | ~601 |
| `02-domain/relationships.md` | 1220 | ~305 |
| `02-domain/organizations.md` | 960 | ~240 |
| `02-domain/events.md` | 1280 | ~320 |
| `02-domain/time-and-space.md` | 1102 | ~276 |
| `02-domain/glossary.md` | 1512 | ~378 |
| `05-team-rules/conventions.md` | 1267 | ~317 |
| `05-team-rules/definition-of-done.md` | 1127 | ~282 |
| `05-team-rules/git-workflow-commit.md` | 1473 | ~368 |
| `05-team-rules/git-workflow-pr.md` | 2610 | ~653 |
| `05-team-rules/dev-workflow.md` | 1709 | ~427 |
| `05-team-rules/ai-usage.md` | 1330 | ~333 |
| `decisions/README.md` | 632 | ~158 |

**Always Load 합계 (index~glossary)**: 14,590자 → **~3,648 토큰**
(기존 ~3,384 → +264 토큰, 파일 업데이트로 증가)

- [ ] **Step 3: context-scope.md 개선 제안 섹션 정리**

`개선 제안 > 2. git-workflow.md 분리 완료` 항목은 이미 완료됐으므로 `(완료)` 표시 추가.

- [ ] **Step 4: 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add \
  docs/05-team-rules/ai-usage.md \
  docs/00-start-here/context-scope.md
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: ai-usage.md 갱신 및 context-scope.md 토큰 예산 재측정 (#34)"
```

---

### Task 5: 02-domain/world-setting.md 이관

**Files:**
- Create: `docs/02-domain/world-setting.md`
- Modify: `docs/_meta/SYNC.md` (⬜ → ✅)

**주의**: 이 문서는 기존 `02-domain/agents.md`, `events.md`, `relationships.md`, `time-and-space.md`와 내용이 겹친다. 신규 파일로 추가하되, 기존 파일의 내용은 수정하지 않는다. 향후 기존 파일의 drift 여부는 별도로 판단한다.

- [ ] **Step 1: Confluence 페이지 조회**

Atlassian MCP `getConfluencePage` 호출:
- cloudId: `jehye.atlassian.net`
- pageId: `10911745`
- contentFormat: `markdown`

- [ ] **Step 2: docs/02-domain/world-setting.md 생성**

frontmatter:
```yaml
---
title: Magic Academy 세계관 설정 (전제 조건)
source: confluence/05_TECH/[전제조건] Magic Academy 세계관 설정
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/10911745
status: draft
visibility: public
updated: 2026-08-05
source_updated: 2026-07-31
---
```

본문은 Confluence 조회 결과를 마크다운으로 변환한다. INTERNAL 정보(팀원 실명 이외의 내용은 모두 PUBLIC)는 이미 없다.

- [ ] **Step 3: SYNC.md 업데이트**

`docs/_meta/SYNC.md`에서:
```
| ⬜ | [전제 조건] Magic Academy 세계관 설정 (#10911745, v1.7) | ...
```
→
```
| ✅ | [전제 조건] Magic Academy 세계관 설정 (#10911745, v1.7) | `02-domain/world-setting.md` | 2026-08-05 |
```

- [ ] **Step 4: 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add docs/02-domain/world-setting.md docs/_meta/SYNC.md
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: 02-domain/world-setting.md 이관 (#10911745) (#34)"
```

---

### Task 6: 03-system-design/ 신규 이관 3종

**Files:**
- Create: `docs/03-system-design/event-master.md`
- Create: `docs/03-system-design/auth.md`
- Create: `docs/03-system-design/policy-signal-delta.md`
- Modify: `docs/_meta/SYNC.md`

각 파일을 순서대로 처리한다. Confluence 조회 → 파일 생성 → SYNC.md 업데이트 → 커밋.

**event-master.md** (pageId: `10878982`)
```yaml
---
title: Event Master Agent 설계
source: confluence/05_TECH/Event Master Agent 설계
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/10878982
status: draft
visibility: public
updated: 2026-08-05
source_updated: 2026-08-04
---
```

**auth.md** (pageId: `23888013`)
```yaml
---
title: 인증·접근 제어 설계
source: confluence/05_TECH/인증·접근 제어 설계
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/23888013
status: draft
visibility: public
updated: 2026-08-05
source_updated: 2026-08-03
---
```

**policy-signal-delta.md** (pageId: `19628033`)
```yaml
---
title: "[Policy] Signal → Delta 규칙"
source: confluence/05_TECH/[Policy] Signal → Delta 규칙
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/19628033
status: draft
visibility: public
updated: 2026-08-05
source_updated: 2026-08-03
---
```

- [ ] **Step 1: event-master.md 생성 및 SYNC.md 업데이트 후 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add docs/03-system-design/event-master.md docs/_meta/SYNC.md
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: 03-system-design/event-master.md 이관 (#10878982) (#34)"
```

- [ ] **Step 2: auth.md 생성 및 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add docs/03-system-design/auth.md docs/_meta/SYNC.md
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: 03-system-design/auth.md 이관 (#23888013) (#34)"
```

- [ ] **Step 3: policy-signal-delta.md 생성 및 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add docs/03-system-design/policy-signal-delta.md docs/_meta/SYNC.md
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: 03-system-design/policy-signal-delta.md 이관 (#19628033) (#34)"
```

---

### Task 7: 03-system-design/ drift 재동기화 2종

**Files:**
- Modify: `docs/03-system-design/tick-engine.md`
- Modify: `docs/03-system-design/policy-engine.md`
- Modify: `docs/_meta/SYNC.md`

- [ ] **Step 1: tick-engine.md drift 확인 및 업데이트**

Atlassian MCP `getConfluencePage` (pageId: `12910622`)로 최신 내용 조회.
기존 `docs/03-system-design/tick-engine.md`와 비교하여 변경된 섹션만 반영.
frontmatter `source_updated: 2026-07-28` → `2026-08-04`, `updated` → `2026-08-05`

- [ ] **Step 2: policy-engine.md drift 확인 및 업데이트**

Atlassian MCP `getConfluencePage` (pageId: `14090319`)로 최신 내용 조회.
기존 `docs/03-system-design/policy-engine.md`와 비교하여 변경된 섹션만 반영.
frontmatter `source_updated` → `2026-08-03`, `updated` → `2026-08-05`

- [ ] **Step 3: 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add \
  docs/03-system-design/tick-engine.md \
  docs/03-system-design/policy-engine.md \
  docs/_meta/SYNC.md
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: tick-engine·policy-engine drift 재동기화 (#34)"
```

---

### Task 8: 04-feature-specs/ 이관 2종

**Files:**
- Create: `docs/04-feature-specs/mvp-feature-spec.md`
- Create: `docs/04-feature-specs/inspector.md`
- Modify: `docs/_meta/SYNC.md`

**mvp-feature-spec.md** (pageId: `16777778`)
```yaml
---
title: "[기능 명세서] 1단계 Magic Academy MVP"
source: confluence/[기능 명세서] 1단계 Magic Academy MVP
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/16777778
status: draft
visibility: public
updated: 2026-08-05
source_updated: 2026-08-04
---
```

**inspector.md** (pageId: `12582917`)
```yaml
---
title: "[Spec] Inspector 기능 정의"
source: confluence/[Spec] Inspector 기능 정의
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/12582917
status: draft
visibility: public
updated: 2026-08-05
source_updated: 2026-08-04
---
```

- [ ] **Step 1: mvp-feature-spec.md 생성 및 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add docs/04-feature-specs/mvp-feature-spec.md docs/_meta/SYNC.md
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: 04-feature-specs/mvp-feature-spec.md 이관 (#16777778) (#34)"
```

- [ ] **Step 2: inspector.md 생성 및 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add docs/04-feature-specs/inspector.md docs/_meta/SYNC.md
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: 04-feature-specs/inspector.md 이관 (#12582917) (#34)"
```

---

### Task 9: 01-product/ 이관 1종 + drift 재동기화 2종

**Files:**
- Create: `docs/01-product/simulation-parameters.md`
- Modify: `docs/01-product/mvp-scope.md`
- Modify: `docs/01-product/functional-requirements.md`
- Modify: `docs/_meta/SYNC.md`

**simulation-parameters.md** (pageId: `21364758`)
```yaml
---
title: "[요구사항] 시뮬레이션 파라미터 설정"
source: confluence/03_Requirements/[요구사항] 시뮬레이션 파라미터 설정
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/21364758
status: draft
visibility: public
updated: 2026-08-05
source_updated: 2026-08-04
---
```

- [ ] **Step 1: simulation-parameters.md 생성 및 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add docs/01-product/simulation-parameters.md docs/_meta/SYNC.md
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: 01-product/simulation-parameters.md 이관 (#21364758) (#34)"
```

- [ ] **Step 2: mvp-scope.md drift 확인 및 업데이트**

Atlassian MCP `getConfluencePage` (pageId: `17989637`)로 최신 내용 조회.
변경된 섹션만 반영. frontmatter `source_updated` → `2026-08-04`, `updated` → `2026-08-05`

- [ ] **Step 3: functional-requirements.md drift 확인 및 업데이트**

Atlassian MCP `getConfluencePage` (pageId: `16777846`)로 최신 내용 조회.
변경된 섹션만 반영. frontmatter `source_updated` → `2026-08-04`, `updated` → `2026-08-05`

- [ ] **Step 4: drift 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add \
  docs/01-product/mvp-scope.md \
  docs/01-product/functional-requirements.md \
  docs/_meta/SYNC.md
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: mvp-scope·functional-requirements drift 재동기화 (#34)"
```

---

### Task 10: context-scope.md 업데이트 (신규 파일 반영)

**Files:**
- Modify: `docs/00-start-here/context-scope.md`

Task 5~9에서 신규 생성된 파일들을 context-scope.md에 반영한다.

- [ ] **Step 1: 신규 파일 토큰 측정**

```bash
wc -m \
  /Users/User/src/Magic_Academy/repo/docs/02-domain/world-setting.md \
  /Users/User/src/Magic_Academy/repo/docs/03-system-design/event-master.md \
  /Users/User/src/Magic_Academy/repo/docs/03-system-design/auth.md \
  /Users/User/src/Magic_Academy/repo/docs/03-system-design/policy-signal-delta.md \
  /Users/User/src/Magic_Academy/repo/docs/04-feature-specs/mvp-feature-spec.md \
  /Users/User/src/Magic_Academy/repo/docs/04-feature-specs/inspector.md \
  /Users/User/src/Magic_Academy/repo/docs/01-product/simulation-parameters.md \
  /Users/User/src/Magic_Academy/repo/docs/superpowers/README.md \
  /Users/User/src/Magic_Academy/repo/docs/superpowers/ai-workflow.md
```

- [ ] **Step 2: context-scope.md 파일별 토큰 테이블 업데이트**

신규 파일을 Task-Specific 분류로 추가한다:
- `02-domain/world-setting.md` → Task (도메인 로직 구현 시)
- `03-system-design/event-master.md` → Task (Event Master 구현 시)
- `03-system-design/auth.md` → Task (인증 구현 시)
- `03-system-design/policy-signal-delta.md` → Task (Policy 구현 시)
- `04-feature-specs/*.md` → Task (해당 기능 구현 직전)
- `01-product/simulation-parameters.md` → Task (파라미터 관련 구현 시)
- `docs/superpowers/*.md` → Always (@ai-native 페르소나 시)

- [ ] **Step 3: 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add docs/00-start-here/context-scope.md
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: context-scope.md 신규 파일 반영 및 토큰 예산 업데이트 (#34)"
```

---

### Task 11: PR 생성

- [ ] **Step 1: push**

```bash
git -C /Users/User/src/Magic_Academy/repo push -u origin feature/issue-34-ai-context-update
```

- [ ] **Step 2: PR 초안 출력 및 사용자 승인**

제목: `[Chore] AI context update — Claude 5 원칙 적용 및 docs/ 이관 (#34)`
base: `develop`

승인 후 `gh pr create --draft` 실행.
