---
title: "[ERD] Magic Academy MVP 데이터 모델 초안"
source: confluence/05_TECH/data-model.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/12189697/ERD+Magic+Academy+MVP
status: draft
visibility: public
updated: 2026-07-28
source_updated: 2026-07-28
---

**상태:** Draft
**최종 수정:** 2026-07-27
**버전:** v0.3
**DBMS / 버전:** PostgreSQL 16 + pgvector

## 1. 범위

### 이 문서가 다루는 것

Magic Academy MVP의 핵심 데이터 구조를 정의한다.

* 시뮬레이션
* Agent
* Agent 상태
* 기억
* 관계
* 조직
* 조직 소속
* 사건
* 사건 참여

### 다루지 않는 것

* 사용자 인증 및 결제
* 커뮤니티 공유 기능
* 설정 공유 및 Replay
* 캐시 및 로그 저장소
* 교수 수업·과제·시험 상세 구조
* 운영 모니터링 데이터

---

## 2. 명명 규칙

| 대상 | 규칙 | 예 |
| --- | --- | --- |
| 테이블 | 복수형 `snake_case` | `agents`, `agent_memories` |
| 컬럼 | `snake_case` | `created_at` |
| PK | `id` | `id` |
| FK | `<대상 단수>_id` | `agent_id` |
| 불리언 | `is_` / `has_` 접두사 | `is_active` |
| 시각 | `_at` 접미사, UTC | `occurred_at` |
| 인덱스 | `idx_<테이블>_<컬럼>` | `idx_agents_simulation_id` |
| 유니크 | `uq_<테이블>_<컬럼>` | `uq_relationships_pair` |
| 외래키 | `fk_<테이블>_<대상>` | `fk_agents_simulation` |

모든 테이블은 `id`, `created_at`, `updated_at`을 가진다.

PK는 애플리케이션에서 생성하는 `ULID`를 사용한다. PostgreSQL에는 `CHAR(26)`으로 저장하는 것을 초안 기준으로 한다.

---

## 3. 전체 관계도

```
erDiagram
    SIMULATIONS ||--o{ AGENTS : "Agent 포함"
    SIMULATIONS ||--o{ ORGANIZATIONS : "조직 포함"
    SIMULATIONS ||--o{ EVENTS : "사건 발생"
    SIMULATIONS ||--o{ RELATIONSHIPS : "관계 관리"

    AGENTS ||--|| AGENT_STATES : "현재 상태 보유"
    AGENTS ||--o{ AGENT_MEMORIES : "기억 보유"

    AGENTS ||--o{ RELATIONSHIPS : "관계 출발"
    AGENTS ||--o{ RELATIONSHIPS : "관계 대상"

    AGENTS ||--o{ ORGANIZATION_MEMBERSHIPS : "조직 가입"
    ORGANIZATIONS ||--o{ ORGANIZATION_MEMBERSHIPS : "구성원 보유"

    EVENTS ||--o{ EVENT_PARTICIPANTS : "참여자 보유"
    AGENTS ||--o{ EVENT_PARTICIPANTS : "사건 참여"

    EVENTS o|--o{ AGENT_MEMORIES : "관련 기억 생성"

    SIMULATIONS {
        char_26 id PK
        varchar_100 name
        varchar_20 status
        int current_day
        bigint current_tick
        boolean magic_enabled
        timestamptz started_at
        timestamptz ended_at
        timestamptz deleted_at
        timestamptz created_at
        timestamptz updated_at
    }

    AGENTS {
        char_26 id PK
        char_26 simulation_id FK
        varchar_20 agent_type
        varchar_50 name
        varchar_20 gender
        varchar_30 personality_type
        smallint openness
        smallint conscientiousness
        smallint extraversion
        smallint agreeableness
        smallint emotional_stability
        text role_description
        boolean is_active
        timestamptz deleted_at
        timestamptz created_at
        timestamptz updated_at
    }

    AGENT_STATES {
        char_26 id PK
        char_26 agent_id FK,UK
        smallint hunger
        smallint fatigue
        smallint stress
        smallint satisfaction
        smallint mood
        varchar_50 current_action
        varchar_50 current_location
        timestamptz created_at
        timestamptz updated_at
    }

    AGENT_MEMORIES {
        char_26 id PK
        char_26 agent_id FK
        char_26 event_id FK
        text content
        varchar_20 memory_type
        smallint importance
        timestamptz occurred_at
        timestamptz last_accessed_at
        vector embedding
        timestamptz created_at
        timestamptz updated_at
    }

    RELATIONSHIPS {
        char_26 id PK
        char_26 simulation_id FK
        char_26 source_agent_id FK
        char_26 target_agent_id FK
        smallint affection
        smallint intimacy
        smallint trust
        smallint tension
        smallint competition
        smallint dependence
        varchar_30 relationship_type
        timestamptz created_at
        timestamptz updated_at
    }

    ORGANIZATIONS {
        char_26 id PK
        char_26 simulation_id FK
        varchar_20 organization_type
        varchar_100 name
        text description
        boolean is_active
        timestamptz deleted_at
        timestamptz created_at
        timestamptz updated_at
    }

    ORGANIZATION_MEMBERSHIPS {
        char_26 id PK
        char_26 simulation_id FK
        char_26 organization_id FK
        char_26 agent_id FK
        varchar_30 membership_role
        timestamptz joined_at
        timestamptz left_at
        timestamptz created_at
        timestamptz updated_at
    }

    EVENTS {
        char_26 id PK
        char_26 simulation_id FK
        varchar_30 event_type
        varchar_100 title
        text description
        varchar_20 status
        int simulation_day
        timestamptz started_at
        timestamptz ended_at
        jsonb metadata
        timestamptz created_at
        timestamptz updated_at
    }

    EVENT_PARTICIPANTS {
        char_26 id PK
        char_26 event_id FK
        char_26 agent_id FK
        varchar_30 participant_role
        text action_taken
        jsonb result
        timestamptz created_at
        timestamptz updated_at
    }
```

