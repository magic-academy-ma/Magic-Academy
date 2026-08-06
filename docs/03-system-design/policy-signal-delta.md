---
title: "[Policy] Signal → Delta 규칙"
source: confluence/05_TECH/[Policy] Signal → Delta 규칙
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/19628033
status: draft
visibility: public
updated: 2026-08-06
source_updated: 2026-08-05
---

# [Policy] Signal → Delta 규칙

> **상태:** Draft
> **작성자:** @김가윤
> **담당자:** @김가윤
> **작성일 / 최종 수정일:** 2026-07-29 / 2026-08-05
> **기준 문서:** [Policy Engine 설계](https://jehye.atlassian.net/wiki/spaces/MA/pages/14090319) · [Agent Runtime 설계](https://jehye.atlassian.net/wiki/spaces/MA/pages/11894790) · [Magic Layer Agent 설계](https://jehye.atlassian.net/wiki/spaces/MA/pages/9371768) · [Tick Engine 스펙](https://jehye.atlassian.net/wiki/spaces/MA/pages/12910622)
> **버전:** v0.5
> **대상 Policy 버전:** `policy-mvp-0.4`

## 0. 개요 및 목적

이 문서는 Agent Runtime과 Magic Layer가 반환한 정성적 결과를 Policy Engine이 상태·관계 변화 후보로 변환할 때 직접 조회하는 단일 실행 규칙표다.

- **목적**: 정성적 signal과 Event 제안을 구현자가 동일한 delta 규칙으로 재현할 수 있도록 단일 기준표를 제공한다.
- **범위**: 입력 계약, 관계·상태·Action·Event 변환, 중복 제거, clamp, Conflict Resolver 경계와 `policy_version` 기록 기준을 다룬다.

## 1. 기준 문서와 적용 우선순위

| 범위 | 기준 문서 |
| --- | --- |
| Policy Engine의 역할, 파이프라인 위치, 입출력 구조 | `Policy Engine 설계` |
| signal·Action·Event별 delta, 허용 범위, Event Policy Registry, `policy_version` | 이 문서 |
| Intent 충돌, 후보 합산, 최종 clamp, Memory 종속성 | `Policy Engine 설계`의 Conflict Resolver 절 |
| 특수 사건의 발생 조건과 효과 방향 | `Magic Layer Agent 설계` |
| Commit과 Tick 재실행 순서 | `Tick Engine 스펙` |

구현자는 구체적인 숫자와 지속 기간을 이 문서만 참조한다. 상위 문서나 예시 코드에 동일한 값이 남아 있더라도 이 문서와 다르면 이 문서를 우선한다. 컴포넌트의 책임 경계와 실행 순서는 `Policy Engine 설계`를 우선한다.

이 문서의 규칙을 코드 또는 설정 파일로 옮길 때에는 하나의 불변 Registry snapshot으로 배포한다. Tick 하나에서 서로 다른 `policy_version`의 규칙을 섞어 사용하지 않는다.

`policy-mvp-0.4`은 본 문서가 승인되고 Registry가 배포된 뒤 활성화한다.

## 2. 입력 계약

### 2.1 필수 입력

| 입력 | 출처 | 사용 방식 |
| --- | --- | --- |
| `signal` | Agent Runtime 또는 검증된 Event effect | 변경할 metric과 증감 방향 결정 |
| `intensity` | Agent Runtime 또는 Event Policy Registry | LOW / MEDIUM / HIGH 기본 delta 선택 |
| `action_type` | Agent Runtime Intent | 행동 자체의 생리적 기본 효과 조회 |
| `event_type`, `event_subtype` | Event Master / Magic Layer 후보 | 등록된 Event 효과와 상태 전이 조회 |
| 현재 수치 | Tick 시작 world snapshot | `before`, `after_preview`, 최종 clamp 계산에 사용 |
| `source_agent_id`, `target_agent_id` | Runtime 결과 또는 Event 대상 | 관계 edge 방향과 상태 대상 결정 |
| `run_id`, `tick_number`, `policy_version` | TickOrchestrator (`run_tick()`) | 재현성, 중복 제거, 규칙 버전 검증 |

현재 수치는 기본 delta의 크기를 감쇠하거나 증폭하는 데 사용하지 않는다. 모든 후보를 합산한 뒤 허용 범위에서 최종 clamp할 때만 사용한다.

### 2.2 허용 intensity

`LOW`, `MEDIUM`, `HIGH`만 허용한다. 누락되거나 알 수 없는 값이면 해당 effect만 거부한다. Runtime 또는 Magic Layer가 숫자 delta를 직접 반환하면 숫자는 무시하고 warning을 남긴다.

## 3. 고정 변환 순서

1. `policy_version`, schema, Agent·Event 참조를 검증한다.
2. `action_type`의 기본 효과 후보를 만든다.
3. Agent Reaction의 `signal × intensity`를 delta 후보로 변환한다.
4. `event_type + event_subtype`으로 Event Policy Registry를 조회한다.
5. Magic Layer 효과 방향을 Registry의 허용 signal·intensity와 대조한다.
6. 같은 Policy 입력 안의 완전 동일 후보를 `effect_source_key`로 제거한다.
7. `before`와 설명용 `after_preview`를 붙여 Conflict Resolver에 반환한다.
8. Conflict Resolver가 실패 Intent 종속 후보를 제거하고, 여러 경로의 동일 원인을 중복 제거한다.
9. Conflict Resolver가 target·metric별 승인 delta를 합산한 뒤 한 번만 clamp한다.
10. Commit이 Resolution Plan과 적용된 `policy_version`을 원자적으로 저장한다.

Policy Engine은 계산 후보만 반환하며 DB에 직접 쓰지 않는다.

## 4. 관계 signal 규칙

관계 변화의 기본 절댓값은 LOW 1, MEDIUM 3, HIGH 5다.

| signal | target metric | LOW | MEDIUM | HIGH |
| --- | --- | --- | --- | --- |
| `TRUST_UP` | trust | +1 | +3 | +5 |
| `TRUST_DOWN` | trust | -1 | -3 | -5 |
| `AFFECTION_UP` | affection | +1 | +3 | +5 |
| `AFFECTION_DOWN` | affection | -1 | -3 | -5 |
| `CLOSENESS_UP` | closeness | +1 | +3 | +5 |
| `CLOSENESS_DOWN` | closeness | -1 | -3 | -5 |
| `TENSION_UP` | tension | +1 | +3 | +5 |
| `TENSION_DOWN` | tension | -1 | -3 | -5 |
| `RIVALRY_UP` | rivalry | +1 | +3 | +5 |
| `RIVALRY_DOWN` | rivalry | -1 | -3 | -5 |
| `DEPENDENCY_UP` | dependency | +1 | +3 | +5 |
| `DEPENDENCY_DOWN` | dependency | -1 | -3 | -5 |

### 4.1 방향성

Runtime Reaction의 관계 변화는 다음 방향으로 적용한다.

```
Runtime 결과를 생성한 Agent(source_agent_id)
→ Reaction의 대상 Agent(target_agent_id)
```

예를 들어 A가 B와 대화한 뒤 `TRUST_UP + MEDIUM`을 반환하면 A가 B를 신뢰하는 `A → B` edge의 `trust`에 `+3` 후보를 만든다. `B → A`는 별도 edge이며 B의 Runtime 결과 또는 명시적인 Event 규칙 없이는 함께 변경하지 않는다.

target이 없거나 유효하지 않거나 자기 자신이면 해당 관계 effect를 거부한다.

## 5. 상태 signal 규칙

상태 변화의 기본 절댓값은 LOW 2, MEDIUM 5, HIGH 8이다.

| signal | target metric | LOW | MEDIUM | HIGH |
| --- | --- | --- | --- | --- |
| `HUNGER_UP` | hunger | +2 | +5 | +8 |
| `HUNGER_DOWN` | hunger | -2 | -5 | -8 |
| `FATIGUE_UP` | fatigue | +2 | +5 | +8 |
| `FATIGUE_DOWN` | fatigue | -2 | -5 | -8 |
| `STRESS_UP` | stress | +2 | +5 | +8 |
| `STRESS_DOWN` | stress | -2 | -5 | -8 |
| `SATISFACTION_UP` | satisfaction | +2 | +5 | +8 |
| `SATISFACTION_DOWN` | satisfaction | -2 | -5 | -8 |
| `MOOD_UP` | mood | +2 | +5 | +8 |
| `MOOD_DOWN` | mood | -2 | -5 | -8 |

Runtime Reaction의 상태 signal은 Runtime 결과를 생성한 Agent 본인에게 적용한다. Event·Magic 효과는 Event Policy Registry가 지정한 참여자 또는 관찰자에게 적용한다.

## 6. Action 기본 효과

Action 기본 효과는 행동 자체의 생리적 비용과 회복만 표현한다. 관계 변화와 Event 고유 효과는 포함하지 않는다.

| `action_type` | 상태 기본 delta |
| --- | --- |
| `ATTEND_CLASS` | hunger +2, fatigue +3 |
| `TEACH_CLASS` | hunger +2, fatigue +4, stress +1 |
| `STUDY` | hunger +2, fatigue +4, stress +1 |
| `TALK` | fatigue +1 |
| `EAT` | hunger -20, satisfaction +2 |
| `MOVE` | hunger +1, fatigue +2 |
| `REST` | fatigue -15, stress -5 |
| `PARTICIPATE_EVENT` | hunger +2, fatigue +3 |
| `HELP` | fatigue +2, satisfaction +2 |
| `AVOID` | 기본 효과 없음 |
| `WAIT` | hunger +2, fatigue +1 |

Intent가 Conflict Resolver에서 실패하거나 `WAIT_FALLBACK`으로 바뀌면 원래 Action의 효과는 제거하고 최종 `WAIT` 효과만 적용한다. 성격 보정계수는 항상 1.0이며 Action 기본 효과에도 MBTI 보정을 적용하지 않는다.

## 7. 일반 Event Policy Registry

| `event_type` | 참여 Agent 기본 효과 | 비고 |
| --- | --- | --- |
| `CLASS` | stress +1 | Action 생리 효과와 별도 |
| `GROUP_PROJECT` | stress +3 | 관계 변화는 Reaction으로만 계산 |
| `EXAM` | stress +8, fatigue +5 | 성적·장학금 효과는 MVP 이후 |
| `MEETING` | satisfaction +2 | 관계 변화는 Reaction으로만 계산 |
| `MT` | satisfaction +5, fatigue +5, hunger +3 | |
| `FESTIVAL` | satisfaction +6, fatigue +4, hunger +3 | |
| `RANDOM_INCIDENT` | 등록된 `event_subtype` 규칙 | 자유 숫자 입력 금지 |

MVP 일반 Event는 위 7종으로 확정한다. `STUDENT_COUNCIL` Event는 3단계 범위이므로 MVP Registry에 등록하지 않는다.

필수 `CLASS` 또는 `EXAM`을 정당한 충돌 일정 없이 `AVOID`한 경우 일정 위반 효과로 stress +5, satisfaction -3 후보를 추가한다.

## 8. Magic Layer Event Policy Registry

Magic Layer는 사건 발생 조건, 대상과 효과 방향만 반환한다. Magic Event의 `signal`과 `intensity`는 Event Policy Registry가 결정하며, Magic Layer는 숫자 delta, 상태 지속 기간, `inactive_until_tick`을 직접 결정하지 않는다.

### 8.1 사건별 변환 규칙

| `event_subtype` | Registry가 허용하는 기본 효과 | 지속 상태 |
| --- | --- | --- |
| `MAGIC_EXPLOSION` | 참여 Agent `FATIGUE_UP/HIGH`, `STRESS_UP/HIGH` | 없음 |
| `CURSE_SPREAD` | 접촉 대상 `SATISFACTION_DOWN/HIGH`, `MOOD_DOWN/HIGH` | `CURSED`는 별도 등록된 duration·해제 규칙 필요 |
| `STUDENT_MISSING` | 대상 Agent `MISSING` 상태 후보, 명시된 주변 Agent `STRESS_UP/MEDIUM` | `INACTIVE_TEMPORARY`, 사건별 duration 필요 |
| `RITUAL_FAILURE` | 참여 Agent `STRESS_UP/HIGH` | 없음 |
| `MAGICAL_DISCOVERY` | 발견 Agent `SATISFACTION_UP/HIGH`, `MOOD_UP/MEDIUM` | 없음 |

Registry에 등록되지 않은 관계 효과는 거부하고 warning을 남긴다. Magic Layer가 제안한 effect와 Registry가 다르면 Registry를 우선한다.

### 8.2 `STUDENT_MISSING` 지속 기간과 비활성화

```
Magic Layer → MISSING 상태 추가 후보와 대상 Agent 반환
Event Policy Registry → STUDENT_MISSING에 등록된 duration_ticks 조회
Policy Engine → active_status=INACTIVE_TEMPORARY, inactive_until_tick=current_tick+duration_ticks 변경 후보 계산
Conflict Resolver → 동일 Tick의 충돌·중복 후보를 정리해 Resolution Plan 생성
Commit → active_status와 inactive_until_tick 최종 저장
SimulationTickService → 다음 Tick 시작 시 inactive_until_tick 만료 여부 판정, 만료한 Agent를 ACTIVE로 포함하고 재활성화 후보 생성
Commit → Tick 결과와 함께 ACTIVE 및 inactive_until_tick=null 저장
```

규칙:
1. `STUDENT_MISSING`의 지속 기간은 배포된 Event Policy Registry의 `duration_ticks`만 사용한다.
2. Magic Layer, LLM 출력 또는 요청 payload의 임의 duration은 무시한다.
3. 등록되지 않은 사건 또는 `duration_ticks`가 없는 사건의 임시 비활성화 후보는 `UNREGISTERED_TEMPORARY_INACTIVE_POLICY`로 거부한다.
4. 일반 임시 비활성화의 기본 상한은 3 Tick이다.
5. `STUDENT_MISSING`은 `EVENT_OVERRIDE` 대상이다. 실제 `duration_ticks`는 팀 확정 전까지 미등록 상태로 두며, 확정 전에는 `STUDENT_MISSING` 비활성화를 Commit할 수 없다.
6. Policy Engine은 상태 변경 후보만 반환하고 DB에 직접 쓰지 않는다.
7. `inactive_until_tick <= current_tick`이면 해당 Tick의 Runtime 대상 선별에서는 ACTIVE로 취급한다.

## 9. 동일 원인의 중복 효과 제거

`effect_source_key`는 다음 필드를 정규화해 만든다.

```
run_id + tick_number + cause_type + cause_id + effect_semantics + target_type + source_agent_id + target_agent_id + metric_or_status
```

| 필드 | 예시 |
| --- | --- |
| `cause_type` | ACTION, EVENT, REACTION, WORLD_EFFECT |
| `cause_id` | intent_id, origin_event_id, world_effect_id |
| `effect_semantics` | ACTION_COST, EVENT_BASE, PERSONAL_REACTION, STATUS_TRANSITION |
| `target_type` | AGENT_STATE, RELATIONSHIP, ACTIVE_STATUS |

처리 기준:
- 같은 key와 같은 delta·status 후보가 여러 경로에서 오면 한 건만 유지한다.
- 같은 key인데 delta 또는 duration이 다르면 `ACTION_POLICY·EVENT_POLICY > 검증된 MAGIC_EXPECTED_EFFECT > AGENT_REACTION` 우선순위로 하나만 유지하고 warning을 남긴다.
- 같은 우선순위에서 값이 다르거나 source가 Registry에 등록되지 않았으면 해당 key 그룹 전체를 `CONFLICTING_DUPLICATE_EFFECT`로 거부한다.
- A→B와 B→A는 관계 edge가 다르므로 중복이 아니다.

## 10. Conflict Resolver와 책임 경계

| 작업 | Policy Engine | Conflict Resolver | Commit |
| --- | --- | --- | --- |
| `signal × intensity` 변환 | 담당 | 하지 않음 | 하지 않음 |
| Action·Event Registry 조회 | 담당 | 하지 않음 | 하지 않음 |
| 단일 후보 schema·target 검증 | 담당 | 재검증 | DB 제약 확인 |
| TALK·자원·Intent 충돌 | 하지 않음 | 담당 | 확정 결과만 저장 |
| 실패 Intent 종속 effect 제거 | 종속 ID 부여 | 담당 | 승인 후보만 저장 |
| 동일 원인 중복 제거 | 단일 입력 내부 | 전체 입력 경로 | `resolution_id` 중복 차단 |
| delta 합산과 최종 clamp | 하지 않음 | 담당 | 계산하지 않음 |
| `active_status`·`inactive_until_tick` 저장 | 후보만 생성 | 충돌 확정 | 담당 |

## 11. 범위와 clamp

| metric | 최소 | 최대 |
| --- | --- | --- |
| affection | -100 | 100 |
| closeness | -100 | 100 |
| trust | -100 | 100 |
| tension | 0 | 100 |
| rivalry | 0 | 100 |
| dependency | 0 | 100 |
| hunger | 0 | 100 |
| fatigue | 0 | 100 |
| stress | 0 | 100 |
| satisfaction | 0 | 100 |
| mood | -100 | 100 |

최종 clamp는 Conflict Resolver가 다음 순서로 정확히 한 번 적용한다.

```
requested_total = sum(승인되고 중복 제거된 delta)
after = clamp(before + requested_total, metric_min, metric_max)
applied_delta = after - before
```

Policy Engine의 `after_preview`는 단일 후보 설명용이며 Commit 값이 아니다.

## 12. `policy_version` 기록 기준

Tick 결과에는 실제로 평가에 사용한 배포 Registry의 `policy_version`을 한 개만 기록한다.

다음 변경은 실행 결과를 바꾸므로 `policy_version`을 올린다:
- signal별 LOW / MEDIUM / HIGH 숫자
- Action 또는 Event 기본 효과
- 허용 Event·signal 목록
- Event 지속 기간, 비활성화 상한과 예외
- metric 최소·최대 범위
- 중복 제거 key 또는 우선 규칙

오탈자, 설명, 링크, 예시만 바꾸고 실행 Registry가 같으면 `policy_version`은 올리지 않는다.

알 수 없거나 아직 배포되지 않은 `policy_version`이면 Tick 전체를 `REJECTED`로 처리하고 Commit하지 않는다.

## 13. 실패 코드

| 코드 | 처리 |
| --- | --- |
| `UNKNOWN_POLICY_VERSION` | 전체 Tick 후보 REJECTED, Commit 금지 |
| `UNKNOWN_SIGNAL_OR_INTENSITY` | 해당 effect만 거부 |
| `INVALID_RELATIONSHIP_TARGET` | 해당 관계 effect 거부 |
| `UNREGISTERED_EVENT_POLICY` | Event expected effect 거부 |
| `UNREGISTERED_TEMPORARY_INACTIVE_POLICY` | 임시 비활성화 후보 거부 |
| `CONFLICTING_DUPLICATE_EFFECT` | 같은 source key에서 우선순위가 같거나 source가 미등록인 상충 후보 그룹 전체 거부 |
| `OUT_OF_RANGE_REQUEST` | 후보는 유지하되 Resolver 최종 clamp 후 requested/applied 모두 기록 |

## 14. 필수 테스트

1. 모든 관계·상태 signal의 LOW / MEDIUM / HIGH 조합이 표와 같은 delta를 만든다.
2. A→B와 B→A 관계 변화가 별도 edge로 계산된다.
3. 현재값이 달라도 clamp 전 기본 delta는 동일하다.
4. 서로 다른 원인의 반대 delta는 합산되고, 같은 원인의 동일 후보는 한 번만 반영된다.
5. 같은 원인의 상충 후보는 Registry source 우선순위에 따라 하나만 유지된다.
6. 같은 우선순위의 상충 후보 또는 미등록 source 충돌은 해당 key 그룹 전체가 거부된다.
7. 실패 Intent의 Action·Reaction effect는 제거된다.
8. 모든 승인 effect를 합산한 뒤 metric별 clamp가 정확히 한 번 적용된다.
9. Magic Layer가 숫자 또는 duration을 반환해도 Registry 값만 사용한다.
10. 등록되지 않은 Event의 임시 비활성화는 Commit되지 않는다.
11. `STUDENT_MISSING`은 일반 3 Tick 상한이 아니라 등록된 `EVENT_OVERRIDE` 값을 사용한다.
12. `inactive_until_tick <= current_tick`인 Agent는 Runtime 대상에 다시 포함되고 재활성화가 batch commit된다.
13. 같은 입력과 같은 `policy_version`은 같은 정렬 결과를 만든다.
14. 배포되지 않은 `policy_version`은 DB 변경을 만들지 않는다.

## 15. 미결정 사항

| 항목 | 상태 | 확정 주체 |
| --- | --- | --- |
| `STUDENT_MISSING.duration_ticks` 실제 값 | 미확정. 등록 전 비활성화 거부 | 팀 리뷰 |
| `CURSED` 상태의 duration 및 해제 조건 | 미확정. 지속 상태 등록 전 상태 전이 거부 | 팀 리뷰 |

미결정 값을 Magic Layer, LLM 또는 구현자 임의 상수로 대체하지 않는다.

## 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
| --- | --- | --- | --- |
| v0.1 | 2026-07-29 | 기존 Policy Engine의 signal·Action·Event 수치 규칙을 단일 하위 규칙표로 분리하고, 방향성·중복 제거·최종 clamp·policy_version 기준과 Magic Event Registry를 정리했다. STUDENT_MISSING은 사건별 duration override를 사용하고, 실제 기간 미등록 시 임시 비활성화를 거부하도록 정의했다. | 김가윤 |
| v0.2 | 2026-08-03 | 공통 문서 템플릿에 맞게 중복 본문 제목을 제거하고 메타데이터·개요 및 목적 형식을 통일했다. | 김가윤 |
| v0.3 | 2026-08-03 | MVP 일반 Event를 7종으로 확정하고, 동일 원인의 상충 후보는 Registry source 우선순위로 선택하되 동순위·미등록 충돌은 그룹 거부하도록 수정했다. Magic Event intensity를 확정 Registry 값으로 정리하고 실행 정책 버전을 policy-mvp-0.4로 올렸다. | 김가윤 |
| v0.4 | 2026-08-05 | 재현성·중복 제거·규칙 버전 검증의 실행 주체를 Tick Engine의 `run_tick()`으로 정합화했다. | Codex |
| v0.5 | 2026-08-05 | 재현성·중복 제거·규칙 버전 검증의 실행 조율 주체를 별도 `TickOrchestrator.run_tick()`으로 변경했다. | Codex |
