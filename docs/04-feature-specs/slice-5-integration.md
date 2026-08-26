# Slice 5 통합 계약 확인 (Task 0)

> **상태:** DRAFT
> **작성자:** @박혜정
> **담당자:** @박혜정
> **작성일 / 최종 수정일:** 2026-08-17 / 2026-08-25
> **기준 문서:** Event Master Agent 설계 · Magic Layer Agent 설계 · Policy Engine 설계 · [Policy] Signal → Delta 규칙
> **관련 Issue:** #88 (Slice 5 — Event Master·Magic·캠페인·WebSocket 통합)

## 0. 개요 및 목적

Slice 5 통합(`Event Master → Magic Layer → Event/Effect → Agent Context → Agent/State/Memory → REST/WebSocket → Frontend`)을 위한 데이터 계약과 완료 기준을 확정한다.

**적용 원칙:** 문서 간 표현이 다를 경우 Policy Engine 설계(v1.2) / Signal→Delta 규칙(v0.6)을 최우선 기준으로 하고, 그 다음 Magic Layer 설계(v0.4), Event Master 설계 순으로 따른다. WebSocket 문서(07-31, 5개 문서 중 최고령)의 payload 예시는 사용하지 않으며, 아래 §4에서 정의하는 스키마로 대체한다.

---

## 1. Event 데이터 계약


Event Master가 매 tick 생성하는 일반 Event의 스키마는 다음과 같다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| event_type | str | `GROUP_PROJECT` `MEETING` `CLASS` `EXAM` `MT` `FESTIVAL` `STUDENT_COUNCIL`(예정) `RANDOM_INCIDENT` |
| title, description | str | 세계관 서술 |
| participant_agent_ids | list[int] | 참여 Agent |
| location | str | 장소 |
| tick | int | 발생 tick |
| source | str | `event_master` |
| impact_level | str | `low` / `medium` / `high` |
| importance | int | 아래 매핑 규칙에 따라 계산 |
| expected_effects | object | 참고용 preview. Policy Engine은 실제 delta 계산에 사용하지 않음 |

### RANDOM_INCIDENT 정의

`RANDOM_INCIDENT`는 Event Master가 생성하는 일반 Event 타입이다.

- 반드시 `event_subtype`을 가진다.
- 실제 효과는 Event Policy Registry에 등록된 `event_subtype` 규칙으로 결정된다.
- Magic Layer의 `special_events` (`STUDENT_MISSING`, `CURSE_SPREAD`, `MAGIC_EXPLOSION`, `RITUAL_FAILURE`, `MAGICAL_DISCOVERY`)와는 별도 경로이다.
- `special_event`는 `RANDOM_INCIDENT`로 변환하지 않는다.
- Slice 5에서는 일반 Event 경로와 Magic Event 경로를 분리하여 처리한다.

### impact_level ↔ importance 매핑

| impact_level | importance |
| --- | --- |
| low | 30 |
| medium | 50 |
| high | 80 |

구현체는 반드시 위 매핑을 사용한다.

**Event Policy Registry 기본 효과 (참여 Agent 대상, Signal→Delta 규칙 §7):**

| event_type | 기본 효과 |
| --- | --- |
| CLASS | stress +1 |
| GROUP_PROJECT | stress +3 |
| EXAM | stress +8, fatigue +5 |
| MEETING | satisfaction +2 |
| MT | satisfaction +5, fatigue +5, hunger +3 |
| FESTIVAL | satisfaction +6, fatigue +4, hunger +3 |
| RANDOM_INCIDENT | 등록된 event_subtype 규칙 적용 |

관계 변화(trust/affection 등)는 Event 기본 효과에 포함되지 않으며, 참여 Agent의 Reaction(typed RelationshipSignal)으로만 발생한다.

---

## 2. Magic 데이터 계약

Magic Layer는 `converted_events`(일반 Event 세계관 변환)와 `special_events`(특수 사건 저장 후보)를 반환한다. 효과는 항상 `{target, direction}` 방향 정보만 포함하며 숫자는 포함하지 않는다.

