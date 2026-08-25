---
title: "[FE] AI-Native 개발 워크플로우 설계"
source: confluence/AI협업/FE_AI_Native_개발_워크플로우
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/30277660
status: approved
visibility: public
updated: 2026-08-25
source_updated: 2026-08-17
---

# [FE] AI-Native 개발 워크플로우 설계

## 0. 개요 및 목적

- **목적**: AI가 스펙 기반 구현 초안을 작성하고 담당자가 검토하는 구조로, 화면 단위 FE 개발의 일관성과 속도를 확보한다.
- **범위**: Figma 시안이 있는 화면의 FE 스펙 작성 → React 구현 → PR 머지. 디자인 생성과 백엔드 구현은 포함하지 않는다.

## 1. 전체 워크플로우

```
[혜정] Figma URL 공유
    │
    ▼ /spec-draft 스킬 (Figma URL 입력 → FE 화면 모드 자동 전환)
      Figma MCP + 도메인 문서 참조
[스펙 초안 자동 생성]
    │
    ▼ confluence-post 스킬
[Confluence Draft 생성]
    │
    ▼ [팀 전원] 검토·보완 → Publish
[Confluence 확정 스펙]  ← 상태가 Approved일 때만 다음 단계 진행
    │
    ▼ [은혜] repo/docs/04-feature-specs/ 이관
[AI 구현 → PR Draft 생성]
    │
    ▼ [팀 전원] 코드 리뷰
[은혜] PR 머지
```

### 핵심 원칙

1. **스펙이 source of truth** — Figma가 바뀌면 스펙부터 업데이트, 코드는 그 다음
2. **도메인 맥락은 검토 단계에서 강제 주입** — Agent·Tick 개념은 Figma에 없으니 팀원이 스펙에 직접 명시
3. **화면 단위 격리** — 화면 하나 = 스펙 하나 = PR 하나, 병렬 작업 가능
4. **AI가 스펙 기반 구현 초안을 작성하고, 담당 개발자가 실행·테스트·코드 리뷰 및 최종 품질을 책임진다**

## 2. 업무 분배

| 단계 | 담당 | 역할 |
| --- | --- | --- |
| Figma URL 제공 | 혜정 | 구현할 화면의 Figma 링크 공유 |
| 스펙 초안 생성 | AI | /spec-draft 스킬 (Figma URL 입력 → FE 화면 모드)로 자동 생성 |
| Confluence Draft 생성 | AI | confluence-post 스킬 호출 |
| 스펙 검토·보완 | 팀 전원 | 도메인 맥락 체크리스트 기준으로 검토 |
| repo/docs/ 이관 | 은혜 | 확정 스펙 이관 처리 (Approved 상태 확인 후) |
| React 구현 초안 | AI | 스펙 기반 컴포넌트 전체 작성 |
| PR Draft 생성 | AI | PR 템플릿 기반 초안 작성 |
| 코드 리뷰·실행 책임 | 혜정 + 팀원 | 구현 초안 실행·검증·코드 리뷰·머지 승인 |
| PR 머지 | 은혜 | approve 확인 후 머지 |

### 스펙 검토 책임 분담

| 검토 영역 | 담당 |
| --- | --- |
| 화면·컴포넌트 구조 | FE 담당자 (혜정) |
| API 계약 | 해당 API 담당자 |
| 도메인 규칙 | 기능 담당자 |
| Approved 전환 권한 | 문서 담당자 (은혜) |

## 3. Claude 설정

### 3-1. AGENTS.md @fe 페르소나 보강

_적용 예정 — 팀 승인 후 AGENTS.md에 반영. 아래는 반영될 내용 초안이다._

```
### @fe — 공통 (4명)

**주요 담당**: React + React Flow, 화면 컴포넌트, Agent 상태 표시

**워크플로우**
1. Figma URL 받기 → /spec-draft 스킬 (Figma URL 입력)로 스펙 초안 + Confluence Draft 생성
2. 팀 검토 후 스펙 Approved → repo/docs/04-feature-specs/ 이관 확인
3. 확정 스펙 기반으로 React 컴포넌트 구현 초안 작성 (AI가 전체 작성, 혜정이 실행·검증 책임)
4. PR Draft 생성 → 팀 코드 리뷰 → 머지

**구현 원칙**
- 화면 하나 = 스펙 하나 = PR 하나
- 기존 frontend/src/ 패턴 따르기 (App.jsx 구조 참조)
- 컴포넌트는 화면 단위로 분리, props로 통신

**자동 로딩 문서**
- docs/03-system-design/
- docs/04-feature-specs/ (FE 관련)
- frontend/src/App.jsx (기존 패턴 참조)
```

