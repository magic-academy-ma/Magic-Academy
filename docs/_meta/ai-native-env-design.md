---
title: AI Native 개발 환경 설계
authored_with: Claude Code
features_used:
  - superpowers:brainstorming
date: 2026-07-08
status: draft
visibility: public
---

# AI Native 개발 환경 설계

## 1. 목적 및 스코프

팀원이 이 저장소를 clone하면, 각자 어떤 AI 도구를 쓰든
**일관된 문서 기준 위에서** Magic Academy를 개발할 수 있는 환경을 만든다.

**이번 cycle 산출물**
- `docs/` — Confluence 위키를 AI 개발 흐름 순서로 재정렬한 문서 계층 (frontmatter · 크로스링크 · 인덱스)
- `AGENTS.md` (도구 무관 진입점) + `CLAUDE.md` (얇게 얹기) + `.claude/settings.json` (공유 권한)
- Confluence → `docs/` 동기화 프로세스 문서 + drift 체크 스크립트 + 문서 무결성 검증 스크립트

**스코프 밖 (다음 cycle)**
- 기술 스택 선택 및 `repo/` 코드 스캐폴딩 — PRD가 아직 설계 단계이고 스택 `미정`

## 2. 확정된 결정

| # | 결정 | 근거 |
|---|------|------|
| D1 | 팀은 **혼합 AI 도구** → 베이스는 도구 무관(`AGENTS.md`), Claude 설정은 얇게 얹음 | 팀원마다 Claude/Cursor/Codex 등 상이 |
| D2 | Confluence(원본, git 밖) → **저장소 `docs/`에 AI용 스냅샷 커밋** | clone만으로 즉시 동작 |
| D3 | 가공 수준 = **목적 기반 구조 재정렬 + 인덱스 + 일관 메타데이터** | AI 개발 흐름 최적화 |
| D4 | 저장소는 **Public 유지 + 민감정보 분리** | 오픈·포트폴리오 성격, 단 내부정보 보호 |
| D5 | **`미정` 항목은 AI가 임의 확정 금지** | PRD 상당수가 미확정 상태 |

## 3. `docs/` 구조 (목적 기반)

Confluence 번호(00~08)가 아니라 **에이전트가 개발 시 읽는 순서**로 재배치한다.

```
docs/
  00-index.md          # 진입점: 읽기 순서 · 우선순위 · "무엇이 미정인지" · source of truth 규칙
  product/             # 개요 · 문제정의 · 타겟 · MVP범위 · 기능우선순위 · 사용자시나리오  (← 02 + PRD §1,2)
  requirements/        # 기능 · 비기능 · 정책/예외 · 화면별                            (← 03 + PRD §3)
  domain/              # 3축(관계·조직·사건) + 배경 + Agent 모델 + 시스템 다이어그램   (← local/CLAUDE.md + PRD + svg) ★핵심
  architecture/        # 시스템 아키텍처 · 백엔드/프론트 구조 · ERD · API명세 · 컨벤션 · 기술스택(미정 명시) · 인프라 (← 05)
  design/              # IA·화면구조 · 플로우 · 와이어프레임 · 디자인시스템            (← 04)
  glossary.md          # 용어 (호감도 · tick · 3축 등)
  _conventions/        # AI 협업 규칙 + 개발 컨벤션                                  (← 06_DEVELOPMENT)
  _meta/               # 이 설계 문서 · SYNC.md (동기화/분류 정책)
```

`01 회의록 / 07 QA / 08 릴리즈 / 99 아카이브`는 초기 개발 계층에서 제외하고 `00-index`에 링크만 둔다.

## 4. 문서 frontmatter 스키마

재정렬해도 원본 추적성을 잃지 않도록 모든 `docs/` 파일에 부여한다.

```yaml
---
title: 시스템 아키텍처
source: confluence/05_TECH/시스템 아키텍처.md   # 원본 미러 경로
canonical: <Confluence URL>                      # 진짜 source of truth
status: draft | review | approved
visibility: public                               # public | (internal은 애초에 미포함)
updated: 2026-07-08
source_updated: 2026-07-08                        # 원본 반영 시점 (drift 판정 기준)
---
```

