---
title: "FR-TBD 스토리모드 CHAPTER 2 — 무너진 팀을 다시 살려라"
status: draft
updated: 2026-10-19
---

# FR-TBD 스토리모드 CHAPTER 2 — 무너진 팀을 다시 살려라

> 2026-10-15 개편: 9/24 기획 재정립(스토리모드·챕터 구조, "행동 대신 정보·관계·환경·선택지 변경" 원칙, 정답 없는 랜덤 전개)에 맞춰 기존 "도전과제 1" 문서를 다시 썼다. 바뀐 점은 §11에 정리했다.

## 1. 목적

스토리모드(챌린지)는 자유 모드와 별도로, 정해진 틀 안에서 플레이어가 개입하고 그 결과로 학생 관계가 어떻게 바뀌는지 관찰하는 시나리오다. 플레이어는 **학생자치위원회 임시 조정관**으로서 한 학기 동안 4개의 독립된 사건을 맡는다. 각 사건의 결과는 **활동 기록**으로 남고, 학기 말 FINAL 엔딩을 정하는 데 쓰인다.

이 문서는 CHAPTER 2 「무너진 팀을 다시 살려라」(핵심 테마: **갈등과 신뢰**)를 다룬다. 또한 스토리모드 챕터들이 공통으로 쓰는 실행 모델(§4.1)을 정의한다. CHAPTER 4 문서는 이 정의를 그대로 따른다.

`docs/01-product/functional-requirements.md`의 FR-18("캠페인·테스트 시나리오: 고정 사건·종료 조건을 가진 실행 시나리오")에서 구체화한 형태다.

## 2. 범위

**포함**
- 스토리모드 공통 실행 모델: 컨트롤러 개입 권한, 랜덤성 원칙, 챕터 결과 기록 형식
- CHAPTER 2의 등장 역할과 초기 상태, 관찰을 통한 속사정 파악, 3개 Round 진행, 개별 엔딩 3종
- CHAPTER 2 업적 판정에 필요한 기록

**제외**
- 실제 증감 수치와 임계값. 방향만 정하고 수치는 Policy Engine 구현과 플레이테스트 단계에서 정한다.
- FINAL 엔딩(BEST/NORMAL/BAD) 집계 규칙. CHAPTER 1~4의 기록을 합치는 공통 규칙이라 별도로 정한다(§10).
- 엔딩 이후 UI/화면 구성

## 3. 입력 / 출력

| 항목 | 설명 |
| --- | --- |
| 입력 | 챕터 시작 요청(초기 상태 프리셋, run 시드), Round 1·2 개입 선택 |
| 출력 | Round별 진행 상황, 개별 엔딩(`UNITED` / `PARTIAL` / `DISBANDED`), 챕터 결과 기록(§4.8), 업적 판정용 기록(§4.9) |

## 4. 핵심 동작

### 4.1 스토리모드 공통 실행 모델

- 각 챕터는 자유 모드와 독립된 별도 run이다. 자유 모드 세이브에 영향을 주지 않는다. 챕터끼리도 독립이라, 이전 챕터 결과가 다음 챕터의 상황이나 난이도를 바꾸지 않는다.
- **1 Round = 1 Day(3 Tick)**. 새 시간 단위를 만들지 않고 기존 "1일 = 3 Tick(아침/오후/저녁)" 구조에 맞춘다.
- **에이전트 원칙**: 컨트롤러는 Agent의 행동(Intent)을 직접 정하지 않는다. 할 수 있는 일은 아래 세 가지뿐이다.

