# AGENTS.md

Magic Academy — 마법 대학교를 배경으로 한 멀티 에이전트 LLM 시뮬레이션.  
agent들이 관계·조직·사건 속에서 상호작용하며 상태가 변화한다.

**현재 상태**: 구현 단계 — Week 4 (2026-07-28 기준)

---

## 기술 스택

| 계층 | 기술 |
|------|------|
| 백엔드 | FastAPI |
| 에이전트 오케스트레이션 | LangGraph |
| DB | PostgreSQL + pgvector |
| 프론트엔드 | React |
| 인프라 | Docker Compose |

- **Agent 수**: 생활 Agent 6명 — Student 5명(User Persona 1명 포함) + Professor 1명 (1단계 MVP) / 2단계 13명, 3단계 25명으로 확장 / Event Master 1 + Magic Layer 1 (시스템 컴포넌트, 생활 Agent 수에서 제외)
- **실행 명령어**: 아직 코드 없음 — `docs/05-team-rules/`에서 환경 설정 가이드 확인

---

## 시작

새 세션은 항상 여기서 시작한다.

```
docs/00-start-here/index.md
```

전체 읽기 순서, 확정/미정 항목, source of truth 규칙이 거기 있다.  
작업 유형별 컨텍스트 로딩 범위(Always Load / Task-Specific / Skip)는 `docs/00-start-here/context-scope.md`에 정의돼 있다.

---

## 문서 구조

```
docs/
├── 00-start-here/   # 진입점 (여기부터)
├── 01-product/      # 제품 정의 · MVP · 유저 시나리오 (미이관 — Confluence 원본 참조)
├── 02-domain/       # 핵심 도메인 모델 ← 구현 전 반드시 읽기
├── 03-system-design/# 아키텍처 · 데이터 모델 · API
├── 04-feature-specs/# 기능별 상세 스펙 (구현 직전 작성)
└── 05-team-rules/   # 코드 컨벤션 · Git · AI 협업 규칙
```

원본은 Confluence. `docs/`는 AI 개발용 스냅샷이며, 각 파일 frontmatter의 `source`가 원본 경로다.

---

## 핵심 도메인 프레임

이 시뮬레이션은 3축으로 구동된다.

- **관계** — Agent 간 연결 (호감도·친밀도·신뢰도·긴장도·경쟁·의존도)
- **조직** — 관계가 생기는 맥락 (기숙사·동아리·전공·총학생회)
- **사건** — 관계와 조직을 변화시키는 트리거 (수업·시험·MT·축제…)

배경(시간·공간·날씨·학기)은 3축에 영향을 주지만 스스로 방향을 만들지 않는다.  
시간은 **Time Tick** 기반이다 — **1 Tick = 8분 = 1블록**, 1일 = 3블록 = 24분, 밤 시간은 스킵 가능.

새 엔티티나 관계/사건 타입은 이 3축 프레임에 맞춰 정의한다.

---

## 작업 범위 원칙

너는 **명시적으로 요청된 작업만** 수행한다. 요청되지 않은 작업은 "개선"이라도 하지 않는다.
아래 규칙은 코드, 문서, 슬라이드, 스프레드시트, 데이터 등 모든 산출물에 동일하게 적용된다.

**절대 금지**
- 요청 범위 밖의 내용 수정·추가·삭제
- 요청하지 않은 구조 변경, 표현 손질, 요소 추가, 파일·섹션 신규 생성
- 원문 삭제 — 필요하다고 판단되면 반드시 먼저 묻는다
- "겸사겸사" 발견한 오류를 임의 수정 → 보고만 한다

**판단이 필요할 때**
요청이 모호하거나 두 가지 이상 해석이 가능하면 추측해서 진행하지 말고 질문한다.
- 나쁜 예: "아마 A를 의미하는 것 같아 A로 작성했습니다"
- 좋은 예: "A와 B 두 해석이 가능합니다. 어느 쪽인가요?"

**범위 밖 발견 사항 처리**

> [범위 외 발견] 위치 — 문제 요약 — 제안. 수정할까요?

**완료 보고 형식**
- **요청받은 것**: (한 줄)
- **변경한 것**: (위치 + 변경 이유 한 줄씩)
- **범위 외 발견**: (있으면 나열, 없으면 "없음")
- **확인 필요**: (있으면 질문, 없으면 "없음")

**자기 검증**
응답 전에 확인한다: "이 변경 중 사용자가 요청하지 않은 것이 하나라도 있는가?"
→ 있다면 되돌리고 보고 항목으로 옮긴다.