---

# 4. 엔티티

## 4.1 `simulations`

**설명:** 하나의 Magic Academy 시뮬레이션 실행 단위를 저장한다.
**한 행의 의미:** 사용자가 생성하거나 실행한 시뮬레이션 하나
**예상 규모:** 초기 수십 건 / 사용자 및 Replay 기능 도입 후 증가

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| id | CHAR(26) | N | | PK | Simulation ULID |
| name | VARCHAR(100) | N | | | 시뮬레이션 이름 |
| status | VARCHAR(20) | N | `'ready'` | CHECK IN (`ready`, `running`, `paused`, `completed`, `failed`) | 실행 상태 |
| current_day | INT | N | `1` | CHECK `current_day >= 1` | 현재 시뮬레이션 날짜 |
| current_tick | BIGINT | N | `0` | CHECK `current_tick >= 0` | 누적 Tick |
| magic_enabled | BOOLEAN | N | `true` | | Magic 요소 활성화 여부 |
| started_at | TIMESTAMPTZ | Y | | | 실행 시작 시각, 미시작이면 NULL |
| ended_at | TIMESTAMPTZ | Y | | | 실행 종료 시각 |
| deleted_at | TIMESTAMPTZ | Y | | | 소프트 삭제 시각 |
| created_at | TIMESTAMPTZ | N | `now()` | | 생성 시각 |
| updated_at | TIMESTAMPTZ | N | `now()` | | 수정 시각 |

### 인덱스

| 이름 | 컬럼 | 종류 | 이유 |
| --- | --- | --- | --- |
| `idx_simulations_status_created` | `status, created_at DESC` | BTREE | 상태별 최신 시뮬레이션 조회 |

---

## 4.2 `agents`

