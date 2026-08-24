---
title: 게임 메카닉
source: confluence/02_PRODUCT/game-mechanics
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/12583007
status: draft
visibility: public
updated: 2026-08-25
source_updated: 2026-08-14
---

# 게임 메카닉

## 핵심 경험

> 관찰 + 제한된 개입 → 사회의 변화 체험

사용자는 Agent를 직접 조종하지 않는다. 시작 전에 Student 5명 중 한 명의 성격을 설정하고, 이후 자율적으로 움직이는 사회에서 행동·관계·사건이 달라지는 과정을 관찰한다.

## 기본 루프

```text
시간 진행 → 상태·일정 변화 → 행동·이동 → 만남·상호작용
→ Event 발생 → 관계·상태·소속 변화 → 다음 Tick
```

Agent는 상태, 성격, 일정, 위치, 관계, Memory, 관찰 가능한 Event와 주변 Agent를 종합해 Tick당 대표 Intent 하나를 반환한다. 실제 효과는 Policy Engine과 Conflict Resolver가 검증하고 Tick 종료 시 일괄 반영한다.

## 사용자 개입

1. 기존 Student 한 명과 MBTI를 선택한다.
2. MBTI별 Big Five 기본값·허용 범위를 적용한다.
3. 허용 범위 안에서 5단위로 값을 조절한다.
4. 검증 후 기존 Student를 User Persona로 갱신한다.
5. 시뮬레이션 시작 후 성격을 잠그고 일반 Student와 같은 자율 Runtime을 사용한다.

사용자는 실행 중 Agent 행동이나 대사를 직접 명령하거나 User Persona를 교체하지 않는다.

## MVP 범위

포함: Tick 진행·일시정지·밤 스킵, Agent 자율 행동, 공간 이동과 만남, 상태·관계 변화, Event, User Persona 설정, 관찰 UI.

제외: Agent 직접 조작, 모든 Agent 대상 명령, 복잡한 퀘스트·자원 관리, 일반 시뮬레이션의 승패 조건.

## 종료 기준

일반 시뮬레이션은 사용자가 관찰을 중단할 때 종료하며 승패를 두지 않는다.

대표 캠페인 **첫 학기, 다섯 명의 마법사**는 Tick 7까지 조기 종료 없이 실행한다. 종료 시 관계·Agent 상태 snapshot을 남기며, 다음 두 조건을 모두 만족하면 성공이다.

- 자기 자신을 제외한 20개 방향성 관계의 평균 친밀도 ≥ 4
- ESTP↔INFP 두 방향의 평균 신뢰도 ≥ 2

## 설계 원칙

- 사용자가 없어도 사회는 계속 움직인다.
- 개입은 직접 조작이 아니라 초기 조건 설정으로 제한한다.
- 행동 결과가 관계와 집단에 영향을 주고 다음 Tick의 입력이 된다.
- 즉시 보상보다 시간에 따른 변화를 관찰하는 경험을 우선한다.