### 3-2. /spec-draft — FE 화면 모드

Figma URL을 입력하면 자동으로 FE 화면 스펙 모드로 전환된다. 상세 실행 절차는 `repo/.claude/skills/spec-draft/SKILL.md` 모드 B를 참조한다.

- **입력**: Figma URL + 화면 이름 (+ FR 번호, 모르면 TBD)
- **출력**: Confluence Draft → 팀 검토 → Approved → `docs/04-feature-specs/FR-{번호두자리}-{화면명-kebab}-screen.md` 이관

### 3-3. FE 스펙 도메인 맥락 검토 체크리스트

팀 검토 시 아래 항목을 모두 확인한 후 Approved로 전환한다.

- [ ] Tick 기반 상태 변화가 반영됐는가 — 화면이 보여주는 상태가 어느 Tick 시점 기준인지 명시
- [ ] Agent 상태 수치 범위가 맞는가 — docs/02-domain/ 기준 확인 (hunger, fatigue, stress 등)
- [ ] 시뮬레이션 생성·Draft 화면이면 Magic Layer 파라미터(magic_frequency, magic_impact, Magic ON/OFF 토글)가 스펙에 포함됐는가
- [ ] API 엔드포인트가 실제 구현된 것과 일치하는가
- [ ] 관계 그래프 관련 화면이면 React Flow 노드/엣지 구조가 명시됐는가
- [ ] 빈 상태 (Agent 0명, 시뮬레이션 없음 등) 처리가 정의됐는가
- [ ] 401/403 응답 시 동작이 정의됐는가

## 4. FE 스펙 문서 형식

### 4-1. Confluence FE 스펙 페이지 템플릿

/spec-draft 스킬 (FE 화면 모드)이 생성하는 Confluence 페이지 형식. 상세 템플릿은 `repo/.claude/skills/spec-draft/SKILL.md` 모드 B 참조.

```
> **상태**: Draft / **작성자**: @Jehye / **작성일**: YYYY-MM-DD

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
| 1.0.0 | YYYY-MM-DD | 최초 작성 | @Jehye |
```

### 4-2. repo/docs/ 이관 시 frontmatter

Confluence 상태가 Approved로 전환된 후 `repo/docs/04-feature-specs/`에 이관.

**파일명 규칙**: `FR-{번호두자리}-{화면명-kebab}-screen.md`

예: `FR-03-user-persona-select-screen.md`, `FR-07-simulation-dashboard-screen.md`

```yaml
---
title: "[화면명] FE 스펙"
source: confluence/[Confluence 경로]
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/[pageId]/[제목]
status: approved
visibility: public
updated: YYYY-MM-DD
source_updated: YYYY-MM-DD
---
```

## 5. 예상 소요 시간

| 구분 | 시간 |
| --- | --- |
| 워크플로우 세팅 (AGENTS.md + /spec-draft FE 모드) | 1~1.5시간 |
| 화면 하나 end-to-end (검토 대기 포함) | 1~2일 |
| AI 실작업 시간 (화면 1개) | 40~70분 |
| FE MVP 전체 (약 9개 화면) | AI 10~15시간 / 팀 2~3주 |

## 변경 이력

| 버전 | 날짜 | 변경 이력 | 수정자 |
| --- | --- | --- | --- |
| 2.2.0 | 2026-08-17 | §3-2 SKILL.md 참조 링크로 교체. §3-1 적용 예정 상태 명시. §4-1에 SKILL.md 참조 추가. | @Jehye |
| 2.1.0 | 2026-08-17 | /fe-spec 스킬 제거, /spec-draft FE 화면 모드로 통합 | @Jehye |
| 2.0.0 | 2026-08-17 | 리뷰 반영: "AI가 코드 전담" 표현 수정, 스펙 검토 책임 분담 표 신설, 파일명 규칙 추가, 테스트 포인트 항목 확장 | @Jehye |
| 1.2.0 | 2026-08-12 | 최초 작성 | @Jehye |
