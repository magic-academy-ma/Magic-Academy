# AI Context 품질 기준 및 승인 지점 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `context-quality.md` 신규 파일 생성, `context-scope.md`에 Always Load 등록, `AGENTS.md` 승인 섹션에 판단 원칙 삽입

**Architecture:** 모두 마크다운 문서 수정이다. 코드 없음. 각 태스크는 독립적으로 검증 가능하고, 태스크 완료 시 커밋한다.

**Tech Stack:** Markdown, Git

## Global Constraints

- 저장소 루트: `/Users/User/src/Magic_Academy/repo/`
- 현재 브랜치: `develop` — `main` 직접 push 금지
- PUBLIC 저장소 — 시크릿·개인정보 포함 금지
- 기존 파일의 기존 내용은 변경하지 않는다 (삽입·추가만)
- 스펙: `docs/superpowers/specs/2026-07-23-ai-context-quality-approval-gates-design.md`

---

### Task 1: `context-quality.md` 신규 생성

**Files:**
- Create: `docs/00-start-here/context-quality.md`

**Interfaces:**
- Produces: `docs/00-start-here/context-quality.md` — Task 2에서 context-scope.md가 이 파일을 참조한다

- [ ] **Step 1: 파일 생성**

`docs/00-start-here/context-quality.md`를 아래 내용으로 생성한다.

```markdown
---
title: AI Context 품질 기준
status: approved
visibility: public
updated: 2026-07-23
---

# AI Context 품질 기준

---

## 파트 1 — AI 자가 점검 (작업 시작 전)

실패 항목이 하나라도 있으면 작업 전 사용자에게 알리고 확인을 받는다.  
추측하거나 빠진 컨텍스트를 가정해서 진행하지 않는다.

- [ ] **완전성**: `context-scope.md` 기준으로 이 작업 유형에 필요한 파일을 모두 로드했는가
- [ ] **미정 확인**: `what-is-pending.md`에서 현재 작업과 교차하는 미정 항목을 확인했는가
- [ ] **충돌 없음**: 로드한 문서 간 서로 모순되는 내용이 없는가
- [ ] **민감 정보**: 로드한 컨텍스트에 시크릿·개인정보가 포함되지 않았는가

**미달 보고 형식**

> **[Context 미달]** 아래 항목을 확인할 수 없습니다.  
> - [실패 항목]  
> 작업을 시작하기 전에 확인이 필요합니다.

---

## 파트 2 — 문서 관리자 점검 (작성·갱신·PR 머지 전)

- [ ] **frontmatter**: `title`, `status`, `updated`, `source_updated` 필드가 모두 채워져 있는가
- [ ] **미정 명시**: 확정되지 않은 내용에 `[미정]` 표시가 있는가
- [ ] **크로스링크**: 관련 문서를 상대 경로로 참조하고 있는가
- [ ] **토큰 효율**: 불필요한 중복·설명 없이 핵심만 담겨 있는가
- [ ] **민감 정보**: PUBLIC 저장소 기준에 맞게 분류됐는가 ([`../_meta/SYNC.md`](../_meta/SYNC.md) 분류 정책 참조)
```

- [ ] **Step 2: 토큰 수 검증**

```bash
wc -m /Users/User/src/Magic_Academy/repo/docs/00-start-here/context-quality.md
```

결과 문자 수를 4로 나눈 값이 250 이하여야 한다.  
예상 결과: ~800자 → ~200토큰

- [ ] **Step 3: 체크리스트 항목 수 검증**

```bash
grep -c "^\- \[ \]" /Users/User/src/Magic_Academy/repo/docs/00-start-here/context-quality.md
```

예상 결과: `9` (파트1 4개 + 파트2 5개)