---

## 작업 원칙

1. **미정 항목은 임의로 확정하지 않는다.** `docs/00-start-here/what-is-pending.md`를 먼저 확인하고, 미정 항목이 걸리면 사용자에게 확인한다.
2. **구현 전 `02-domain/`을 읽는다.** 도메인 모델과 어긋나는 구현은 하지 않는다.
3. **기능 구현 전 `04-feature-specs/`에 스펙이 있는지 확인한다.** 없으면 먼저 작성한다.
4. **컨벤션은 `05-team-rules/`를 따른다.** 코드 스타일, 브랜치, 커밋, PR 규칙이 거기 있다.
5. **이 저장소는 Public이다.** 팀원 정보·시크릿·내부 KPI를 코드나 커밋에 포함하지 않는다.

---

## 코딩 원칙

### Think Before Coding
구현 전에 가정과 성공 기준을 명시한다.
- 해석이 여러 개면 차이를 설명하고, 결과가 크게 달라질 때는 확인한다
- 더 단순한 접근이 있으면 함께 제시한다
- 불명확한 요구사항을 숨긴 채 구현하지 않는다

여러 단계의 작업은 다음 형식으로 짧게 계획한다:
```
1. [작업] → verify: [검증 방법]
2. [작업] → verify: [검증 방법]
```

### Simplicity First
요청을 해결하는 최소한의 코드만 작성한다.
- 요청하지 않은 유연성, 추상화, 설정 가능성을 추가하지 않는다
- 불가능한 상황을 위한 방어 코드를 추가하지 않는다

### Surgical Changes
요청된 것만 수정하고, 인접 코드는 건드리지 않는다.
- 기존 코드베이스의 스타일과 패턴을 따른다
- 변경으로 새로 발생한 미사용 import·변수·함수만 정리한다
- 기존 관련 없는 dead code는 삭제하지 말고 알린다

### 의존성 방향
의존성은 안정된 방향으로 흐른다.
- domain → application → infrastructure 순으로 의존
- 고수준 모듈이 저수준 모듈의 세부 구현에 의존하지 않는다
- 순환 의존(circular dependency) 금지

### 테스트 우선 (TDD)
핵심 로직과 버그 수정은 테스트를 먼저 작성한다.
- 기능 구현: 실패 테스트 먼저 → 통과하도록 구현
- 버그 수정: 동일 실패를 재현하는 회귀 테스트 → 수정

---

## 디버깅

예상하지 못한 오류가 발생하면 다음 순서를 따른다.

1. **STOP**     — 기능 추가와 추가 변경을 중단한다
2. **PRESERVE** — 오류 출력, 로그, 재현 절차를 보존한다
3. **DIAGNOSE** — 증상이 아니라 근본 원인을 찾는다
4. **FIX**      — 근본 원인을 수정한다
5. **GUARD**    — 동일한 실패를 잡는 회귀 테스트를 작성한다
6. **RESUME**   — end-to-end로 검증한 뒤 작업을 재개한다

---

## 승인 필요 작업

다음 작업은 사용자의 명시적 확인 없이 수행하지 않는다.

### 판단 3원칙

목록에 없는 상황에서도 아래 중 하나라도 해당하면 승인 요청한다.

1. **되돌릴 수 없는가** — 파일 삭제, DB drop, force push 등
2. **요청 범위를 벗어났는가** — A 수정 요청인데 B도 건드려야 할 때
3. **외부에 영향을 주는가** — push, PR 생성, 외부 API 쓰기 호출 등

### 작업 흐름상 승인 게이트

| 시점 | 멈추는 조건 |
|------|------------|
| 시작 전 | 작업 범위가 두 가지 이상으로 해석될 때 |
| 도중 | 예상치 못한 상황이 생겨 범위를 넘어야 할 때 |
| 완료 전 | 돌이키기 어려운 변경이 포함될 때 (커밋, push, 파일 삭제 등) |

### 승인 후 처리 원칙

- 승인받은 범위만 수행한다. 연관 작업이 생겨도 별도 승인을 받는다.
- 승인 도중 새로운 승인 필요 상황이 생기면 작업을 멈추고 다시 요청한다.
- 거절 시: 대안을 제안하거나 작업을 중단한다. 우회하지 않는다.

---

**Git**
- 기능 또는 프로젝트 코드를 `main`에 직접 push
- `--force` push
- 브랜치 삭제
- 이미 원격에 push된 커밋 amend

