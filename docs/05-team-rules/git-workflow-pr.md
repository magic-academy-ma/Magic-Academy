---
title: Issue·PR·리뷰 컨벤션
source: confluence/09_CONVENTIONS/2.Issue라벨·제목컨벤션 + 3.PR크기·리뷰컨벤션
canonical:
  - https://jehye.atlassian.net/wiki/spaces/MA/pages/4358188/2.+Issue
  - https://jehye.atlassian.net/wiki/spaces/MA/pages/4096005/3.+PR
status: approved
visibility: public
updated: 2026-07-21
source_updated: 2026-07-09
---

# Issue·PR·리뷰 컨벤션

## Issue 컨벤션

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

## PR 컨벤션

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

| 타입 | 용도 | 커밋 타입 대응 |
|------|------|--------------|
| Feature | 새로운 기능 추가 | `feat` |
| Fix | 버그 수정 | `fix` |
| Refactor | 기능 변경 없는 코드 개선 | `refactor` |
| Docs | 문서 수정 | `docs` |
| Test | 테스트 코드 추가 및 수정 | `test` |
| Chore | 설정, 의존성 등 기타 작업 | `chore` |
| Style | 코드 포맷, 공백 등 기능 무관 변경 | `style` |

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

---

## Branch Protection Rulesets

`main`과 `develop` 브랜치에 GitHub Ruleset이 설정되어 있다.

| 규칙 | main | develop |
|------|------|---------|
| PR 없이 직접 push | 차단 | 차단 |
| PR 승인 필수 인원 | 1명 | 1명 |
| Force push | 차단 | 차단 |
| 브랜치 삭제 | 차단 | 차단 |
| 새 커밋 push 시 기존 승인 무효화 | 적용 | 적용 |
| Admin bypass | 불가 | 불가 |

- `bypass_actors`를 빈 배열로 설정하여 Admin을 포함한 모든 계정에 동일하게 적용된다.
- `feature/*` 브랜치에는 별도 ruleset이 없으며 컨벤션으로만 관리한다.