## 5. 공개/민감정보 분류 정책 (D4)

| 구분 | 처리 | 예시 |
|------|------|------|
| PUBLIC 안전 | `docs/`에 큐레이션 | 제품 컨셉 · 도메인 모델 · 기능/비기능 요구사항 · 아키텍처 방향 · 용어집 · IA/디자인 · 개발 컨벤션 |
| INTERNAL | 미포함, `canonical` Confluence 링크로만 참조 | 팀원 실명·연락 채널(PII) · 회의록 원본 · 배포/인프라 시크릿 · 내부 KPI |

- 분류 판단과 제외 목록은 `docs/_meta/SYNC.md`에 명문화한다.
- 커밋 전 민감정보 스캔을 검증 단계에 포함한다.

## 6. AI 협업 설정 (D1)

- **`AGENTS.md`** (모든 AI 공통 진입점): 프로젝트 한 줄 정의 · source of truth 규칙(`docs/`가 기준, canonical은 Confluence) · 읽기 순서(→ `docs/00-index`) · 작업 원칙(3축 프레임 준수 · tick(24분=1일) 전제 · **`미정` 항목 임의 확정 금지, 사용자 확인**) · 문서↔코드 규칙 · 개발 컨벤션 위치(`docs/_conventions`)
- **`CLAUDE.md`**: 3~4줄. "먼저 `AGENTS.md`를 읽어라" + Claude 전용 힌트만.
- **`.claude/settings.json`**: 팀 공유 권한(읽기·문서 위주 allowlist)을 커밋.
- 다른 도구(Cursor/Codex/Gemini)는 대부분 `AGENTS.md`를 읽으므로 별도 파일 없이 커버.

## 7. 동기화 프로세스

- **원칙**: Confluence(원본) → `confluence/` 미러 → `docs/`(AI용 재정렬). 재정렬은 판단이 필요하므로 **수동 큐레이션**, drift는 자동 감지.
- **`scripts/docs-drift`**: 각 `docs/` 파일의 `source` + `source_updated`를 원본 `confluence/` 파일의 실제 갱신과 비교해 뒤처진 문서 목록 출력.
- **소유자·주기**: 문서 담당자가 Confluence 갱신 시 재큐레이션 후 커밋. `_meta/SYNC.md`에 명문화.

> 주의: `confluence/`는 저장소 밖(git 밖)이므로, drift 스크립트는 로컬에 `confluence/` 미러가 있는 담당자 환경에서 실행하는 것을 전제로 한다.

## 8. 검증 (코드 아님 → 문서 무결성 기준)

- `docs-drift` 스크립트 동작 확인
- 크로스링크 무결성 체크(깨진 내부 링크 0)
- frontmatter 스키마 린트(필수 필드 존재)
- 민감정보 스캔(분류 정책 위반 0)

## 9. 단계 분할 (수직 슬라이스)

- **Phase 1 — 뼈대**: `AGENTS.md` · `CLAUDE.md` · `.claude/settings.json` · `docs/00-index` · `docs/_conventions` · `docs/glossary` · `docs/_meta/SYNC.md` + drift/린트/스캔 스크립트.
  → 이 시점에 팀원이 clone → AI 실행 → 협업 규칙·진입점 확보 (동작하는 최소 환경)
- **Phase 2 — 본문 이관**: `product/` · `requirements/` · `domain/` · `architecture/` · `design/` 실제 재정렬 커밋.

## 10. 미결 / 위험

- 스택 `미정` → `architecture/`는 "확정/미정"을 명확히 구분해 기술.
- 수동 큐레이션은 사람 판단 의존 → drift 스크립트로 방치 방지, 하지만 완전 자동화는 불가.
- Public 저장소 → 신규 문서 추가 시마다 분류 정책 재확인 필요.
