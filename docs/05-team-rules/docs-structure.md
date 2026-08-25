---
title: "[AI 협업] docs/ 문서 구조 가이드"
source: confluence/AI협업/docs_문서_구조_가이드
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/30048346
status: approved
visibility: public
updated: 2026-08-25
source_updated: 2026-08-17
---

# [AI 협업] docs/ 문서 구조 가이드

## 0. 개요 및 목적

- **목적**: Magic Academy GitHub `docs/` 폴더의 구조와 각 문서의 내용 범위를 정의한다.
- **범위**: 폴더 구조, 파일별 내용 범위 원칙, Always Load 지정 기준.

`docs/`는 Confluence 원본의 AI 개발용 스냅샷이다. 각 파일 frontmatter의 `source` / `canonical`이 원본 경로다.

**문서 유형별 원본 기준**

| 유형 | 원본 |
| --- | --- |
| 제품 정의·정책·팀 결정 | Confluence |
| AI 개발용 스냅샷 | `docs/` (본 가이드 대상) |
| DB 마이그레이션·OpenAPI·코드·테스트 | 저장소 산출물 |

불일치 발견 시 임의 선택하지 않고 원본 담당자에게 동기화 요청한다.

## 1. 폴더 구조

```
docs/
├── 00-start-here/    # AI 진입점 — 세션 시작 시 반드시 읽기
├── 01-product/       # 제품 정의 (미이관 — Confluence 원본 참조)
├── 02-domain/        # 핵심 도메인 모델 ← 구현 전 반드시 읽기
├── 03-system-design/ # 아키텍처 · 컴포넌트 설계
├── 04-feature-specs/ # 기능별 상세 스펙 (구현 직전 작성)
├── 05-team-rules/    # 코드 컨벤션 · Git · AI 협업 규칙
├── _meta/            # AI 환경 설계 내부 문서 (팀 비공개)
├── decisions/        # ADR (Architecture Decision Records)
├── superpowers/      # Claude 계획·스펙 초안 (팀 비공개)
└── README.md         # 폴더 구조 안내
```

## 2. 00-start-here/

새 세션은 이 폴더부터 시작한다. Always Load 문서는 작업 유형에 관계없이 항상 읽는다.

| 파일 | 내용 범위 | 상태 | Always Load |
| --- | --- | --- | --- |
| `index.md` | 프로젝트 한 줄 정의, 읽기 순서, source of truth 규칙 | 이관 완료 | ✅ |
| `what-is-decided.md` | 기술 스택·아키텍처·Agent 수·Tick 단위 등 팀 확정 사항 | 이관 완료 | ✅ |
| `what-is-pending.md` | 임의 확정 금지 미정 항목 목록 | 이관 완료 | ✅ |
| `context-scope.md` | 작업 유형별 파일 로드 범위 정의 (토큰 예산 포함) | 이관 완료 | — |
| `context-quality.md` | 작업 시작 전 AI 자가 점검 체크리스트 | 이관 완료 | — |

**AGENTS.md와의 역할 구분**: AGENTS.md는 페르소나·팀 규칙·도메인 개요를 담고, `00-start-here/`는 현재 확정/미정 항목 상태와 컨텍스트 범위를 보완한다. 두 곳 모두 세션 시작 시 읽되, 중복 내용은 AGENTS.md 기준을 따른다. Always Load 파일은 요약 없이 전문을 읽는다.

## 3. 01-product/

원본: Confluence. 미이관 항목은 Confluence에서 직접 확인한다.

| 파일 | 내용 범위 | 상태 |
| --- | --- | --- |
| `functional-requirements.md` | PRD 핵심 기능 정의 (FR 목록) | 이관 완료 |
| `mvp-scope.md` | MVP 범위 및 기능 우선순위 | 이관 완료 |

## 4. 02-domain/

구현 전 반드시 읽는다. 도메인 모델과 어긋나는 구현은 하지 않는다.

| 파일 | 내용 범위 | 상태 |
| --- | --- | --- |
| `overview.md` | 시뮬레이션 3축(관계·조직·사건) 개요 | 이관 완료 |
| `agents.md` | Agent 종류·역할·속성 정의 | 이관 완료 |
| `relationships.md` | Agent 간 관계 타입·속성 정의 | 이관 완료 |
| `events.md` | 사건 타입·트리거·효과 정의 | 이관 완료 |
| `organizations.md` | 조직 구조·소속 관계 정의 | 이관 완료 |
| `time-and-space.md` | Time Tick 구조, 공간·배경 정의 | 이관 완료 |
| `glossary.md` | 프로젝트 전체 용어 통일 정의 | 이관 완료 |

