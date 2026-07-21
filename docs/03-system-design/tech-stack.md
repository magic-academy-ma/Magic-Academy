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

각 항목은 선행조사 문서에서 도출된 확정 결론이다. 탈락 옵션과 조건도 함께 기록한다.

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
                 Memory 선택: pgvector RAG top-3 + 최신 2개 고정 (최대 5개)
     ↓
[Persistence]  PostgreSQL + pgvector (HNSW 인덱스) / Alembic
```

---

## 기술 스택 확정 테이블

### AI / Agent

| 항목 | 채택 | 탈락 옵션 | 근거 문서 |
| --- | --- | --- | --- |
| 오케스트레이션 | LangGraph + Custom Tick Orchestrator | AutoGen (업무 해결형), CrewAI (역할 고정형), 완전 Custom (구현 과다) | 멀티에이전트 오케스트레이션 프레임워크 조사 |
| Agent Memory 구조 | Memory Stream + 단순 Reflection (B안) — 큰 사건 참여 Agent에게만 Reflection 생성 | A안 원본 전체 재현 (구현 과다), C안 Memory 없음 (관계·서사 누적 불가) | Generative Agents 논문 구현 분석 |
| Memory 선택 전략 | pgvector RAG top-3 + 최신 2개 고정 (최대 5개) — score = α×importance + β×recency + γ×relevance | Sliding Window (중요 기억 손실), LLM 요약 압축 (Summarization Drift 문제), Hybrid (파라미터 튜닝 필요) | 토큰 비용 대응 — 메모리 압축 전략 |
| 25명 병렬 실행 | asyncio.gather + Semaphore(10) | 순차 실행 (tick당 수십 초 이상), LangGraph Supervisor (LLM 추가 비용) | LangGraph 25명 병렬 실행 패턴 |
| LLM 모델 | Haiku 4.5 (학생·교수·Magic Layer), Sonnet 4.6 (Event Master) | Sonnet 전체 (~2배 비용), Opus 전체 (~5배 비용) | 토큰 비용 시나리오 추정 |
| 토큰 최적화 | 3블록 단위 tick + 프롬프트 캐싱 + Memory 5개 제한 (Naive 대비 약 89% 절감) | A안 Naive 전체 Sonnet ($4,170/8주), B안 모델 다운그레이드만 ($2,080/8주) | 토큰 비용 시나리오 추정 |

### DB / 저장소

| 항목 | 채택 | 탈락 옵션 | 근거 문서 |
| --- | --- | --- | --- |
| 주 DB | PostgreSQL + pgvector | SQLite (동시 write 취약), Redis (보조 저장소 → MVP 이후 도입) | Agent 상태 저장소 옵션 |
| pgvector 인덱스 | HNSW | IVFFlat (소규모 데이터에서 Recall 감소) | pgvector 인덱스 전략 (HNSW vs IVFFlat) |
| DB 마이그레이션 | Alembic Revision + Merge Revision — 기능 완료 후 Revision 생성, PR 전 Migration 확인 | 각자 Revision 생성 (충돌), 담당자 지정 (의존성) | Alembic 마이그레이션 전략 |

### 백엔드 API

| 항목 | 채택 | 탈락 옵션 | 근거 문서 |
| --- | --- | --- | --- |
| 서버 모듈 구조 | 도메인 중심 모듈 구조 — api / core / domain / repositories / services / simulation | Flat 구조 (파일 증가 시 관리 불가), MVC 계층 (simulation 로직 위치 불명확) | FastAPI 서버 모듈 구조 |
| 실시간 통신 | WebSocket (FastAPI 내장, WS /ws/simulation) — tick push + 향후 User Persona 개입 수신 동일 채널 | Polling (실시간성 없음), SSE (단방향, 향후 개입 수신 별도 REST 필요) | WebSocket 실시간 통신 (SSE vs WebSocket) |

### 시뮬레이션 실행 환경

| 항목 | 채택 | 탈락 옵션 | 근거 문서 |
| --- | --- | --- | --- |
| Tick 스케줄러 | APScheduler (in-process) + asyncio.gather — Week 1~2 로컬 Docker, Week 3+ Railway 전환 | Redis + Celery/BullMQ (25명 규모 과잉, 세팅 3~5일), 서버리스 (상태 유지 불가) | Tick 기반 시뮬레이션 실행 환경 |
| 시스템 레이어 | 도메인 중심 4단계 — Frontend·API / Tick Engine·Event Master·Magic Layer / Agent Runtime·Domain Services / Persistence | A안 3레이어 (Simulation Engine 비대화), B안 5레이어 수직 분리 (Agent↔Domain 경계 모호) | 시스템 레이어 구조 (Magic Layer 포함) |

### 인프라

| 항목 | 채택 | 탈락 옵션 | 근거 문서 |
| --- | --- | --- | --- |
| 로컬 개발 환경 | Docker Compose — pgvector, FastAPI+uvicorn, React+Vite 서비스 분리 + magic-net 브리지 | 모노리식 컨테이너 (핫리로드 불가), 별도 compose 파일 (MVP 과도) | Docker Compose 서비스 분리 |
| Cloud PaaS | Railway + PostgreSQL(pgvector) | Render (무료 플랜 Sleep), Fly.io (Docker 필수, 운영 복잡) | Cloud PaaS 비교: Render / Railway / Fly.io |
| 환경변수 관리 | 로컬 .env + .env.example / CI GitHub Secrets / 배포 Railway Variables | .env 공유 (보안 취약) | Secret / 환경변수 관리 전략 |
| 모니터링 (MVP) | Railway Logs + Python Logging + Agent Trace 로그 (INFO/WARNING/ERROR) | Grafana+Loki, OpenTelemetry (→ Week 5~6 이후 도입) | 모니터링 / 로깅 전략 |

### 프론트엔드

| 항목 | 채택 | 탈락 옵션 | 근거 문서 |
| --- | --- | --- | --- |
| UI 패턴 | The Sims + AI Town + RimWorld 하이브리드 — 학교 맵 / 행동·위치·Tick / Event 로그 / Agent 상태 우측 패널 / Agent 목록 좌측 패널 | 단일 레퍼런스 직접 채택 | 시뮬레이션 관찰 UI 레퍼런스 |
| 관계 그래프 | React Flow — 선택한 Agent 중심, 선택 시에만 렌더링 (상시 렌더링 금지) | D3.js (React 연동 추가 작업, 난이도 높음), Cytoscape.js (현재 규모 기능 과잉) | 관계 그래프 시각화 라이브러리 비교 |

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