**설명:** 학생, 교수, User Persona 등 모든 Agent의 공통 정보를 저장한다.
**한 행의 의미:** 시뮬레이션에 존재하는 Agent 한 명
**예상 규모:** 1단계 6명 / 2단계 13명 / 3단계 25명

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| id | CHAR(26) | N | | PK | Agent ULID |
| simulation_id | CHAR(26) | N | | FK → `simulations.id` | 소속 시뮬레이션 |
| agent_type | VARCHAR(20) | N | | CHECK IN (`student`, `professor`, `user_persona`) | Agent 종류 |
| name | VARCHAR(50) | N | | | Agent 이름 |
| gender | VARCHAR(20) | Y | | CHECK IN (`male`, `female`, `non_binary`, `unspecified`) | 성별, 미정이면 NULL |
| personality_type | VARCHAR(30) | N | | | 성취 경쟁형, 사교 협력형 등 대표 성향 코드 |
| openness | SMALLINT | N | `50` | CHECK BETWEEN 0 AND 100 | 개방성 |
| conscientiousness | SMALLINT | N | `50` | CHECK BETWEEN 0 AND 100 | 성실성 |
| extraversion | SMALLINT | N | `50` | CHECK BETWEEN 0 AND 100 | 외향성 |
| agreeableness | SMALLINT | N | `50` | CHECK BETWEEN 0 AND 100 | 우호성 |
| emotional_stability | SMALLINT | N | `50` | CHECK BETWEEN 0 AND 100 | 정서 안정성 |
| role_description | TEXT | Y | | | Agent 대표 역할 설명 |
| is_active | BOOLEAN | N | `true` | | 활동 가능 여부 |
| deleted_at | TIMESTAMPTZ | Y | | | 소프트 삭제 시각 |
| created_at | TIMESTAMPTZ | N | `now()` | | 생성 시각 |
| updated_at | TIMESTAMPTZ | N | `now()` | | 수정 시각 |

User Persona Agent는 사용자가 입력한 다섯 가지 성격 수치를 저장한다. 기본 Student Agent와 Professor Agent도 동일한 성격 수치 구조를 사용한다.

### 제약

* `UNIQUE(simulation_id, id)` — `uq_agents_simulation_id`

### 인덱스

| 이름 | 컬럼 | 종류 | 이유 |
| --- | --- | --- | --- |
| `idx_agents_simulation_type` | `simulation_id, agent_type` | BTREE | 시뮬레이션별 Agent 목록 조회 |
| `idx_agents_simulation_active` | `simulation_id, is_active` | BTREE | 활성 Agent 조회 |

---

## 4.3 `agent_states`

**설명:** Agent의 현재 내부 상태값을 저장한다.
**한 행의 의미:** Agent 한 명의 현재 상태
**예상 규모:** Agent당 1행

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| id | CHAR(26) | N | | PK | 상태 ULID |
| agent_id | CHAR(26) | N | | FK → `agents.id`, UNIQUE | 대상 Agent |
| hunger | SMALLINT | N | `50` | CHECK BETWEEN 0 AND 100 | 배고픔 |
| fatigue | SMALLINT | N | `0` | CHECK BETWEEN 0 AND 100 | 피로도 |
| stress | SMALLINT | N | `0` | CHECK BETWEEN 0 AND 100 | 스트레스 |
| satisfaction | SMALLINT | N | `50` | CHECK BETWEEN 0 AND 100 | 만족도 |
| mood | SMALLINT | N | `50` | CHECK BETWEEN 0 AND 100 | 기분 |
| current_action | VARCHAR(50) | Y | | | 현재 수행 행동 |
| current_location | VARCHAR(50) | Y | | | 현재 위치 |
| created_at | TIMESTAMPTZ | N | `now()` | | 생성 시각 |
| updated_at | TIMESTAMPTZ | N | `now()` | | 수정 시각 |

### 제약

* 유니크: `uq_agent_states_agent_id`
* Agent 한 명당 현재 상태는 한 행만 존재한다.

---

## 4.4 `agent_memories`

