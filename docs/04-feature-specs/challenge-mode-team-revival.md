---
title: "FR-TBD 도전과제 모드 — 무너진 팀을 다시 살려라"
status: draft
updated: 2026-09-16
---

# FR-TBD 도전과제 모드 — 무너진 팀을 다시 살려라

## 1. 목적

자유 시뮬레이션 모드는 사용자가 User Persona Agent의 성격·성향을 지정하는 것 외에는 개입할 수 없고, 결과를 지켜보는 관찰형 경험이다(`docs/00-start-here/what-is-decided.md` — "사용자 개입 범위: User Persona Agent 1명의 성격·성향 지정까지로 제한").

"도전과제 모드"는 이와 별도로, 정해진 초기 상황과 종료 조건을 가진 짧은 시나리오를 사용자가 직접 진행하며 매 국면마다 선택을 내리는 경험을 제공한다. GTA의 프리로밍(자유 시뮬레이션)과 스토리 미션(도전과제)의 관계와 같다.

`docs/01-product/functional-requirements.md`의 FR-18("캠페인·테스트 시나리오: 고정 사건·종료 조건을 가진 실행 시나리오")이 이미 이런 종류의 실행 시나리오를 위한 자리를 만들어 두었다. 도전과제 모드는 FR-18의 구체적인 한 형태이며, FR-21(대표 캠페인)과 달리 진행 중 사용자 선택 지점을 포함하고 종료 시 성공/실패 판정을 생성한다는 점이 다르다.

이 문서는 도전과제 1건("무너진 팀을 다시 살려라")의 설계를 다룬다.

## 2. 범위

**포함**
- 도전과제 모드가 자유 시뮬레이션 모드와 별도의 독립된 실행(run)이라는 정의
- 도전과제 1의 초기 상태, 3개 Round(Day) 진행 구조, 각 Round의 사용자 선택지, 성공 조건
- 기존 Tick/Event/Policy 파이프라인과의 연동 지점 식별

**제외**
- 도전과제 2("축제 부스 운영하기") — 동아리·총학생회 조직 스코프가 아직 보류 상태라 별도 문서에서 다룬다
- project_progress 등 신규 값의 실제 증감 수치, 신규 RANDOM_INCIDENT subtype의 실제 효과값 — 방향만 정하고 수치는 Policy Engine 구현 단계에서 결정한다
- 엔딩 분기 이후의 UI/화면 구성

## 3. 입력 / 출력

| 항목 | 설명 |
| --- | --- |
| 입력 | 도전과제 시작 요청(강제 초기 상태 프리셋 포함), Round 1·2 사용자 선택지 응답 |
| 출력 | Round별 진행 상황(강제/자율 Event 결과), Day 3 종료 시점의 Perfect/Normal/Bad 판정 |

## 4. 핵심 동작

### 4.1 실행 모델

- 도전과제는 자유 시뮬레이션과 독립된 별도 run으로 시작한다. 기존 사용자의 자유 시뮬레이션 세이브에는 영향을 주지 않는다.
- 시작 시 강제 초기 상태를 주입한다(§4.2).
- Round 3(Day 3) 종료 평가 후 해당 run을 종료한다.
- Agent 자율성은 자유 시뮬레이션과 동일하게 유지한다. 도전과제 컨트롤러가 할 수 있는 것은 다음 두 가지로 제한한다.
  1. 특정 Tick에 특정 유형의 Event를 강제로 주입(참여자 지정 포함)
  2. 특정 Agent의 특정 Tick Intent를 강제로 지정(오버라이드)
  - 위 두 가지 외의 모든 반응(화해할지, 협업에 얼마나 성실히 참여할지, 책임을 떠넘길지 등)은 항상 기존 Agent Runtime → Policy Engine → Conflict Resolver 파이프라인이 자율적으로 결정한다.
- Round 용어는 신규 시간 단위를 만들지 않고 기존 "1일 = 3 Tick(아침/오후/저녁 블록)" 구조에 그대로 매핑한다. **1 Round = 1 Day(3 Tick)**.

