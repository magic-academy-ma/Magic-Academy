---
title: Slice 7 — 설정 공유·가져오기·배포 계약
status: approved
updated: 2026-08-25
visibility: public
source:
  - "GitHub Issue #142"
  - "GitHub Issue #143"
  - "Confluence [Plan] 1단계 수직 Slice 0~7"
  - "Confluence API 명세 및 공통 규약"
  - "docs/04-feature-specs/slice-6-replay-restore.md"
  - "docs/03-system-design/infra.md"
---

# Slice 7 — 설정 공유·가져오기·배포 계약

> 이 문서는 Slice 7 Task 0에서 동결할 설정 공유·가져오기·배포 구현 계약이다.
> PR 승인과 병합 시 `status`를 `approved`로 변경한다.

## 1. 목적

사용자가 자신의 Simulation 설정을 안전하게 공유하고, 다른 사용자가 이를 새
Simulation으로 가져와 실행할 수 있게 한다. Railway 배포와 외부 사용자 검증까지
같은 계약으로 수행한다.

Slice 7의 핵심 불변 조건은 다음과 같다.

- 공유 Snapshot은 생성 후 수정하지 않는다.
- 가져오기는 원본 Simulation과 공유 Snapshot을 변경하지 않는다.
- 가져온 Simulation의 소유자는 요청 JWT로 식별한 내부 사용자다.
- 가져오기 과정에서는 Runtime, LLM, Tick Engine을 호출하지 않는다.
- 비공개 설정과 민감정보는 목록·응답·로그로 노출하지 않는다.
- 가져오기 중 하나라도 실패하면 새 Simulation과 모든 하위 데이터가 rollback된다.

## 2. 용어와 책임 경계

| 용어 | 정의 |
| --- | --- |
| 공유 설정 | 다른 사용자가 새 Simulation을 만들 수 있도록 공개한 설정 묶음 |
| 공유 Snapshot | 공유 생성 시점의 설정을 보존하는 불변 payload |
| 가져오기 | 공유 Snapshot을 검증하고 요청자 소유의 새 Simulation을 생성하는 동작 |
| 원본 Simulation | 공유 Snapshot을 생성한 소유자 Simulation |
| `schema_version` | 공유 payload 구조의 호환성을 판별하는 버전 |

### 범위에 포함

- 공유 생성·목록·상세·취소
- 공개 범위와 접근 권한
- 공유 설정 export/import
- 가져온 Simulation의 소유권과 transaction
- Railway 배포·healthcheck·구조화 로그
- 외부 사용자 검증과 Slice 7 최종 PASS

### 범위에서 제외

- 원본 실행 기록·Replay 기록의 복제
- 가져오기 중 Runtime·LLM·Tick 실행
- 공유 설정 공동 편집
- 사용자 계정·인증정보 이전
- Prompt 원문과 Chain of Thought 공유

## 3. 공유 범위와 접근 권한

| visibility | 소유자 조회 | 공유 ID 직접 접근 | 공개 목록·검색 | 다른 사용자 가져오기 |
| --- | ---: | ---: | ---: | ---: |
| `private` | 허용 | 불가 | 불가 | 불가 |
| `unlisted` | 허용 | 허용 | 불가 | 허용 |
| `public` | 허용 | 허용 | 허용 | 허용 |

- 공유 생성·취소와 소유자 전용 조회는 인증된 원본 Simulation 소유자만 수행한다.
- 공개 목록·검색은 `public`만 반환하며 `private`, `unlisted`의 존재를 노출하지 않는다.
- `unlisted`는 정확한 공유 ID를 아는 사용자만 상세 조회하고 가져올 수 있다.
- 접근할 수 없는 공유와 취소된 공유는 모두 404로 응답하여 존재 여부를 숨긴다.
- 공유 생성 시 설정을 Snapshot으로 복사하며 이후 원본 설정 변경은 기존 공유에
  반영하지 않는다. 변경 내용을 공유하려면 새 공유 Snapshot을 생성한다.
