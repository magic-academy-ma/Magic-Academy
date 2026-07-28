---
title: API 명세 및 공통 규약
source: confluence/05_TECH/api-spec.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/12451842/API
status: draft
visibility: public
updated: 2026-07-28
source_updated: 2026-07-24
---

> 상태: Draft
> 작성자: 박혜정
> 최종 수정: 2026-07-24 (v1.1)
> Base URL: `https://{server}/v1`

---

# 1. 공통 규약

## 1.1 기본

| 항목 | 값 |
| --- | --- |
| 프로토콜 | HTTPS |
| 인코딩 | UTF-8 |
| 요청/응답 형식 | `application/json` |
| 시각 표기 | ISO 8601 UTC |
| 필드 표기 | `snake_case` |
| ID 형식 | ULID 또는 프로젝트 공통 ID 형식 |
| 시간 기준 | `simulation_day` + `current_tick` 기반 시뮬레이션 시간 |

---

## 1.2 인증

MVP에서는 별도 사용자 인증을 적용하지 않는다.

* 권한: 시뮬레이션 접근 가능한 클라이언트
* 관리자/테스트용 API는 별도 접근 제어 필요
* 향후 인증 도입 시 `Authorization: Bearer <token>` 방식 검토

---

## 1.3 공통 응답 형식

### 성공

```json
{
  "data": {}
}
```

목록 응답처럼 페이지네이션이나 부가 정보가 필요한 경우에만 `meta`를 추가한다.

```json
{
  "data": [],
  "meta": {
    "next_cursor": null,
    "has_more": false
  }
}
```