## 5. 03-system-design/

컴포넌트 단위 설계 문서. Slice 구현 시 해당 컴포넌트 파일을 선택적으로 로드한다.

| 파일 | 내용 범위 | 상태 |
| --- | --- | --- |
| `architecture.md` | 전체 시스템 레이어 구조, 컴포넌트 간 의존 관계 | 이관 완료 |
| `agent-runtime.md` | Agent 실행 루프, LangGraph 노드 구조, 프롬프트 분리 설계 | 이관 완료 |
| `tick-engine.md` | Tick 기반 시간 진행 로직, 블록 구조, 스킵 조건 | 이관 완료 |
| `magic-layer.md` | Magic Layer Agent 설계, 감정·사건 조작 인터페이스 | 이관 완료 |
| `security-principles.md` | LLM 입출력 보안, 공급망, Secure SDLC 원칙 (구현 상세 비공개) | 이관 완료 |
| `infra.md` | Docker Compose 구성, 배포 환경, 운영 전략 | 이관 완료 |
| `policy-engine.md` | 행동 정책 규칙 엔진 설계 | 이관 완료 |
| `tech-stack.md` | 기술 스택 확정 근거 (선행조사 통합 결론) | 이관 완료 |
| `user-flow.md` | 프론트엔드 화면 흐름, React Flow 구조 | 이관 완료 |

## 6. 04-feature-specs/

기능 구현 직전에 작성한다. 스펙 없이 구현 시작 금지.

**파일명 형식**

- 일반 기능 스펙: `FR-{번호두자리}-{기능명-kebab}.md`
- FE 화면 스펙: `FR-{번호두자리}-{화면명-kebab}-screen.md` (화면 하나 = 스펙 하나 = PR 하나)

| 파일 | 내용 범위 | 상태 |
| --- | --- | --- |
| `FR-13-initial-setup.md` | 초기 환경 설정 스펙 | 이관 완료 |
| `mvp-feature-spec.md` | MVP 기능 전체 스펙 (구현 계약 수준) | 이관 완료 |
| `FR-{번호}-{화면명}-screen.md` | FE 화면 단위 스펙 (Approved 후 이관) | 미작성 |

## 7. 05-team-rules/

| 파일 | 내용 범위 | 상태 |
| --- | --- | --- |
| `conventions.md` | 코드 스타일, 폴더 구조 컨벤션 | 이관 완료 |
| `definition-of-done.md` | Slice 완료 기준 체크리스트 | 이관 완료 |
| `git-workflow-commit.md` | 브랜치 전략, 커밋 메시지 컨벤션 | 이관 완료 |
| `git-workflow-pr.md` | Issue 라벨, PR 크기·리뷰 컨벤션 | 이관 완료 |
| `ai-usage.md` | AI 사용 가능·주의·금지 작업 정의 | 이관 완료 |
| `claude-session-guide.md` | 페르소나 3종, 스킬, 워크플로우 | 이관 완료 |
| `ai-fe-workflow.md` | FE AI 협업 워크플로우 | 이관 완료 |
| `docs-structure.md` | docs/ 구조와 각 파일 범위 (본 문서) | 이관 완료 |

## 8. 동기화 절차

- **담당**: 은혜
- **시점**: Confluence 문서 Approved 상태 전환 후
- **방법**: frontmatter `source_updated`와 Confluence 최종 수정일 비교 → 다르면 재이관
- **직접 편집 금지**: `docs/` 파일은 Confluence 원본에서만 갱신
- **Historical 처리**: Confluence에서 Historical 전환 후 로컬 파일 제거 또는 `_archived/`로 이동
- **충돌 시**: 임의 결정하지 않고 Confluence 작성자에게 확인

## 변경 이력

| 날짜 | 내용 | 수정자 |
| --- | --- | --- |
| 2026-08-17 | fe-spec → /spec-draft 통합 반영 | @Jehye |
| 2026-08-17 | 리뷰 반영: 누락 폴더 구조 추가, SoT 규칙 세분화, 파일 표 상태 열 추가, FE 스펙 파일명 규칙 추가, 동기화 절차 신설 | @Jehye |
| 2026-08-12 | 최초 작성 | @Jehye |