**설명:** Agent가 기억하는 사건과 상호작용 정보를 저장한다.
**한 행의 의미:** Agent가 보유한 기억 하나
**예상 규모:** MVP Agent당 최대 10개 활성 기억

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| id | CHAR(26) | N | | PK | 기억 ULID |
| agent_id | CHAR(26) | N | | FK → `agents.id` | 기억 소유 Agent |
| event_id | CHAR(26) | Y | | FK → `events.id` | 관련 사건, 일반 기억이면 NULL |
| content | TEXT | N | | | 기억 내용 |
| memory_type | VARCHAR(20) | N | `'observation'` | CHECK IN (`observation`, `conversation`, `reflection`, `plan`) | 기억 유형 |
| importance | SMALLINT | N | `1` | CHECK BETWEEN 1 AND 10 | 중요도 |
| occurred_at | TIMESTAMPTZ | N | | | 기억 대상이 발생한 시각 |
| last_accessed_at | TIMESTAMPTZ | Y | | | 마지막 회상 시각 |
| embedding | VECTOR(n) | Y | | | 의미 검색용 임베딩 |
| created_at | TIMESTAMPTZ | N | `now()` | | 생성 시각 |
| updated_at | TIMESTAMPTZ | N | `now()` | | 수정 시각 |

> `VECTOR`의 차원 `n`은 사용할 임베딩 모델 확정 후 결정한다.

`memory_type`은 API 명세와 동일하게 `observation`, `conversation`, `reflection`, `plan`으로 통일한다. `interaction`, `summary` 값은 사용하지 않는다.

### 1단계 활성 Memory 보존 정책

Memory 저장 후 Agent별 활성 Memory가 10개를 초과하면 `importance`가 가장 낮은 Memory부터 삭제하고 10개 이하가 될 때까지 반복한다.

`importance`가 동일한 경우의 삭제 우선순위는 미결 사항으로 유지한다.

### 인덱스

| 이름 | 컬럼 | 종류 | 이유 | 적용 시점 |
| --- | --- | --- | --- | --- |
| `idx_agent_memories_agent_occurred` | `agent_id, occurred_at DESC` | BTREE | Agent별 최신 기억 조회 | 초기 마이그레이션 |
| `idx_agent_memories_embedding` | `embedding` | HNSW | 유사도 기반 기억 검색 | 임베딩 모델과 VECTOR(n) 확정 후 |

HNSW 인덱스는 초기 테이블 생성 마이그레이션에 포함하지 않는다. 임베딩 모델과 벡터 차원을 확정한 이후 별도 마이그레이션에서 생성한다.

---

## 4.5 `relationships`

**설명:** 두 Agent 사이의 방향성 있는 관계 수치와 관계 상태를 저장한다.
**한 행의 의미:** 출발 Agent가 대상 Agent에게 가지는 관계 하나
**예상 규모:** 모든 생활 Agent 간 방향성 관계를 생성할 경우 1단계 6명 기준 최대 30행, 2단계 13명 기준 최대 156행, 3단계 25명 기준 최대 600행

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| id | CHAR(26) | N | | PK | 관계 ULID |
| simulation_id | CHAR(26) | N | | FK → `simulations.id` | 소속 시뮬레이션 |
| source_agent_id | CHAR(26) | N | | 복합 FK → agents | 관계를 느끼는 Agent |
| target_agent_id | CHAR(26) | N | | 복합 FK → agents | 관계 대상 Agent |
| affection | SMALLINT | N | `0` | CHECK BETWEEN -100 AND 100 | 호감도 |
| intimacy | SMALLINT | N | `0` | CHECK BETWEEN 0 AND 100 | 친밀도 |
| trust | SMALLINT | N | `0` | CHECK BETWEEN -100 AND 100 | 신뢰도 |
| tension | SMALLINT | N | `0` | CHECK BETWEEN 0 AND 100 | 긴장도 |
| competition | SMALLINT | N | `0` | CHECK BETWEEN 0 AND 100 | 경쟁 |
| dependence | SMALLINT | N | `0` | CHECK BETWEEN 0 AND 100 | 의존도 |
| relationship_type | VARCHAR(30) | Y | | CHECK IN (`friend`, `senior_junior`, `rival`, `confession`, `betrayal`, `reconciliation`) | 대표 관계 종류 |
| created_at | TIMESTAMPTZ | N | `now()` | | 생성 시각 |
| updated_at | TIMESTAMPTZ | N | `now()` | | 수정 시각 |

### 제약

* `source_agent_id <> target_agent_id`
* `UNIQUE(simulation_id, source_agent_id, target_agent_id)`
* 복합 FK로 서로 다른 Simulation에 속한 Agent 간 관계 생성을 DB 수준에서 차단한다.

