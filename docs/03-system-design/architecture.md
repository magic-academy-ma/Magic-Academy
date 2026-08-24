---
title: 시스템 아키텍처
source: confluence/05_TECH/architecture.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/8290305
status: draft
updated: 2026-08-25
source_updated: 2026-08-05
---

## 1. 시스템 개요

마법 대학교를 배경으로 생활 Agent 6명부터 시작해 단계적으로 확장하는 멀티에이전트 LLM 시뮬레이션.

| 제약 | 값 |
| --- | --- |
| Agent 수 | 1단계: 생활 Agent 6명(Student 5명 중 User Persona 1명 포함 + Professor 1명). 2단계 13명, 3단계 25명으로 확장. Event Master와 Magic Layer는 시스템 컴포넌트로 별도 관리 |
| 시간 단위 | 1 Tick = 8분 = 1블록, 1일 = 3블록 = 24분 |
| 하루 구조 | 3블록 (아침 / 오후 / 저녁), 밤 스킵 |
| 병렬 실행 | asyncio.gather + Semaphore(10) |

---

## 2. 레이어 구조 다이어그램

```
Frontend — React + React Flow
    ↕ REST / WebSocket
API Layer — FastAPI
    ↓
Tick Engine 논리 영역
    ├─ TickScheduler — Trigger·대기 관리
    ├─ SimulationTickService — snapshot·schedule 준비
    └─ TickOrchestrator — 실행 순서·실패·Commit 조율
        ↓
Event Master → Magic Layer → Agent Runtime
        ↓
Intent Collector → Policy Engine → Conflict Resolver
        ↓
Commit Service — 원자적 batch write + Tick Outbox
        ↓
PostgreSQL + pgvector → Outbox Dispatcher → WebSocket
```

### 레이어 방향도

```
TickScheduler Trigger
    ↓
TickOrchestrator — Simulation별 lease 획득·heartbeat 갱신
    ├─ 활동 Tick → 전체 실행 파이프라인
    └─ 야간 대기 → 야간 회복·다음 날 MORNING 전환
        ↓
Commit Service — fence/state version 검증 후 원자적 저장
        ↓ commit 성공
Outbox Dispatcher → WebSocket delta 발행
```

의존성은 위에서 아래로 흐른다. 하위 컴포넌트는 상위 오케스트레이션을 역호출하지 않으며 DB를 직접 수정하지 않는다. 영속화는 Commit Service만 담당한다.

---

## 3. 컴포넌트별 역할

| 컴포넌트 | 책임 | 하지 않는 일 |
| --- | --- | --- |
| TickScheduler | APScheduler lifecycle, Simulation별 job·8분 주기·야간 대기 관리 | 활동/야간 분기와 파이프라인 판단 |
| SimulationTickService | 짧은 read-only transaction에서 TickContext·snapshot·schedule·유효 Agent 후보 준비 | Event 생성과 DB 저장 |
| TickOrchestrator | lease·heartbeat, 활동/야간 분기, 호출 순서, 실패 처리, Commit 후 발행 조율 | Agent 판단·delta 계산·DB 직접 수정 |
| Event Master Agent | 학사 일정과 world state 기반 일반 Event 후보 생성 | 마법 변환·delta 계산·직접 저장 |
| Magic Layer | 일반 Event 변환과 조건 기반 특수 Event 후보 생성 | 숫자 delta 계산·직접 저장 |
| Agent Runtime | Agent별 Context로 Intent·Memory 후보·Decision Explanation 생성 | 실행 대상 최종 선정·Commit |
| Intent Collector | Runtime 결과를 agent_id 기준으로 수집·정렬 | 결과 의미 변경 |
| Policy Engine | 정성적 signal을 숫자 delta 후보로 변환 | 후보 병합·DB 저장 |
| Conflict Resolver | 승인 delta 합산, 최종 clamp, Event 참여 중복 제거 | DB 저장 |
| Commit Service | Resolution Plan·승인 후보·Outbox Event 원자적 저장 | 행동 판단·파이프라인 분기 |

---

## 4. Tick 기준 데이터 흐름

### 4.1 스케줄링과 분기

* TickScheduler는 실행 Trigger와 8분 주기만 관리한다.
* TickOrchestrator가 현재 상태를 검사해 활동 Tick과 야간 전환을 분기한다.
* EVENING commit 후 1 Tick의 야간 대기를 시작하며 자동 전환과 수동 밤 스킵은 같은 야간 경로를 사용한다.
* 야간 전환은 Event Master·Magic Layer·Agent Runtime을 호출하지 않고 Tick 번호도 증가시키지 않는다.

### 4.2 활동 시간대 — 블록 실행 순서

SimulationTickService → Event Master → Magic Layer → Runtime 대상 편성 → Agent Runtime 병렬 호출 → Intent Collector → Policy Engine → Conflict Resolver → Commit Service → Outbox Dispatcher

상세 실행 순서 및 각 단계 책임: `docs/03-system-design/tick-engine.md §3`

### 4.3 동시성·저장·재시도 경계

* TickOrchestrator는 snapshot 전에 PostgreSQL 기반 Simulation별 lease를 획득하고 heartbeat를 갱신한다.
* 동일 Simulation의 `running` Tick은 최대 1개만 허용한다.
* Snapshot은 짧은 read-only `REPEATABLE READ`, Commit은 짧은 `READ COMMITTED` transaction을 사용한다.
* Commit은 Simulation row lock과 fence/state version을 검증하고 블록당 한 번의 batch write로 저장한다.
* 같은 Resolution Plan과 `resolution_id`로 Commit만 최대 2회 재시도하며 전체 Tick 파이프라인은 자동 재시도하지 않는다.
* 도메인 변경과 Outbox Event는 같은 transaction에 저장한다. 전송 실패는 Outbox만 재시도한다.

---

## 5. 주요 인터페이스

### WebSocket

* 방향: 서버→클라이언트 단방향 push (tick 완료 시 delta만 전송)
* 향후 User Persona 개입 수신도 동일 채널 사용 예정

### REST (개요)

* 시뮬레이션 제어: start / pause / reset
* Agent 조회: 상태, 관계, 기억
* 이벤트 조회: tick별 이벤트 목록
* 상세 스펙은 API 설계 문서 별도 관리

### 영속화 범위

PostgreSQL + pgvector에는 Agent·상태·관계·사건·Memory·Tick 실행 이력과 Outbox Event를 저장한다. 구체 스키마와 테이블 계약은 비공개 데이터 모델에서 관리한다.

---

## 6. 배포 구조

| 기간 | 환경 | 구성 |
| --- | --- | --- |
| Week 1–2 | 로컬 | Docker Compose — pgvector / FastAPI+uvicorn / React+Vite 서비스 분리, `magic-net` 브리지 네트워크 |
| Week 3+ | Railway | 단일 서버 + Railway PostgreSQL(pgvector) |
| Week 5–6 (조건부) | Redis 추가 | 실제 부하 문제 발생 시에만 도입 |

---
