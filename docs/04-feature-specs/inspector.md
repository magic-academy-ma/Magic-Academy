---
title: "[Spec] Inspector 기능 정의"
source: confluence/03_REQUIREMENTS/inspector.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/12582917
status: draft
visibility: public
updated: 2026-08-06
source_updated: 2026-08-04
---

**기준 문서:** Agent Runtime 설계 (#11894790) · [Policy] MBTI → Big Five 초기값 및 허용 범위 (#21791106) · [기능 명세서] 1단계 Magic Academy MVP (#16777778)

---

## 0. 개요 및 목적

이 문서는 Agent를 클릭했을 때 열리는 Inspector 패널의 관찰 정보와 읽기·쓰기 경계를 정의한다.

* **목적**: 사용자에게 Agent가 왜 행동했는지 설명하고 개발자가 Runtime 입력·판단·최종 결과를 검증할 수 있게 한다.
* **범위**: 프로필·MBTI·Big Five·상태·Decision Explanation·행동 로그·Memory·관계 표시를 다룬다.

## 1. 목적 및 대상

| 대상 | 목적 |
| --- | --- |
| 최종 사용자 | Agent의 성격, 상태, 관계, 기억이 행동에 어떻게 영향을 주는지 관찰 |
| 개발자 / 포트폴리오 | Agent Runtime의 출력 구조와 의사결정 맥락을 시각적으로 설명 |

이 문서는 Agent Runtime v0.4와 맞춰 정리한다. Decision Explanation 섹션을 기본 표시 항목으로 포함한다.

## 2. 현재 확정 사항과 충돌 정리

* Decision Explanation은 LLM의 내부 추론(COT) 노출이 아니다.
* Runtime이 같은 호출에서 생성한 구조화된 설명을 Inspector가 표시한다.
* User Persona의 성격 입력은 MBTI 5종 중 하나를 선택한 뒤 유형별 Big Five 기본값·허용 범위를 적용하고 `-50~+50` 축에서 5단위 슬라이더로 조절하는 방식이다.
* mood는 다른 상태값과 범위가 다르다.
* 행동 로그는 Runtime의 제안값만이 아니라, Commit 이후 최종 결과와 구분해서 보여주는 편이 안전하다.

## 3. Inspector 데이터 카테고리 및 표시 범위

### 3.1 프로필 (Profile)

표시 항목:

* 이름, 학년, 전공
* 단계별 소속 정보
  * 1단계: 전공·학년
  * 2단계: 동아리 배지 추가
  * 3단계: 기숙사 조직·총학생회 배지 추가
* User Persona 여부
* MBTI 대표 슬롯 (ISTJ, ESTP, INFP, ENTJ, ESFJ)
* Big Five 5개 값
  * 개방성 · 성실성 · 외향성 · 우호성 · 정서 안정성
  * `Low / Neutral / High` 라벨과 게이지로 표시
  * API 원본 값 `-50~+50`을 함께 확인 가능

데이터 출처는 Agent profile, 고정 fixture와 성격 규칙 버전이다. 시작 이후 Inspector에서 이 값을 수정하지 않는다.

### 3.2 내부 상태 (State)

| 상태값 | 범위 |
| --- | --- |
| hunger | 0 ~ 100 |
| fatigue | 0 ~ 100 |
| stress | 0 ~ 100 |
| satisfaction | 0 ~ 100 |
| mood | -100 ~ 100 |

mood만 음수와 양수를 허용한다. 나머지 상태는 0~100으로 유지한다.

Tick 완료 후 전달되는 committed snapshot 또는 delta를 반영해 갱신한다. WebSocket 기반 갱신이 있다면 reconnect 시 최신 snapshot 재동기화를 지원해야 한다.

### 3.3 의사결정 설명 (Decision Explanation)

이 섹션은 실제 내부 추론이 아니라, Runtime 입력과 출력 컨텍스트를 바탕으로 재구성한 설명이다.

표시 목적:

* 현재 선택된 행동이 무엇인지 보여준다.
* 대안이 무엇이었는지 보여준다.
* 어떤 입력이 선택에 영향을 줬는지 보여준다.

권장 표현 규칙:

* 대안은 최대 3개
* 선택된 항목은 정확히 1개
* 상대 우선순위는 HIGH / MEDIUM / LOW만 사용
* 영향 요소는 source와 direction을 명시

권장 스키마:

```json
{
  "alternatives": [
    {
      "action_type": "TALK",
      "description": "카이에게 과제를 함께 하자고 제안한다.",
      "relative_priority": "HIGH",
      "selected": true
    }
  ],
  "influencing_factors": [
    {
      "source": "RELATIONSHIP",
      "description": "카이와의 친밀도가 높다.",
      "direction": "SUPPORT"
    }
  ]
}
```

허용 값:

* `source`: `STATE`, `PERSONALITY`, `RELATIONSHIP`, `MEMORY`, `SCHEDULE`, `LOCATION`, `EVENT`
* `direction`: `SUPPORT`, `OPPOSE`

Inspector는 이 섹션을 verbose debug trace처럼 보이게 만들지 않는다. 설명은 짧고 구조적으로 유지한다.

### 3.4 행동 로그 (Behavior Log)

표시 대상은 최근 N Tick의 행동 타임라인이다.

각 행에는 다음을 포함한다:

* Tick 번호와 시간대 블록
* 최종 행동
* `utterance`
* `motivation_summary`
* `status` 또는 commit 결과 상태
* 필요하면 Runtime의 제안값과 최종 커밋값의 차이

중요한 원칙:

* 기본 기준은 Commit 이후의 최종 결과다.
* Runtime의 `PROPOSED`, `FALLBACK`, `SKIPPED`는 보조 상태로 구분 표시한다.
* 제안과 최종 결과가 다르면 둘을 같은 값으로 덮어쓰지 않는다.

이 섹션은 "무엇을 하려 했는가"와 "실제로 무엇이 확정됐는가"를 구분할 수 있어야 한다.

### 3.5 Memory

저장된 Memory 목록을 최대 10개까지 보여준다.

표시 항목:

* `memory_type`
* `content`
* `importance`
* `created_tick`
* 관련 Agent 또는 Event
* 이번 Tick에 프롬프트로 들어간 Memory 하이라이트

권장 memory type: `OBSERVATION` · `CONVERSATION` · `PLAN` · `REFLECTION`

하이라이트는 단순 최근 목록이 아니라, `latest 2 + RAG top 3`로 선택된 항목을 기준으로 한다. Inspector는 이 추적 정보를 함께 보여줘야 재현 가능성이 생긴다.

### 3.6 관계 (Relationships)

이 Agent가 다른 Agent를 어떻게 보는지 방향성 관계로 표시한다.

표시 항목:

* 상대 Agent 이름, 학년, 전공
* 6개 척도 미니 바: affection · closeness · trust · tension · rivalry · dependency
* 지속 관계 라벨: `FRIEND` · `SENIOR_JUNIOR` · `RIVAL`
* 최근 사건 기록: `CONFESSION` · `BETRAYAL` · `RECONCILIATION`

라벨과 사건 기록은 같은 개념이 아니다. 현재 관계 라벨은 상태를, 사건 기록은 변화를 설명한다.

## 4. Read vs. Write 경계

### 4.1 조회 전용 기본 모드

Inspector의 기본 모드는 읽기 전용이다. 3.1 ~ 3.6은 모두 조회 용도이며, 상태를 직접 바꾸지 않는다.

### 4.2 허용되는 별도 설정

User Persona의 초기 성향 설정은 시뮬레이션 시작 전에만 별도 설정 화면에서 수행한다.

* 시작 전에는 설정 가능
* 시작 후에는 Inspector에서 수정 불가
* 일반 Student Agent와 동일한 Runtime 규칙을 따른다

## 5. 필요한 API 엔드포인트

| Method | Path | 용도 |
| --- | --- | --- |
| GET | `/agents/{id}` | 프로필 + 현재 상태 + 성격 |
| GET | `/agents/{id}/memory` | Memory 목록과 retrieval trace |
| GET | `/agents/{id}/relationships` | 방향성 관계 전체 |
| GET | `/agents/{id}/behavior-log?limit=N` | 최근 N Tick 행동 히스토리 |
| GET | `/agents/{id}/decision-explanation?tick={tick}` | 특정 Tick의 의사결정 설명 |
| POST 또는 PATCH | `/simulations/setup/user-persona` | 시뮬레이션 시작 전 User Persona 초기 성향 설정 |

권장 사항:

* behavior log는 committed history를 기준으로 제공한다.
* decision explanation은 tick 단위로 조회 가능해야 한다.
* memory 조회는 `latest 2 + RAG top 3`가 왜 선택됐는지 추적 가능한 형태가 좋다.

## 6. Out of Scope

* Inspector에서 Event 직접 생성
* Agent 추가 / 삭제
* Memory 수동 삽입
* Tick 속도 조절
* 관계, 상태, 성격 수치 직접 수정
* 시작 이후 User Persona 초기값 재설정

## 7. 남은 결정 사항

| # | 항목 | 협의 대상 | 영향 |
| --- | --- | --- | --- |
| 1 | 행동 로그에 proposed vs. final diff를 기본 노출할지 여부 | FE / BE | UI 복잡도, 디버깅 편의성 |

## 8. 검증 기준

* Agent 클릭 시 Inspector 패널이 열린다.
* 프로필에 이름, 학년, 전공, 소속 단계, User Persona 여부, MBTI 슬롯이 표시된다.
* 프로필에 MBTI 유형과 Big Five 5개의 Low / Neutral / High 라벨·게이지가 표시되고 API 원본 값(-50~+50)을 확인할 수 있다.
* 상태값은 hunger, fatigue, stress, satisfaction, mood로 표시되며 mood만 -100 ~ 100이다.
* Decision Explanation에는 선택된 행동 1개와 대안 최대 3개, 영향 요소가 표시된다.
* 대안은 HIGH / MEDIUM / LOW, 영향 요소는 source / direction enum을 사용한다.
* 행동 로그는 committed 결과와 Runtime 제안값을 구분할 수 있다.
* Memory 하이라이트는 latest 2 + RAG top 3 기준으로 표시된다.
* 관계는 방향성으로 표시되고, 현재 라벨과 사건 기록이 분리된다.
* 조회 전용 모드에서 어떤 상태도 변경되지 않는다.
* 시뮬레이션 시작 후 Inspector에서 User Persona 초기값을 수정할 수 없다.

---

## 변경 이력

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| v0.6 | 2026-08-04 | 개발용 writable Inspector 제외 결정에 따라 §7 별도 Spec 분리 여부 항목 삭제. 조회 전용 Inspector 범위 유지. |
| v0.5 | 2026-07-31 | Big Five 표시를 -50~+50 원본 값과 Low / Neutral / High 라벨·게이지로 정합화. |
| v0.4 | 2026-07-30 | 성격 입력 방식 확정 반영 — MBTI 유형 선택 + Big Five 5개 토글. |
| v0.3 | 2026-07-24 | Runtime v0.3 기준으로 Big Five/Mood/Decision Explanation/행동 로그/Memory/관계 스키마 정합화. |
| v0.2 | 2026-07-23 | 상태값 공통 0~100으로 정리, 단계별 소속 노출 및 시작 후 읽기 전용 경계 명확화. |
| v0.1 | 2026-07-21 | 최초 작성. Inspector 6개 섹션 정의, Decision Explanation 재구성 개념 추가. |
