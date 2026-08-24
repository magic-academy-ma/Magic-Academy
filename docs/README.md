# docs/

AI 개발용 문서 계층. 원본은 Confluence, 이 폴더는 AI가 읽는 스냅샷.

| 폴더 | 역할 | 주요 파일 |
|------|------|-----------|
| `00-start-here/` | AI 진입점 | `index.md` (읽기 순서), `what-is-decided.md`, `what-is-pending.md` |
| `01-product/` | 무엇을 만드는지 | `mvp-scope.md`, `functional-requirements.md`, `simulation-parameters.md`, `game-mechanics.md` |
| `02-domain/` | 핵심 개념 — **AI가 구현 전 반드시 읽음** | `overview.md` (3축), `agents.md`, `relationships.md`, `organizations.md`, `events.md`, `time-and-space.md` |
| `03-system-design/` | 어떻게 만드는지 | `architecture.md`, `tick-engine.md`, `agent-runtime.md`, `policy-engine.md`, `security-principles.md` |
| `04-feature-specs/` | 기능별 상세 스펙 | `mvp-feature-spec.md`, `inspector.md`, `student-agent-initial-values.md`, `professor-agent-initial-values.md` |
| `05-team-rules/` | AI·팀원 공통 규칙 | `conventions.md`, `git-workflow-commit.md`, `git-workflow-pr.md`, `ai-usage.md`, `definition-of-done.md` |

---

## docs/ 가시성 정책

이 저장소는 public이다. 아래 기준으로 문서를 분류한다.

| 구분 | 위치 | 해당 문서 |
|------|------|-----------|
| **git (공개)** | `repo/docs/` | 도메인 모델, 아키텍처 개요, 팀 규칙, 기능 스펙 |
| **local 전용** | `local/docs/` (gitignore) | API 엔드포인트 명세, 데이터 모델·인증 상세, 인프라 설정 등 내부 구현 세부 사항 |
| **Confluence만** | Confluence 원본 | 위 어느 쪽도 아닌 문서 |

**판단 기준**: "공개됐을 때 경쟁사나 외부에 노출되면 곤란한가?" → `local/` 또는 Confluence 원본만 유지.
