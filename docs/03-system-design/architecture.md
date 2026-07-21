---
title: 시스템 아키텍처
source: confluence/05_TECH/architecture.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/8290305
status: approved
visibility: public
updated: 2026-07-21
source_updated: 2026-07-18
---

## 1. 시스템 개요

마법 대학교 배경 25명 Agent 멀티에이전트 LLM 시뮬레이션.

| 제약 | 값 |
| --- | --- |
| Agent 수 | 학생 20명 + 교수 5명 + Event Master 1명 + Magic Layer 1명 |
| 시간 단위 | 1 Tick = 24분 = 1일 |
| 하루 구조 | 3블록 (아침 / 오후 / 저녁), 밤 스킵 |
| 병렬 실행 | asyncio.gather + Semaphore(10) |

---

## 2. 레이어 구조 다이어그램

```
┌──────────────────────────────────────────────────┐
│  Layer 1: Frontend + API                          │
│  React (React Flow 관계 그래프) + FastAPI REST/WS  │
├──────────────┬──────────────────┬────────────────┤
│  Tick Engine │  Event Master    │  Magic Layer   │
│  (APScheduler│  Agent           │  (테마 레이어) │
│   asyncio)   │  (Sonnet 4.6)    │  (Haiku 4.5)   │
├──────────────┴────────┬─────────┴────────────────┤
│  Agent Runtime        │  Domain Services          │
│  (LangGraph, 25명)    │  (관계·조직·사건 계산)    │
│  Haiku 4.5            │                           │
├───────────────────────┴───────────────────────────┤
│  Persistence: PostgreSQL + pgvector               │
└───────────────────────────────────────────────────┘
```

### 레이어 방향도

```
Frontend (React + React Flow)
    ↕  WebSocket /ws/simulation + REST
API Layer (FastAPI)
    ↓
Tick Engine (APScheduler + asyncio)
    ↓  DB 조회
[ world state snapshot ]
    ├──→ Event Master Agent (Sonnet 4.6)  —  일반 이벤트 생성
    │           ↓
    ├──→ Magic Layer (Haiku 4.5)  —  ① 마법 세계관 변환  ② 30% 특수 사건 추가
    │           ↓
    └──→ Agent Runtime × 25명 병렬 (Haiku 4.5, LangGraph 7노드)
                ↓  Intent
Domain Services  —  Intent 수집 → Conflict Resolve → Commit
    ↓
PostgreSQL + pgvector
    ↓  tick 완료 delta broadcast
Frontend
```

의존성 방향: 항상 위→아래 단방향. Frontend ↔ API 간만 양방향 (WebSocket).

---

## 3. 컴포넌트별 역할

| 컴포넌트 | 책임 | 모델 | 비고 |
| --- | --- | --- | --- |
| Tick Engine | tick 트리거, world state snapshot 생성, 전체 파이프라인 조율 | — | APScheduler in-process |
| Event Master Agent | 매 tick 일반 대학 생활 이벤트 생성 (수업·과제·과팅·시험 등) | Sonnet 4.6 | 단일 LLM 호출 |
| Magic Layer | ① Event Master 이벤트 마법 세계관 변환 ② 30% 확률 마법 특수 사건 생성 | Haiku 4.5 | 별도 담당 |
| Agent Runtime | 25명 병렬 실행 (LangGraph 7노드), Intent 반환 | Haiku 4.5 | asyncio.gather + Semaphore(10) |
| Domain Services | Intent 수집 → Conflict Resolve → DB Commit | — | DB 직접 수정 담당 |
| API Layer | REST + WebSocket 라우터 | — | FastAPI 내장 WS |

### FastAPI 서버 모듈 구조

```
backend/
└── app/
    ├── main.py              # FastAPI 진입점
    ├── api/                 # REST + WebSocket 라우터
    ├── core/                # 설정, DB 연결, 미들웨어
    ├── domain/              # 도메인 모델
    ├── repositories/        # PostgreSQL + pgvector 접근
    ├── services/            # 유즈케이스 조합
    └── simulation/          # 시뮬레이션 엔진
        ├── tick_engine.py
        ├── agent_runtime.py
        ├── event_master.py
        └── magic_layer.py
```

---

## 4. Tick 기준 데이터 흐름

### 4.1 스케줄링

* APScheduler (in-process 스케줄러)가 실제 시간 기준으로 tick 트리거
* 활동 시간대: 하루 3블록 (아침 / 오후 / 저녁) — 블록당 1회 판단
* 밤 시간대: tick 번호만 전진, Agent 호출 없음