**특수 사건 발생 조건 및 우선순위 (Magic Layer 설계 §3.2.1, §3.2.2):**

| 우선순위 | event_subtype | 발생 조건 | Registry 확정 효과 (Signal→Delta §8.1) |
| --- | --- | --- | --- |
| 1 | STUDENT_MISSING | stress ≥ 90이 최근 10 tick 중 10회 이상 지속 | 대상 MISSING 상태, 주변 STRESS_UP/MEDIUM |
| 2 | CURSE_SPREAD | CURSED 상태 Agent와 접촉 | 대상 SATISFACTION_DOWN/HIGH, MOOD_DOWN/HIGH |
| 3 | MAGIC_EXPLOSION | 장소 내 학생 3명 이상 중 80% 이상 fatigue ≥ 80 | 참여 FATIGUE_UP/HIGH, STRESS_UP/HIGH |
| 4 | RITUAL_FAILURE | 참여자 4명 이상 + 관계 상태 나쁨 | 참여 STRESS_UP/HIGH |
| 5 | MAGICAL_DISCOVERY | 위 4개 후보 없음 + 교수·학생 각 1명 이상 연구실 존재 | 발견자 SATISFACTION_UP/HIGH, MOOD_UP/MEDIUM |

**지속 상태 duration (Task 0 확정, Signal→Delta 규칙 §15 반영 대상):**

| 상태 | duration_ticks | 해제 조건 |
| --- | --- | --- |
| STUDENT_MISSING (INACTIVE_TEMPORARY) | 3 | 자동 만료 (`inactive_until_tick` 도달) |
| CURSED | 3 | 자동 만료 (`cursed_until_tick` 도달), 조건부 해제 없음 |

**최초 CURSED 상태 생성 규칙 (Task 0 확정):**

STUDENT_MISSING 재활성화 시점에 시스템 로직이 결정론적으로 CURSED를 부여한다. LLM/확률 판단 없음.

```
Tick N   : stress 조건 충족 → STUDENT_MISSING
           Commit: active_status=INACTIVE_TEMPORARY, inactive_until_tick=N+3
Tick N+3 : 만료 판정 → ACTIVE 복귀 + CURSED=true, cursed_until_tick=N+6
Tick N+4~N+6 : 접촉 시 CURSE_SPREAD 후보 발생 가능
Tick N+6 : CURSED 자동 해제
```


---

## 3. Context 데이터 계약

Event Master가 참여 후보 선정에 사용하는 `agent_summaries`(L1) 필드는 Event Master 설계 §3.1, §6.3 기준으로 다음을 현재 계약으로 사용한다.

| L1 필드 | 용도 |
| --- | --- |
| agent_id, name, role | 참여 후보 식별 |
| major_id, year | 전공·학년 맥락 |
| active_status, current_location_id | 참여 가능 여부·장소 조건 |
| mood, stress, fatigue | 상태 조건 판단 |

`relationship_summaries`는 MEETING 후보 선정에만 사용한다. 이 필드 목록은 Task 2(Agent별 Context 분리, 가윤)의 Context Assembler 구현과 함께 최종 확정되며, Task 0은 이 표를 Slice 5 착수 시점의 작업 기준으로 확정한다.

---

## 4. WebSocket 데이터 계약

Commit 성공 후 `tick_completed` 메시지로 전 클라이언트에 broadcast한다. Payload는 Policy Engine `ConflictResolutionResult.resolved_effects` 구조를 그대로 따른다 (REST 응답과 필드 동일, §5 참고).

```json
{
  "type": "tick_completed",
  "run_id": "sim-20260721-01",
  "tick_number": 42,
  "block": "afternoon",
  "policy_version": "policy-mvp-0.4",
  "resolver_version": "resolver-mvp-0.1",
  "resolution_id": "...",
  "events": [
    {"event_type": "GROUP_PROJECT", "title": "...", "participant_agent_ids": [3, 7]}
  ],
  "resolved_effects": [
    {
      "target_type": "RELATIONSHIP",
      "source_agent_id": 3,
      "target_agent_id": 7,
      "metric": "trust",
      "before": 21,
      "applied_delta": 3,
      "after": 24
    },
    {
      "target_type": "AGENT_STATE",
      "source_agent_id": 3,
      "target_agent_id": null,
      "metric": "fatigue",
      "before": 40,
      "applied_delta": 5,
      "after": 45
    }
  ]
}
```

