---
title: Git 브랜치·커밋 컨벤션
source: confluence/09_CONVENTIONS/1.브랜치컨벤션
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/4161548/1.
status: approved
visibility: public
updated: 2026-07-21
source_updated: 2026-07-18
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
