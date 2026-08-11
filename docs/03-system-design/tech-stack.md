---
title: 기술 스택 확정 — 선행조사 통합 결론
source: confluence/05_TECH/tech-stack.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/10911784
status: approved
visibility: public
updated: 2026-07-21
source_updated: 2026-07-18
---

**작성일:** 2026-07-18  |  **근거:** 선행조사 18개 문서 결론 취합

---

## 시스템 레이어 구조

```
[Frontend]  React + Vite  /  React Flow (관계 그래프, 선택 시에만 렌더링)
     ↕ WebSocket (WS /ws/simulation) + REST
[Backend API]  FastAPI — 도메인 중심 모듈 구조
               (api / core / domain / repositories / services / simulation)
     ↓
[Tick Engine]  APScheduler (in-process) + asyncio.gather + Semaphore(10)
     ↓
[Event Master Agent]  Sonnet 4.6 — 매 tick 일반 이벤트 생성
     ↓
[Magic Layer]  Haiku 4.5 — ① 이벤트 마법 세계관 변환 (매 tick)
                           ② 30% 확률 마법 특수 사건 추가 생성
     ↓
[Agent Runtime]  LangGraph 7노드 × 25명 병렬
                 Memory Stream + 단순 Reflection
                 Memory 선택: pgvector RAG top-3 + 최신 2개 고정 (매 tick 주입 최대 5개 — 보유 상한 10개와 별개)
     ↓
[Persistence]  PostgreSQL + pgvector (HNSW 인덱스) / Alembic
```

---

## 기술 스택 확정 테이블

### AI / Agent

| 항목 | 채택 |
| --- | --- |
| 오케스트레이션 | LangGraph + Custom Tick Orchestrator |
| Agent Memory 구조 | Memory Stream + 단순 Reflection (B안) — 큰 사건 참여 Agent에게만 Reflection 생성 |
| Memory 선택 전략 | pgvector RAG top-3 + 최신 2개 고정 (매 tick 주입 최대 5개, 보유 상한 10개와 별개) — score = α×importance + β×recency + γ×relevance |
| 25명 병렬 실행 | asyncio.gather + Semaphore(10) |
| LLM 모델 | Haiku 4.5 (학생·교수·Magic Layer), Sonnet 4.6 (Event Master) |
| 토큰 최적화 | 3블록 단위 tick + 프롬프트 캐싱 + Memory 5개 제한 (Naive 대비 약 89% 절감) |

### DB / 저장소

| 항목 | 채택 |
| --- | --- |
| 주 DB | PostgreSQL + pgvector |
| pgvector 인덱스 | HNSW |
| DB 마이그레이션 | Alembic Revision + Merge Revision — 기능 완료 후 Revision 생성, PR 전 Migration 확인 |

### 백엔드 API

| 항목 | 채택 |
| --- | --- |
| 서버 모듈 구조 | 도메인 중심 모듈 구조 — api / core / domain / repositories / services / simulation |
| 실시간 통신 | WebSocket (FastAPI 내장, WS /ws/simulation) — tick push + 향후 User Persona 개입 수신 동일 채널 |

### 시뮬레이션 실행 환경

| 항목 | 채택 |
| --- | --- |
| Tick 스케줄러 | APScheduler (in-process) + asyncio.gather |
| 시스템 레이어 | 도메인 중심 4단계 — Frontend·API / Tick Engine·Event Master·Magic Layer / Agent Runtime·Domain Services / Persistence |

### 인프라

| 항목 | 채택 |
| --- | --- |
| 로컬 개발 환경 | Docker Compose — pgvector, FastAPI+uvicorn, React+Vite 서비스 분리 + magic-net 브리지 |
| Cloud PaaS | Railway + PostgreSQL(pgvector) |
| 환경변수 관리 | 로컬 .env + .env.example / CI GitHub Secrets / 배포 Railway Variables |
| 모니터링 (MVP) | Railway Logs + Python Logging + Agent Trace 로그 (INFO/WARNING/ERROR) |

### 프론트엔드

| 항목 | 채택 |
| --- | --- |
| UI 패턴 | The Sims + AI Town + RimWorld 하이브리드 — 학교 맵 / 행동·위치·Tick / Event 로그 / Agent 상태 우측 패널 / Agent 목록 좌측 패널 |
| 관계 그래프 | React Flow — 선택한 Agent 중심, 선택 시에만 렌더링 (상시 렌더링 금지) |

---

## MVP 이후 보류 항목

| 기술 | 예상 도입 시점 | 보류 이유 |
| --- | --- | --- |
| Redis (Pub/Sub, Queue, Lock) | Week 5~6 | 현재 규모에서 asyncio + semaphore로 충분 |
| Anthropic Batch API (-50% 비용) | Week 5~6 | 실제 호출 로그 기반으로 고도화 단계에서 적용 |
| 비활성 Agent LLM 호출 스킵 | Week 3~4 | importance_score 컬럼 추가 후 구현 |
| Grafana + Loki | Week 5~6 | MVP에서 Railway Logs로 대체 가능 |
| OpenTelemetry / Sentry | Week 5~6 | MVP 규모에 과함 |
| Cytoscape.js (관계 그래프) | Agent 수 대폭 증가 시 | 현재 20명 규모에서 React Flow로 충분 |
| Vault / AWS Secrets Manager | 프로덕션 전환 시 | 현재 Railway Variables로 충분 |