### 4.2 등장 Agent 및 초기 상태

- Student 5명(A~E) — 기존 MVP Student 5명 구성을 그대로 사용한다(`docs/02-domain/agents.md`).
- 시작 시 강제 주입하는 초기 조건(방향만 확정, 구체 수치 [미정]):
  - A→B, B→A 호감도(affection)가 낮은 음수 상태
  - C의 스트레스가 높은 상태
  - D의 피로도가 높은 상태
  - E의 만족도가 낮은 상태
  - 마감까지 Round 3개(Day 3개) 남음

  관계 척도 6개 중 음수를 표현할 수 있는 것은 affection·closeness·trust뿐이다(`docs/03-system-design/policy-engine.md` §11). 이 도전과제에서 "관계도"는 **호감도(affection)**를 가리키는 것으로 확정한다.

### 4.3 Round 1 — 팀 내 갈등 (Day 1)

1. Day 1 첫 Tick에 도전과제 컨트롤러가 `GROUP_PROJECT` Event(A·B 충돌 상황)를 강제 주입한다. importance는 `high`로 설정해 Reflection 대상이 되게 한다(`docs/03-system-design/event-master.md` §4.3 영향도 판정).
2. 이 Event 직후 사용자에게 선택지를 제공한다. 하나만 선택할 수 있다.

| 선택지 | 강제 조치 |
| --- | --- |
| 역할 재배정 | 다음 `GROUP_PROJECT`의 참여 서브그룹 구성을 바꿔 A·B를 분리 |
| 두 사람을 직접 대화시킴 | A·B를 대상으로 `MEETING` Event를 강제 주입 |
| Agent들이 스스로 해결하도록 둠 | 추가 주입 없이 Event Master의 정상 동적 Event 로직을 그대로 둠 |

3. 이후 실제로 화해하는지, 갈등이 지속되는지는 A·B 각자의 Agent Runtime 판단에 달려 있다. 다른 Agent들의 중재/편들기/무시 행동도 각자의 자율 판단이다.

### 4.4 Round 2 — 과로 문제 (Day 2)

1. Day 2 시작 시점에 스트레스·피로가 가장 높은 Agent(초기 조건상 C 또는 D)를 기준으로 사용자에게 선택지를 제공한다.

| 선택지 | 강제 조치 | 방향성 결과 |
| --- | --- | --- |
| 쉬게 함 | 해당 Agent의 이번 Day Intent를 `REST`로 강제 오버라이드 | 이번 Round는 project_progress 증가 없음(정체) |
| 업무 이양 | `GROUP_PROJECT` 참여자에서 해당 Agent를 제외하고 다른 Agent를 강제 편입 | project_progress는 정상 진행, 단 이양받은 Agent의 피로·스트레스는 원래보다 더 크게 증가하는 방향 |
| 일정대로 강행 | 오버라이드 없음, 정상 진행 | 관계·상태 변화 방향은 해당 Agent의 자율 반응에 따라 증가/감소 모두 가능 |

2. 선택과 무관하게 나머지 4명의 행동은 항상 자율이다.

### 4.5 Round 3 — 마감 직전 위기 (Day 3)

1. Day 3 첫 Tick에 다음 세 후보 중 하나를 신규 `RANDOM_INCIDENT` subtype으로 강제 주입한다: `PRESENTATION_ERROR`(발표 자료 오류), `MEMBER_DROPOUT`(담당자 이탈), `SUPPLY_MISSING`(준비물 누락).
   - 기존 `RANDOM_INCIDENT`는 마법 테마 subtype(`MAGIC_MALFUNCTION`, `DISAPPEARANCE`, `CURSE`, `EXPLOSION`)만 Policy Engine Event Registry에 등록되어 있다(`docs/02-domain/world-setting.md` §4.1, `docs/03-system-design/policy-engine.md` §9.2). 위 3개 신규 subtype은 Registry에 새로 등록해야 하며, 자유 숫자 입력은 금지되어 있으므로([policy-engine.md §9.2](../03-system-design/policy-engine.md)) 효과값을 반드시 Registry에 정의한 뒤에만 사용할 수 있다.
