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

Event Master의 L1 `agent_summaries`와 Agent Runtime의 `nearby_agents`는 용도가 다르다. L1은 Event Master가 Event 참여 후보를 선정하기 위한 전체 후보 snapshot이고, `nearby_agents`는 각 observer Agent가 현재 관찰할 수 있는 Agent만 포함하는 Runtime 전용 부분집합이다. Event Master의 `relationship_summaries`는 MEETING 후보 선정에만 사용한다.

Agent Runtime의 `nearby_agents`는 다음 `AgentSummary` 필드를 사용한다.

| Runtime AgentSummary 필드 | 설명 |
| --- | --- |
| agent_id, name, agent_type | 관찰 가능한 Agent 식별 |
| active_status, current_location_id | 활성 상태와 현재 위치 |
| mood, stress, fatigue | Runtime 판단용 상태 요약 |

Agent Runtime의 `relationships`는 다음 `RelationshipSummary` 필드를 사용한다.

| Runtime RelationshipSummary 필드 | 설명 |
| --- | --- |
| source_agent_id, target_agent_id | 방향성 관계의 observer와 visible Agent |
| affection, closeness, trust | 호감도·친밀도·신뢰도 |
| tension, rivalry, dependency | 긴장도·경쟁·의존도 |

Runtime Context 가시성 규칙은 다음과 같다.

- `nearby_agents`에는 observer와 같은 위치의 active Agent만 포함한다. observer 자신, 비활성 Agent, 다른 위치 Agent는 제외한다.
- `relationships`에는 `observer → visible Agent` 방향의 관계만 포함한다.
- Event는 observer가 participant이거나 Event 위치가 observer의 현재 위치와 같을 때 노출한다.
- mandatory Schedule Event는 위 Event 가시성 조건과 관계없이 항상 노출한다. non-mandatory Schedule Event에는 이 예외를 적용하지 않는다.

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