클라이언트→서버 방향(`set_persona` 등 사용자 개입)은 Slice 5 범위에 포함하지 않는다.

### events 필드 계약

`events` 배열은 Event Master 및 Magic Layer 처리 결과가 Commit된 최종 Event 객체 목록이다.

각 Event는 §1 Event 데이터 계약에서 정의한 전체 필드를 포함한다.

예시 payload의 Event 객체는 가독성을 위해 일부 필드만 표시하였으며 실제 전송 시 다음 필드가 모두 포함된다.

```json
{
  "event_type": "...",
  "title": "...",
  "description": "...",
  "participant_agent_ids": [1, 2],
  "location": "...",
  "tick": 42,
  "source": "event_master",
  "impact_level": "high",
  "importance": 80,
  "expected_effects": {}
}
```

Frontend는 §1 Event 계약을 기준으로 구현한다.

---

## 5. REST · WebSocket 정합성 기준

1. 단일 진실 소스: REST와 WebSocket 모두 Commit 이후 저장값을 그대로 전송한다.
2. delta 표현 통일: `{metric, before, applied_delta, after}`.
3. 버전 필드 포함: `policy_version`, `resolver_version`, `resolution_id` 를 REST/WS 모두에 포함한다.
4. WebSocket은 알림 채널이며 진실의 원천은 REST 저장 결과이다.

### Task 3 저장 경계 (#103)

