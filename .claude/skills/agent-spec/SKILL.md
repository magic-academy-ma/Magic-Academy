---
description: Agent 이름과 역할을 받아 페르소나·행동 규칙·LangGraph 노드 인터페이스 초안을 생성할 때 사용
---

# /agent-spec

Agent 이름과 역할을 받아 페르소나·행동 규칙·LangGraph 노드 인터페이스 초안을 생성한다.

## 입력

사용자에게 다음을 확인한다 (이미 제공됐으면 생략):
1. Agent 이름 — 예: Student, Professor, Event Master
2. 핵심 역할 — 이 Agent가 시뮬레이션에서 하는 일
3. 참조할 도메인 문서 — `docs/02-domain/`의 관련 파일 (없으면 전체 참조)

## 사전 확인

- `docs/02-domain/`을 읽어 도메인 모델(Agent, 관계, 조직, 사건)과 어긋나지 않는지 확인한다
- `docs/04-feature-specs/agent-design/` 또는 `agent-runtime/`에 기존 스펙이 있으면 참조한다 (미구현 시 생략)
- 미정 항목(`docs/00-start-here/what-is-pending.md`)과 교차하는 부분은 명시하고 임의 확정하지 않는다

## 출력 형식

```markdown
# [Agent 이름] Agent 스펙 초안

## 1. 페르소나

**역할**: 한 줄 설명
**성격 특성**: 행동에 영향을 주는 주요 속성 (예: 호기심, 경쟁심)
**목표**: 이 Agent가 추구하는 것

## 2. 상태 구조

| 필드 | 타입 | 설명 |
|------|------|------|
| ...  | ...  | ...  |

(02-domain/의 Agent 상태 모델 기반)

## 3. 행동 규칙

1. [조건] → [행동]
2. [조건] → [행동]

## 4. LangGraph 노드 인터페이스

### 입력 (State)
- `agent_id`: str
- `current_tick`: int
- 기타 필요 필드

### 노드 목록
| 노드 이름 | 역할 |
|-----------|------|
| ...       | ...  |

### 출력 (State 업데이트)
- 변경되는 상태 필드 목록

## 5. 미정 항목

- [미정] ...

## 6. 관련 문서

- `docs/02-domain/`
- `docs/04-feature-specs/agent-design/` (미구현, 생성 후 추가)
```

## 주의

- 이 초안은 팀 검토 후 `04-feature-specs/`에 정식 스펙으로 작성한다
- 미정 항목을 임의로 확정하지 않고 반드시 표시한다
- Public 저장소이므로 팀원 개인정보를 포함하지 않는다
