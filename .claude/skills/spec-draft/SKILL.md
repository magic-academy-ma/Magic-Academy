---
description: 기능 설명 또는 FE 화면 디자인(Figma URL / 화면 ID / HTML 목업 경로)을 받아 스펙 초안을 생성할 때 사용. 디자인 입력이 있으면 FE 화면 모드(모드 B)로 자동 전환.
---

# /spec-draft

기능 설명 또는 화면 디자인을 받아 스펙 초안을 생성한다.
**다음 중 하나가 입력되면 모드 B(FE 화면 스펙)로 자동 전환된다:**
- Figma URL (`https://www.figma.com/...`)
- 화면 ID (`S0`–`S9` 등 `docs/04-feature-specs/mvp-feature-spec.md` 기준)
- HTML 목업 경로 (`mockup/screens/*.html`)

---

## 모드 A — 일반 기능 스펙

Figma URL, 화면 ID, HTML 목업 경로 없이 기능 설명만 주어진 경우.

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

Figma URL, 화면 ID, HTML 목업 경로 중 하나가 입력된 경우. `docs/04-feature-specs/`에 스펙을 생성하고 Mock Data를 내장하여 즉시 화면 구현을 지원한다.

### 입력

1. 디자인 입력 — Figma URL, 화면 ID, HTML 목업 경로 중 하나
2. 화면 이름 — 화면 ID나 목업에서 확인할 수 없으면 사용자에게 질문
3. FR 번호 — `docs/04-feature-specs/mvp-feature-spec.md`에서 확인하고, 없으면 TBD

### 실행 순서

1. 입력 유형에 따라 디자인 컨텍스트 추출
   - Figma URL: Figma MCP (`get_design_context` + `get_screenshot`) 사용
   - 화면 ID: `docs/04-feature-specs/mvp-feature-spec.md`에서 화면명·관련 FR·기능·API를 찾고 대응하는 `../mockup/screens/*.html`을 읽는다
   - HTML 목업 경로: 저장소 루트 기준 경로를 확인하고 해당 HTML을 읽는다
   - 화면 ID에 대응하는 목업이 없거나 여러 개라 확정할 수 없으면 임의 선택하지 않고 사용자에게 확인한다
2. `docs/02-domain/`, `docs/03-system-design/`과 기존 API 명세를 참조하여 도메인·연동 맥락 확보
3. 아래 형식으로 FE 스펙 초안 작성
4. 작성할 전체 초안을 사용자에게 보여주고 승인 받기
5. 승인 후 `docs/04-feature-specs/FR-{번호두자리}-{화면명-kebab}-screen.md`에 저장

### 출력

파일 경로: `docs/04-feature-specs/FR-{번호두자리}-{화면명-kebab}-screen.md`
예) `FR-03-user-persona-select-screen.md`

### 스펙 초안 형식

```markdown
---
title: "[화면명] FE 스펙"
status: draft
visibility: public
updated: YYYY-MM-DD
---

# FR-XX [화면명] FE 스펙

> **상태**: Draft / **작성자**: @작성자 / **작성일**: YYYY-MM-DD

## 0. 개요 및 목적
## 1. 컴포넌트 트리
## 2. State / Props
| 이름 | 타입 | 출처 | 설명 |
## 3. API 연동
| Method | Endpoint | 호출 시점 | 응답 |
## 4. 빈 상태 / 로딩 / 에러 처리
## 5. Mock Data Fixture (백엔드 미완성 시 프론트 독립 실행용)
- API 응답 스키마와 `docs/02-domain/` 규칙에 맞는 샘플 JSON
- `VITE_USE_MOCK=true`에서 사용할 fixture 경로 또는 Props 주입 지점
- API 명세에서 확정되지 않은 값은 `[미정]`으로 표시
## 6. 테스트 포인트
- 컴포넌트 단위 테스트 (vitest/jest)
- Mock Data 기반 독립 렌더링 확인
- E2E (핵심 경로)
- 401·403 접근 권한
- 지원 해상도 동작 확인
- 접근성 기준 (키보드 탐색, aria)
- 입력 디자인과 시각 비교
- 로딩·빈 데이터·서버 오류·재시도 케이스
## 변경 이력
| 버전 | 날짜 | 변경 내용 | 작성자 |
| 1.0.0 | YYYY-MM-DD | 최초 작성 | @작성자 |
```

---

## 주의 (공통)

- 초안이므로 status는 `draft`로 시작한다
- 미정 항목은 `[미정]`으로 표시하고 임의 확정하지 않는다
- PUBLIC 저장소 — 팀원 실명·내부 KPI·시크릿 포함 금지
- 파일 작성 전에 초안 전체를 사용자에게 보여주고 승인을 받는다
- 개발 중에는 Git `docs/`를 기준으로 작업하며 Confluence 이관은 마일스톤 완료 후 별도 흐름으로 수행한다