| 권한 | 바꾸는 것 | 구현 지점 |
| --- | --- | --- |
| Event 주입 | 환경: 특정 Tick에 특정 유형의 Event를 참여자를 지정해 넣는다 | `forced_events.py` |
| 정보 주입 | 정보: 특정 Agent의 runtime 입력에 공지·대화 기억을 추가한다(예: "조정관이 오늘은 쉬어도 된다고 했다") | `llm_override.py`를 입력 보강 래퍼로 변경(§6) |
| 일정 변경 | 환경: Event 참여자 조합, 일정의 필수 여부(`is_mandatory`)를 바꾼다 | `forced_events.py`, 일정 구성 |

  - 실제로 쉴지, 화해할지, 협업에 얼마나 참여할지, 탈퇴할지는 항상 Agent Runtime → Policy Engine → Conflict Resolver 파이프라인이 정한다.
  - 기존의 "특정 Agent Intent 강제 오버라이드" 권한은 **삭제**한다.
- **랜덤성 원칙**: 틀(역할, Round 순서, 개입 시점, 선택지 종류)은 고정한다. 전개(각 학생의 속사정, 돌발 상황 종류, Agent 반응)는 run마다 달라진다. 컨트롤러가 고르는 랜덤 요소는 run 시드 RNG로 정해 replay를 재현할 수 있게 한다. **어떤 선택지도 항상 정답이 되도록 설계하지 않는다.** 선택지의 효과는 그 선택이 그 run의 속사정과 맞는지, 그리고 Agent가 어떻게 반응하는지에 달려 있다.
- **개입 선택지 공통 규칙**: 모든 개입 지점에 `WATCH`(지켜본다) 선택지를 둔다. 각 개입 지점의 선택 결과와 **선택에 걸린 시간**을 기록한다(공통 업적 「우유부단하시네요」 판정용).
- run이 중단되면 `ABORTED`로 처리하고 엔딩과 기록을 만들지 않는다.

### 4.2 등장 역할 및 초기 상태

마법전술 경연대회를 준비하는 Student 5명(A~E). 역할은 고정 틀이다.

| 학생 | 역할 | 초기 상태(방향만) |
| --- | --- | --- |
| A | 리더. 결과를 위해 자기 방식으로 팀을 끌고 간다 | B에 대한 affection 음수 |
| B | 의견이 무시된다고 느끼는 팀원 | A에 대한 affection 음수, satisfaction 낮음 |
| C | 탈퇴를 선언하려는 팀원 | satisfaction 낮음, stress 높음 |
| D | 반복되는 실수의 당사자. 책임 공방의 대상이 된다 | stress 높음 |
| E | 갈등에서 거리를 두는 팀원 | 기본 상태 |

- **속사정(hidden motive)**: 각 학생에게 "무엇이 불만인지 / 누구와 갈등하는지 / 팀에서 원하는 역할"을 하나씩 부여한다. 역할마다 후보 풀을 두고, run 시작 시 시드 RNG로 하나를 뽑는다. 예를 들어 C가 탈퇴하려는 이유는 run마다 "원하는 역할을 못 맡아서", "D의 실수를 자기가 메우고 있어서", "A의 방식이 싫어서" 중 하나다. 그래서 같은 선택지가 run마다 맞기도 하고 틀리기도 한다.
- 속사정은 해당 Agent의 페르소나 맥락으로 runtime 입력에 들어가서, Agent의 자율 판단에 반영된다.
- 관계 척도는 **affection(호감도)**을 기본으로 쓴다. affection·closeness·trust 중 음수를 표현할 수 있는 척도이기 때문이다(`docs/03-system-design/policy-engine.md` §11).
- run 시작 시점의 20개 방향성 affection edge 값을 기록한다(엔딩과 업적에서 비교 기준으로 쓴다).

### 4.3 속사정 파악 — 라운드 진행 중 관찰

별도의 대화 단계는 두지 않는다. 플레이어는 라운드가 진행되는 동안 학생들의 대사와 행동, 관계 변화를 **관찰**해서 각자의 속사정을 스스로 짐작한다.

- 각 학생은 매 Tick 입력에 자기 속사정을 페르소나 맥락으로 받는다. 그래서 불만이나 갈등 상대가 대사와 행동에 자연스럽게 드러날 수 있다. 드러낼지, 얼마나 드러낼지는 Agent가 정한다.
- 시스템은 "파악했다/못 했다"를 판정하거나 기록하지 않는다.
- 조정관의 개입 문구에는 속사정을 직접 담지 않는다. 플레이어가 속사정을 제대로 짐작해 맞는 선택지를 골랐는지는 그 선택지에 대한 Agent의 반응으로만 드러난다.

