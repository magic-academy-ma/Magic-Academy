---
title: "[AI 협업] Claude 세션 협업 가이드"
source: confluence/AI협업/Claude_세션_협업_가이드
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/30048328
status: approved
visibility: public
updated: 2026-08-25
source_updated: 2026-08-17
---

# [AI 협업] Claude 세션 협업 가이드

Magic Academy 프로젝트에서 Claude Code를 활용하는 협업 방식을 정의한다.  
페르소나 체계, 스킬 운용 방식, 승인 게이트, AI 네이티브 개발 워크플로우를 포함한다.

## 1. 페르소나 체계 (3종)

담당자가 아닌 **지금 하는 작업 유형**을 기준으로 선택한다.

| 페르소나 | 쓰는 상황 | 자동 로딩 문서 |
| --- | --- | --- |
| `@pm` | Issue 작성, 스펙 초안, 요구사항 정리 | `docs/01-product/`, `docs/02-domain/`, `docs/04-feature-specs/`, `docs/05-team-rules/git-workflow-pr.md` |
| `@dev` | Slice 단위 구현 (백엔드·DB·인프라) | `docs/02-domain/`, `docs/03-system-design/architecture.md`, 해당 컴포넌트 문서, 해당 Slice 스펙, 컨벤션·DoD·커밋 규칙 |
| `@fe` | React, React Flow, 화면 컴포넌트 | `docs/02-domain/`, `docs/03-system-design/architecture.md`, `user-flow.md`, FE 관련 feature-specs, 컨벤션 |

**담당 영역 보호 규칙**: 페르소나는 현재 작업 방식을 선택하는 기준이며, 문서·기능의 담당 권한을 대체하지 않는다. 담당 영역 밖의 스펙이나 구현을 변경할 때는 해당 담당자의 검토를 받는다.

## 2. 세션 시작 방법

1. `AGENTS.md` 읽기 — 프로젝트 규칙·도메인·코딩 원칙 확인
2. 지금 하려는 작업 유형 파악
3. 위 페르소나 표에서 맞는 것 선택
4. 해당 페르소나의 자동 로딩 문서 읽기

## 3. 스킬

### /issue-writer

- **언제**: GitHub Issue를 만들기 전
- **방법**: 작업 내용을 설명하면 제목·본문 초안 생성 → 확인 후 `gh issue create` 실행
- **주의**: 초안 → 사용자 승인 → 생성 순서 필수. Issue 본문은 한국어로 작성

### /spec-draft

- **언제**: 기능 구현 전 `docs/04-feature-specs/` 스펙 문서를 작성할 때, 또는 FE 화면 스펙을 Confluence에 올릴 때
- **모드 A — 일반 기능 스펙**: 기능 이름·FR 번호·핵심 동작 설명 → 스펙 초안 생성 → `docs/04-feature-specs/FR-{번호}-{기능명}.md`에 직접 저장
- **모드 B — FE 화면 스펙**: Figma URL 입력 시 자동 전환 → Figma MCP로 디자인 추출 → 스펙 초안 생성 → Confluence Draft 생성 → Approved 후 `docs/04-feature-specs/FR-{번호}-{화면명}-screen.md`에 이관
- **주의**: 미정 항목은 `[미정]`으로 표시, 임의 확정하지 않음. 파일 작성·Confluence Draft 생성 전 초안 확인 필수

### /pr-review

- **언제**: PR 코드 리뷰를 작성할 때
- **방법**: diff 분석 후 아래 태그 기반 리뷰 초안 생성 → 확인 후 GitHub에 게시

| 태그 | 의미 |
| --- | --- |
| `[Must]` | 반드시 수정 |
| `[Question]` | 확인 필요 |
| `[Suggest]` | 개선 제안 |
| `[Nit]` | 사소한 수정 |
| `[Good]` | 좋은 구현, 유지 권장 |

### /confluence-post

- **언제**: 문서 초안을 Confluence에 올릴 때
- **방법**: 문서 초안 제공 → Draft 페이지 생성 → 링크 공유 → 승인 후 Publish
- **주의**: Publish는 Confluence UI에서 직접 버튼 클릭 (MCP 제약)

### /briefing

- **언제**: 기능 완료 시, 작업 방향이 바뀌었을 때, 세션이 길어졌을 때
- **방법**: `/briefing` 입력 / **출력 형식**: Done / In progress / Next

