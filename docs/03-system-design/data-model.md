---
title: "[ERD] Magic Academy MVP 데이터 모델 초안"
source: confluence/05_TECH/data-model.md
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/12189697/ERD+Magic+Academy+MVP
status: draft
visibility: public
updated: 2026-07-21
source_updated: 2026-07-21
---

**상태:** Draft
**최종 수정:** 2026-07-20
**버전:** 0.1.0
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
        text role_description
        boolean is_active
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
        varchar_20 mood
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
        timestamptz created_at
        timestamptz updated_at
    }

    ORGANIZATION_MEMBERSHIPS {
        char_26 id PK
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
**예상 규모:** MVP 시뮬레이션당 5~26명 / 확장 시 증가

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| id | CHAR(26) | N | | PK | Agent ULID |
| simulation_id | CHAR(26) | N | | FK → `simulations.id` | 소속 시뮬레이션 |
| agent_type | VARCHAR(20) | N | | CHECK IN (`student`, `professor`, `user_persona`, `event_master`) | Agent 종류 |
| name | VARCHAR(50) | N | | | Agent 이름 |
| gender | VARCHAR(20) | Y | | CHECK IN (`male`, `female`, `non_binary`, `unspecified`) | 성별, 미정이면 NULL |
| personality_type | VARCHAR(30) | N | | | MBTI 또는 성향 코드 |
| role_description | TEXT | Y | | | Agent 대표 역할 설명 |
| is_active | BOOLEAN | N | `true` | | 활동 가능 여부 |
| created_at | TIMESTAMPTZ | N | `now()` | | 생성 시각 |
| updated_at | TIMESTAMPTZ | N | `now()` | | 수정 시각 |

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
| mood | VARCHAR(20) | N | `'neutral'` | CHECK IN (`very_bad`, `bad`, `neutral`, `good`, `very_good`) | 현재 기분 |
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
| memory_type | VARCHAR(20) | N | `'observation'` | CHECK IN (`observation`, `interaction`, `reflection`, `summary`) | 기억 유형 |
| importance | SMALLINT | N | `1` | CHECK BETWEEN 1 AND 10 | 중요도 |
| occurred_at | TIMESTAMPTZ | N | | | 기억 대상이 발생한 시각 |
| last_accessed_at | TIMESTAMPTZ | Y | | | 마지막 회상 시각 |
| embedding | VECTOR | Y | | | 의미 검색용 임베딩 |
| created_at | TIMESTAMPTZ | N | `now()` | | 생성 시각 |
| updated_at | TIMESTAMPTZ | N | `now()` | | 수정 시각 |

> `VECTOR`의 차원은 사용할 임베딩 모델 확정 후 `VECTOR(n)`으로 결정한다.

### 인덱스

| 이름 | 컬럼 | 종류 | 이유 |
| --- | --- | --- | --- |
| `idx_agent_memories_agent_occurred` | `agent_id, occurred_at DESC` | BTREE | Agent별 최신 기억 조회 |
| `idx_agent_memories_embedding` | `embedding` | HNSW | 유사도 기반 기억 검색 |

---

## 4.5 `relationships`

**설명:** 두 Agent 사이의 방향성 있는 관계 수치와 관계 상태를 저장한다.
**한 행의 의미:** 출발 Agent가 대상 Agent에게 가지는 관계 하나
**예상 규모:** Agent 5명 기준 최대 20행, 25명 기준 최대 600행

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| id | CHAR(26) | N | | PK | 관계 ULID |
| simulation_id | CHAR(26) | N | | FK → `simulations.id` | 소속 시뮬레이션 |
| source_agent_id | CHAR(26) | N | | FK → `agents.id` | 관계를 느끼는 Agent |
| target_agent_id | CHAR(26) | N | | FK → `agents.id` | 관계 대상 Agent |
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

### 인덱스

| 이름 | 컬럼 | 종류 | 이유 |
| --- | --- | --- | --- |
| `uq_relationships_pair` | `simulation_id, source_agent_id, target_agent_id` | UNIQUE | 중복 관계 방지 |
| `idx_relationships_target` | `simulation_id, target_agent_id` | BTREE | 특정 Agent를 향한 관계 조회 |

---

## 4.6 `organizations`

**설명:** 기숙사, 동아리, 전공, 총학생회 등의 조직을 저장한다.
**한 행의 의미:** 시뮬레이션 내 조직 하나

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| id | CHAR(26) | N | | PK | 조직 ULID |
| simulation_id | CHAR(26) | N | | FK → `simulations.id` | 소속 시뮬레이션 |
| organization_type | VARCHAR(20) | N | | CHECK IN (`dormitory`, `club`, `major`, `student_council`) | 조직 종류 |
| name | VARCHAR(100) | N | | | 조직 이름 |
| description | TEXT | Y | | | 조직 문화 또는 설명 |
| is_active | BOOLEAN | N | `true` | | 활성 여부 |
| created_at | TIMESTAMPTZ | N | `now()` | | 생성 시각 |
| updated_at | TIMESTAMPTZ | N | `now()` | | 수정 시각 |

### 제약

* `UNIQUE(simulation_id, organization_type, name)`

---

## 4.7 `organization_memberships`

**설명:** Agent와 조직 간 소속 관계를 저장한다.
**한 행의 의미:** Agent 한 명의 조직 소속 하나

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| id | CHAR(26) | N | | PK | 소속 ULID |
| organization_id | CHAR(26) | N | | FK → `organizations.id` | 조직 |
| agent_id | CHAR(26) | N | | FK → `agents.id` | 소속 Agent |
| membership_role | VARCHAR(30) | Y | | | 회장, 부원, 전공생 등 |
| joined_at | TIMESTAMPTZ | N | `now()` | | 가입 시각 |
| left_at | TIMESTAMPTZ | Y | | | 탈퇴 시각, 현재 소속이면 NULL |
| created_at | TIMESTAMPTZ | N | `now()` | | 생성 시각 |
| updated_at | TIMESTAMPTZ | N | `now()` | | 수정 시각 |

### 제약

* 동일 Agent의 동일 조직 중복 활성 가입 금지
* 부분 유니크 인덱스: `WHERE left_at IS NULL`

---

## 4.8 `events`

**설명:** 시뮬레이션에서 발생한 수업, 시험, 축제, 랜덤 사건 등을 저장한다.
**한 행의 의미:** 시뮬레이션 사건 하나

| 컬럼 | 타입 | NULL | 기본값 | 제약 | 설명 |
| --- | --- | --- | --- | --- | --- |
| id | CHAR(26) | N | | PK | 사건 ULID |
| simulation_id | CHAR(26) | N | | FK → `simulations.id` | 소속 시뮬레이션 |
| event_type | VARCHAR(30) | N | | CHECK IN (`class`, `group_assignment`, `exam`, `meeting`, `mt`, `festival`, `random`) | 사건 유형 |
| title | VARCHAR(100) | N | | | 사건 제목 |
| description | TEXT | Y | | | 사건 설명 |
| status | VARCHAR(20) | N | `'scheduled'` | CHECK IN (`scheduled`, `in_progress`, `completed`, `cancelled`) | 사건 상태 |
| simulation_day | INT | N | | CHECK `simulation_day >= 1` | 사건 발생 일차 |
| started_at | TIMESTAMPTZ | Y | | | 사건 시작 시각 |
| ended_at | TIMESTAMPTZ | Y | | | 사건 종료 시각 |
| metadata | JSONB | N | `'{}'::jsonb` | | 사건별 추가 데이터 |
| created_at | TIMESTAMPTZ | N | `now()` | | 생성 시각 |
| updated_at | TIMESTAMPTZ | N | `now()` | | 수정 시각 |

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
| result | JSONB | N | `'{}'::jsonb` | | 상태·관계 변화 결과 |
| created_at | TIMESTAMPTZ | N | `now()` | | 생성 시각 |
| updated_at | TIMESTAMPTZ | N | `now()` | | 수정 시각 |

### 제약

* `UNIQUE(event_id, agent_id)`

---

# 5. 관계

| 부모 | 자식 | 카디널리티 | 필수 | ON DELETE | ON UPDATE |
| --- | --- | --- | --- | --- | --- |
| `simulations` | `agents` | 1:N | 필수 | CASCADE | RESTRICT |
| `simulations` | `organizations` | 1:N | 필수 | CASCADE | RESTRICT |
| `simulations` | `events` | 1:N | 필수 | CASCADE | RESTRICT |
| `agents` | `agent_states` | 1:1 | 필수 | CASCADE | RESTRICT |
| `agents` | `agent_memories` | 1:N | 필수 | CASCADE | RESTRICT |
| `agents` | `relationships` | 1:N | 필수 | CASCADE | RESTRICT |
| `agents` | `organization_memberships` | 1:N | 필수 | CASCADE | RESTRICT |
| `organizations` | `organization_memberships` | 1:N | 필수 | CASCADE | RESTRICT |
| `events` | `event_participants` | 1:N | 필수 | CASCADE | RESTRICT |
| `agents` | `event_participants` | 1:N | 필수 | CASCADE | RESTRICT |
| `events` | `agent_memories` | 1:N | 선택 | SET NULL | RESTRICT |

---

# 6. 삭제 / 이력 정책

| 테이블 | 방식 | 이유 | 보존 기간 |
| --- | --- | --- | --- |
| `simulations` | 소프트 삭제 검토 | Replay 및 결과 보존 가능성 | 미결정 |
| `agents` | 소프트 삭제 검토 | 과거 사건·관계 이력 유지 | 시뮬레이션 수명 동안 |
| `agent_states` | 하드 삭제 | Agent 없이 의미 없음 | Agent 삭제 시 |
| `agent_memories` | 하드 삭제 또는 아카이브 | Memory 상한 관리 필요 | MVP 최대 10개 |
| `relationships` | 하드 삭제 | 시뮬레이션 종속 데이터 | 시뮬레이션 수명 동안 |
| `organizations` | 소프트 삭제 검토 | 과거 소속 이력 유지 | 시뮬레이션 수명 동안 |
| `events` | 하드 삭제 금지 권장 | Replay 및 Inspector 근거 | 시뮬레이션 수명 동안 |
| `event_participants` | 하드 삭제 금지 권장 | 사건 결과 근거 | 시뮬레이션 수명 동안 |

---

# 7. 무결성 규칙

| 규칙 | 강제 위치 | 위반 시 |
| --- | --- | --- |
| Agent는 자신과 관계를 맺을 수 없다 | DB CHECK | 422 |
| 같은 방향의 Agent 관계는 중복될 수 없다 | DB UNIQUE | 409 |
| Agent당 현재 상태는 하나만 존재한다 | DB UNIQUE | 409 |
| 동일 사건에 동일 Agent는 한 번만 참여한다 | DB UNIQUE | 409 |
| Agent 상태 수치는 정의된 범위를 벗어날 수 없다 | DB CHECK | 422 |
| Agent Memory 활성 개수는 최대 10개다 | 애플리케이션 트랜잭션 | 오래된 기억 요약 또는 삭제 |
| 관계에 속한 두 Agent는 같은 Simulation에 있어야 한다 | 애플리케이션 + 트리거 검토 | 422 |
| 조직 소속 Agent와 조직은 같은 Simulation에 있어야 한다 | 애플리케이션 + 트리거 검토 | 422 |

---

# 8. 정규화 / 비정규화

| 위치 | 판단 | 이유 | 동기화 방법 |
| --- | --- | --- | --- |
| `agent_states` | `agents`에서 분리 | 상태값 업데이트 빈도가 높음 | 1:1 FK |
| `event_participants.result` | 일부 비정규화 | 사건 유형별 결과 구조가 다름 | 애플리케이션 검증 |
| `events.metadata` | 일부 비정규화 | 랜덤 사건별 추가 속성 유연성 | Pydantic Schema 검증 |
| 관계 대표 타입 | 비정규화 가능 | 관계 수치 기반 빠른 UI 표시 | 수치 변경 시 애플리케이션 재계산 |

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
| 2 | `simulations` 생성 | N | DROP TABLE |
| 3 | `agents`, `agent_states` 생성 | N | DROP TABLE |
| 4 | `organizations`, `organization_memberships` 생성 | N | DROP TABLE |
| 5 | `events`, `event_participants` 생성 | N | DROP TABLE |
| 6 | `relationships`, `agent_memories` 생성 | N | DROP TABLE |
| 7 | 인덱스 및 제약 추가 | N | DROP INDEX / CONSTRAINT |

---

# 11. 미결

| # | 쟁점 | 결정권자 | 기한 |
| --- | --- | --- | --- |
| 1 | 전체 PK를 ULID로 사용할지 UUID로 사용할지 | Backend 팀 | 아키텍처 확정 전 |
| 2 | ULID PostgreSQL 저장 타입을 CHAR(26) 또는 UUID로 변환할지 | Backend 팀 | 마이그레이션 작성 전 |
| 3 | Student와 Professor를 단일 `agents`로 관리할지 별도 상세 테이블을 둘지 | PM / Backend | Agent 모델 확정 전 |
| 4 | 임베딩 모델과 `VECTOR(n)` 차원 | AI 팀 | 모델 선정 후 |
| 5 | 관계가 방향성인지 양방향 단일 행인지 | PM / Backend | 관계 규칙 확정 전 |
| 6 | Replay를 위해 상태 스냅샷 테이블을 추가할지 | 전체 팀 | MVP 범위 논의 |
| 7 | 사용자·설정 공유 테이블을 이번 ERD에 포함할지 | PM | PRD 수정 후 |

---

## 부록: 확정 전 체크리스트

* 모든 테이블에 한 행의 의미를 작성함
* 모든 FK에 ON DELETE 정책을 초안으로 명시함
* NULL 허용 컬럼의 의미를 설명함
* 핵심 조회 기준 인덱스를 작성함
* 실제 API 쿼리 패턴 확정 후 인덱스 재검토
* 소프트 삭제 대상 확정
* 애플리케이션 무결성 규칙의 동시성 처리 확정
* Replay용 이력·스냅샷 구조 검토
* 1년 후 규모 추정 보완