### 4.2 활동 시간대 — 블록 실행 순서

```
[1] SimulationTickService
    - tick 시작
    - 현재 world state snapshot 생성

[2] Event Master Agent (Sonnet 4.6)
    - 일반 대학 생활 이벤트 생성 (수업·과제·과팅·시험 등)
    - 관련 학생 2~5명 선택, 사건 유형·장소·영향도 결정

[3] Magic Layer (Haiku 4.5)
    - ① Event Master 이벤트를 마법 세계관으로 변환 (매 tick)
    - ② 30% 확률로 마법 특수 사건 추가 생성 (폭발·저주·실종 등)
    - 생성된 이벤트는 동일 events 테이블에 source = 'magic_layer' 로 저장

[4] StudentAgentGraph — 25명 병렬 실행
    - 입력: world state snapshot + 개인 memory + 관계 정보 + 현재 이벤트
    - asyncio.gather() + semaphore(max=10) 동시 호출 제한
    - Agent별 LangGraph 실행 (7노드):
        Observe
        → Retrieve Memory
        → Evaluate Relationship / Emotion
        → Decide Action
        → Generate Intent
        → Save Observation
        → Reflection 조건 확인
    - 각 Agent: DB 직접 수정 없이 Intent만 반환

[5] Intent Collector
    - 25명 Agent의 Intent 수집

[6] Conflict Resolver
    - 같은 tick, 같은 관계에 복수 delta → 합산 후 clamp(-100, +100)
    - 같은 Agent 상태에 복수 수정 → 마지막 값 우선 (덮어쓰기)
    - 이벤트 중복 참여 → event_id 기준 dedup

[7] Commit (PostgreSQL batch write)
    - 관계 변화 저장
    - Agent 상태 변화 저장
    - memory 저장
    - event log 저장

[8] WebSocket broadcast
    - tick 완료 결과를 변경분(delta)만 프론트엔드에 push
```

---

## 5. 주요 인터페이스

### WebSocket

* 경로: `WS /ws/simulation`
* 방향: 서버→클라이언트 단방향 push (tick 완료 시 delta만 전송)
* 향후 User Persona 개입 수신도 동일 채널 사용 예정

### REST (개요)

* 시뮬레이션 제어: start / pause / reset
* Agent 조회: 상태, 관계, 기억
* 이벤트 조회: tick별 이벤트 목록
* 상세 스펙은 API 설계 문서 별도 관리

### DB 테이블

| 테이블 | 저장 내용 |
| --- | --- |
| `agents` | Agent 기본 정보 (이름·역할·기숙사·전공·성격·목표) |
| `agent_states` | tick별 Agent 내부 상태 (위치·기분·스트레스·에너지·명성 등) |
| `relationships` | Agent 쌍별 관계 수치 (신뢰·호감·경쟁·긴장 등) |
| `events` | 발생 이벤트 (유형·tick·장소·출처: event_master / magic_layer) |
| `event_participants` | 이벤트 참여 Agent 및 역할 |
| `agent_memories` | Agent 기억 (자연어 + embedding vector, 중요도·최근성 기반 검색) |
| `simulation_ticks` | tick 실행 이력 (상태·시작/종료 시각) |

---

## 6. 배포 구조

| 기간 | 환경 | 구성 |
| --- | --- | --- |
| Week 1–2 | 로컬 | Docker Compose — pgvector / FastAPI+uvicorn / React+Vite 서비스 분리, `magic-net` 브리지 네트워크 |
| Week 3+ | Railway | 단일 서버 + Railway PostgreSQL(pgvector) |
| Week 5–6 (조건부) | Redis 추가 | 실제 부하 문제 발생 시에만 도입 |

---

## 7. 변경 이력

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| v1.0 | 2026-07-13 | 초안 작성 — 선행조사 11개 기반, 회의 출발점. 미확정 항목 §8 포함. |
| v2.0 | 2026-07-18 | 구성 재편 — §1 시스템 개요 추가. Magic Layer 실행 위치 확정 반영. 레이어 방향도 추가. §5 주요 인터페이스 신설. 토큰 비용·미확정 항목 섹션 삭제. |
| v2.1 | 2026-07-18 | 레이어 방향도 수정 — world state snapshot 공유 입력 및 수신 컴포넌트 명시. |