### 인덱스

| 이름 | 컬럼 | 종류 | 이유 |
| --- | --- | --- | --- |
| `uq_relationships_pair` | `simulation_id, source_agent_id, target_agent_id` | UNIQUE | 중복 관계 방지 |
| `idx_relationships_target` | `simulation_id, target_agent_id` | BTREE | 특정 Agent를 향한 관계 조회 |

---

## 4.6 `organizations`

**설명:** 단계별로 활성화되는 전공, 동아리, 기숙사 조직, 총학생회를 저장한다. 1단계 기숙사는 조직이 아니라 생활 공간이므로 이 테이블에 생성하지 않는다.
**한 행의 의미:** 시뮬레이션 내 조직 하나

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| id | CHAR(26) | N | | PK | 조직 ULID |
| simulation_id | CHAR(26) | N | | FK → `simulations.id` | 소속 시뮬레이션 |
| organization_type | VARCHAR(20) | N | | CHECK IN (`dormitory`, `club`, `major`, `student_council`) | 조직 종류 |
| name | VARCHAR(100) | N | | | 조직 이름 |
| description | TEXT | Y | | | 조직 문화 또는 설명 |
| is_active | BOOLEAN | N | `true` | | 활성 여부 |
| deleted_at | TIMESTAMPTZ | Y | | | 소프트 삭제 시각 |
| created_at | TIMESTAMPTZ | N | `now()` | | 생성 시각 |
| updated_at | TIMESTAMPTZ | N | `now()` | | 수정 시각 |

### 제약

* `UNIQUE(simulation_id, organization_type, name)`
* `UNIQUE(simulation_id, id)`

1단계는 `major`만 사용한다. 2단계부터 `club`, 3단계부터 `dormitory`와 `student_council`을 사용한다.

---

## 4.7 `organization_memberships`

**설명:** Agent와 조직 간 소속 관계를 저장한다.
**한 행의 의미:** Agent 한 명의 조직 소속 하나

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| id | CHAR(26) | N | | PK | 소속 ULID |
| simulation_id | CHAR(26) | N | | FK → `simulations.id` | 소속 시뮬레이션 |
| organization_id | CHAR(26) | N | | 복합 FK → organizations | 조직 |
| agent_id | CHAR(26) | N | | 복합 FK → agents | 소속 Agent |
| membership_role | VARCHAR(30) | Y | | | 회장, 부원, 전공생 등 |
| joined_at | TIMESTAMPTZ | N | `now()` | | 가입 시각 |
| left_at | TIMESTAMPTZ | Y | | | 탈퇴 시각, 현재 소속이면 NULL |
| created_at | TIMESTAMPTZ | N | `now()` | | 생성 시각 |
| updated_at | TIMESTAMPTZ | N | `now()` | | 수정 시각 |

### 제약

* 복합 FK로 Agent와 조직이 동일한 Simulation에 속하는지 검증한다.
* 동일 Agent의 동일 조직 중복 활성 가입 금지 (부분 유니크 인덱스: `WHERE left_at IS NULL`)

### 인덱스

| 이름 | 컬럼 | 종류 | 이유 |
| --- | --- | --- | --- |
| `uq_organization_memberships_active` | `organization_id, agent_id` | PARTIAL UNIQUE (`WHERE left_at IS NULL`) | 동일 Agent의 동일 조직 중복 활성 가입 방지 |
| `idx_organization_memberships_agent` | `simulation_id, agent_id` | BTREE | Agent별 조직 소속 조회 |
| `idx_organization_memberships_organization` | `simulation_id, organization_id` | BTREE | 조직별 구성원 조회 |

```sql
CREATE UNIQUE INDEX uq_organization_memberships_active
ON organization_memberships (organization_id, agent_id)
WHERE left_at IS NULL;
```

---

## 4.8 `events`

