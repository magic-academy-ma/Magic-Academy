# Magic Academy Claude Teams 설계

**작성일:** 2026-07-24  
**작성자:** 정은혜 (PM)  
**상태:** approved

---

## 개요

Magic Academy 팀의 개발 효율화를 위한 Claude 에이전트 팀 설계.

**목표**
- 팀 전체의 AI 활용 수준 향상 — 팀원이 Claude를 "잘 몰라도" 명령어만 알면 쓸 수 있도록
- 반복 워크플로우 자동화 — 문서·이슈·리뷰 작업을 명령어 하나로 실행

**접근**: 역할 페르소나(AGENTS.md) + 워크플로우 Skills + 선택적 서브에이전트

---

## 전체 구조

```
Magic Academy Claude Teams
├── AGENTS.md (공통 진입점)
│   ├── 역할별 컨텍스트 로딩 범위
│   └── 행동 원칙 + 페르소나 선언
│
├── .claude/skills/ (워크플로우 자동화)
│   ├── /issue-writer     — GitHub Issue 초안 생성
│   ├── /spec-draft       — 기능 스펙 초안 작성
│   ├── /pr-review        — PR 리뷰 (태그 기반)
│   ├── /confluence-post  — Confluence 문서 생성 + Discord 공지 문구
│   ├── /agent-spec       — Agent 페르소나·행동 규칙 초안 생성
│   ├── /briefing         — 세션 상태 브리핑
│   └── /context-scope    — 문서 로딩 범위 안내
│
└── Subagent (선택적, 무거운 작업만)
    └── superpowers:dispatching-parallel-agents 활용
```

---

## 역할별 페르소나

| 페르소나 | 담당자 | 주요 담당 | 자동 로딩 문서 |
|---------|--------|----------|--------------|
| `@system` | 은혜 | Event Master Agent, Tick Engine, 시스템 오케스트레이션 | `02-domain/`, `03-system-design/`, `04-feature-specs/event-master/`, `04-feature-specs/tick-engine/` |
| `@pm` | 은혜 (+ 공통) | Issue 작성, 스펙 초안, 요구사항 명확화, 범위 관리 | `01-product/`, `04-feature-specs/`, `02-domain/` |
| `@ai-native` | 은혜 | AGENTS.md·Skills 설계, AI context 문서 관리, Claude Code 설정 | `00-start-here/`, `05-team-rules/`, `docs/superpowers/` |
| `@agent-dev` | 가윤 + 지유 (공통) | Agent 캐릭터·페르소나 정의, Agent 행동 설계, LangGraph 노드, Agent Runtime | `02-domain/`, `03-system-design/`, `04-feature-specs/agent-runtime/`, `04-feature-specs/agent-design/` |
| `@magic-layer` | 혜정 | Magic Layer Agent, Frontend (React Flow) | `02-domain/`, `03-system-design/`, `04-feature-specs/magic-layer/` |
| `@infra` | 지유 | PostgreSQL+pgvector, Docker, CI/CD | `03-system-design/data-model/`, `05-team-rules/` |
| `@backend` | 공통 (4명) | FastAPI 라우터, API 설계, 공통 BE 패턴 | `03-system-design/api/`, `05-team-rules/` |
| `@fe` | 공통 (4명) | React + React Flow, 화면 컴포넌트, Agent 상태 표시 | `03-system-design/`, `04-feature-specs/` (FE 관련) |

**은혜 페르소나 선택 기준**
- 시스템 구현 작업 → `@system`
- Issue·스펙·요구사항 → `@pm`
- AI 환경 설계·관리 → `@ai-native`

**지유 페르소나 선택 기준**
- DB·Docker·인프라 작업 → `@infra`
- Professor Agent 설계 → `@agent-dev`

**역할 침범 방지**: 본인 영역 밖을 수정해야 할 경우 해당 페르소나 담당자에게 먼저 확인.

---

## Skills

| Skill | 명령어 | 동작 | 주 사용자 |
|-------|--------|------|---------|
| Issue Writer | `/issue-writer` | 작업 내용 받아 GitHub Issue 제목·배경·수용 기준·범위 밖 항목 초안 생성 | `@pm`, 전체 |
| Spec Draft | `/spec-draft` | 기능 설명 받아 `04-feature-specs/` 형식에 맞는 스펙 초안 작성 | `@pm`, `@system` |
| PR Review | `/pr-review` | diff 분석 후 `[Must]`/`[Suggest]`/`[Nit]`/`[Good]` 태그 기반 리뷰 코멘트 생성 | 전체 |
| Confluence Post | `/confluence-post` | 문서 초안 받아 Confluence 페이지 생성 + Discord 공지 문구 출력 | `@pm`, `@ai-native` |
| Agent Spec | `/agent-spec` | Agent 이름·역할 받아 페르소나·행동 규칙·LangGraph 노드 인터페이스 초안 생성 | `@agent-dev`, `@system` |
| Briefing | `/briefing` | Done / In progress / Next 형식으로 세션 상태 정리 | 전체 |
| Context Scope | `/context-scope` | 현재 작업 유형에 맞는 문서 로딩 범위 안내 | 전체 |

**구현 우선순위**: `/issue-writer` → `/pr-review` → `/agent-spec` → AGENTS.md 페르소나 → 나머지 Skills

---

## 서브에이전트 활용 기준

**쓰는 경우 (무겁고 독립적인 작업)**

| 상황 | 예시 |
|------|------|
| 스펙 작성 + 이슈 분해 동시 실행 | Event Master Agent 스펙 작성하면서 GitHub Issue 5개 병렬 생성 |
| 여러 에이전트 설계 일관성 크로스체크 | Student / Professor / Event Master 행동 규칙 동시 검토 |
| 코드 리뷰 + 스펙 검증 동시 진행 | PR diff 리뷰하면서 해당 feature spec과 충돌 여부 확인 |

**쓰지 않는 경우**
- 파일 하나 수정, 단순 질문, Skills로 해결되는 작업
- 이전 결과가 다음 입력이 되는 순차 작업

**실행 방식**: `superpowers:dispatching-parallel-agents` skill. `@ai-native` 페르소나에서 판단.
