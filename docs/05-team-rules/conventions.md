---
title: 코드 스타일·폴더 구조 컨벤션
source: confluence/09_CONVENTIONS/4.코드스타일·폴더구조컨벤션
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/4096026/4.
status: approved
visibility: public
updated: 2026-07-21
source_updated: 2026-07-09
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