**설명:** 시뮬레이션에서 발생한 수업, 시험, 축제, 랜덤 사건 등을 저장한다.
**한 행의 의미:** 시뮬레이션 사건 하나

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| id | CHAR(26) | N | | PK | 사건 ULID |
| simulation_id | CHAR(26) | N | | FK → `simulations.id` | 소속 시뮬레이션 |
| event_type | VARCHAR(30) | N | | CHECK IN (`class`, `group_project`, `exam`, `meeting`, `mt`, `festival`, `random_incident`, `student_council`) | 사건 유형 |
| title | VARCHAR(100) | N | | | 사건 제목 |
| description | TEXT | Y | | | 사건 설명 |
| status | VARCHAR(20) | N | `'scheduled'` | CHECK IN (`scheduled`, `ongoing`, `completed`, `cancelled`) | 사건 상태 |
| simulation_day | INT | N | | CHECK `simulation_day >= 1` | 사건 발생 일차 |
| started_at | TIMESTAMPTZ | Y | | | 사건 시작 시각 |
| ended_at | TIMESTAMPTZ | Y | | | 사건 종료 시각 |
| metadata | JSONB | N | `'{}'::jsonb` | | 사건별 추가 데이터 |
| created_at | TIMESTAMPTZ | N | `now()` | | 생성 시각 |
| updated_at | TIMESTAMPTZ | N | `now()` | | 수정 시각 |

`events.status`는 ERD와 API 명세 모두 `scheduled`, `ongoing`, `completed`, `cancelled`로 통일한다. `in_progress` 값은 사용하지 않는다.

### 인덱스

| 이름 | 컬럼 | 종류 | 이유 |
| --- | --- | --- | --- |
| `idx_events_simulation_day` | `simulation_id, simulation_day, created_at` | BTREE | 일차별 사건 조회 |
| `idx_events_metadata` | `metadata` | GIN | 사건 조건 검색이 필요할 경우 |

---

## 4.9 `event_participants`

**설명:** 사건에 참여한 Agent와 사건 결과를 저장한다.
**한 행의 의미:** Agent 한 명의 사건 참여 기록 하나

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| id | CHAR(26) | N | | PK | 참여 ULID |
| event_id | CHAR(26) | N | | FK → `events.id` | 사건 |
| agent_id | CHAR(26) | N | | FK → `agents.id` | 참여 Agent |
| participant_role | VARCHAR(30) | Y | | | 주최자, 참여자, 대상자 등 |
| action_taken | TEXT | Y | | | 사건 중 수행 행동 |
| result | JSONB | N | `'{}'::jsonb` | Pydantic Schema 검증 | 상태·관계·Memory 변화 결과 |
| created_at | TIMESTAMPTZ | N | `now()` | | 생성 시각 |
| updated_at | TIMESTAMPTZ | N | `now()` | | 수정 시각 |

### 제약

* `UNIQUE(event_id, agent_id)`

### result 예상 구조

```json
{
  "state_deltas": {
    "hunger": 0, "fatigue": 5, "stress": -3, "satisfaction": 2, "mood": 4
  },
  "relationship_deltas": [
    {
      "target_agent_id": "01K00000000000000000000000",
      "affection": 3, "intimacy": 2, "trust": 1, "tension": -1,
      "competition": 0, "dependence": 0
    }
  ],
  "memory_candidates": [
    {
      "memory_type": "observation",
      "content": "조별 과제를 성공적으로 마쳤다.",
      "importance": 5
    }
  ]
}
```

`result`는 `EventParticipantResult` Pydantic Schema에서 검증한다. Event와 Agent는 DB 값을 직접 수정하지 않고 delta 형태의 결과만 반환한다.

---

# 5. 관계

| 부모 | 자식 | 카디널리티 | 필수 | ON DELETE | ON UPDATE |
| --- | --- | --- | --- | --- | --- |
| `simulations` | `agents` | 1:N | 필수 | RESTRICT | RESTRICT |
| `simulations` | `organizations` | 1:N | 필수 | RESTRICT | RESTRICT |
| `simulations` | `events` | 1:N | 필수 | RESTRICT | RESTRICT |
| `simulations` | `relationships` | 1:N | 필수 | RESTRICT | RESTRICT |
| `agents` | `agent_states` | 1:1 | 필수 | RESTRICT | RESTRICT |
| `agents` | `agent_memories` | 1:N | 필수 | RESTRICT | RESTRICT |
| `agents` | `relationships` | 1:N | 필수 | RESTRICT | RESTRICT |
| `agents` | `organization_memberships` | 1:N | 필수 | RESTRICT | RESTRICT |
| `organizations` | `organization_memberships` | 1:N | 필수 | RESTRICT | RESTRICT |
| `events` | `event_participants` | 1:N | 필수 | RESTRICT | RESTRICT |
| `agents` | `event_participants` | 1:N | 필수 | RESTRICT | RESTRICT |
| `events` | `agent_memories` | 1:N | 선택 | SET NULL | RESTRICT |