**파괴적 작업**
- `rm -rf` 또는 파일·디렉터리 일괄 삭제
- DB drop, truncate, 마이그레이션 롤백
- 의도하지 않은 기존 파일 덮어쓰기

**외부 영향**
- GitHub PR 또는 Issue 생성·닫기·댓글
- Slack, 이메일 등 메시지 전송
- npm, PyPI 등 패키지 배포
- 외부 서비스 API 쓰기 호출

**코드와 문서**
- 요청하지 않은 리팩터링 또는 범위 밖 기능 추가
- `.env`, 시크릿, 자격증명 파일 커밋
- `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` 등 설정 파일 무단 수정

승인 요청 형식:
> **[승인 필요]** `[명령어 또는 작업]`을 실행하려 합니다.  
> 영향 범위: [대상]  
> 되돌릴 수 있는지: [가능 / 불가능]  
> 진행할까요?

---

## 역할별 페르소나

> **세션 시작 전**: 아래 본인 페르소나를 확인하고, 지정된 자동 로딩 문서를 읽는다.  
> 은혜 선택 기준: 시스템 구현 → `@system` / Issue·스펙 → `@pm` / AI 환경 관리 → `@ai-native`  
> 가윤 선택 기준: Agent 캐릭터·행동 설계 → `@agent-dev`  
> 지유 선택 기준: DB·Docker·인프라 → `@infra` / Professor Agent 설계 → `@agent-dev`  
> 혜정 선택 기준: Magic Layer·Frontend → `@magic-layer`  
> 역할 침범 방지: 본인 영역 밖을 수정해야 할 경우 해당 페르소나 담당자에게 먼저 확인

### @system — 은혜

**주요 담당**: Event Master Agent, Tick Engine, 시스템 오케스트레이션

**자동 로딩 문서**
- `docs/02-domain/`
- `docs/03-system-design/architecture.md`
- `docs/03-system-design/tick-engine.md`
- `docs/04-feature-specs/event-master/` (미구현, 추후 추가)
- `docs/04-feature-specs/tick-engine/` (미구현, 추후 추가)

---

### @pm — 은혜 (+ 공통)

**주요 담당**: Issue 작성, 스펙 초안, 요구사항 명확화, 범위 관리

**자동 로딩 문서**
- `docs/01-product/`
- `docs/04-feature-specs/`
- `docs/02-domain/`
- `docs/05-team-rules/git-workflow-pr.md`

---

### @ai-native — 은혜

**주요 담당**: AGENTS.md·Skills 설계, AI context 문서 관리, Claude Code 설정

**자동 로딩 문서**
- `docs/00-start-here/`
- `docs/05-team-rules/`

---

### @agent-dev — 가윤·지유 (공통)

**주요 담당**: Agent 캐릭터·페르소나 정의, Agent 행동 설계, LangGraph 노드, Agent Runtime

**자동 로딩 문서**
- `docs/02-domain/`
- `docs/03-system-design/architecture.md`
- `docs/03-system-design/agent-runtime.md`
- `docs/04-feature-specs/agent-runtime/` (미구현, 추후 추가)
- `docs/04-feature-specs/agent-design/` (미구현, 추후 추가)

---

### @magic-layer — 혜정

**주요 담당**: Magic Layer Agent, Frontend (React Flow)

**자동 로딩 문서**
- `docs/02-domain/`
- `docs/03-system-design/architecture.md`
- `docs/03-system-design/magic-layer.md`
- `docs/03-system-design/user-flow.md`
- `docs/04-feature-specs/magic-layer/` (미구현, 추후 추가)

---

### @infra — 지유

**주요 담당**: PostgreSQL+pgvector, Docker, CI/CD

**자동 로딩 문서**
- `docs/03-system-design/architecture.md`
- `docs/03-system-design/infra.md`
- `docs/03-system-design/tech-stack.md`
- `docs/05-team-rules/`

---

### @backend — 공통 (4명)

**주요 담당**: FastAPI 라우터, API 설계, 공통 BE 패턴

**자동 로딩 문서**
- `docs/03-system-design/architecture.md`
- `docs/05-team-rules/`

---

### @fe — 공통 (4명)

**주요 담당**: React + React Flow, 화면 컴포넌트, Agent 상태 표시

**자동 로딩 문서**
- `docs/03-system-design/architecture.md`
- `docs/03-system-design/user-flow.md`
- `docs/04-feature-specs/` (FE 관련)
