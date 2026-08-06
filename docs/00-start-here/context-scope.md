---
title: AI Context 로딩 범위
status: approved
visibility: public
updated: 2026-08-06
---

# AI Context 로딩 범위

> 이 파일은 AI 에이전트가 작업 유형별로 어떤 파일을 로드해야 하는지 정의한다.  
> 불필요한 파일을 제거해 토큰 예산을 절약하고, 필요한 문맥을 빠뜨리지 않도록 가이드한다.

---

## 파일별 토큰 예산

> 측정 기준: `wc -m`(실제 문자 수) ÷ 4 = 예상 토큰  
> 한국어는 UTF-8에서 1자 = 3 bytes이므로 byte 기반보다 문자 수 기반이 더 정확하다.

| 파일 | 문자 수 | 예상 토큰 | 분류 |
|------|------:|----------:|------|
| `00-start-here/index.md` | 898 | ~225 | Always |
| `00-start-here/what-is-decided.md` | 2,448 | ~612 | Always |
| `00-start-here/what-is-pending.md` | 959 | ~240 | Always |
| `00-start-here/context-quality.md` | 895 | ~224 | Always |
| `02-domain/overview.md` | 913 | ~228 | Always |
| `02-domain/agents.md` | 2,403 | ~601 | Always |
| `02-domain/relationships.md` | 1,220 | ~305 | Always |
| `02-domain/organizations.md` | 960 | ~240 | Always |
| `02-domain/events.md` | 1,280 | ~320 | Always |
| `02-domain/time-and-space.md` | 1,102 | ~276 | Always |
| `02-domain/glossary.md` | 1,512 | ~378 | Always |
| `superpowers/README.md` | 1,255 | ~314 | Always (@ai-native 세션) |
| `superpowers/ai-workflow.md` | 1,553 | ~388 | Always (@ai-native 세션) |
| `05-team-rules/conventions.md` | 1,267 | ~317 | Task |
| `05-team-rules/definition-of-done.md` | 1,127 | ~282 | Task |
| `05-team-rules/git-workflow-commit.md` | 1,473 | ~368 | Task (구현·커밋 시) |
| `05-team-rules/git-workflow-pr.md` | 2,610 | ~653 | Task (PR 작성·리뷰 시) |
| `05-team-rules/dev-workflow.md` | 1,709 | ~427 | Task (외부 게시 작업 시) |
| `05-team-rules/ai-usage.md` | 1,330 | ~333 | Task |
| `decisions/README.md` | 632 | ~158 | Task |
| `README.md` | — | ~211 | Skip |
| `_meta/SYNC.md` | — | ~1,020 | Skip |
| `_meta/ai-native-env-design.md` | — | ~1,063 | Skip |

> 측정일: 2026-08-06 (`wc -m`)

**총 Always Load 토큰**: ~3,648 토큰 (00-start-here/ + 02-domain/ 기준, superpowers/ 제외)  
**@ai-native Always Load**: ~4,350 토큰 (위 + superpowers/ 2종)  
**전체 docs/ 토큰 (Skip 제외)**: ~6,887 토큰

---

## Always Load (모든 작업)

모든 작업 시작 시 아래 파일을 로드한다.

```
docs/00-start-here/index.md
docs/00-start-here/what-is-decided.md
docs/00-start-here/what-is-pending.md
docs/00-start-here/context-quality.md
docs/02-domain/overview.md
docs/02-domain/agents.md
docs/02-domain/relationships.md
docs/02-domain/organizations.md
docs/02-domain/events.md
docs/02-domain/time-and-space.md
docs/02-domain/glossary.md
```

**이유**:
- `00-start-here/` 4종: 프로젝트 방향, 확정/미정 경계를 파악하지 못하면 임의 결정이 발생한다. 모든 작업의 전제 조건.
- `02-domain/` 7종: 이 프로젝트는 도메인 용어(3축, Tick, Agent 종류, 관계 척도)가 코드 구조와 직결된다. 도메인을 모르면 잘못된 변수명, 잘못된 관계 방향, 잘못된 사건 분류가 생긴다.
- `00-start-here/context-quality.md`: AI context 충분성을 작업 시작 전에 판단하는 기준. 이 파일 없이는 AI가 잘못된 컨텍스트로 작업을 시작해도 알아차릴 수 없다.

---

## Task-Specific Load

### 도메인 로직 구현 (새 기능)

Always Load 전체 + 아래 추가:

```
docs/05-team-rules/conventions.md
docs/05-team-rules/definition-of-done.md
docs/05-team-rules/git-workflow-commit.md
```

**추가 이유**: 폴더 구조·네이밍 컨벤션, 완료 기준, 브랜치·커밋 형식을 확인해야 구현 방향이 팀 규칙과 어긋나지 않는다.  
해당 기능 스펙이 있으면 `docs/04-feature-specs/<기능명>.md`도 필수 로드 (구현 직전).

### 버그 수정

Always Load 전체 + 아래 추가:

```
docs/05-team-rules/conventions.md
docs/05-team-rules/git-workflow-commit.md
```

**추가 이유**: 수정 후 변수명·폴더 위치가 컨벤션에 맞는지, 커밋 타입이 올바른지 확인이 필요하다.  
git-workflow-pr, definition-of-done은 버그 수정 시 불필요 — PR 작성 단계에서 로드한다.

### 문서 작업 / 이관

Always Load 중 `02-domain/` 7종 + 아래:

```
docs/00-start-here/index.md
docs/00-start-here/what-is-decided.md
docs/00-start-here/what-is-pending.md
docs/00-start-here/context-quality.md
docs/05-team-rules/ai-usage.md
docs/05-team-rules/definition-of-done.md
```

**참고**: `_meta/SYNC.md`는 이관 담당자가 직접 확인하는 운영 문서다. AI가 이관 작업 자체를 수행하는 경우에만 로드한다. 일반 문서 작업에서는 불필요.

### PR 작성·리뷰

Always Load 중 `00-start-here/` 4종 + 아래:

```
docs/05-team-rules/git-workflow-pr.md
docs/05-team-rules/dev-workflow.md
docs/05-team-rules/definition-of-done.md
docs/05-team-rules/ai-usage.md
```

**추가 이유**: PR 제목·본문 형식, 리뷰 코멘트 태그(`[Must]`, `[Suggest]` 등), AI 사용 여부 표기가 git-workflow-pr에 정의돼 있다. `dev-workflow.md`는 Draft PR 생성·Ready 전환·리뷰 코멘트 게시 전의 승인 절차를 정의한다. 브랜치·커밋 파일(git-workflow-commit)과 도메인 파일은 이 시점에 불필요하다.

---

## 로드하지 않는 파일 (이유 포함)

| 파일 | 이유 |
|------|------|
| `docs/README.md` | `00-start-here/index.md`와 내용이 중복된다. 사람이 저장소를 탐색할 때 필요한 안내 파일이며, AI context로서 독립 가치가 없다. |
| `docs/_meta/SYNC.md` | Confluence → docs/ 이관 큐와 동기화 운영 정책을 담고 있다. AI 개발 작업 중 읽을 필요가 없고, ~1,020 토큰 소비 대비 도움이 없다. 이관 담당자 전용 운영 문서. |
| `docs/_meta/ai-native-env-design.md` | AI Native 환경 설계 과정 기록(ADR 성격)이다. 결정 결과는 이미 `CLAUDE.md`와 `docs/`에 반영됐다. 과거 설계 프로세스를 AI에게 설명할 필요가 없으며 ~1,063 토큰을 소모한다. |
| `docs/decisions/README.md` | ADR 양식과 미결 항목 목록이다. ADR을 작성하는 시점에만 필요하다. 일상 개발 작업에서는 불필요. |

---

## 개선 제안

### 1. `what-is-decided.md` 중복 정리 가능 (~100토큰 절감)

`what-is-decided.md`의 **세계관 카테고리 섹션** (시간/공간/조직/관계/사건/배경)은 `02-domain/` 파일들과 내용이 거의 중복된다. 현재는 확정 출처 표시가 필요해서 유지하는 것이 맞지만, 향후 도메인 파일이 확정 상태가 되면 해당 섹션을 링크로 대체하면 토큰을 줄일 수 있다.

### 2. `05-team-rules/git-workflow.md` 분리 완료 (~500토큰 절감)

`git-workflow.md` (~847 토큰)를 `git-workflow-commit.md` / `git-workflow-pr.md`로 분리했다. 작업 유형별 로드량이 절반으로 줄었다. (2026-07-21 완료)

### 3. `05-team-rules/ai-usage.md` 섹션 정리 (~100토큰 절감 가능)

8.6 AI 사용 기록 양식과 8.7 PR 표기 예시는 사람이 기록할 때 참조하는 내용이다. AI가 PR을 작성할 때 이 양식을 그대로 생성하는 목적이라면 유용하지만, AI 스스로 이 규칙을 따르기 위해 매번 전체를 읽을 필요는 없다. 핵심 제약(8.3 주의 작업, 8.4 금지 정보)만 CLAUDE.md에 인라인으로 두는 방안도 검토할 수 있다.

### 4. `_meta/SYNC.md` 이관 큐는 AI context 아님

이관 큐(⬜/✅ 테이블)는 상태 추적용 운영 데이터다. AI가 이관 큐를 읽어도 실제 Confluence에 접근할 수 없으므로 정보 가치가 없다. 이 파일은 AI context에서 완전히 제외하고, 이관 담당자 로컬 작업 시에만 참조한다.

### 5. `02-domain/glossary.md` Always Load 유지 권장

용어집은 ~382 토큰이지만, 도메인 용어를 잘못 사용하는 것(예: Event와 Tick을 혼동)이 코드 설계 오류로 직결된다. 개별 도메인 파일에 정의가 분산돼 있어 이 파일이 없으면 용어 불일치가 발생할 수 있으므로 Always Load를 유지한다.