- 공유 취소는 `revoked_at`을 기록하는 soft delete로 처리한다. 취소 후 상세 조회와
  가져오기는 허용하지 않는다.

## 4. export/import 계약

### 4.1 스키마 버전

- 최초 버전은 문자열 `slice7-share-v1`이다.
- export 최상위에 `schema_version`을 반드시 포함한다.
- 서버가 지원하지 않는 버전은 HTTP 422와
  `UNSUPPORTED_SHARE_SCHEMA_VERSION`을 반환한다.
- 알 수 없는 필드는 무시하지 않고 schema 검증 오류로 처리한다.
- 동일 버전의 필수 필드 의미와 타입은 변경하지 않는다. 호환되지 않는 변경은 새
  `schema_version`으로 배포한다.

### 4.2 포함 범위

- 공유 표시 정보: 제목, 설명, visibility
- Simulation 실행 설정과 해당 설정 버전
- `execution_seed`, `model_version`, `prompt_version`, `policy_version`,
  `resolver_version`의 식별자
- 생활 Agent roster와 fixture 식별자
- Student·Professor Profile과 User Persona 대상의 fixture 식별자
- 가져오기 직후 상태를 구성하는 Location, Agent State, 방향성 Relationship,
  Organization과 Organization membership Snapshot

Organization Snapshot은 원본 DB ID 대신 비어 있지 않은 `fixture_key`를 안정적인
식별자로 사용한다. `fixture_key`는 한 Simulation 안에서 유일해야 하며 Snapshot에는
최소 `fixture_key`, `organization_type`, `name`, `description`, `is_active`를 포함한다.
membership은 `organization_fixture_key`와 `agent_fixture_key`로 양쪽을 참조한다.
가져오기는 Organization을 먼저 새 ID로 생성하고
`organization_fixture_key -> 새 organization_id` 매핑으로 membership FK를 구성한다.

버전 필드는 실제 비밀 값이나 Prompt 본문이 아니라 재현 조건을 식별하는 값만
포함한다.

#### 4.2.1 `slice7-share-v1` payload 구조

아래 필드는 모두 서버가 공유 생성 시 DB에서 조립한다. 배열 안의 참조는 원본 DB
ID가 아니라 fixture 식별자를 사용한다.

```json
{
  "schema_version": "slice7-share-v1",
  "share": {
    "title": "공유 설정 제목",
    "description": "공유 설정 설명",
    "visibility": "public"
  },
  "simulation": {
    "name": "새 Simulation 기본 이름",
    "magic_enabled": true,
    "settings_version": "string",
    "execution_seed": 12345,
    "model_version": "string",
    "prompt_version": "string",
    "policy_version": "string",
    "resolver_version": "string",
    "user_persona_fixture_key": "student-03"
  },
  "locations": [
    {"code": "dormitory", "name": "기숙사", "is_active": true}
  ],
  "organizations": [
    {
      "fixture_key": "major-magic-theory",
      "organization_type": "major",
      "name": "마법이론학과",
      "description": null,
      "is_active": true
    }
  ],
  "agents": [
    {
      "fixture_key": "student-03",
      "fixture_version": "student-fixture-v0.2",
      "agent_type": "user_persona",
      "name": "리아",
      "gender": "female",
      "personality_type": "INFP",
      "mbti_type": "INFP",
      "traits": {
        "openness": 20,
        "conscientiousness": -10,
        "extraversion": -20,
        "agreeableness": 30,
        "emotional_stability": -10
      },
      "role_profile": {
        "profile_type": "student",
        "grade": 1,
        "interest_field": "마법약학"
      },
      "state": {
        "location_code": "dormitory",
        "hunger": 50,
        "fatigue": 0,
        "stress": 0,
        "satisfaction": 50,
        "mood": 0,
        "current_action": null
      }
    }
  ],
  "relationships": [
    {
      "source_agent_fixture_key": "student-01",
      "target_agent_fixture_key": "student-02",
      "metrics": {
        "affection": 0,
        "closeness": 0,
        "trust": 0,
        "tension": 0,
        "rivalry": 0,
        "dependency": 0
      }
    }
  ],
  "organization_memberships": [
    {
      "organization_fixture_key": "major-magic-theory",
      "agent_fixture_key": "student-03",
      "membership_role": "member"
    }
  ]
}
```