### 4.4 Round 1 — 갈등의 표면화 (Day 1)

1. Day 1 첫 Tick에 A·B가 함께하는 `GROUP_PROJECT`를 importance `high`로 주입한다(연습 중 충돌).
2. Tick 1 직후 플레이어가 개입한다.

| 선택지 | 컨트롤러 조치 | 권한 |
| --- | --- | --- |
| `REASSIGN_ROLES` 역할 재배정 | 이후 `GROUP_PROJECT`를 서로 다른 참여자 조합으로 분리하고, 해당 학생들에게 역할 재배정 공지를 주입한다 | 일정 변경 + 정보 주입 |
| `MEDIATE` 대화 자리 마련 | A·B `MEETING`을 주입한다 | Event 주입 |
| `WATCH` 지켜본다 | 추가 조치 없음 | — |

3. Day 1 마지막 Tick에 C의 **탈퇴 선언** Event를 주입한다(5명 `MEETING`, importance `high`). 무엇을 선택했든 선언은 일어난다. 다만 선언의 강도와 분위기(설명 문구)는 R1 진행 결과에 따라 Agent가 반응하는 대로 달라진다.

### 4.5 Round 2 — 책임 공방과 탈퇴 위기 (Day 2)

1. Day 2 첫 Tick에 반복 실수 상황을 `GROUP_PROJECT`로 주입한다(D 포함, 5명). 이 Tick의 반응은 자율이고, 책임 떠넘기기가 일어날 수 있다.
2. Tick 1 직후 플레이어가 개입한다.

| 선택지 | 컨트롤러 조치 | 권한 |
| --- | --- | --- |
| `PERSUADE_LEAVER` 탈퇴 선언자와 이야기하기 | C에게 "조정관이 팀에 남아 달라고 이야기했다"는 대화 기억을 남은 Day 2 Tick마다 주입한다 | 정보 주입 |
| `TEAM_MEETING` 팀 전체 회의 | 5명 `MEETING`을 주입한다. 이 Tick은 진행도 집계에서 빠진다(정체) | Event 주입 |
| `REDISTRIBUTE` 업무 재분배 | D·C의 다음 `GROUP_PROJECT` 참여 조합을 바꾸고, 새 분담을 공지로 주입한다 | 일정 변경 + 정보 주입 |
| `WATCH` 지켜본다 | 추가 조치 없음 | — |

3. 어떤 선택지도 항상 통하지는 않는다. 예를 들어 C의 속사정이 "A의 방식이 싫어서"라면 업무 재분배로는 해결되지 않을 수 있다.

### 4.6 Round 3 — 대회 직전 (Day 3)

1. Day 3 첫 Tick에 돌발 상황 하나를 `RANDOM_INCIDENT`로 주입한다. 후보는 `PRESENTATION_ERROR`(발표 자료 오류), `MEMBER_DROPOUT`(담당자 이탈), `SUPPLY_MISSING`(준비물 누락)이고, run 시드 RNG로 하나를 고른다.
2. 이 Round에는 개입이 없다. 지금까지 쌓인 관계와 기억을 바탕으로 Agent들이 협력하거나 책임을 떠넘긴다.
3. Day 3 마지막 Tick은 대회 최종 준비 `GROUP_PROJECT`(5명)다. **C가 여기에 실제로 참여하는지**(AVOID가 아닌지)를 기록한다. 이것이 팀 존속 여부를 정한다.

### 4.7 개별 엔딩 (Day 3 종료 시점)

| 엔딩 | 서사 | 판정 |
| --- | --- | --- |
| `DISBANDED` | 팀이 결국 해체되고 대회를 포기한다 | C가 최종 `GROUP_PROJECT`에 불참, 또는 `project_progress` 미달 |
| `UNITED` | 갈등을 해결하고 팀이 다시 하나가 된다 | `DISBANDED`가 아니고, affection 평균이 임계값 이상이며 run 시작 시점보다 상승 |
| `PARTIAL` | 대회는 참가하지만 일부 갈등이 남는다 | 그 외 |