### 실패

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "시뮬레이션을 찾을 수 없습니다.",
    "trace_id": "req_9f8a2b1c"
  }
}
```

---

## 1.4 공통 에러 코드

| HTTP | code | 의미 |
| --- | --- | --- |
| 400 | `VALIDATION_FAILED` | 요청 형식 오류 |
| 404 | `RESOURCE_NOT_FOUND` | 요청한 리소스가 존재하지 않음 |
| 409 | `CONFLICT` | 현재 리소스 상태와 요청이 충돌 |
| 422 | `BUSINESS_RULE_VIOLATION` | 형식은 올바르나 비즈니스 규칙 위반 |
| 500 | `INTERNAL_ERROR` | 서버 내부 오류 |

---

## 1.5 페이지네이션

Agent, Event, Organization 등 목록 조회 API에 적용한다.

### 요청

```
?limit=20&cursor=<opaque>
```

| 파라미터 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `limit` | int | | 조회 개수. 기본 20, 최대 100 |
| `cursor` | string | | 다음 페이지 조회용 불투명 커서 |

### 응답

```json
{
  "data": [],
  "meta": {
    "next_cursor": "opaque_cursor",
    "has_more": true
  }
}
```

---

# 2. 리소스 목록

| 리소스 | 설명 | 엔드포인트 |
| --- | --- | --- |
| Simulation | 시뮬레이션 전체 진행 상태 | `/simulations` |
| Agent | 시뮬레이션 내 자율 행위자 | `/agents` |
| Agent State | Agent의 현재 상태 | `/agents/{agent_id}/state` |
| Memory | Agent의 기억 | `/agents/{agent_id}/memories` |
| Relationship | Agent 간 관계 | `/agents/{agent_id}/relationships` |
| Organization | 전공·동아리·기숙사 등의 조직 | `/organizations` |
| Event | 시뮬레이션에서 발생한 사건 | `/events` |
| World Map | 학교 공간 및 Agent 위치 | `/world/map` |
| User Persona | 사용자가 설정하는 Persona Agent | `/user-persona` |

---

# 3. Simulation API

## 3.1 Simulation 상태 조회

```
GET /simulations/{simulation_id}
```

**설명**: 특정 시뮬레이션의 현재 진행 상태를 조회한다.

### 요청 파라미터

| 위치 | 이름 | 타입 | 필수 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| path | `simulation_id` | string | ✓ | 유효한 Simulation ID | 조회할 시뮬레이션 ID |

### 응답 (200)

```json
{
  "data": {
    "id": "sim_01",
    "name": "Magic Academy",
    "status": "RUNNING",
    "current_day": 5,
    "current_tick": 125,
    "magic_enabled": true,
    "started_at": "2026-07-21T10:00:00Z",
    "ended_at": null
  }
}
```

### 응답 필드

| 이름 | 타입 | null 가능 | 설명 |
| --- | --- | --- | --- |
| `id` | string | | Simulation ID |
| `name` | string | | 시뮬레이션 이름 |
| `status` | enum | | `READY`, `RUNNING`, `PAUSED`, `COMPLETED` |
| `current_day` | int | | 현재 시뮬레이션 날짜 |
| `current_tick` | int | | 현재 Tick |
| `magic_enabled` | boolean | | 마법 시스템 활성화 여부 |
| `started_at` | datetime | ✓ | 시작 시각 |
| `ended_at` | datetime | ✓ | 종료 시각 |

### 에러

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 404 | `RESOURCE_NOT_FOUND` | Simulation이 존재하지 않음 |

---

## 3.2 Simulation 시작

```
POST /simulations/{simulation_id}/start
```

**설명**: 대기 중인 Simulation을 시작한다.

### 요청 파라미터

| 위치 | 이름 | 타입 | 필수 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| path | `simulation_id` | string | ✓ | 유효한 Simulation ID | 시작할 시뮬레이션 ID |

### 응답 (200)

```json
{
  "data": {
    "id": "sim_01",
    "status": "RUNNING",
    "current_day": 1,
    "current_tick": 0,
    "started_at": "2026-07-21T10:00:00Z"
  }
}
```

### 에러

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 404 | `RESOURCE_NOT_FOUND` | Simulation이 존재하지 않음 |
| 409 | `CONFLICT` | 이미 실행 중이거나 종료된 Simulation |
| 422 | `BUSINESS_RULE_VIOLATION` | 시작 조건을 만족하지 않음 |

### 비고

* 부수 효과: Simulation 실행 시작
* 멱등성: 있음 — 동일한 Simulation이 이미 `RUNNING` 상태인 경우 현재 상태를 반환한다.

---

# 4. Tick API

## 4.1 현재 Tick 조회

```
GET /simulations/{simulation_id}/ticks/current
```

**설명**: Simulation의 현재 Tick과 진행 상태를 조회한다.

### 요청 파라미터

| 위치 | 이름 | 타입 | 필수 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| path | `simulation_id` | string | ✓ | 유효한 Simulation ID | Simulation ID |

### 응답 (200)

```json
{
  "data": {
    "simulation_id": "sim_01",
    "current_day": 5,
    "tick_number": 125,
    "status": "RUNNING"
  }
}
```

### 에러

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 404 | `RESOURCE_NOT_FOUND` | Simulation이 존재하지 않음 |

---

## 4.2 Tick 진행 요청

```
POST /simulations/{simulation_id}/ticks/advance
```

**설명**: 테스트 또는 관리자 환경에서 Simulation을 다음 Tick으로 진행한다.

**권한**: Admin/Test 전용

### 요청 파라미터

| 위치 | 이름 | 타입 | 필수 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| path | `simulation_id` | string | ✓ | 유효한 Simulation ID | Simulation ID |

### 응답 (200)

```json
{
  "data": {
    "simulation_id": "sim_01",
    "previous_tick": 125,
    "current_tick": 126,
    "current_day": 5,
    "status": "COMPLETED"
  }
}
```

### 에러

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 404 | `RESOURCE_NOT_FOUND` | Simulation이 존재하지 않음 |
| 409 | `CONFLICT` | Simulation이 Tick 진행 가능한 상태가 아님 |

### 비고

* 부수 효과: Agent 실행, Intent 생성, 관계·상태·Memory 변경 가능
* 멱등성: 없음
* 실제 운영 환경에서는 Tick Orchestrator가 자동으로 진행한다.

---

# 5. Agent API

## 5.1 Agent 목록 조회

```
GET /simulations/{simulation_id}/agents
```

**설명**: Simulation에 포함된 Agent 목록과 현재 행동 및 위치를 조회한다.

### 요청 파라미터

| 위치 | 이름 | 타입 | 필수 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| path | `simulation_id` | string | ✓ | 유효한 Simulation ID | Simulation ID |
| query | `limit` | int | | 1~100, 기본 20 | 조회 개수 |
| query | `cursor` | string | | 불투명 문자열 | 페이지 커서 |

### 응답 (200)

```json
{
  "data": [
    {
      "id": "student-01",
      "name": "루나",
      "agent_type": "STUDENT",
      "current_action": "STUDY",
      "current_location": "library"
    }
  ],
  "meta": {
    "next_cursor": null,
    "has_more": false
  }
}
```

### 응답 필드

| 이름 | 타입 | null 가능 | 설명 |
| --- | --- | --- | --- |
| `id` | string | | Agent ID |
| `name` | string | | Agent 이름 |
| `agent_type` | enum | | `STUDENT`, `PROFESSOR`, `USER_PERSONA` |
| `current_action` | string | ✓ | 현재 행동 |
| `current_location` | string | ✓ | 현재 위치 |

### 에러

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 404 | `RESOURCE_NOT_FOUND` | Simulation이 존재하지 않음 |

---

## 5.2 Agent 상세 조회

```
GET /agents/{agent_id}
```

**설명**: Agent의 기본 정보, 현재 상태, 소속 조직을 조회한다.

### 응답 (200)

```json
{
  "data": {
    "id": "student-01",
    "simulation_id": "sim_01",
    "name": "루나",
    "agent_type": "STUDENT",
    "gender": "FEMALE",
    "personality_type": "INTROVERT",
    "role_description": "변환 마법을 전공하는 학생",
    "is_active": true,
    "state": {
      "hunger": 30,
      "fatigue": 40,
      "stress": 40,
      "satisfaction": 70,
      "mood": 20,
      "current_action": "STUDY",
      "current_location": "library"
    },
    "organizations": [
      {
        "id": "org-major-01",
        "name": "변환마법학과",
        "organization_type": "MAJOR",
        "membership_role": "MEMBER"
      }
    ]
  }
}
```

### 에러

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 404 | `RESOURCE_NOT_FOUND` | Agent가 존재하지 않음 |

---

# 6. Agent State API

## 6.1 현재 State 조회

```
GET /agents/{agent_id}/state
```

**설명**: Agent의 현재 내부 상태를 조회한다.

### 응답 (200)

```json
{
  "data": {
    "agent_id": "student-01",
    "hunger": 30,
    "fatigue": 40,
    "stress": 40,
    "satisfaction": 70,
    "mood": 20,
    "current_action": "STUDY",
    "current_location": "library",
    "updated_at": "2026-07-21T10:00:00Z"
  }
}
```

### 응답 필드

| 이름 | 타입 | null 가능 | 설명 |
| --- | --- | --- | --- |
| `agent_id` | string | | Agent ID |
| `hunger` | int | | 배고픔 수치 |
| `fatigue` | int | | 피로도 |
| `stress` | int | | 스트레스 |
| `satisfaction` | int | | 만족도 |
| `mood` | int | | 현재 기분 (0~100) |
| `current_action` | string | ✓ | 현재 행동 |
| `current_location` | string | ✓ | 현재 위치 |
| `updated_at` | datetime | | 마지막 변경 시각 |

### 에러

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 404 | `RESOURCE_NOT_FOUND` | Agent가 존재하지 않음 |

### 비고

* `agent_states`는 Agent당 현재 State 1개를 보유한다.
* 과거 상태 이력은 MVP API에서 제공하지 않는다.

---

# 7. Memory API

## 7.1 최근 Memory 조회

```
GET /agents/{agent_id}/memories
```

**설명**: Agent가 보유한 최근 Memory를 조회한다.

### 요청 파라미터

| 위치 | 이름 | 타입 | 필수 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| path | `agent_id` | string | ✓ | 유효한 Agent ID | Agent ID |
| query | `limit` | int | | 1~10, 기본 5 | 조회할 Memory 개수 |
| query | `cursor` | string | | 불투명 문자열 | 페이지 커서 |

### 응답 (200)

```json
{
  "data": [
    {
      "id": "memory-01",
      "event_id": "event-100",
      "memory_type": "OBSERVATION",
      "content": "루나와 함께 변환 마법 과제를 수행했다.",
      "importance": 70,
      "occurred_at": "2026-07-21T10:00:00Z",
      "last_accessed_at": "2026-07-21T10:10:00Z"
    }
  ],
  "meta": {
    "next_cursor": null,
    "has_more": false
  }
}
```

### 응답 필드

| 이름 | 타입 | null 가능 | 설명 |
| --- | --- | --- | --- |
| `id` | string | | Memory ID |
| `event_id` | string | ✓ | 관련 Event ID |
| `memory_type` | enum | | Memory 종류 (`OBSERVATION`, `CONVERSATION`, `REFLECTION`, `PLAN`) |
| `content` | string | | 기억 내용 |
| `importance` | int | | 중요도 |
| `occurred_at` | datetime | | 기억이 발생한 시각 |
| `last_accessed_at` | datetime | ✓ | 마지막 접근 시각 |

### 에러

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 404 | `RESOURCE_NOT_FOUND` | Agent가 존재하지 않음 |

### 비고

* Agent당 Memory 최대 개수는 10개이다.
* 초과 시 중요도가 낮은 Memory부터 요약 또는 삭제한다.
* Memory 검색은 Agent 내부 `RetrieveMemoryNode`에서 수행한다.

---

# 8. Relationship API

## 8.1 Agent 관계 조회

```
GET /agents/{agent_id}/relationships
```

**설명**: 특정 Agent와 연결된 다른 Agent와의 관계 정보를 조회한다.

### 요청 파라미터

| 위치 | 이름 | 타입 | 필수 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| path | `agent_id` | string | ✓ | 유효한 Agent ID | 기준 Agent ID |
| query | `limit` | int | | 1~100, 기본 20 | 조회 개수 |
| query | `cursor` | string | | 불투명 문자열 | 페이지 커서 |

### 응답 (200)

```json
{
  "data": [
    {
      "id": "relationship-01",
      "source_agent_id": "student-01",
      "target_agent_id": "student-02",
      "scores": {
        "affection": 70,
        "intimacy": 60,
        "trust": 60,
        "tension": 10,
        "competition": 30,
        "dependence": 20
      },
      "relationship_type": "FRIEND"
    }
  ],
  "meta": {
    "next_cursor": null,
    "has_more": false
  }
}
```

### 관계 수치 규칙

* 관계 수치는 Agent 간 방향성을 가진다.
* Agent는 DB를 직접 수정하지 않고 Intent를 생성한다.
* Orchestrator가 모든 Intent를 수집해 충돌 조정 후 반영한다.

### 에러

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 404 | `RESOURCE_NOT_FOUND` | Agent가 존재하지 않음 |

---

# 9. Event API

## 9.1 Event 목록 조회

```
GET /simulations/{simulation_id}/events
```

**설명**: Simulation에서 발생한 Event 목록을 조회한다.

### 요청 파라미터

| 위치 | 이름 | 타입 | 필수 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| path | `simulation_id` | string | ✓ | 유효한 Simulation ID | Simulation ID |
| query | `limit` | int | | 1~100, 기본 20 | 조회 개수 |
| query | `cursor` | string | | 불투명 문자열 | 페이지 커서 |
| query | `event_type` | enum | | EventType | Event 유형 필터 |
| query | `status` | enum | | Event 상태 | 상태 필터 |

### 응답 (200)

```json
{
  "data": [
    {
      "id": "event-100",
      "event_type": "RANDOM_INCIDENT",
      "title": "마법 실험실 폭발 사고",
      "description": "마법 실험실에서 불안정한 마력이 폭발했다.",
      "status": "COMPLETED",
      "simulation_day": 5,
      "started_at": "2026-07-21T10:00:00Z",
      "ended_at": "2026-07-21T10:05:00Z"
    }
  ],
  "meta": {
    "next_cursor": null,
    "has_more": false
  }
}
```

---

## 9.2 Event 상세 조회

```
GET /events/{event_id}
```

**설명**: 특정 Event의 상세 정보와 참여 Agent를 조회한다.

### 응답 (200)

```json
{
  "data": {
    "id": "event-100",
    "simulation_id": "sim_01",
    "event_type": "RANDOM_INCIDENT",
    "title": "마법 실험실 폭발 사고",
    "description": "마법 실험실에서 불안정한 마력이 폭발했다.",
    "status": "COMPLETED",
    "simulation_day": 5,
    "started_at": "2026-07-21T10:00:00Z",
    "ended_at": "2026-07-21T10:05:00Z",
    "metadata": {},
    "participants": [
      {
        "agent_id": "student-01",
        "participant_role": "ACTOR",
        "action_taken": "STABILIZE_MAGIC",
        "result": {
          "relationship_changed": true
        }
      }
    ]
  }
}
```

### Event Type (MVP 8종)

```
CLASS
GROUP_PROJECT
EXAM
MEETING
MT
FESTIVAL
STUDENT_COUNCIL
RANDOM_INCIDENT
```

### Event Status

```
SCHEDULED
ONGOING
COMPLETED
CANCELLED
```

### 에러

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 404 | `RESOURCE_NOT_FOUND` | Event가 존재하지 않음 |

---

# 10. World Map API

## 10.1 학교 맵 및 Agent 위치 조회

```
GET /simulations/{simulation_id}/world/map
```

**설명**: 학교 공간과 각 공간에 위치한 Agent를 조회한다.

### 응답 (200)

```json
{
  "data": {
    "locations": [
      {
        "id": "library",
        "name": "마법 도서관",
        "agents": ["student-01", "student-02"]
      },
      {
        "id": "magic_lab",
        "name": "마법 실험실",
        "agents": []
      }
    ]
  }
}
```

### 에러

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 404 | `RESOURCE_NOT_FOUND` | Simulation이 존재하지 않음 |

---

# 11. Organization API

## 11.1 Organization 목록 조회

```
GET /simulations/{simulation_id}/organizations
```

**설명**: Simulation에 포함된 조직 목록을 조회한다.

### 요청 파라미터

| 위치 | 이름 | 타입 | 필수 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| path | `simulation_id` | string | ✓ | 유효한 Simulation ID | Simulation ID |
| query | `limit` | int | | 1~100, 기본 20 | 조회 개수 |
| query | `cursor` | string | | 불투명 문자열 | 페이지 커서 |
| query | `organization_type` | enum | | 조직 유형 | 조직 유형 필터 |

### 응답 (200)

```json
{
  "data": [
    {
      "id": "org-major-01",
      "organization_type": "MAJOR",
      "name": "변환마법학과",
      "description": "변환 마법을 전공하는 조직",
      "is_active": true,
      "members": [
        {
          "agent_id": "student-01",
          "membership_role": "MEMBER",
          "joined_at": "2026-07-21T10:00:00Z"
        }
      ]
    }
  ],
  "meta": {
    "next_cursor": null,
    "has_more": false
  }
}
```

### Organization Type

```
MAJOR
CLUB
DORMITORY
```

### Membership Role

```
MEMBER
LEADER
PROFESSOR
RESIDENT
```

### 에러

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 404 | `RESOURCE_NOT_FOUND` | Simulation이 존재하지 않음 |

---

# 12. User Persona API

User Persona Agent는 사용자의 개입을 시뮬레이션에 반영하기 위한 특수 Agent다. 사용자는 성격 및 성향만 설정할 수 있으며, 직접 조종하거나 행동을 명령할 수 없다.

## 12.1 User Persona 설정 옵션 조회

```
GET /simulations/{simulation_id}/user-persona/config
```

**설명**: User Persona Agent에 설정 가능한 성격 및 성향 옵션을 조회한다.

### 응답 (200)

```json
{
  "data": {
    "personality_options": {
      "extraversion": { "type": "SLIDER", "min": 0, "max": 100 },
      "agreeableness": { "type": "SLIDER", "min": 0, "max": 100 },
      "conscientiousness": { "type": "SLIDER", "min": 0, "max": 100 },
      "openness": { "type": "SLIDER", "min": 0, "max": 100 },
      "emotional_stability": { "type": "SLIDER", "min": 0, "max": 100 }
    }
  }
}
```

---

## 12.2 User Persona 생성 및 적용

```
POST /simulations/{simulation_id}/user-persona
```

**설명**: 사용자가 설정한 성격 및 성향을 기반으로 User Persona Agent를 생성하고 Simulation에 적용한다.

### 요청 파라미터 (body)

| 이름 | 타입 | 필수 | 제약 | 설명 |
| --- | --- | --- | --- | --- |
| `extraversion` | int | ✓ | 0~100 | 외향성 |
| `agreeableness` | int | ✓ | 0~100 | 우호성 |
| `conscientiousness` | int | ✓ | 0~100 | 성실성 |
| `openness` | int | ✓ | 0~100 | 개방성 |
| `emotional_stability` | int | ✓ | 0~100 | 정서 안정성 |

### 응답 (201)

```json
{
  "data": {
    "id": "user-persona-01",
    "simulation_id": "academy-001",
    "agent_type": "USER_PERSONA",
    "personality": {
      "extraversion": 25,
      "agreeableness": 90,
      "conscientiousness": 60,
      "openness": 80,
      "emotional_stability": 55
    },
    "status": "APPLIED",
    "locked": true
  }
}
```

### 에러

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 404 | `RESOURCE_NOT_FOUND` | Simulation이 존재하지 않음 |
| 409 | `CONFLICT` | 이미 User Persona가 적용됨 |
| 422 | `BUSINESS_RULE_VIOLATION` | 설정값이 허용 범위를 벗어남 |

### 비고

* MVP에서는 적용 후 성격 및 성향을 다시 변경할 수 없다.

---

## 12.3 적용된 User Persona 조회

```
GET /simulations/{simulation_id}/user-persona
```

### 응답 (200)

```json
{
  "data": {
    "id": "user-persona-01",
    "simulation_id": "academy-001",
    "agent_type": "USER_PERSONA",
    "personality": {
      "extraversion": 25,
      "agreeableness": 90,
      "conscientiousness": 60,
      "openness": 80,
      "emotional_stability": 55
    },
    "status": "APPLIED",
    "locked": true
  }
}
```

### 에러

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 404 | `RESOURCE_NOT_FOUND` | User Persona가 아직 설정되지 않음 |

---

# 13. Agent Runtime API (Internal)

Agent Runtime은 Backend 내부 API로, Frontend에 노출하지 않는다. Simulation Orchestrator가 Tick 진행 시 호출한다.

## 13.1 Agent Runtime 실행 흐름

```
Observe
    ↓
