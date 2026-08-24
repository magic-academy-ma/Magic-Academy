---
title: Definition of Done
source: confluence/09_CONVENTIONS/11.DefinitionOfDone
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/4358231/11.+Definition+of+Done
status: approved
updated: 2026-07-21
source_updated: 2026-07-09
---

# Definition of Done

"완료"의 기준을 명확히 하여, 단순히 코드를 작성한 상태와 실제로 팀이 사용할 수 있는 상태를 구분한다.

## 공통 Done 기준

```markdown
- [ ] 관련 Issue가 생성되어 있다.
- [ ] 작업 브랜치가 컨벤션에 맞게 생성되어 있다.
- [ ] 기능이 정상적으로 동작한다.
- [ ] 기본 에러 케이스를 확인했다.
- [ ] 코드 스타일 컨벤션을 지켰다.
- [ ] 불필요한 로그와 주석을 제거했다.
- [ ] PR 설명을 작성했다.
- [ ] 리뷰를 받았다.
- [ ] 필요한 문서를 업데이트했다.
- [ ] 중요한 결정이나 변경 사항은 Decision Log에 기록했다.
```

## 기능 구현 Done 기준

```markdown
- [ ] 요구사항에 맞게 기능이 구현되었다.
- [ ] 정상 케이스가 동작한다.
- [ ] 주요 예외 케이스가 처리되었다.
- [ ] API 응답 형식이 컨벤션에 맞다.
- [ ] 프론트와 백엔드 연결에 필요한 정보가 문서화되었다.
```

## 문서 작업 Done 기준

```markdown
- [ ] 문서 목적이 명확하다.
- [ ] 결정 사항과 이유가 함께 기록되어 있다.
- [ ] 관련 문서나 Issue가 연결되어 있다.
- [ ] 변경 기록이 남아 있다.
- [ ] 팀원이 문서만 보고 다음 작업을 이해할 수 있다.
```

## AI 사용 작업 Done 기준

```markdown
- [ ] AI 사용 여부가 기록되어 있다.
- [ ] AI에게 제공한 context가 적절하다.
- [ ] 민감정보가 포함되지 않았다.
- [ ] AI 결과물을 사람이 검토했다.
- [ ] 반영한 내용과 반영하지 않은 내용을 구분했다.
```