2. 이 Round에는 사용자 선택지가 없다. 지금까지 쌓인 관계·기억을 바탕으로 Agent들이 자율적으로 협력하거나 책임을 떠넘긴다.

### 4.6 성공 조건 (Day 3 종료 시점 평가)

- `project_progress >= 70` (임시값, §8 참조 — 플레이테스트 후 조정 가능하도록 상수로 분리)
- Student 5명 사이 20개 방향성 호감도(affection) edge의 평균 `>= 0`
- Student 5명 전원 `stress < 90`
- 위 조합에 따라 Perfect / Normal / Bad Ending으로 분기한다.

## 5. 경계 조건

- 도전과제 진행 중 자유 시뮬레이션의 Tick Orchestrator·Event Master·Policy Engine 파이프라인 자체를 변경하지 않는다. 도전과제 컨트롤러는 그 앞단에서 Event를 주입하거나 특정 Agent Intent를 오버라이드하는 방식으로만 개입한다.
- Round 2에서 오버라이드된 Agent를 제외한 나머지 4명, Round 3에서는 5명 전원이 항상 정상적으로 Agent Runtime을 통해 자율 판단한다.
- 도전과제 run이 중단(사용자 이탈 등)되면 FR-21의 대표 캠페인과 동일하게 ABORTED로 처리하고 성공/실패 판정을 생성하지 않는 것을 기본값으로 제안한다. [미정 — PRD 확정 필요]

## 6. 데이터 구조 및 연동 지점 (코드 조사로 확정)

기존 코드베이스 조사 결과, 아래 세 가지는 새 인터페이스를 만들 필요 없이 기존 구조를 그대로 재사용한다.

- **Event 강제 주입**: 신규 컴포넌트 불필요. `EventMaster.build_random_incident()`(`backend/app/simulation/event_master.py:225`)가 이미 `event_subtype`·`participant_agent_ids`·`location_id`를 직접 지정해 Event를 생성하는 public 메서드다. Round 3의 세 신규 subtype 주입에 그대로 사용한다. Round 1의 GROUP_PROJECT/MEETING 강제 주입은 `EventMaster`의 private 자동 생성 메서드(`_generate_group_project`/`_generate_meeting`)를 거치지 않고, public `Event` dataclass(`event_master.py:108`)를 직접 구성해 이벤트 목록에 끼워넣는 방식으로 처리한다.
- **Agent 행동 강제 오버라이드**: `AgentRuntime`은 생성자에서 `LLMClient`(`.generate(runtime_input) -> object` 계약, `agent_runtime.py:410`)를 주입받는 구조다. `backend/tests/slice5_campaign.py`의 `CanonicalCampaignLLM`이 "tick_number + agent 조건에 따라 스크립트된 응답 반환, 그 외는 위임"하는 패턴을 이미 사용 중이다. 도전과제 컨트롤러는 실제 LLM 클라이언트를 감싸고 지정된 `(tick_number, agent_id)` 쌍에서만 스크립트된 Intent를 반환하는 래퍼(`ChallengeLLMOverride`류)를 이 패턴 그대로 구현한다. 오버라이드되지 않은 모든 Agent·Tick은 실제 LLM 호출로 위임되어 완전 자율성이 유지된다.
- **RANDOM_INCIDENT 신규 subtype**: `Event` DB 모델의 `event_type` CHECK 제약(`models.py:397`)은 `random_incident`까지만 검증하고 subtype 자체에는 제약이 없다. subtype은 `event_metadata`(JSONB, `models.py:413`)에 자유롭게 저장되는 구조라 **스키마 마이그레이션이 필요 없다**. Policy Engine의 Event Registry에 `PRESENTATION_ERROR`/`MEMBER_DROPOUT`/`SUPPLY_MISSING` 세 항목을 추가하기만 하면 된다(효과값 자체는 여전히 [미정]).

