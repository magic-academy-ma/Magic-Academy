---
title: Tick Engine 스펙
source: confluence/05_TECH/tick-engine.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/12910622/Tick+Engine
status: approved
updated: 2026-07-28
source_updated: 2026-07-28
---

**출처:** 시스템 아키텍처 (#8290305) · Tick 기반 시뮬레이션 실행 환경 (#5996546) · WebSocket 실시간 통신 (#6717441)

---

## 1. 개요

| 항목 | 값 |
| --- | --- |
| 1 Tick | 8분 (실제 시간) = 1블록 (시뮬레이션) |
| 하루 구조 | 3블록 (아침 / 오후 / 저녁), 밤 스킵 |
| Agent 수 | 생활 Agent 6명 (학생 5명 + 교수 1명), 시스템 컴포넌트: Event Master 1 + Magic Layer 1 |
| 스케줄러 | APScheduler (in-process) |
| Agent 병렬화 | asyncio.gather() + Semaphore(10) |

---

## 2. 스케줄링

* **APScheduler in-process**: FastAPI 서버 내에서 tick을 트리거. 별도 프로세스·메시지 큐 없음.
* **활동 시간대(3블록)**: §3 실행 순서 전체 수행.
* **야간 대기**: EVENING Tick의 batch commit 완료 후 시작한다. 설정된 대기시간이 지나면 자동 전환하며, 수동 밤 스킵은 남은 대기시간만 생략하고 같은 전환 로직을 실행한다.
* **야간 전환**: Agent Runtime·Event Master·Magic Layer를 호출하지 않는다. 야간 회복 Policy를 적용하고 Tick 번호 증가 없이 `current_day + 1`, 다음 블록 MORNING으로 전환한다.

---

## 3. Tick 루프 실행 순서

활동 시간대 블록 1회 기준. **하루 3블록 = 아래 순서를 3회 반복.**

```
[1] SimulationTickService
    - tick 시작
    - 현재 world state snapshot 생성 (DB 조회)


[2] Event Master Agent  (Sonnet 4.6, LLM 단일 호출)
    - 일반 대학 생활 이벤트 생성 (수업·과제·과팅·시험 등)
    - 관련 학생 2~5명 선택, 사건 유형·장소·영향도 결정


[3] Magic Layer  (Haiku 4.5)
    - ① Event Master 이벤트를 마법 세계관으로 변환 (매 블록 필수)
    - ② world_state가 사건별 조건을 만족할 때만 마법 특수 사건 생성 (폭발·저주·실종 등)
    - 변환 Event와 특수 Event 저장 후보를 반환
    - DB에 직접 쓰지 않으며, 최종 Event 저장은 Tick 단위 batch commit에서 수행


[4] 활성 Student 5명 + 실행 조건을 충족한 Professor 병렬
    asyncio.gather() + Semaphore(max=10) 동시 LLM 호출 제한
    Agent Runtime 실행 흐름:
      ValidateInput
      → Observe
      → RetrieveMemory
      → EvaluateContext
      → DecideAction / GenerateIntent / GenerateMemoryCandidate
      → ReflectIfNeeded
      → ValidateOutput
    Agent당 Intent 1개와 Memory 후보를 반환하며, reaction은 정성적 signal만 포함한다.
    각 Agent: DB 직접 수정 없이 Intent만 반환


[5] Intent Collector
    - 활성 Student 5명과 실행 조건을 충족한 Professor의 Intent 수집
    - Professor가 관련 수업·시험·사건이 없는 Tick에는 Professor Intent를 요구하지 않음


[6] Policy Engine
    - Agent Runtime이 반환한 정성적 signal과 intensity를 수치 delta 후보로 변환
    - Action 기본 생리 효과 및 Event 기본 효과 적용
    - Magic Layer expected_effects 허용 목록 및 상한 검증
    - 같은 source·rule의 내부 중복 effect 제거
    - DB를 직접 수정하지 않으며 delta 후보(effect_candidates)만 반환


[7] Conflict Resolver
    - 서로 다른 source에서 나온 delta 후보를 합산
    - 같은 Tick, 같은 관계·상태 metric의 승인된 delta를 최종 합산
    - 합산 결과를 metric별 허용 범위로 clamp
    - 이벤트 중복 참여는 event_id 기준으로 dedup


[8] DB Commit  (PostgreSQL batch write, 블록당 1회)
    - 관계 변화 (relationships 테이블)
    - Agent 내부 상태 변화 (agent_states 테이블)
    - memory 저장 (agent_memories 테이블)
    - event log (events + event_participants 테이블)


[9] WebSocket broadcast
    - 변경분(delta)만 프론트엔드에 push (전체 상태 아님)
```

---

## 4. Agent 병렬 실행

* `asyncio.gather()` + `Semaphore(10)` — 동시 LLM 호출 최대 10개
* Semaphore 상한은 설정 파일(`AGENT_SEMAPHORE_MAX`)로 조정 가능

```python
async def run_agents(agents, context):
    semaphore = asyncio.Semaphore(settings.AGENT_SEMAPHORE_MAX)
    async def run_one(agent):
        async with semaphore:
            return await agent.run(context)
    return await asyncio.gather(*[run_one(a) for a in agents])
```

---

## 5. 상태 저장 시점

* 블록 완료 후 **1회 batch write** (단계 [7])
* 이벤트·Agent 행동 직후 즉시 저장 없음 (DB 쓰기 횟수 최소화)
* 블록 중 실패 시 해당 블록 내 변화 유실 가능 → 재시작 단위 = 블록

---

## 6. WebSocket 브로드캐스트

* 경로: `wss://{server}/v1/ws/simulations/{simulation_id}`
* 방향: 서버 → 클라이언트 단방향 push
* 발행 시점: Tick 단위 batch commit 성공 후
* commit이 실패한 Tick의 메시지는 발행하지 않는다.

메시지 Schema는 [API 명세 §14](https://jehye.atlassian.net/wiki/spaces/MA/pages/12451842)를 단일 기준으로 사용한다.

* `TICK_UPDATED`
* `AGENT_ACTION_UPDATED`
* `EVENT_CREATED`
* `RELATIONSHIP_UPDATED`

---

## 7. 확정된 설계 결정

| # | 항목 | 결정 | 비고 |
| --- | --- | --- | --- |
| D1 | Reflection 트리거 조건 | 확정 — 큰 사건 참여자만 | importance >= threshold 인 이벤트 참여 Agent만 Reflection 실행. threshold는 설정 파일(`REFLECTION_THRESHOLD`, 기본 0.7)로 관리. |
| D2 | Memory 초과(10개) 처리 | 확정 — importance 기반 압축 | 10개 초과 시 importance 낮은 항목 제거 |
| D3 | 관계 수치 변화량 공식 | 확정 — 단순 delta 가산 | 이벤트 유형별 delta 테이블로 관리. |

---

---

---

