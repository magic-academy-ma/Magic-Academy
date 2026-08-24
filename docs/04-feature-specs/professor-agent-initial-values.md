---
title: Professor Agent 초기값
source: confluence/03_REQUIREMENTS/professor-agent-initial-values
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/22348159
status: draft
visibility: public
updated: 2026-08-25
source_updated: 2026-08-14
---

# Professor Agent 초기값

MVP는 `professor-01` 고정 fixture의 마법공학과 전공 교수 에단 1명을 사용한다.

| 항목 | 값 |
| --- | --- |
| MBTI | ISTJ |
| Big Five | 개방성 -20, 성실성 +40, 외향성 -25, 우호성 +10, 정서 안정성 +35 |
| 초기 위치 | 강의실 |
| 초기 상태 | hunger 20, fatigue 15, stress 20, satisfaction 70, mood 20 |
| 초기 Memory | 없음. 첫 Event 이후 후보를 통해 생성 |

Professor→Student 관계는 trust 20, 나머지 척도 0으로 시작한다. Student→Professor 관계는 trust 30, tension 10, dependency 10, 나머지 척도 0으로 시작한다. 총 10개의 방향성 관계를 만들며 자기 관계와 교수 간 관계는 없다.

- 성격은 사용자가 설정하지 않으며 실행 중 변경하지 않는다.
- Student는 Professor의 원시 성격 수치를 직접 보지 않고 행동·대화·Reaction의 관찰 가능한 결과만 사용한다.
- 관련 schedule 또는 최종 Event 참여 조건을 만족할 때만 Runtime 대상에 포함한다.
- 같은 fixture version은 같은 프로필·성격·상태·위치·관계를 만든다.

구체 저장 구조와 식별자 형식은 비공개 데이터 모델에서 관리한다.