신규 상태값은 다음과 같이 저장 없이 계산으로 처리하기로 확정했다.

- `project_progress`: **별도 컬럼·테이블에 저장하지 않는다.** `AgentState`는 CHECK 제약으로 컬럼이 고정된 스키마라 추가하려면 Alembic 마이그레이션이 필요하고, `Simulation`에도 자유 필드가 없다. 대신 Day 3 평가 시점에 해당 도전과제 run에 속한 Event 기록(`event_metadata`)을 훑어 그때그때 계산한다. 3일짜리 단발 시나리오라 실시간 중간 조회 필요성이 낮고, AGENTS.md의 Simplicity First 원칙에도 부합한다. 집계 규칙은 §8 참조.

## 7. 완료 기준

- [x] 도전과제 컨트롤러의 위치(Tick Orchestrator와의 연동 지점) — Event는 `EventMaster` 앞단에서 직접 주입, Agent 행동은 `LLMClient` 래퍼로 오버라이드
- [x] Event 강제 주입 인터페이스 — 기존 `build_random_incident()` + `Event` dataclass 직접 구성으로 해결, 신규 계약 불필요
- [x] 특정 Agent Intent 강제 오버라이드 — 기존 `LLMClient` 주입 지점 + `CanonicalCampaignLLM` 패턴 재사용으로 해결
- [x] `project_progress` 저장 위치 — 저장하지 않고 Event 기록 기반 계산으로 확정
- [x] 신규 RANDOM_INCIDENT subtype 3종의 강도 — MEDIUM 티어(기존 표 재사용)로 확정 (§8)
- [x] project_progress 판정 규칙 — GROUP_PROJECT 참여자 reaction.valence 기준으로 확정 (§8)
- [x] 성공 조건 임계값 — 70/0/90을 임시값으로 확정, 상수로 분리해 플레이테스트 후 조정 (§8)

## 8. 확정된 세부 규칙 (구조 결정 완료, 프로젝트 소유자 직접 확정)

- **"역할 재배정"**: 신규 역할/서브그룹 필드를 추가하지 않는다. A·B를 서로 다른 `GROUP_PROJECT` Event 인스턴스(별도 참여자 조합)로 분리하는 방식으로 구현한다.
- **RANDOM_INCIDENT 신규 subtype 3종의 강도**: `PRESENTATION_ERROR`/`MEMBER_DROPOUT`/`SUPPLY_MISSING` 모두 MEDIUM 티어(`policy-engine.md` §6 상태 signal 기준, 절댓값 5)를 사용한다. 새 숫자를 발명하지 않고 기존 티어표를 재사용한다.
- **project_progress 판정 규칙**: 해당 Round의 `GROUP_PROJECT` Event에 실제 참여한 Agent들의 `reaction.valence`를 본다. POSITIVE면 진행도 ↑, NEGATIVE면 ↓, NEUTRAL 또는 미참여(AVOID)면 정체.
- **성공 조건 임계값**: `project_progress >= 70`, 평균 호감도 `>= 0`, 스트레스 `< 90`을 임시값으로 코드에 반영한다. 매직 넘버로 흩뿌리지 않고 이름 있는 상수로 분리해 플레이테스트 후 조정하기 쉽게 만든다.

## 9. 남은 미정 항목

- [미정] 엔딩 분기 이후 UI/화면 구성
- [미정] 도전과제 run 중단 시 처리(ABORTED 여부)
- [미정] 이 기능의 정식 FR 번호 (FR-18 하위 항목으로 편입할지 별도 FR로 분리할지)

## 10. 관련 문서

- `docs/00-start-here/what-is-decided.md` — 사용자 개입 범위 확정 사항
- `docs/01-product/functional-requirements.md` — FR-18(캠페인·테스트 시나리오), FR-21(대표 캠페인)
- `docs/02-domain/agents.md`, `relationships.md`, `events.md`, `world-setting.md`
- `docs/03-system-design/tick-engine.md`, `event-master.md`, `policy-engine.md`, `agent-runtime.md`