- `project_progress`는 저장하지 않고 평가 시점에 Event 기록으로 계산한다(기존 `calculate_project_progress()` 재사용). 집계 대상은 실제 참여자의 `reaction.valence`이고, POSITIVE면 ↑, NEGATIVE면 ↓, NEUTRAL이나 미참여면 정체다.
- 임계값은 기존 이름 있는 상수를 초기값으로 재사용하고 플레이테스트 후 조정한다.
- 기존 "전원 stress < 한계값" 조건은 CHAPTER 2 테마(갈등과 신뢰)에 맞지 않아 엔딩 판정에서 뺀다. 과로·번아웃은 CHAPTER 4에서 다룬다.

### 4.8 챕터 결과 기록

FINAL 엔딩 집계를 위해 챕터마다 같은 형식의 활동 기록을 남긴다.

| 개별 엔딩 | 활동 기록 등급 |
| --- | --- |
| `UNITED` | `GOOD` |
| `PARTIAL` | `MIXED` |
| `DISBANDED` | `BAD` |

기록에는 등급, 개별 엔딩, 각 개입 지점의 선택을 함께 남긴다. FINAL 단계에서 교수가 "네 권의 기록"을 검토하는 서사에 쓰인다.

### 4.9 업적 판정

| 업적 | 상태 | 판정 |
| --- | --- | --- |
| CHAPTER 2 클리어 | 기획 확정 | 엔딩 종류와 관계없이 run을 정상 종료(`ABORTED` 아님) |
| 마이너스의 손 | 기획 확정 | 종료 시 affection 평균이 run 시작 시점보다 낮음 |
| 다 계획이 있구나! | 기획 확정 | R1·R2 개입에서 모두 `WATCH`를 고르고 `UNITED` 달성 |
| 원수에서 전우로 | 기획 확정 | 종료 시 20개 방향성 affection edge가 **모두** 0보다 큼 |
| 돌아온 전우 | 신규 제안 | 탈퇴를 선언한 C가 최종 `GROUP_PROJECT`에 참여하고 C의 satisfaction이 run 시작 시점보다 상승 |

## 5. 경계 조건

- 컨트롤러는 Tick Orchestrator·Event Master·Policy Engine 파이프라인 자체를 바꾸지 않는다. 그 앞단에서 Event·정보·일정만 바꾼다.
- 5명 전원은 모든 Tick에서 Agent Runtime으로 자율 판단한다. 강제 REST 같은 행동 지정은 없다.
- 조정관의 개입 문구(Event 설명, 주입 기억)에는 학생의 속사정을 담지 않는다.

## 6. 데이터 구조 및 연동 지점

- **Event 주입**: 기존 구조를 유지한다. `forced_events.py`의 `build_forced_group_project`·`build_forced_meeting`, `EventMaster.build_random_incident()`를 사용한다.
- **정보 주입 (변경)**: `ChallengeLLMOverride`는 지금 지정된 `(tick, agent)`에서 스크립트된 응답을 대신 반환한다. 이를 **runtime 입력을 보강한 뒤 실제 LLM으로 넘기는 래퍼**로 바꾼다. 지정된 `(tick, agent)`에서 `memories`에 조정관 공지나 대화 기억을 추가하고, `events`의 title/description에 맥락을 넣은 뒤, 항상 실제 `LLMClient.generate()`를 호출한다. 스크립트된 응답 반환 경로는 삭제한다.
- **일정 변경**: Event 참여자 조합은 `forced_events.py`에서, 일정의 필수 여부는 `ScheduleSummary.is_mandatory`로 바꾼다.
- **신규 RANDOM_INCIDENT subtype 3종**: `PRESENTATION_ERROR`·`MEMBER_DROPOUT`·`SUPPLY_MISSING`. `event_metadata`에 저장하므로 마이그레이션이 필요 없다. MEDIUM 티어를 재사용한다(기존 확정 유지).
- **신규 기록값**: 속사정 추첨 결과, 시작 시점 affection 스냅샷, 개입 선택과 소요 시간, C의 최종 참여 여부. 별도 테이블 없이 run 단위 `event_metadata` 또는 challenge 기록으로 남기는 방향이다. 저장 위치는 구현 시 정한다.

