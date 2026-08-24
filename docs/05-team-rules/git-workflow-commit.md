---
title: Git 브랜치·커밋 컨벤션
source: confluence/09_CONVENTIONS/1.브랜치컨벤션
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/4161548/1.
status: approved
updated: 2026-08-25
source_updated: 2026-08-12
---

# Git 브랜치·커밋 컨벤션

## 브랜치 구조

```
main        : 배포 가능하거나 최종 제출 가능한 안정 버전
develop     : 개발 통합 브랜치
feature/*   : 새로운 기능 개발
fix/*       : 버그 수정
docs/*      : 문서 작성 및 수정
refactor/*  : 기능 변경 없는 코드 구조 개선
chore/*     : 설정, 패키지, 환경 구성 등 기타 작업
```

### 브랜치 이름 형식

```
타입/issue-번호-작업명
```

### 예시

```
feature/issue-12-agent-profile
fix/issue-21-relationship-update-bug
docs/issue-05-pr-template
refactor/issue-30-agent-service-structure
chore/issue-02-project-setting
```

### 규칙

- 모든 작업은 가능하면 Issue를 먼저 만들고 브랜치를 생성한다.
- 브랜치명에는 작업 목적이 드러나야 한다.
- 한 브랜치에서는 하나의 주요 작업만 진행한다.
- 작업이 끝나면 Pull Request를 생성한다.
- `main` 브랜치에는 직접 push하지 않는다.

---

## Git worktree 운영

- 동시에 진행하는 브랜치는 작업 디렉터리를 격리해 미커밋 변경이 섞이지 않도록 한다.
- 격리가 필요한 작업은 저장소 내부 `.worktrees/<브랜치명>` 경로에 worktree를 만든다.
- `.worktrees/`는 Git 추적 대상에서 제외한다.
- 기능 개발과 버그 수정은 각각 별도 브랜치에서 진행하고 `main`에서는 직접 개발하지 않는다.
- 작업 완료 후 제거 여부를 확인하고 더 이상 필요 없는 worktree만 정리한다.

---

## 브랜치 보호 원칙

`main`과 `develop`은 저장소 Ruleset으로 보호한다.

- Pull Request 없는 직접 push, force push와 브랜치 삭제를 차단한다.
- 병합 전 최소 1명의 승인을 요구한다.
- 승인 이후 새 커밋이 추가되면 기존 승인을 무효화하고 다시 검토한다.
- 관리자도 기본 보호 규칙을 우회하지 않는다.
- 기능 브랜치는 별도 Ruleset 대신 브랜치·PR 컨벤션으로 관리한다.

Ruleset 활성 상태, 대상 브랜치, 승인 수, stale review 무효화와 bypass 설정을 주기적으로 확인한다.

---

## 커밋 컨벤션

### 형식

```
타입: 제목
```

- 제목은 50자 이내 / 마침표 없음 / 한국어 또는 영어 일관되게 사용

### 타입 목록

| 타입 | 용도 | 브랜치 대응 |
|------|------|------------|
| `feat` | 새 기능 추가 | `feature/` |
| `fix` | 버그 수정 | `fix/` |
| `chore` | 설정·환경·의존성 변경 | `chore/` |
| `docs` | 문서 추가·수정 | `docs/` |
| `refactor` | 기능 변화 없는 코드 구조 개선 | `refactor/` |
| `test` | 테스트 추가·수정 | — |
| `style` | 코드 포맷, 공백 등 (기능 무관) | — |

### 예시

```
feat: 학생 Agent 상태값 저장 API 구현
fix: 관계 수치 음수 clamp 오류 수정
chore: Docker Compose pgvector 서비스 추가
refactor: AgentRuntime tick 루프 분리
```

### 본문 (선택)

- 72자 이내 줄바꿈
- **what보다 why** — 무엇을 바꿨는지보다 왜 바꿨는지를 적는다
- 제목과 본문 사이 빈 줄 필수