소프트 삭제 대상인 `simulations`, `agents`, `organizations`에 대해 일반적인 물리 삭제를 허용하지 않는다.

---

# 6. 삭제 / 이력 정책

| 테이블 | 방식 | 이유 | 보존 기간 |
| --- | --- | --- | --- |
| `simulations` | 소프트 삭제 | Replay 및 결과 보존 가능성 | 운영 정책 확정 전까지 |
| `agents` | 소프트 삭제 | 과거 사건·관계 이력 유지 | 시뮬레이션 수명 동안 |
| `agent_states` | Agent와 함께 보존 | 현재 상태 및 향후 이력 조회 가능성 | Agent 보존 기간과 동일 |
| `agent_memories` | 삭제 또는 향후 요약·아카이브 | Memory 상한 관리 필요 | MVP 활성 Memory 최대 10개 |
| `relationships` | 일반 API에서 삭제 금지 | 관계 데이터 및 변화 근거 유지 | 시뮬레이션 수명 동안 |
| `organizations` | 소프트 삭제 | 과거 소속 이력 유지 | 시뮬레이션 수명 동안 |
| `organization_memberships` | 이력 보존 | 가입·탈퇴 기록 유지 | 시뮬레이션 수명 동안 |
| `events` | 일반 API에서 삭제 금지 | Replay 및 Inspector 근거 | 시뮬레이션 수명 동안 |
| `event_participants` | 일반 API에서 삭제 금지 | 사건 결과 근거 | 시뮬레이션 수명 동안 |

소프트 삭제 대상 조회 시 기본 조건: `WHERE deleted_at IS NULL`

---

# 7. 무결성 규칙

| 규칙 | 강제 위치 | 위반 시 |
| --- | --- | --- |
| Agent는 자신과 관계를 맺을 수 없다 | DB CHECK | 422 |
| 같은 방향의 Agent 관계는 중복될 수 없다 | DB UNIQUE | 409 |
| Agent당 현재 상태는 하나만 존재한다 | DB UNIQUE | 409 |
| 동일 사건에 동일 Agent는 한 번만 참여한다 | DB UNIQUE | 409 |
| Agent 상태 및 성격 수치는 정의된 범위를 벗어날 수 없다 | DB CHECK | 422 |
| Agent Memory 활성 개수는 최대 10개다 | 애플리케이션 트랜잭션 | 중요도가 낮은 Memory부터 정리 |
| 관계에 속한 두 Agent는 같은 Simulation에 있어야 한다 | DB 복합 FK + 애플리케이션 검증 | 422 |
| 조직 소속 Agent와 조직은 같은 Simulation에 있어야 한다 | DB 복합 FK + 애플리케이션 검증 | 422 |
| 동일 Agent의 동일 조직 활성 가입은 하나만 존재한다 | DB 부분 유니크 인덱스 | 409 |
| 소프트 삭제된 Agent는 신규 관계·사건·조직 소속에 사용할 수 없다 | 애플리케이션 검증 | 422 |
| 소프트 삭제된 조직에는 신규 Agent를 가입시킬 수 없다 | 애플리케이션 검증 | 422 |

---

# 8. 정규화 / 비정규화

| 위치 | 판단 | 이유 | 동기화 방법 |
| --- | --- | --- | --- |
| `agent_states` | `agents`에서 분리 | 상태값 업데이트 빈도가 높음 | 1:1 FK |
| Agent Big Five | `agents`에 개별 컬럼 저장 | 값의 범위 검증과 조회가 명확함 | DB CHECK |
| `event_participants.result` | 일부 비정규화 | 사건 유형별 결과 구조가 다름 | Pydantic Schema 검증 |
| `events.metadata` | 일부 비정규화 | 랜덤 사건별 추가 속성 유연성 | Pydantic Schema 검증 |
| `relationship_type` | 비정규화 | 관계 수치 기반 UI 표시 속도 향상 | 수치 변경 시 애플리케이션 재계산 |