## 7. 완료 기준

- [x] `ChallengeLLMOverride`를 입력 보강 래퍼로 바꾸고, 스크립트된 응답 경로와 강제 REST를 삭제 (`llm_override.py`)
- [x] 역할별 속사정 후보 풀과 시드 추첨 (`controller.py`, 후보 문구는 초안)
- [x] 속사정을 매 Tick 페르소나 맥락으로 주입 (`plan_motive_injections`)
- [x] R1·R2 선택지(`WATCH` 포함), 개입 문구에 속사정 미포함
- [x] R1 종료 시 탈퇴 선언 Event, R3 돌발 상황 시드 추첨, C 최종 참여 여부 판정
- [x] 개별 엔딩 3종 판정, 챕터 결과 기록(§4.8) (`evaluation.py`, `record.py`)
- [x] 업적 판정 (기획 확정 3종, 공통 「우유부단하시네요」 판정 함수). 기록값 저장 위치는 미정

## 8. 기존 확정 사항 중 유지하는 것

- `project_progress`는 저장하지 않고 Event 기록으로 계산한다. 판정은 `GROUP_PROJECT` 참여자의 `reaction.valence` 기준이다.
- "역할 재배정"은 역할 필드를 새로 만들지 않고, Event 참여자 조합을 분리해 표현한다.
- 신규 RANDOM_INCIDENT subtype은 MEDIUM 티어를 재사용한다.
- 임계값은 이름 있는 상수로 분리한다.

## 9. 남은 미정 항목

- [미정] 속사정 후보 풀의 구체 문구
- [미정] 신규 기록값의 저장 위치
- [미정] 엔딩 이후 UI/화면 구성
- [미정] 정식 FR 번호

## 10. 챕터 바깥에서 정할 것 (공통)

- FINAL 엔딩(BEST/NORMAL/BAD) 집계 규칙: CHAPTER 1~4의 `GOOD`/`MIXED`/`BAD` 기록을 어떻게 합칠지
- CHAPTER 1·3도 §4.8 기록 형식을 쓰는지 맞추기

## 11. 개편 전후 비교

| 항목 | 개편 전(도전과제 1) | 개편 후(CHAPTER 2) |
| --- | --- | --- |
| 개입 권한 | Event 주입 + Intent 강제 오버라이드 | Event 주입 + 정보 주입 + 일정 변경. 행동 지정 없음 |
| 등장인물 | A~E에 상태만 부여 | 리더·무시받는 팀원·탈퇴 선언자 등 역할 + 시드 추첨 속사정 |
| 정보 파악 | 없음 | 라운드 진행 중 관찰(시스템 판정 없음) |
| R2 | 과로 문제(쉬게 함 = 강제 REST) | 책임 공방과 탈퇴 위기(정보·일정 개입) |
| 엔딩 | Perfect/Normal/Bad(진행도·호감도·스트레스) | `UNITED`/`PARTIAL`/`DISBANDED`(탈퇴자 최종 참여 여부 중심) + 활동 기록 등급 |
| 랜덤성 | R3 돌발 상황 선택 규칙 없음 | 속사정·돌발 상황 모두 시드 추첨 |

## 12. 관련 문서

- `docs/04-feature-specs/challenge-mode-festival-booth.md` — CHAPTER 4
- `docs/01-product/functional-requirements.md` — FR-18, FR-21
- `docs/02-domain/agents.md`, `relationships.md`, `events.md`, `world-setting.md`
- `docs/03-system-design/tick-engine.md`, `event-master.md`, `policy-engine.md`, `agent-runtime.md`
