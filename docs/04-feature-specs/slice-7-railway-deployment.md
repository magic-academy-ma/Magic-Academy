---
title: Slice 7 — Railway 배포 런북
status: draft
updated: 2026-08-27
source:
  - "GitHub Issue #146"
  - "docs/04-feature-specs/slice-7-config-sharing-import-deployment.md §6"
  - "docs/03-system-design/infra.md §3"
---

# Slice 7 — Railway 배포 런북

> 이 문서는 Task 3(#146)의 배포 구성·절차를 기록한다. 실제 `railway login`/배포
> 실행은 이 세션에서 완료할 수 없었다(아래 "현재 상태" 참고). 배포 없이 준비
> 가능한 코드/설정은 모두 완료했다.

## 1. 현재 상태 — BLOCKED

이 세션에는 Railway CLI 인증 수단이 전혀 없다.

- `npx @railway/cli whoami` → `Unauthorized. Please login with 'railway login'`
- `RAILWAY_TOKEN` 등 관련 환경변수 없음
- Repository에 Railway GitHub App 연동 없음(webhook은 Discord만 존재)
- Repository Actions secrets 없음

`railway login`은 브라우저 기반 OAuth 상호작용이 필요해 자율 Agent가 완료할 수
없다. 기존 Railway project가 있다면 사람이 다음 중 하나를 제공해야 재개할 수
있다.

1. 이 머신에서 `railway login` 실행(대화형), 또는
2. `RAILWAY_TOKEN`(프로젝트 토큰) 환경변수 제공

기존 Railway project가 전혀 없다면 새 프로젝트 생성이 필요한데, 이는 과금
발생 가능성이 있는 새 리소스 생성이라 임의로 진행하지 않는다.

## 2. 서비스 구성

Root Directory 기준으로 Railway 서비스 3개를 구성한다(모두 GitHub 연동 자동
배포 권장, `docs/03-system-design/infra.md` §3 결론과 동일):

| 서비스 | Root Directory | 비고 |
| --- | --- | --- |
| PostgreSQL | (Railway 제공 Managed DB) | pgvector 지원 필요 — Railway의 PostgreSQL 템플릿이 아니라 `pgvector/pgvector` 호환 이미지 확인 필요. 미지원 시 Railway의 Docker Image 서비스로 `pgvector/pgvector:0.8.5-pg16`을 직접 배포 |
| backend | `backend/` | `backend/railway.toml` + `backend/Dockerfile` 사용 |
| frontend | `frontend/` | `frontend/railway.toml` + `frontend/Dockerfile` 사용 |

### 2.1 backend 필수 Variables

| 이름 | 값 |
| --- | --- |
| `DATABASE_URL` | Railway PostgreSQL의 연결 문자열(`postgresql+psycopg://` 접두어로 변환됨, `app/core/config.py` 참고) |
| `JWT_SECRET` | 32자 이상 랜덤 값(새로 생성 금지 지시에 따라 기존 값이 있으면 재사용, 없으면 사람이 생성) |
| `CORS_ORIGINS` | 배포된 frontend 공개 URL 정확히 지정(와일드카드 금지, §6.1) |
| `ENVIRONMENT` | `production` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | 실제 사용 중인 provider만, 존재 여부만 확인하고 값은 노출하지 않는다 |

### 2.2 frontend 필수 Variables (빌드 타임에 필요)

| 이름 | 값 |
| --- | --- |
| `VITE_API_URL` | 배포된 backend 공개 URL |
| `VITE_WS_URL` | 배포된 backend의 WebSocket URL(`wss://` 스킴) |

Vite는 `import.meta.env.VITE_*`를 빌드 시점에 정적으로 inline하므로, 이 값들은
런타임이 아니라 **빌드 이전**에 Railway Variables로 설정돼 있어야 한다.

## 3. 시작 커맨드 (로컬 검증 완료)

- backend: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`
  (`backend/railway.toml`) — 격리 PostgreSQL로 로컬에서 기동·`/health` 200 확인함.
- frontend: `npm run build && npm run preview -- --host 0.0.0.0 --port ${PORT:-4173}`
  (`frontend/railway.toml`) — 로컬에서 기동 확인, 임의 Host 헤더로도 200 확인함
  (`vite.config.js`의 `preview.allowedHosts = true`).

migration 실패 시 `alembic upgrade head`가 0이 아닌 코드로 종료되어 `&&` 뒤의
uvicorn이 시작되지 않으므로, 실패한 버전은 트래픽을 받지 못한다(fail-closed).

## 4. `/health` 계약

`GET /health`는 다음을 모두 만족해야 200을 반환한다(`backend/app/api/health.py`).

1. 애플리케이션이 요청을 처리할 수 있다.
2. DB에 연결할 수 있다(`SELECT 1`).
3. DB에 적용된 Alembic revision이 이 배포의 migration head와 정확히 일치한다
   (`backend/app/core/migration_status.py`).

셋 중 하나라도 실패하면 503을 반환한다. Railway healthcheckPath로 지정되어
있어(§3의 `backend/railway.toml`), migration이 끝나기 전이나 실패한 배포는
Railway가 트래픽을 넘기지 않는다.

## 5. 구조화 로그

모든 요청이 한 줄 JSON으로 로그에 남는다
(`backend/app/core/logging_middleware.py`). 필드: `timestamp`, `level`,
`service`, `environment`, `trace_id`, `request_id`, `operation`, `result`,
`duration_ms`, 그리고 경로에 존재할 때만 `simulation_id`/`share_id`/`run_id`/
`tick_number`.

절대 로그에 남기지 않는 값(코드로 보장, 헤더/바디를 아예 읽지 않음):
Authorization/JWT/cookie/API key/Secret, 요청·응답 본문 전체, Prompt/Chain of
Thought.

## 6. 배포 Golden Path (Railway 접근 가능해진 뒤 수행)

1. `railway login` 또는 `RAILWAY_TOKEN` 설정 확인 (`railway whoami`)
2. 기존 project 확인(`railway status` 또는 dashboard) — 없으면 STOP하고 사용자에게
   보고(새 프로젝트 생성은 과금 가능성이 있어 임의 진행 금지)
3. 위 Variables가 3개 서비스에 설정돼 있는지 확인
4. backend 배포 → `/health` 200 확인 → 로그에서 구조화 JSON 한 줄 확인
5. frontend 배포 → 루트 페이지 200 확인
6. 인증된 상태로 Simulation 생성 → 공유 생성(public) → 목록/검색에서 발견 →
   상세 조회 → 가져오기(Idempotency-Key 포함) → 새 Simulation 확인
7. 가져오기 중 Runtime/LLM/Tick 호출 0회 확인(§4의 instrumentation 카운터는
   프로덕션에 없으므로, 로그의 `operation`이 import 경로 이외의 Tick/Runtime
   엔드포인트를 호출하지 않았는지로 대체 확인)
8. WebSocket AUTH handshake 확인(`wss://<backend>/ws/simulations/{id}`)

## 7. 장애 확인 절차

- `/health` 503 → backend 로그에서 `"operation": "GET /health"` 라인의
  `result`/직전 예외 확인. DB 연결 문제인지 migration 불일치인지 구분.
- migration 실패 → Railway backend 서비스의 최신 배포 로그에서
  `alembic upgrade head`의 표준 출력 확인(fail-closed이므로 이전 정상 버전이
  계속 서비스 중이어야 한다).
- CORS 오류 → `CORS_ORIGINS`가 frontend의 실제 공개 URL과 정확히 일치하는지
  확인(트레일링 슬래시 등 사소한 불일치도 실패 원인이 될 수 있음).