Retrieve Memory
    ↓
Evaluate
    ↓
Decide Action
    ↓
Generate Intent
    ↓
Generate Memory Candidate
    ↓
Reflect If Needed
```

## 13.2 Agent Runtime 실행

```
POST /internal/simulations/{simulation_id}/agents/{agent_id}/runtime
```

### 요청

| 위치 | 이름 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- | --- |
| path | `simulation_id` | string | ✓ | Simulation 식별자 |
| path | `agent_id` | string | ✓ | 실행 대상 Agent |
| body | `tick_number` | bigint | ✓ | 실행 기준 Tick |

### 에러

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 404 | `RESOURCE_NOT_FOUND` | Simulation 또는 Agent가 존재하지 않음 |
| 409 | `CONFLICT` | 해당 Tick의 Agent Runtime이 이미 실행됨 |
| 422 | `BUSINESS_RULE_VIOLATION` | 실행할 수 없는 상태의 Agent |
| 500 | `AGENT_RUNTIME_ERROR` | Agent Runtime 실행 중 내부 오류 |

## 13.3 Intent Schema

Agent Runtime은 DB를 직접 수정하지 않고 Intent만 반환한다. 상태·관계 변화는 signal로 표현하며, 수치 계산은 Policy Engine이 담당한다.

```json
{
  "agent_id": "student-01",
  "tick_number": 120,
  "action_type": "TALK",
  "target_agent_id": "student-02",
  "content": "루나는 미아에게 시험 준비를 같이 하자고 제안했다.",
  "signals": {
    "relationship": ["TRUST_UP", "AFFECTION_UP", "TENSION_DOWN"],
    "state": ["STRESS_DOWN"]
  }
}
```

### Action Type

```
TALK
MOVE
STUDY
REST
EAT
PARTICIPATE_EVENT
```

## 13.4 Orchestrator 연동

```
[Tick 시작]
    ↓