### /context-scope

- **언제**: 지금 작업에 어떤 문서를 읽어야 할지 모를 때
- **방법**: 현재 작업 유형을 설명하면 Always Load / Task-Specific / Skip 분류로 안내

## 4. 주요 승인 게이트

| 작업 | 절차 |
| --- | --- |
| git commit | staged diff 확인 → 메시지 초안 출력 → 승인 → 실행 |
| git push | 대상 브랜치·커밋 확인 → 승인 → 실행 |
| GitHub Issue 생성 | 초안 출력 → 승인 → `gh issue create` |
| GitHub PR 생성 | 템플릿 기반 초안 출력 → 승인 → `gh pr create --draft` |
| Confluence 초안 텍스트 작성 | 자동 실행 (승인 불필요) |
| Confluence 페이지 생성 | 제목·위치·구조 확인 → 승인 → Draft 생성 |
| Confluence Publish | Confluence UI에서 직접 클릭 (MCP 제약) |
| PR 리뷰 코멘트 게시 | 태그 포함 초안 출력 → 승인 → 게시 |

## 5. AI 네이티브 개발 워크플로우

### 단계별 흐름

| 단계 | 작업 | 페르소나 | 사용 스킬 | 승인 게이트 |
| --- | --- | --- | --- | --- |
| 기획 | 요구사항 정리, Issue 작성 | `@pm` | `/issue-writer` | 초안 → 승인 → `gh issue create` |
| 설계 | 스펙 문서 작성 | `@pm` | `/spec-draft` | 초안 → 승인 → 파일 저장 (모드 A) 또는 Confluence Draft (모드 B) |
| 구현 | Slice 단위 코드 작성 | `@dev` / `@fe` | — | — |
| 커밋 | 변경사항 커밋 | — | — | staged diff 확인 → 승인 → `git commit` |
| PR | Draft PR 생성 | — | — | 초안 → 승인 → `gh pr create --draft` |
| 리뷰 | 코드 리뷰 작성 | — | `/pr-review` | 초안 → 승인 → GitHub 게시 |
| 문서화 | Confluence 페이지 생성/수정 | `@pm` | `/confluence-post` | 초안 → 승인 → Draft → UI에서 Publish |

### 세션 흐름 예시 (@dev 기준)

1. `AGENTS.md` 읽기
2. `@dev` 선택 → 문서 로드  
   **[공통 — 항상]**: `docs/02-domain/`, `docs/03-system-design/architecture.md`, `conventions.md`, `definition-of-done.md`, `git-workflow-commit.md`  
   **[Slice마다]**: 해당 컴포넌트 문서 + `docs/04-feature-specs/<해당 Slice>.md`
3. `docs/00-start-here/what-is-pending.md` 확인
4. 구현 (TDD: 테스트 먼저 → 구현)
5. `/briefing` → git commit (승인 후) → git push (승인 후)

### 브랜치 전략

```
main
 └── develop
      ├── feature/{issue번호}-{기능명}   ← 기능 추가
      ├── fix/{issue번호}-{버그명}        ← 버그 수정
      ├── docs/{issue번호}-{문서명}       ← 문서 작업
      ├── refactor/{issue번호}-{대상}     ← 리팩터링
      └── chore/{issue번호}-{대상}        ← 환경·설정
```

- 모든 브랜치는 PR을 통해 `develop`에 병합, 이후 `main`으로 병합
- `main` 직접 push 금지
- 브랜치 격리: git worktree 사용 (`.worktrees/<브랜치명>`)
  - `.worktrees/`는 `.gitignore`에 등록
  - 작업 완료 후 `git worktree remove`로 제거
  - 상세 규칙: `docs/05-team-rules/git-workflow-commit.md` 참조

## 변경 이력

| 날짜 | 내용 | 수정자 |
| --- | --- | --- |
| 2026-08-17 | /fe-spec 스킬 제거, /spec-draft 모드 A/B 통합 반영 | @Jehye |
| 2026-08-17 | 리뷰 반영: 담당 영역 보호 규칙 추가, /spec-draft FE 화면 스펙 구분, 승인 게이트 세분화, 브랜치 전략 확장 | @Jehye |
| 2026-08-12 | 최초 작성 — 페르소나 3종 체계, 스킬, 워크플로우 | @Jehye |
