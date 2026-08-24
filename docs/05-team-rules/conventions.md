---
title: 코드 스타일·폴더 구조 컨벤션
source: confluence/09_CONVENTIONS/4.코드스타일·폴더구조컨벤션
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/4096026/4.
status: approved
updated: 2026-07-21
source_updated: 2026-07-31
---

# 코드 스타일·폴더 구조 컨벤션

## 공통 코드 스타일

- 변수명과 함수명은 의미가 드러나게 작성한다.
- 불필요한 축약어는 사용하지 않는다.
- 하나의 함수는 하나의 역할을 하도록 작성한다.
- 중복 로직은 공통 함수로 분리한다.
- 매직 넘버는 상수로 분리한다.
- `console.log` 또는 디버깅 코드는 PR 전에 제거한다.

## 이름 규칙

```
변수명           : camelCase
함수명           : camelCase
컴포넌트명       : PascalCase
타입/인터페이스명 : PascalCase
상수명           : UPPER_SNAKE_CASE
파일명           : PascalCase
```

## 프론트엔드 폴더 구조

```
src/
├── app/
├── pages/
├── components/
├── features/
│   ├── agent/
│   ├── relationship/
│   └── event/
├── hooks/
├── api/
├── types/
├── utils/
└── constants/
```

## 백엔드 폴더 구조

```
src/
├── domain/
│   ├── agent/
│   ├── relationship/
│   └── event/
├── controller/
├── service/
├── repository/
├── dto/
├── config/
├── common/
└── exception/
```

## Magic Academy 도메인 기준 폴더

```
agent/
relationship/
organization/
event/
simulation/
user-persona/
```

## 코드 스타일 체크리스트

```markdown
- [ ] 이름만 보고 역할을 이해할 수 있는가?
- [ ] 함수가 너무 많은 일을 하고 있지 않은가?
- [ ] 중복 로직이 없는가?
- [ ] 사용하지 않는 코드가 남아 있지 않은가?
- [ ] 폴더 위치가 적절한가?
- [ ] 팀 컨벤션에 맞는 파일명인가?
```

## 공통 응답 원칙

- 성공 여부, 사용자용 메시지와 실제 payload를 일관된 envelope로 구분한다.
- 실패 응답은 안정적인 오류 식별자와 안전한 설명을 제공한다.
- 리스트 응답은 항목 목록과 전체 개수를 함께 제공한다.
- 오류 상세에는 시크릿, 내부 경로, stack trace나 다른 사용자의 정보를 포함하지 않는다.
- 조회·생성·부분 수정·전체 교체·삭제의 의미에 맞는 표준 HTTP method와 상태 코드를 사용한다.

구체 URL, payload Schema, 오류 코드 목록과 인증 연계 규칙은 비공개 API 명세에서 관리한다.