- 참여 Agent ID는 실제 DB와 동일한 UUID를 사용한다 (위 정수 예시는 설명용).
- CURSED 기간은 Task 0의 3 Tick 계약을 따른다. 이전 Policy snapshot의 미확정 표기보다 이 계약을 적용한다.
- `persist_event_batch(session, batch)`는 내부 서버용 저장 인터페이스다. HTTP 쓰기 API로 노출하지 않는다.
- 일반 Event와 Magic 특수 Event를 구분해 `events`/`event_participants`에 저장한다. Magic은 `random_incident`로 변환하지 않는다.
- 확정 State delta만 받으며 `before`, `requested_total`, `applied_delta`, `after`, 기여 effect ID와 버전을 저장한다. preview로 수치를 계산하지 않는다.
- Memory는 생성된 후보를 저장할 뿐 새 내용을 생성하지 않는다. Event·Agent·Location은 같은 Simulation이어야 하고 Memory 작성자는 해당 Event 참여자여야 한다.
- `(simulation_id, tick_number)`당 동일 입력은 재저장하지 않는다. 다른 입력의 재사용과 stale State는 오류다.
- 저장 함수는 flush만 수행한다. 상위 Tick transaction이 Runtime·관계·현재 Tick과 함께 commit/rollback한다. 실패 예외를 삼키고 commit하면 안 된다.
- `GET /v1/simulations/{simulation_id}/event-results/{tick_number}`는 저장된 결과를 반환한다. JWT 401, 비소유자 403, 없는 Simulation/결과 404.
- 응답의 `events`, `resolved_effects`, `memories`, `agent_statuses`는 해당 Tick의 저장 snapshot이다. WS 발행은 commit 성공 후 이 저장값을 사용한다.
- TODO(#101/#105): Event Master/Magic 및 Resolver 결과를 이 입력 계약에 연결하고, lease/fence 검증·Tick 진행·WS 발행을 상위 통합 경계에서 수행한다. Task 3은 Scheduler/Runtime 선택 로직을 변경하지 않는다.

#### 호출 순서 및 검증 증적 (2026-08-27)

1. 상위 Commit 경계에서 lease/fence 검증 후 `persist_event_batch(session, EventBatch(...))` 호출.
2. `tick_number`는 DB의 `current_tick + 1`. State는 아직 적용하지 않은 확정 delta를 전달한다. 기존 `evaluate_and_apply_policy`와 같은 delta를 두 번 적용하지 않는다.
3. 같은 transaction 안에서 나머지 Runtime/Relationship 저장과 `current_tick` 진행 후 commit. 어느 단계든 예외면 전체 rollback.
4. 성공 후 새 Session에서 `get_event_result`를 읽어 WS에 전달. 반환 payload를 commit 전에 외부로 발행하지 않는다.

Event ID는 배치에 저장할 신규 Event UUID이며, 기존 fixture Event 행을 덮어쓰지 않는다. 지속 일정을 재사용하는 상위 로직은 해당 Tick의 발생 Event를 별도로 식별해야 한다.
`missing_agent_ids`는 Policy/Resolver가 승인한 실종 대상만 전달하며, STUDENT_MISSING 참여자 중 Student여야 한다. 저장 계층은 발생 조건을 재계산하지 않는다.
만료 상태는 Commit 시점에 저장된다. Task 5는 동일 만료 규칙을 Runtime 대상 선정용 snapshot에도 반영해야 하며, Task 3만으로 해당 선정 로직이 연결되지는 않는다.

검증 환경: 개발 DB와 분리된 로컬 PostgreSQL `magic_academy_slice5_task3`.

- `alembic upgrade head`: 빈 DB부터 `20260827_0103`까지 성공.
- `alembic check`: 모델/migration drift 없음.
- `pytest -q -p no:cacheprovider tests/test_event_persistence.py tests/test_schema_models.py`: 21 passed.
- DB 환경변수 없이 전체 `pytest -q -p no:cacheprovider`: 229 passed, 65 skipped (DB 연동 테스트 등; 전체 DB 검증 완료를 의미하지 않음).
- 신규 PostgreSQL 검증: 실제 JWT REST 조회·401/403/404, 동일 입력 재시도, 동시 transaction, State stale 및 타 Simulation 참조 거부, Memory 10개 제한, repository 실패·DB 제약 실패·후속 단계 실패 rollback, 실종/저주 만료.
- migration downgrade는 실행하지 않음. Task 1/5 연결·WS 정합성 및 Slice 5 E2E/PASS는 미검증.

---

## 6. Tick 10 E2E 검증 시나리오 및 완료 기준

**시나리오 최소 커버리지:**

- [ ] 예정 Event 1건 (CLASS 또는 EXAM)
- [ ] 동적 일반 Event 1건 (GROUP_PROJECT 또는 MEETING)
- [ ] MAGIC_EXPLOSION 또는 RITUAL_FAILURE 1건
- [ ] STUDENT_MISSING → 재활성화 → CURSED 부여 전체 사이클 1건 (§2 로직 검증)
- [ ] CURSE_SPREAD 1건 (위 CURSED Agent 접촉으로 발생)
- [ ] TALK 충돌 케이스 1건 (상호 TALK vs 제3자 요청 → WAIT_FALLBACK)
- [ ] 관계 라벨 전이 1건 (FRIEND 진입 또는 이탈)
- [ ] Reflection 적격 Event 1건 (importance ≥ 70)

**Reflection 적격 조건 참고**

Reflection 적격 조건은 `importance >= 70`이다.

현재 Task 0 계약의 importance 매핑(30 / 50 / 80) 기준으로 Reflection 적격 Event는 `high(80)` 이벤트만 해당한다.

**완료 기준:**

- [ ] 각 단계 산출물이 추적 가능하다: Event Master → Magic Layer → Policy effect_candidates → Resolver resolved_effects → Commit → WebSocket → Frontend
- [ ] REST 재조회 결과와 WebSocket push 결과가 필드 단위로 일치한다 (diff = 0)
- [ ] §2의 STUDENT_MISSING/CURSED 사이클이 Commit까지 정상 완료된다
- [ ] Inspector UI에서 위 8개 케이스가 모두 정상 렌더링된다


---
