---
description: 기능 설명 또는 FE 화면 Figma URL을 받아 스펙 초안을 생성할 때 사용. Figma URL이 있으면 FE 화면 모드로 자동 전환.
---

# /spec-draft

기능 설명 또는 Figma URL을 받아 스펙 초안을 생성한다.
**Figma URL이 입력되면 모드 B(FE 화면 스펙)로 자동 전환된다.**

---

## 모드 A — 일반 기능 스펙

Figma URL 없이 기능 설명만 주어진 경우.

### 입력

사용자에게 다음을 확인한다 (이미 제공됐으면 생략):
1. 기능 이름 — 예: 학생 Agent 프로필, 관계 시스템, Event Master
2. PRD 기능 번호 — FR-XX (PRD에서 찾거나 모르면 TBD로 표기)
3. 핵심 동작 — 이 기능이 무엇을 하는가

### 사전 확인

- `docs/02-domain/`을 읽어 도메인 모델(Agent, 관계, 조직, 사건)과 어긋나지 않는지 확인한다
- `docs/03-system-design/`에서 관련 아키텍처·데이터 모델을 참조한다
- `docs/00-start-here/what-is-pending.md`에서 미정 항목이 걸리면 `[미정]`으로 표시하고 임의 확정하지 않는다

### 출력

파일 경로: `docs/04-feature-specs/FR-{번호두자리}-{기능명-kebab-case}.md`  
예) `FR-01-student-agent.md`

### 출력 형식

```markdown
---
title: FR-XX {기능명}
status: draft
updated: {오늘 날짜}
---

# FR-XX {기능명}

## 1. 목적

이 기능이 왜 필요한가, 어떤 문제를 해결하는가.

## 2. 범위

**포함**
- ...

**제외**
- ...

## 3. 입력 / 출력

| 항목 | 설명 |
|------|------|
| 입력 | ... |
| 출력 | ... |

## 4. 핵심 동작

1. ...
2. ...

## 5. 경계 조건

- ...

## 6. 데이터 구조

(02-domain/ 기반 — 변경이 필요하면 도메인 파일 수정 후 반영)

## 7. 완료 기준

- [ ] ...

## 8. 미정 항목

- [미정] ...

## 9. 관련 문서

- `docs/02-domain/`
- `docs/03-system-design/`
- PRD FR-XX
```

---

## 모드 B — FE 화면 스펙

Figma URL이 입력된 경우. Confluence Draft → Approved → docs 이관 흐름을 거친다.

### 입력

1. Figma URL
2. 화면 이름 — 예: 유저 페르소나 선택 화면
3. FR 번호 (모르면 TBD)

### 실행 순서

1. Figma MCP (`get_design_context` + `get_screenshot`)로 디자인 컨텍스트 추출
2. `docs/02-domain/`, `docs/03-system-design/` 참조하여 도메인 맥락 확보
3. 아래 형식으로 FE 스펙 초안 작성
4. 작성된 FE 스펙 초안을 사용자에게 보여주고 승인 받기
5. `/confluence-post` 스킬 호출하여 Confluence Draft 생성
6. 팀 검토 → Approved 전환 후 `docs/04-feature-specs/`에 이관

### 출력

Confluence Draft 페이지 (이관 시 파일명: `FR-{번호두자리}-{화면명-kebab}-screen.md`)
예) `FR-03-user-persona-select-screen.md`

### 스펙 초안 형식

```markdown
> **상태**: Draft / **작성자**: {작성자} / **작성일**: YYYY-MM-DD

## 0. 개요 및 목적
## 1. 컴포넌트 트리
## 2. State / Props
| 이름 | 타입 | 출처 | 설명 |
## 3. API 연동
| Method | Endpoint | 호출 시점 | 응답 |
## 4. 빈 상태 / 로딩 / 에러 처리
## 5. 테스트 포인트
- 컴포넌트 단위 테스트 (vitest/jest)
- API mock 또는 통합 테스트
- E2E (핵심 경로)
- 401·403 접근 권한
- 지원 해상도 동작 확인
- 접근성 기준 (키보드 탐색, aria)
- Figma 시각 비교
- 로딩·빈 데이터·서버 오류·재시도 케이스
## 변경 이력
| 버전 | 날짜 | 변경 내용 | 작성자 |
| 1.0.0 | YYYY-MM-DD | 최초 작성 | {작성자} |
```

---

## 주의 (공통)

- 초안이므로 status는 `draft`로 시작한다
- 미정 항목은 `[미정]`으로 표시하고 임의 확정하지 않는다
- PUBLIC 저장소 — 팀원 실명·내부 KPI·시크릿 포함 금지
- 파일 작성 또는 Confluence Draft 생성 전에 초안을 사용자에게 보여주고 승인을 받는다