---

# 9. 민감 정보

MVP 핵심 시뮬레이션 테이블에는 직접적인 개인정보를 저장하지 않는다.

| 컬럼 | 분류 | 처리 |
| --- | --- | --- |
| `agents.name` | 가상 캐릭터 정보 | 실제 개인정보 입력 제한 |
| `agent_memories.content` | 생성형 데이터 | API 로그에 전체 내용 기록 금지 |
| `events.metadata` | 생성형 데이터 | Secret 및 사용자 개인정보 저장 금지 |

---

# 10. 마이그레이션

| 순서 | 내용 | 파괴적 | 롤백 |
| --- | --- | --- | --- |
| 1 | `pgvector` Extension 활성화 | N | Extension 제거 |
| 2 | `simulations` 생성 및 `deleted_at` 추가 | N | DROP TABLE |
| 3 | `agents`, `agent_states` 생성 및 Big Five 컬럼 추가 | N | DROP TABLE |
| 4 | `organizations`, `organization_memberships` 생성 | N | DROP TABLE |
| 5 | `organization_memberships` 부분 유니크 인덱스 생성 | N | DROP INDEX |
| 6 | `events`, `event_participants` 생성 | N | DROP TABLE |
| 7 | `relationships`, `agent_memories` 생성 | N | DROP TABLE |
| 8 | 복합 FK, CHECK, UNIQUE 및 일반 인덱스 추가 | N | DROP INDEX / CONSTRAINT |
| 9 | 임베딩 모델 확정 후 `VECTOR(n)` 및 HNSW 인덱스 적용 | 조건부 | 컬럼 및 인덱스 제거 |

---

# 11. 미결

| # | 쟁점 | 결정권자 | 기한 |
| --- | --- | --- | --- |
| 1 | 전체 PK를 ULID로 사용할지 UUID로 사용할지 | Backend 팀 | 아키텍처 확정 전 |
| 2 | ULID PostgreSQL 저장 타입을 CHAR(26) 또는 UUID로 변환할지 | Backend 팀 | 마이그레이션 작성 전 |
| 3 | Student와 Professor를 단일 `agents`로 관리할지 별도 상세 테이블을 둘지 | PM / Backend | Agent 모델 확정 전 |
| 4 | 임베딩 모델과 `VECTOR(n)` 차원 | AI 팀 | 모델 선정 후 |
| 5 | User Persona의 다섯 성격 수치를 `agents`의 개별 컬럼, JSONB 또는 별도 테이블 중 어디에 저장할지 | PM / Backend | 마이그레이션 작성 전 |
| 6 | `importance`가 같은 활성 Memory 중 무엇을 먼저 삭제할지 | PM / Backend | MemoryService 구현 전 |
| 7 | Replay를 위해 상태 스냅샷 테이블을 추가할지 | 전체 팀 | MVP 범위 논의 |
| 8 | 사용자·설정 공유 테이블을 이번 ERD에 포함할지 | PM | PRD 수정 후 |

---

## 변경 이력

| 버전 | 날짜 | 변경 내용 |
| --- | --- | --- |
| v0.1 | 2026-07-20 | 초안 작성 |
| v0.2 | 2026-07-23 | 생활 Agent 규모, 상태값 0~100, 1단계 Memory 보존 정책, 방향성 관계 규모, 단계별 조직·Event 범위 정비. 관계 방향성 확정으로 미결 목록에서 제거. |
| v0.3 | 2026-07-28 | Memory 및 Event enum을 API 명세와 통일. Big Five 성격 수치, 조직 소속 부분 유니크 인덱스, Cross-simulation 복합 FK, 소프트 삭제 정책, 조건부 임베딩 마이그레이션, Event 결과 JSONB 구조 구체화. ON DELETE RESTRICT로 변경. |