[Agent Runtime 실행]
    ↓
[Agent별 Intent 생성]
    ↓
[Orchestrator가 Intent 수집]
    ↓
[Intent 충돌 처리 — signal → 수치 변환은 Policy Engine이 수행]
    ↓
[Tick 단위 Batch Commit]
    ↓
[State / Relationship / Event / Memory 반영]
    ↓
[WebSocket을 통한 변경사항 전달]
```

---

# 14. WebSocket API

## 14.1 Simulation 실시간 연결

```
wss://{server}/v1/ws/simulations/{simulation_id}
```

**설명**: Tick 진행, Agent 행동, Event, Relationship 변화를 실시간으로 전달한다.

## 14.2 Tick 업데이트

```json
{
  "type": "TICK_UPDATED",
  "data": {
    "simulation_id": "sim_01",
    "current_day": 5,
    "tick_number": 126
  }
}
```

## 14.3 Agent 행동 변경

```json
{
  "type": "AGENT_ACTION_UPDATED",
  "data": {
    "agent_id": "student-01",
    "action": "MOVE",
    "location": "library"
  }
}
```

## 14.4 Event 발생

```json
{
  "type": "EVENT_CREATED",
  "data": {
    "event_id": "event-100",
    "event_type": "RANDOM_INCIDENT",
    "title": "마법 실험실 폭발 사고",
    "description": "마법 실험 중 마력이 폭주했다.",
    "location": "magic_lab"
  }
}
```

## 14.5 Relationship 변경

```json
{
  "type": "RELATIONSHIP_UPDATED",
  "data": {
    "relationship_id": "relationship-01",
    "source_agent_id": "student-01",
    "target_agent_id": "student-02",
    "changes": {
      "affection": 5,
      "trust": 3,
      "tension": -1
    }
  }
}
```

---

# 15. Backend Internal Contract

## 15.1 Full Intent Schema

```json
{
  "run_id": "sim-20260721-01",
  "tick_number": 126,
  "agent_id": "student-01",
  "status": "PROPOSED",
  "intent": {
    "action_type": "TALK",
    "target_agent_id": "student-02",
    "target_location_id": null,
    "related_event_id": null,
    "utterance": "루나는 미아에게 시험 준비를 같이 하자고 제안했다.",
    "motivation_summary": "시험 준비를 함께하며 협력하려고 한다.",
    "reaction": {
      "valence": "POSITIVE",
      "intensity": "MEDIUM",
      "relationship_signals": ["TRUST_UP", "AFFECTION_UP"],
      "state_signals": ["STRESS_DOWN"]
    }
  },
  "memory_candidates": [],
  "reflection_candidate": null
}
```

---

# 16. 데이터 타입

## Agent Type

```
STUDENT
PROFESSOR
USER_PERSONA
```

## Simulation Status

```
READY
RUNNING
PAUSED
COMPLETED
```

## Event Type

```
CLASS
GROUP_PROJECT
EXAM
MEETING
MT
FESTIVAL
STUDENT_COUNCIL
RANDOM_INCIDENT
```

## Event Status

```
SCHEDULED
ONGOING
COMPLETED
CANCELLED
```

## Memory Type

```
OBSERVATION
CONVERSATION
REFLECTION
PLAN
```

## Relationship Type

```
FRIEND
RIVAL
SENIOR_JUNIOR
CONFESSION
BETRAYAL
RECONCILIATION
```

## Organization Type

```
MAJOR
CLUB
DORMITORY
```

---

# 17. MVP API 범위

## 포함

* Simulation 상태 조회 / 시작
* 현재 Tick 조회
* Agent 목록 및 상세 조회
* Agent 현재 State 조회
* 최근 Memory 조회
* Relationship 조회
* Event 목록 및 상세 조회
* 학교 Map 및 Agent 위치 조회
* Organization 조회
* User Persona 설정
* WebSocket 기반 실시간 변화 전달

## 제외

* Agent 직접 명령
* Memory 전체 타임라인 / 검색 Frontend API
* Relationship Graph 상시 실시간 렌더링
* Agent State 이력 조회
* Event 직접 생성 API
* Organization 생성·수정 API
* 사용자 Agent 직접 조종 API

---

# 18. 변경 이력

| 날짜 | 버전 | 변경 | 파괴적 |
| --- | --- | --- | --- |
| 2026-07-21 | v0.1 | API 명세서 초안 | N |
| 2026-07-24 | v1.1 | Agent Runtime 출력 계약 및 Agent State mood 타입 정리 | N |