- [ ] **Step 4: 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add docs/00-start-here/context-quality.md docs/superpowers/
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: add context-quality.md — AI context 품질 기준 및 문서 관리자 점검 체크리스트"
```

---

### Task 2: `context-scope.md` Always Load 등록

**Files:**
- Modify: `docs/00-start-here/context-scope.md`

**Interfaces:**
- Consumes: `docs/00-start-here/context-quality.md` (Task 1에서 생성)
- Produces: context-quality.md가 Always Load로 등록된 context-scope.md

- [ ] **Step 1: 토큰 표에 한 줄 추가**

`context-scope.md`의 파일별 토큰 예산 표에서 `00-start-here/what-is-pending.md` 행 바로 아래에 아래 행을 삽입한다.

기존:
```
| `00-start-here/what-is-pending.md` | 31 | ~177 | Always |
| `02-domain/overview.md` | 44 | ~228 | Always |
```

변경 후:
```
| `00-start-here/what-is-pending.md` | 31 | ~177 | Always |
| `00-start-here/context-quality.md` | ~50 | ~200 | Always |
| `02-domain/overview.md` | 44 | ~228 | Always |
```

- [ ] **Step 2: Always Load 토큰 합계 업데이트**

기존:
```
**총 Always Load 토큰**: ~3,184 토큰
```

변경 후:
```
**총 Always Load 토큰**: ~3,384 토큰
```

- [ ] **Step 3: Always Load 파일 목록에 추가**

"Always Load (모든 작업)" 섹션의 코드 블록에서 `what-is-pending.md` 바로 아래에 추가한다.

기존:
```
docs/00-start-here/what-is-pending.md
docs/02-domain/overview.md
```

변경 후:
```
docs/00-start-here/what-is-pending.md
docs/00-start-here/context-quality.md
docs/02-domain/overview.md
```

- [ ] **Step 4: 이유 섹션에 새 bullet 추가**

Always Load 이유 섹션(`**이유**:` 블록)에서 `02-domain/ 7종:` 줄 바로 아래에 새 줄을 추가한다. 기존 줄은 변경하지 않는다.

기존:
```
- `02-domain/` 7종: 이 프로젝트는 도메인 용어(3축, Tick, Agent 종류, 관계 척도)가 코드 구조와 직결된다. 도메인을 모르면 잘못된 변수명, 잘못된 관계 방향, 잘못된 사건 분류가 생긴다.
```

변경 후:
```
- `02-domain/` 7종: 이 프로젝트는 도메인 용어(3축, Tick, Agent 종류, 관계 척도)가 코드 구조와 직결된다. 도메인을 모르면 잘못된 변수명, 잘못된 관계 방향, 잘못된 사건 분류가 생긴다.
- `00-start-here/context-quality.md`: AI context 충분성을 작업 시작 전에 판단하는 기준. 이 파일 없이는 AI가 잘못된 컨텍스트로 작업을 시작해도 알아차릴 수 없다.
```

- [ ] **Step 5: 변경 검증**

```bash
grep -n "context-quality" /Users/User/src/Magic_Academy/repo/docs/00-start-here/context-scope.md
```

예상 결과: 3줄 (토큰 표, 파일 목록, 이유 섹션)

- [ ] **Step 6: 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add docs/00-start-here/context-scope.md
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: register context-quality.md as Always Load in context-scope"
```

---

### Task 3: `AGENTS.md` 승인 섹션 확장

**Files:**
- Modify: `AGENTS.md` (저장소 루트)

**Interfaces:**
- Produces: 판단 3원칙·게이트·처리 원칙이 추가된 AGENTS.md

- [ ] **Step 1: 삽입 위치 확인**

```bash
grep -n "^## 승인 필요 작업" /Users/User/src/Magic_Academy/repo/AGENTS.md
grep -n "^\*\*Git\*\*" /Users/User/src/Magic_Academy/repo/AGENTS.md
```

예상 결과: `## 승인 필요 작업`은 162번째 줄, `**Git**`은 166번째 줄

- [ ] **Step 2: 판단 3원칙·게이트·처리 원칙 삽입**

`AGENTS.md`의 `다음 작업은 사용자의 명시적 확인 없이 수행하지 않는다.` 줄과 `**Git**` 줄 사이에 아래 내용을 삽입한다.

기존:
```markdown
다음 작업은 사용자의 명시적 확인 없이 수행하지 않는다.

**Git**
```

변경 후:
```markdown
다음 작업은 사용자의 명시적 확인 없이 수행하지 않는다.

### 판단 3원칙

목록에 없는 상황에서도 아래 중 하나라도 해당하면 승인 요청한다.

1. **되돌릴 수 없는가** — 파일 삭제, DB drop, force push 등
2. **요청 범위를 벗어났는가** — A 수정 요청인데 B도 건드려야 할 때
3. **외부에 영향을 주는가** — push, PR 생성, 외부 API 쓰기 호출 등

### 작업 흐름상 승인 게이트

| 시점 | 멈추는 조건 |
|------|------------|
| 시작 전 | 작업 범위가 두 가지 이상으로 해석될 때 |
| 도중 | 예상치 못한 상황이 생겨 범위를 넘어야 할 때 |
| 완료 전 | 돌이키기 어려운 변경이 포함될 때 (커밋, push, 파일 삭제 등) |

### 승인 후 처리 원칙

- 승인받은 범위만 수행한다. 연관 작업이 생겨도 별도 승인을 받는다.
- 승인 도중 새로운 승인 필요 상황이 생기면 작업을 멈추고 다시 요청한다.
- 거절 시: 대안을 제안하거나 작업을 중단한다. 우회하지 않는다.

---

**Git**
```

- [ ] **Step 3: 기존 내용 보존 검증**

```bash
grep -c "rm -rf" /Users/User/src/Magic_Academy/repo/AGENTS.md
grep -c "GitHub PR" /Users/User/src/Magic_Academy/repo/AGENTS.md
grep -c "진행할까요" /Users/User/src/Magic_Academy/repo/AGENTS.md
```

예상 결과: 각 `1` — 기존 내용이 그대로 있어야 한다.

- [ ] **Step 4: 신규 섹션 존재 검증**

```bash
grep -c "판단 3원칙\|승인 게이트\|승인 후 처리" /Users/User/src/Magic_Academy/repo/AGENTS.md
```

예상 결과: `3`

- [ ] **Step 5: 커밋**

```bash
git -C /Users/User/src/Magic_Academy/repo add AGENTS.md
git -C /Users/User/src/Magic_Academy/repo commit -m "docs: expand AGENTS.md with approval principles, gates, and post-approval rules"
```
