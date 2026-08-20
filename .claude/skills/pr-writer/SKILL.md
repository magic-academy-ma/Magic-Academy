---
description: 현재 브랜치의 diff와 커밋 내역을 분석해 Magic Academy PR 템플릿 기반 초안을 작성하고 Draft PR을 생성할 때 사용
---

# /pr-writer

현재 브랜치의 변경 사항과 커밋 내역을 분석하여 `.github/pull_request_template.md` 양식에 맞춘 PR 초안을 생성한다.

## 실행 순서

1. **브랜치 및 diff 분석**:
   - 현재 브랜치명 확인 (`git branch --show-current`)
   - base 브랜치 확인 (기본: `develop`, `main` 직접 PR 금지)
   - `git diff origin/{base}...HEAD --stat` 및 `git log origin/{base}...HEAD --oneline` 확인
   - 브랜치명 또는 사용자 입력에서 관련 Issue 번호 추출
   - 연결할 Issue 내용 확인 (`gh issue view {이슈번호}`)
   - Issue 번호를 찾지 못하면 Issue 조회를 생략하고 `관련 Issue 없음`으로 작성
2. **사전 검증**:
   - PR 변경 규모 확인 (권장: 300~500줄 이내 / 1,000줄 이상 시 분리 권고)
   - Public 저장소 보안 검증 (시크릿, API 키, 팀원 개인정보·내부 KPI 포함 여부)
3. **초안 작성**:
   - `.github/pull_request_template.md`의 모든 섹션을 채워 출력

## 출력 양식

```markdown
제목: [타입] 작업 내용

## 작업 개요

이번 PR에서 변경한 내용을 간단히 설명한다.

## 관련 Issue

Closes #이슈번호

## 변경 내용

- 변경 사항 1
- 변경 사항 2

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

## MA PR 컨벤션

- **타입 매핑**: Feature(신규 기능) / Fix(버그 수정) / Refactor(리팩토링) / Docs(문서) / Test(테스트) / Chore(환경/설정) / Style(스타일)
- **타깃 브랜치**: `develop` (main 직접 PR 금지)
- **Branch Protection Ruleset**: develop/main은 1명 이상 승인 필수, force push 금지

## 생성 전 확인

PR 생성은 외부 쓰기 작업이므로:
1. 작성된 초안을 사용자에게 먼저 출력한다.
2. 사용자 승인을 받은 후 `gh pr create --draft --base {base} --title "..." --body "..."`를 실행한다.
