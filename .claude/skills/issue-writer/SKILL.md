---
description: 작업 내용을 받아 Magic Academy GitHub Issue 초안을 생성할 때 사용
---

# /issue-writer

작업 내용을 받아 Magic Academy GitHub Issue 초안을 생성한다.

## 입력

사용자에게 다음을 확인한다 (이미 제공됐으면 생략):
1. 작업 내용 — 무엇을 구현하거나 해결하는 작업인가
2. 타입 — Feature / Bug / Docs / Design / Refactor / Chore / Discussion / Decision

## 출력

아래 형식으로 Issue 초안을 출력한다. 사용자가 직접 GitHub에 등록하거나, 승인 후 `gh issue create`로 생성한다.

```
제목: [타입] 작업 내용

라벨: feature | bug | docs | design | refactor | chore (타입에 맞게 선택)

---

## 작업 목적

이 Issue에서 해결하려는 문제나 구현하려는 기능을 작성한다.

## 작업 내용

- [ ] 작업 1
- [ ] 작업 2

## 완료 기준

어떤 상태가 되면 완료로 볼 수 있는지 작성한다.

## 참고 자료

- 관련 문서:
- 관련 회의록:
- 관련 Decision Log:
- 관련 PR:

## 추가 메모

논의가 필요한 부분이나 주의할 점을 작성한다.
```

## MA 프로젝트 컨텍스트

- 저장소: magic-academy-ma/Magic-Academy (Public)
- 브랜치 규칙: Issue 생성 후 `feature/issue-{번호}-{작업명}` 브랜치 분기
- 타깃 브랜치: `develop` (main 직접 push 금지)
- 시크릿·개인정보·팀원 개인 KPI를 Issue에 포함하지 않는다

## 생성 전 확인

Issue 생성은 외부 쓰기 작업이므로 초안을 출력한 뒤 사용자 승인을 받고 `gh issue create`를 실행한다.