Professor의 `role_profile`은 `profile_type=professor`, `academic_rank`, `specialty`를
사용한다. 각 배열은 자신의 fixture 식별자 또는 방향성 pair 기준으로 중복될 수 없다.
payload 전체는 strict schema로 검증하며 필수 필드 누락과 알 수 없는 필드는
`INVALID_SHARE_PAYLOAD`다.

### 4.3 제외 범위

- 사용자 ID, username, display name과 인증·인가 정보
- 비밀번호 hash, JWT, API key, Secret, 환경변수 값
- Prompt 원문, system prompt, Chain of Thought
- Runtime 결과, Intent, 행동 로그, Event 실행 기록, Memory, Replay 기록
- 운영 로그, 요청·응답 원문과 사용자 자유 입력

### 4.4 가져오기 결과와 소유권

- 공유 생성은 `status=ready`, `started_at=null`, `current_tick=0`인 시작 전
  Simulation에만 허용한다. 실행된 Simulation은 공유할 수 없으며 409
  `SIMULATION_SHARE_NOT_READY`를 반환한다.
- 따라서 공유 Snapshot의 Agent State와 Relationship은 시작 전 초기값이며, 가져온
  Simulation의 Tick 0 초기 상태로 그대로 사용한다. 실행 중 상태의 공유·복원은
  Slice 6 Replay/Restore 계약의 범위다.
- 가져오기는 기존 Simulation을 대상으로 하지 않고 항상 새 Simulation을 만든다.
- 새 Simulation ID와 하위 엔티티 ID를 발급하며 원본 ID를 재사용하지 않는다.
- 새 Simulation의 `owner_id`는 요청 JWT의 `sub`다.
- 원본 Simulation과 공유 ID는 provenance로만 기록한다.
- 공유 Snapshot의 User Persona fixture가 가져온 roster에 없으면 422
  `SHARE_PERSONA_TARGET_INVALID`를 반환한다.
- User Persona는 Snapshot의 fixture 식별자로 새 Agent에 매핑한다. 임의 Student를
  선택하거나 기존 Persona 설정을 덮어쓰는 경로는 제공하지 않는다.
- 새 Simulation은 시작 전 상태로 생성하며 User Persona는 변경 가능하다. 시작 시
  기존 Slice 4 계약에 따라 설정을 적용하고 잠근다.
- Simulation, 설정, Snapshot, roster, Profile, State, Relationship, Organization
  membership 생성은 하나의 transaction이다. 일부 실패 시 전체 rollback한다.

### 4.5 중복 요청

- 가져오기 API는 `POST /v1/shares/{share_id}/imports`이며 요청 body를 받지 않는다.
  클라이언트는 `Idempotency-Key` header만 필수로 전달한다.
- 서버는 DB에 저장된 공유 Snapshot만 읽으며 클라이언트가 `schema_version` 또는
  export payload를 제출하거나 덮어쓰는 인터페이스를 제공하지 않는다.
- 중복 기준은 `(request_user_id, idempotency_key)`다.
- 요청 fingerprint는 canonical JSON으로 직렬화한 `{ "share_id": "<UUID>" }`의
  SHA-256이다. 같은 key와 같은 fingerprint면 최초 생성 결과를 반환하며 새
  Simulation을 만들지 않는다.
- 같은 사용자가 동일 key로 다른 `share_id`를 요청해 fingerprint가 다르면 409
  `IMPORT_IDEMPOTENCY_CONFLICT`를 반환한다.
- 서버 저장 Snapshot의 schema version·필수 필드·참조 무결성이 유효하지 않으면
  422로 처리하며, 검증 중에도 클라이언트 입력을 Snapshot에 병합하지 않는다.

## 5. 오류 계약

