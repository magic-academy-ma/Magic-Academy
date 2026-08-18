---
title: "[요구사항] 시뮬레이션 파라미터 설정"
source: confluence/03_REQUIREMENTS/simulation-parameters.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/21364758
status: review
visibility: public
updated: 2026-08-06
source_updated: 2026-08-06
---

**기준 문서:** [Event Master Agent 설계](https://jehye.atlassian.net/wiki/spaces/MA/pages/10878982)

---

## 0. 개요 및 목적

**상위 기준:** PRD · 핵심 기능 정의 FR-12  
**상태:** 검토 중  
**범위:** MVP

* **목적**: 시뮬레이션 파라미터 설정의 요구사항 및 적용 범위를 정의한다.
* **범위**: 일반 Event 파라미터와 Magic Layer 초기 파라미터를 다룬다.

## 1. 목적

사용자가 일반 Event의 빈도·영향도를 실행 전과 실행 중에 조정하고, Magic Layer의 초기 조건을 실행 전에 정할 수 있도록 한다.

## 2. 초기 파라미터

| 구분 | 파라미터 | 저장값 | 설명 | 기본값 |
| --- | --- | --- | --- | --- |
| 일반 Event | `event_frequency` | `low` / `medium` / `high` | 동적 일반 Event의 생성 빈도 | `medium` |
| 일반 Event | `event_impact` | `low` / `medium` / `high` | 일반 Event가 상태·관계에 미치는 영향의 크기 | `medium` |
| Magic Layer | `magic_frequency` | low/medium/high | 마법 변환·특수 사건 생성 빈도 | medium |
| Magic Layer | `magic_impact` | low/medium/high | Magic Layer 결과가 상태·관계·world_effect에 미치는 영향의 크기 | medium |
| Magic Layer | Magic ON/OFF | boolean | 해당 실행에서 Magic Layer 호출 여부 | ON |

## 3. 일반 Event 파라미터 시스템 조건

일반 Event 파라미터는 Event Master의 동적 일반 Event 후보 생성과 Policy Engine의 일반 Event 효과 적용에만 사용하며, 마법 특수 사건에는 적용하지 않는다.

### 빈도 기준

`CLASS`, `EXAM`, `MT`, `FESTIVAL`, `STUDENT_COUNCIL`처럼 학사 일정으로 활성화된 예정 Event는 `event_frequency`와 무관하게 생성한다. 빈도 파라미터는 Event Master의 `GROUP_PROJECT`, `MEETING` 동적 일반 Event 생성 여부만 제어한다. `RANDOM_INCIDENT`는 Magic Layer의 마법 특수 사건이므로 일반 Event 빈도 설정의 대상이 아니다.

| 빈도 | 동적 Event 후보 생성 확률 | 하루 최대 생성 수 | Tick당 최대 생성 수 |
| --- | --- | --- | --- |
| `low` | 25% | 1 | 1 |
| `medium` | 50% | 2 | 1 |
| `high` | 75% | 3 | 1 |

1. Tick 시작 시 학사 일정의 예정 Event를 먼저 확정한다.
2. 예정 Event가 3개 이상이면 동적 Event를 생성하지 않는다.
3. 예정 Event가 3개 미만이면 빈도 확률과 일일 상한을 기준으로 동적 Event 후보 생성 여부를 판정한다.
4. 최종 일반 Event 수는 Tick당 0~3개를 넘지 않는다.
5. Replay 재현을 위해 확률 판정은 `simulation_id`, `tick_number`, 해당 Tick의 파라미터 스냅샷을 시드로 사용한다.

### 영향도 기준

| 영향도 | Event importance | 효과 강도 배율 | 참여 Agent 상한 | 동일 참여자 쿨다운 | Reflection 적격 |
| --- | --- | --- | --- | --- | --- |
| `low` | 30 | 0.5 | 2명 | 없음 | 아니오 |
| `medium` | 50 | 1.0 | 4명 | 1 Tick | 아니오 |
| `high` | 80 | 1.5 | 5명 | 3 Tick | 예 |

* Event Master는 Event에 `impact_level`을 기록하고, Policy Engine은 이벤트 유형별 기본 delta에 효과 강도 배율을 적용한다.
* 모든 상태·관계 delta는 Policy Engine의 metric별 허용 범위에서 최종 clamp한다.
* 기본 `REFLECTION_THRESHOLD=0.7`에서는 `high` 영향도 Event만 Reflection 대상이다.
* 쿨다운 중에는 같은 Event 유형에 동일 Agent 조합을 다시 선택할 수 없다. 예정 Event는 학사 일정 우선 원칙에 따라 예외다.
* `high × high` 조합은 허용한다. 단, 동일 Agent의 high 영향도 Event 참여는 하루 최대 1회이며, 초과 후보는 `medium`으로 하향하거나 생성하지 않는다.

## 4. Magic Layer 파라미터 시스템 조건

Magic Layer 파라미터(Magic Layer 빈도, Magic Layer 영향도)는 마법 특수 사건 후보의 생성 여부와 효과 강도를 조절하는 데만 사용하며, 일반 Event의 생성 및 효과에는 적용하지 않는다.

마법 특수 사건 자체의 발생 여부는 world_state가 사건별 조건을 만족하는지로 결정되며, 빈도 파라미터는 조건을 만족한 후보를 실제로 생성할지와 그 상한만 제어한다.

### 빈도 기준

| 빈도 | 조건 충족 후보의 생성 확률 | 하루 최대 생성 수 | Tick당 최대 생성 수 |
| --- | --- | --- | --- |
| low | 25% | 1 | 1 |
| medium | 50% | 2 | 1 |
| high | 75% | 3 | 1 |

* Tick 시작 시 schedule에서 예정 Magic 사건을 먼저 확정한다.
* 예정 Magic 사건 수가 3개 이상이면 새로 생성하지 않는다.
* 최종 Magic 사건 수는 Tick당 0~3개를 넘지 않는다.
* Replay 재현을 위해 확률 판정은 simulation_id, tick_number, 해당 Tick의 파라미터 스냅샷을 시드로 사용한다.

### 영향도 기준

| 영향도 | Magic importance | 효과 강도 배율 | 참여 Agent 상한 | 동일 참여자 쿨다운 |
| --- | --- | --- | --- | --- |
| low | 30 | 0.5 | 2명 | 없음 |
| medium | 50 | 1.0 | 4명 | 1 Tick |
| high | 80 | 1.5 | 5명 | 3 Tick |

* Magic Layer는 impact_level을 기록하고, Policy Engine이 사건 유형별 기본 delta에 효과 강도 배율을 적용한다.
* 모든 상태·관계 delta는 Policy Engine의 metric별 허용 범위에서 최종 clamp한다.
* high × high 조합은 허용하되, 동일 Agent는 하루 최대 1회만 high 영향도 Magic 사건에 참여 가능. 초과 시 참여 Agent 재선정, 불가하면 해당 후보는 생성하지 않는다.
* STUDENT_MISSING처럼 시뮬레이션 영향도가 높은 사건은 `magic_frequency=low, magic_impact=low` 조합에서는 후보로 생성하지 않는다.

## 5. 설정 생명주기

| 항목 | 기준 |
| --- | --- |
| 일반 Event 파라미터 | Draft·실행·일시정지 상태에서 빈도·영향도를 변경할 수 있다. 현재 Tick에는 영향을 주지 않고 다음 Tick의 world state snapshot 생성 전에 원자적으로 반영한다. |
| Tick 실행과 변경 요청 경합 | 현재 Tick은 기존 파라미터 스냅샷으로 완료하고, 변경값은 다음 Tick부터 적용한다. |
| Magic Layer 파라미터·ON/OFF | Draft에서만 저장·변경 가능하며 시작 요청 성공 시 해당 실행의 고정 초기 조건이 된다. |
| Replay | 저장된 Tick 결과(Event·상태·파라미터 스냅샷)를 순서대로 재생한다. Replay 중 Event Master·LLM을 재호출하지 않으며, 원본 설정은 유지한다. |
| 실행 중 변경 제한 | Agent 행동·대사 직접 명령과 User Persona 성격 재설정은 불가하다. |

## 6. 일반 Event 파라미터 변경 이력

실행·일시정지 상태에서 일반 Event 파라미터가 변경되면 `TickOrchestrator`는 다음 정보를 불변 Tick 이력에 기록한다. Tick 시작 시 적용할 `simulation_config` 버전을 TickContext에 고정하고, Commit Service는 실제 사용한 설정 버전을 Tick 결과와 함께 저장한다. Draft 상태의 변경은 실행 전 설정값 갱신으로만 저장하며 Tick 이력을 만들지 않는다.

Tick 실행 중 변경 요청이 승인되어도 현재 Tick은 시작 시 고정한 설정 버전으로 완료하고 변경값은 다음 Tick부터 적용한다. 동일한 적용 시작 Tick에 여러 변경이 승인되면 가장 높은 설정 버전을 사용하되 모든 변경 이력은 보존한다.

| 기록 항목 | 내용 |
| --- | --- |
| 변경 시점 | 변경 요청이 승인된 시각과 당시 완료 Tick 번호 |
| 변경 전·후 값 | `event_frequency`, `event_impact`의 이전 값과 새 값 |
| 적용 시작 Tick | 변경값이 처음 적용되는 Tick 번호 |
| 적용 범위 | 해당 시뮬레이션의 이후 일반 Event 후보 생성과 일반 Event Policy 효과 적용 |
| 설정 버전 | 변경 후 `simulation_config` 버전 |

각 Tick 결과에는 적용된 `simulation_config` 버전을 함께 저장한다. 이를 통해 비교·Replay 시 특정 Tick이 어떤 파라미터로 생성·처리됐는지 추적한다.

## 7. 수용 조건

| ID | 조건 |
| --- | --- |
| AC-01 | Draft 시뮬레이션에서 일반 Event 및 Magic Layer 초기 파라미터를 저장·변경할 수 있다. |
| AC-02 | 시작 성공 후 Magic Layer 파라미터 및 magic on/off는 읽기 전용이며 변경 요청은 거부된다. 일반 Event 파라미터는 실행 중에도 변경할 수 있다. |
| AC-03 | 예정 Event는 `event_frequency`와 무관하게 생성되며, 동적 Event는 설정된 빈도 확률·일일 상한·Tick당 상한을 따른다. |
| AC-04 | `event_impact`은 Event의 `impact_level`, 효과 강도 배율, 참여 Agent 상한, 쿨다운 및 Reflection 적격 여부에 반영된다. |
| AC-05 | 실행 중 일반 Event 파라미터 변경은 현재 Tick에 영향을 주지 않고 다음 Tick부터 적용된다. |
| AC-06 | Replay는 저장된 Tick 결과와 파라미터 스냅샷을 재생하며, Event Master·LLM을 재호출하지 않는다. |
| AC-06a | 실행·일시정지 상태의 일반 Event 파라미터 변경은 변경 시점, 변경 전·후 값, 적용 시작 Tick, 적용 범위, 설정 버전을 Tick 이력에 기록한다. |

---

## 변경 이력

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| v1.1 | 2026-08-06 | §2에 Magic ON/OFF 파라미터 추가. Magic Layer 빈도·영향도 저장값·기본값 확정. §4(신규) Magic Layer 파라미터 시스템 조건 섹션 추가. AC-02에 Magic ON/OFF 명시. §7(구) 미결 결정 해소 삭제. |
| v1.0 | 2026-08-05 | 실행 중 일반 Event 파라미터 변경 이력 모델 확정. Tick 시작 시 설정 버전 고정, 변경 이력 저장 모델 명시. |
| v0.9 | 2026-08-04 | Magic ON/OFF 관련 내용 삭제. 섹션 6·7 제거, AC-07·AC-08 삭제. |
| v0.8 | 2026-08-03 | `RANDOM_INCIDENT`를 Magic Layer의 마법 특수 사건으로 분리, 일반 Event 빈도 적용 대상에서 제외. |
| v0.7 | 2026-08-03 | 일반 Event 파라미터 변경 이력 기록 항목 명시. |
| v0.6 | 2026-08-03 | Replay를 저장된 Tick 결과 재생으로 고정, Event Master·LLM 재호출 제외. |
| v0.5 | 2026-07-31 | 문서 제목 변경, Event Master 설계 기준 일반 Event 빈도·영향도 규칙·Tick별 적용 시점·Replay 재현 조건 반영. |
| v0.4 | 2026-07-30 | 일반 Event 빈도·영향도의 실행 중 변경 명시. 변경 이력 저장 모델과 Replay·복원 중 변경 정책 미결로 분리. |
| v0.1 | 2026-07-30 | PRD의 시뮬레이션 시작 전 파라미터 설정 및 Magic ON/OFF 정책을 상세 요구사항 문서로 분리. |
