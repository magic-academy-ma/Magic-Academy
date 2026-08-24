---
title: FR-04 방향성 관계 Policy
status: draft
updated: 2026-08-25
---

# FR-04 방향성 관계 Policy

## 1. 목적

Agent Runtime의 정성적 관계 signal을 결정론적인 관계 delta로 변환하고, 방향성 관계를 안전하게 갱신한다.

## 2. 범위

**포함**
- 6개 관계 척도의 signal·intensity 기반 delta 계산
- A→B와 B→A 방향성 분리
- Conflict Resolver의 단순 delta 합산과 최종 clamp
- stale 값 및 교차 Simulation 참조 차단
- effect별 추적 정보 보존

**제외**
- LLM의 숫자 delta 생성
- 관계 유형 임계값 결정
- Event·Magic 전용 효과
- WebSocket 전송
- 과거 관계 이력 조회 API

## 3. 입력 / 출력

| 항목 | 설명 |
|---|---|
| 입력 | Runtime 관계 signal, 관계 snapshot, 유효 Agent ID, policy version |
| 출력 | 방향성 관계별 effect candidate와 최종 적용 delta |
| 저장 | `relationships`의 방향성 6개 척도 |
| 추적 | 모든 원본 effect ID, rule ID, policy/resolver version, resolution ID |

## 4. 핵심 동작

1. Runtime 결과에 숫자 delta가 포함되면 입력 계약에서 거부한다.
2. source·target Agent와 동일 Simulation 소속 여부를 검증한다.
3. 자기 자신을 대상으로 한 signal을 거부한다.
4. signal과 intensity를 승인된 규칙표의 delta로 변환한다.
5. 동일 원인의 중복 effect를 제거한다.
6. 동일 방향·metric의 서로 다른 effect를 합산한다.
7. 관계별 범위로 최종값을 clamp한다.
8. 현재 DB 값이 snapshot의 before와 다르면 stale Commit으로 거부한다.
9. 동일 Tick transaction 안에서 관계 변경을 적용한다.

## 5. 경계 조건

- `(simulation_id, source_agent_id, target_agent_id)`는 유일하다.
- A→B와 B→A는 독립된 행이다.
- `source_agent_id != target_agent_id`여야 한다.
- 신규 Relationship ID는 UUIDv7이다.
- 동일 metric의 UP/DOWN signal이 한 Reaction에 함께 있으면 둘 다 거부한다.
- 합쳐진 effect의 모든 원본 `effect_id`를 보존한다.
- 일부 관계 write 실패 시 Tick 전체를 rollback한다.

## 6. 데이터 구조

| 필드 | 범위 |
|---|---:|
| affection | -100~100 |
| closeness | -100~100 |
| trust | -100~100 |
| tension | 0~100 |
| rivalry | 0~100 |
| dependency | 0~100 |

`relationships`는 Agent를 `(simulation_id, id)` 복합 FK로 참조한다.

## 7. 완료 기준

- [ ] 6개 관계 signal의 UP/DOWN과 LOW/MEDIUM/HIGH를 테스트한다.
- [ ] A→B 변화가 B→A에 영향을 주지 않는다.
- [ ] 자기 관계와 교차 Simulation 관계를 거부한다.
- [ ] LLM 숫자 delta 입력을 거부한다.
- [ ] 중복 effect는 한 번만 적용한다.
- [ ] 서로 다른 effect의 합산 후 clamp가 적용된다.
- [ ] 합산된 모든 effect ID가 보존된다.
- [ ] stale 값과 부분 write가 Tick 전체 rollback을 유발한다.
- [ ] 신규 Relationship ID가 UUIDv7이다.
- [ ] 단위·DB 통합·Tick E2E·Ruff·Mypy 검사가 통과한다.

## 8. 미정 항목

- [미정] 관계 유형 label 전환 임계값
- [미정] 관계 변화 이력의 Slice 2 저장 범위와 Slice 6 Replay 저장 범위의 경계

## 9. 관련 문서

- `docs/02-domain/relationships.md`
- `docs/03-system-design/policy-engine.md`
- `docs/03-system-design/policy-signal-delta.md`
- Confluence ERD v1.8
- PRD FR-04