| 상황 | HTTP | 오류 코드 |
| --- | ---: | --- |
| 인증 정보 없음·유효하지 않음 | 401 | `AUTHENTICATION_REQUIRED` |
| 공유 생성·취소 권한 없음 | 403 | `SHARE_ACCESS_DENIED` |
| 공유 없음·접근 불가·취소됨 | 404 | `SHARE_NOT_FOUND` |
| 시작 전 상태가 아닌 Simulation 공유 요청 | 409 | `SIMULATION_SHARE_NOT_READY` |
| 동일 idempotency key의 요청 불일치 | 409 | `IMPORT_IDEMPOTENCY_CONFLICT` |
| 지원하지 않는 `schema_version` | 422 | `UNSUPPORTED_SHARE_SCHEMA_VERSION` |
| 공유 payload 검증 실패 | 422 | `INVALID_SHARE_PAYLOAD` |
| User Persona 대상 매핑 실패 | 422 | `SHARE_PERSONA_TARGET_INVALID` |
| 가져오기 transaction 실패 | 500 | `SHARE_IMPORT_FAILED` |

오류 응답과 로그에는 원본 payload, 인증정보, Secret, Prompt 또는 Chain of Thought를
포함하지 않는다.

## 6. Railway 배포와 운영 로그

### 6.1 배포 게이트

- Railway 배포 환경변수는 저장소에 값을 기록하지 않고 Railway Variables로 관리한다.
- 최소 필수 항목은 DB 연결, JWT 검증, CORS, Backend/Frontend 공개 URL과 실제로
  활성화한 LLM provider key다.
- migration은 애플리케이션 기동 전 한 번 실행한다. `alembic upgrade head` 실패 시
  새 버전을 시작하지 않는다.
- `/health`는 애플리케이션, DB 연결 및 현재 migration head 준비 상태를 확인한다.
- Backend healthcheck 성공 전 Frontend에서 보호 API의 정상 동작을 선언하지 않는다.
- 허용 origin은 배포된 Frontend URL로 제한하고 wildcard와 credentials를 함께 쓰지 않는다.

### 6.2 구조화 로그

운영 로그는 JSON 한 줄 형식이며 다음 필드를 사용한다.

- `timestamp`, `level`, `service`, `environment`
- `trace_id`, `request_id`, `operation`
- 해당하는 경우 `simulation_id`, `share_id`, `run_id`, `tick_number`
- `result`, `error_code`, `duration_ms`

다음 값은 로그에 기록하지 않는다.

- JWT, cookie, password, API key, Secret과 전체 환경변수
- username, display name과 사용자 자유 입력
- request/response 전체 payload
- Prompt 원문, Chain of Thought, Memory 원문
- DB connection string과 stack trace 안의 자격증명

예외 stack trace는 ERROR 로그에 남길 수 있지만 위 민감정보를 제거한 뒤 기록한다.

## 7. 외부 사용자 검증과 PASS

### 7.1 Golden Path

1. 사용자 A가 Simulation 설정을 `public`으로 공유한다.
2. 사용자 B가 공개 목록·검색에서 공유를 찾고 상세를 조회한다.
3. 사용자 B가 같은 idempotency key로 두 번 가져온다.
4. 사용자 B 소유의 새 Simulation이 정확히 하나 생성되는지 확인한다.
5. 설정·roster·Persona·상태 Snapshot이 원본 공유 Snapshot과 일치하는지 확인한다.
6. 가져온 Simulation을 시작하고 최소 한 Tick 실행 가능 여부를 확인한다.
7. 원본 Simulation과 공유 Snapshot이 변경되지 않았는지 확인한다.

### 7.2 필수 음수 시나리오

- 다른 사용자의 `private` 공유 조회·가져오기 불가
- `unlisted`가 공개 목록·검색에 나타나지 않음
- 취소된 공유 조회·가져오기 404
- 지원하지 않는 schema version 422
- 서버 저장 Snapshot의 schema·참조 무결성 오류와 Persona 대상 불일치 422
- 가져오기 중 강제 실패 시 전체 rollback
- 가져오기 과정의 Runtime·LLM·Tick 호출 0회
- 로그에 민감정보가 남지 않음

### 7.3 최종 PASS 기준

