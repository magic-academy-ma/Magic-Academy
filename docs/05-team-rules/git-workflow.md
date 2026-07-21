---
title: Git 워크플로우 컨벤션
source: confluence/09_CONVENTIONS/1.브랜치컨벤션 + 2.Issue라벨·제목컨벤션 + 3.PR크기·리뷰컨벤션
canonical:
  - https://jehye.atlassian.net/wiki/spaces/MA/pages/4161548/1.
  - https://jehye.atlassian.net/wiki/spaces/MA/pages/4358188/2.+Issue
  - https://jehye.atlassian.net/wiki/spaces/MA/pages/4096005/3.+PR
status: approved
visibility: public
updated: 2026-07-21
source_updated: 2026-07-18
---

# Git 워크플로우 컨벤션

## 1. 브랜치 구조

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

## 2. 커밋 컨벤션

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

---

## 3. Issue 컨벤션

### 제목 형식

```
[타입] 작업 내용
```

### 타입 예시

```
[Feature] 학생 Agent 기본 프로필 구조 정의
[Bug] 이벤트 발생 조건이 중복 적용되는 문제 수정
[Docs] AI Context 문서 템플릿 작성
[Decision] MVP 범위 확정
[Refactor] Agent 상태 업데이트 로직 분리
[Chore] 프로젝트 초기 환경 설정
```

### 라벨

```
feature      : 새로운 기능
bug          : 오류 수정
docs         : 문서 작성 및 수정
design       : 화면 / UX / 구조 설계
refactor     : 기능 변경 없는 코드 개선
chore        : 환경 설정, 패키지 관리 등
discussion   : 논의가 필요한 사항
decision     : 결정된 사항 기록
ai-context   : AI context 문서 관련 작업
blocked      : 다른 작업에 막힌 상태
question     : 확인이 필요한 질문
```

### 작성 양식

```markdown
## 작업 목적
이 Issue에서 해결하려는 문제나 구현하려는 기능을 작성한다.

## 작업 내용
- [ ] 작업 1
- [ ] 작업 2

## 완료 기준
- 어떤 상태가 되면 완료로 볼 수 있는지 작성한다.

## 참고 자료
- 관련 문서 / 회의록 / Decision Log / PR

## 추가 메모
논의가 필요한 부분이나 주의할 점을 작성한다.
```

---

## 4. PR 컨벤션

### 기본 규칙

- PR 하나는 하나의 목적만 가진다.
- 기능 구현과 대규모 리팩토링은 가능하면 분리한다.
- 관련 Issue를 반드시 연결한다.
- 변경 이유를 PR 설명에 작성한다.
- AI를 사용한 경우, 사용 범위와 사람이 검토한 내용을 작성한다.
- 리뷰 승인 전에는 `develop` 또는 `main`에 merge하지 않는다.
- **PR 크기 권장**: 300~500줄 이내(문서 제외), 1,000줄 이상이면 가능하면 분리

### 제목 형식

```
[타입] 작업 내용
```

| 타입 | 용도 |
|------|------|
| Feature | 새로운 기능 추가 |
| Fix | 버그 수정 |
| Refactor | 기능 변경 없는 코드 개선 |
| Docs | 문서 수정 |
| Test | 테스트 코드 추가 및 수정 |
| Chore | 설정, 의존성 등 기타 작업 |

### 작성 양식

```markdown
## 작업 개요
이번 PR에서 변경한 내용을 간단히 설명한다.

## 관련 Issue
Closes #이슈번호

## 변경 내용
- 변경 사항 1

## 결정 사항 및 이유
이 구현 방식이나 구조를 선택한 이유를 작성한다.

## 테스트 / 확인 내용
- [ ] 로컬 실행 확인
- [ ] 주요 기능 동작 확인
- [ ] 에러 케이스 확인
- [ ] 관련 문서 업데이트 확인

## AI 사용 여부
- 사용 여부: 사용함 / 사용하지 않음
- 사용한 작업:
- 사람이 검토한 내용:

## 리뷰어가 봐야 할 부분
특히 확인이 필요한 코드나 설계 포인트를 작성한다.
```

### 코드 리뷰 코멘트 태그

```
[Must]     반드시 수정해야 하는 부분
[Question] 질문 또는 확인이 필요한 부분
[Suggest]  개선 제안
[Nit]      사소한 수정
[Good]     좋은 구현 또는 유지하면 좋은 부분
```
