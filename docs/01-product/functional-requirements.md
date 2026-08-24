---
title: 핵심 기능 정의 (FR)
source: confluence/02_PRODUCT_PLANNING/functional-requirements.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/16777846
status: draft
visibility: public
updated: 2026-08-06
source_updated: 2026-08-05
---

| ID | 기능 | 핵심 요구사항 | MVP | 상태 |
| --- | --- | --- | --- | --- |
| FR-01 | 학생 Agent | Student 5명이 동일 Runtime으로 자율 행동. mood는 -100~100, 나머지 상태는 0~100. 활성 Memory 최대 10개 | ✓ | 확정 |
| FR-02 | 교수 Agent | Professor 1명이 관련 수업·시험·사건이 있을 때 실행 | ✓ | 확정 |
| FR-03 | User Persona | Student 5명 중 1명. 시작 전 성격 설정, 시작 후 직접 명령·재설정 불가 | ✓ | 검토 중 |
| FR-04 | 관계 시스템 | 방향성 affection·closeness·trust·tension·rivalry·dependency 관리 | ✓ | 확정 |
| FR-05 | 일반 Event | 수업·조별과제·시험·미팅·MT·축제·랜덤 일반 사건 | ✓ | 확정 |
| FR-06 | 시간 진행 | 1 Tick=8분=1블록, 하루 MORNING·AFTERNOON·EVENING 3 Tick. 중첩 실행 금지 | ✓ | 확정 |
| FR-07 | 조직 | 1단계는 단일 전공만 사용 | ✓ | 확정 |
| FR-08 | 공간 | 교실·식당·도서관·연구실·기숙사 공간 | ✓ | 확정 |
| FR-09 | Event Master | 매 Tick 일반 대학 생활 Event 후보 생성. DB 직접 쓰기 금지 | ✓ | 확정 |
| FR-10 | 확장성 | 단과대학·Agent·조직·사건 규모 확장 | ✗ | 추후 |
| FR-11 | Inspector | 상태·성격·관계·기억·Decision Explanation을 읽기 전용으로 표시 | ✓ | 검토 중 |
| FR-12 | Magic ON/OFF | Magic Layer 활성 설정. 변경 가능 시점은 미확정 | ✓ | 검토 중 |
| FR-13 | 초기 설정 저장 | 성격·조직·seed 등 초기 설정 저장 | ✓ | 검토 중 |
| FR-14 | 설정 공유 | 저장 설정을 권한 정책에 따라 공유 | ✓ | 검토 중 |
| FR-15 | 설정 가져오기 | 공유받은 설정으로 새 Simulation 생성 | ✓ | 검토 중 |
| FR-16 | Replay | 저장된 Tick Event·상태·관계 변화를 시간순 재생 | ✓ | 검토 중 |
| FR-17 | 시점 복원 | 특정 Tick snapshot 조회·복원 전용. 새 실행 생성·이력 변경 없음. 분기 생성 MVP 제외 | ✓ | 확정 |
| FR-18 | 캠페인·테스트 시나리오 | 고정 사건·종료 조건을 가진 실행 시나리오 | ✓ | 검토 중 |
| FR-19 | 인증·접근 제어 | MVP 포함. 구체 방식과 보호 경계는 비공개 보안 문서에서 관리 | ✓ | 검토 중 |
| FR-20 | Magic Layer | world_state 조건 충족 시에만 특수 사건 후보 생성. 수치·기간은 Policy가 결정 | ✓ | 확정 |
| FR-21 | 대표 캠페인 | 10 Tick 정상 완료. 사용자 중단은 ABORTED이며 결과 판정 없음 | ✓ | 검토 중 |
| FR-22 | LLM 실행 쿼터 | Tick당 Agent별 LLM 호출 횟수 및 비용 상한 설정 | ✓ | 확정 |

---

## 상태값

| 상태 | 범위 |
| --- | --- |
| hunger | 0~100 |
| fatigue | 0~100 |
| stress | 0~100 |
| satisfaction | 0~100 |
| mood | -100~100 |

## 관계값

| 필드 | 의미 | 범위 |
| --- | --- | --- |
| affection | 호감도 | -100~100 |
| closeness | 친밀도 | -100~100 |
| trust | 신뢰도 | -100~100 |
| tension | 긴장도 | 0~100 |
| rivalry | 라이벌 의식 | 0~100 |
| dependency | 의존도 | 0~100 |

## 대표 캠페인 종료

- Tick 10 결말 Event와 마지막 batch commit 완료 후 COMPLETED
- 사용자 중단은 ABORTED
- ABORTED 실행에는 성공·실패 판정을 생성하지 않음
- Magic OFF와 ON은 동일한 초기 조건을 기준으로 비교 가능해야 함