- Task 1~6의 PR과 테스트 증빙이 Slice 7 base에 통합되어 있다.
- PostgreSQL migration·Repository·transaction 테스트가 통과한다.
- Frontend 목록·검색·상세·가져오기 및 오류 상태 테스트가 통과한다.
- Railway에서 migration, `/health`, CORS와 공개 URL 검증이 통과한다.
- 외부 사용자 Golden Path와 음수 시나리오가 통과한다.
- 가져오기 전후 원본 불변성과 idempotency가 검증된다.
- 미해결 Must 리뷰가 없고 외부 사용자 피드백의 처리 결과가 기록되어 있다.

## 8. Task 경계와 통합 순서

| Task | 책임 | 선행 조건 |
| --- | --- | --- |
| Task 0 (#143) | 본 계약 확정 및 증빙 기준 동결 | Slice 6 계약 |
| Task 1 (#144) | 공유·가져오기 API, DB, transaction | Task 0 |
| Task 2 (#145) | 공유 목록·검색·상세·가져오기 UI | Task 0, API 연동은 Task 1 |
| Task 3 (#146) | Railway 배포·healthcheck·운영 로그 | Task 0 |
| Task 4 (#147) | 가져오기 재현성 및 무실행 검증 | Task 0, 통합 검증은 Task 1 |
| Task 5 (#148) | 외부 사용자 검증 및 피드백 | Task 1~4 |
| Task 6 (#149) | 전체 E2E·회귀·최종 PASS 증빙 | Task 1~5 |

모든 Task 브랜치는 `feature/issue-142-slice7-base`에서 분기하고 Task PR의 base도
같은 브랜치로 지정한다. Slice 7 base는 Slice 6 최종 PASS와 `develop` 병합 후 최신
`develop` 기준으로 갱신한 뒤에만 구현 Task를 병합한다.

각 Task의 실행 명령과 PASS 결과는 해당 Task PR의 `테스트 / 확인 내용`에 기록하고
Parent #142에 링크한다. Task 6은 전체 증빙을 취합한다.

## 9. Task 0 결정 사항

1. **공개 범위**: `private`, `unlisted`, `public` 세 단계와 3장의 접근표를 적용한다.
2. **공유 데이터**: 실행 기록이 아니라 4.2의 불변 설정·상태 Snapshot을 공유한다.
3. **공유 시점**: 시작 전 `ready`·Tick 0 Simulation만 공유하며 실행 중 상태 복원은
   Slice 6 범위로 분리한다.
4. **가져오기 방식**: 서버 저장 Snapshot으로 요청자 소유의 새 Simulation을 한
   transaction으로 생성한다.
5. **Persona·Organization 매핑**: fixture 식별자로 매핑하며 불일치 시 가져오기를
   거부한다.
6. **스키마 버전**: 최초 버전은 `slice7-share-v1`이며 비호환 payload는 422다.
7. **중복 방지**: 사용자 단위 `Idempotency-Key`와 `share_id` fingerprint를 사용한다.
8. **공유 취소**: soft delete 후 외부 조회·가져오기는 404다.
9. **배포**: migration 선행, DB·migration readiness healthcheck, Railway Variables를 사용한다.
10. **로그**: 구조화 로그의 허용 필드와 민감정보 제외 목록은 6.2를 적용한다.
11. **최종 승인**: Railway Golden Path, 음수 시나리오, 외부 사용자 피드백과 누적 회귀가
    모두 통과해야 Slice 7 PASS다.

## 10. Task 0 완료 기준

- [x] 공유 visibility와 접근 권한이 확정되어 있다.
- [x] export/import 범위와 schema version 오류가 확정되어 있다.
- [x] 새 Simulation 소유권, 원본 불변성과 Persona 매핑이 명확하다.
- [x] 민감정보 제외 규칙과 운영 로그 필드가 확정되어 있다.
- [x] Railway migration·healthcheck 게이트가 확정되어 있다.
- [x] 외부 사용자 시나리오와 최종 PASS 기준이 확정되어 있다.
- [x] Task 1~6의 책임과 통합 순서가 명확하다.
