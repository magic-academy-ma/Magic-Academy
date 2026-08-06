---
title: 인증·접근 제어 설계
source: confluence/05_TECH/인증·접근 제어 설계
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/23888013
status: draft
visibility: public
updated: 2026-08-06
source_updated: 2026-08-06
---

# 인증·접근 제어 설계

> **상태:** Draft
> **작성자:** @jiyou
> **담당자:** @jiyou
> **작성일 / 최종 수정일:** 2026-08-03 / 2026-08-06
> **기준 문서:** [API 명세 및 공통 규약](https://jehye.atlassian.net/wiki/spaces/MA/pages/12451842), [ERD — Magic Academy MVP](https://jehye.atlassian.net/wiki/spaces/MA/pages/12189697)
> **버전:** v0.3

## 0. 개요 및 목적

인증·접근 제어 기능은 사용자 인증 정보와 요청 대상 리소스를 입력받아 요청 주체를 식별하고, 사용자별 Simulation·설정·Replay·분기 접근 허용 여부를 결정하는 역할을 한다.

- **목적**: 인증된 사용자만 보호 API를 호출하고, 사용자별 데이터를 분리하여 접근하도록 구현 기준을 제공한다.
- **범위**: REST API 인증, 사용자별 인가, Admin/Test 및 Internal API 접근, 토큰 수명주기, 인증 데이터 모델 책임을 다룬다. OAuth 공급자별 화면 흐름과 인프라 배포 상세는 다루지 않는다.

## 1. 연관 컴포넌트와의 관계

| 연관 컴포넌트 | 기존 역할 | 이 설계에서 추가하는 것 |
| --- | --- | --- |
| FastAPI 사용자 API | Simulation·Agent·Event 등 리소스 제공 | Bearer token 검증과 요청 사용자 식별 |
| Simulation 서비스 | Simulation 생성·조회·실행 | 소유 User 검증과 하위 리소스 권한 상속 |
| OAuth/OIDC 공급자 | 외부 사용자 본인 확인 | 공급자 계정과 User 연결 기준 |
| PostgreSQL 인증 모델 | User·OAuthAccount·RefreshToken 저장 | token 발급·만료·폐기 및 소유권 데이터 관리 |
| Tick Orchestrator | Simulation Tick 실행 | 사용자 소유권과 LLM 실행 쿼터 선검사 |
| Admin/Test API | Tick 수동 진행 등 운영·테스트 기능 | X-Internal-Api-Key 검증 |
| Agent Runtime Internal API | 내부 Agent 실행 | 내부망 격리와 내부용 secret 검증 |
| WebSocket | Tick·Agent·Event 변경 실시간 전달 | MVP 무인증 경계 및 향후 인증 전환 기준 |

## 2. 책임 경계

### 2.1 하는 일

- Bearer access token을 검증하고 요청 사용자를 식별한다.
- 사용자와 보호 리소스의 소유권을 비교한다.
- Simulation 소유권을 Agent·Event·Relationship·Organization 등 하위 리소스에 적용한다.
- refresh token의 발급·갱신·폐기 상태를 관리한다.
- Admin/Test 및 Internal API의 별도 접근 조건을 검증한다.
- 인증 사용자 기준으로 LLM 실행 쿼터를 검사한다.
- 인증·인가 실패를 공통 오류 형식으로 반환하고 필요한 감사 로그를 남긴다.

### 2.2 하지 않는 일

- 클라이언트가 전달한 사용자 ID를 인증 근거로 사용하지 않는다.
- Agent가 인증 DB 또는 도메인 DB를 직접 조회·수정하도록 하지 않는다.
- OAuth 공급자별 로그인 화면과 사용자 경험을 정의하지 않는다.
- 저장 설정 공유 권한 모델이나 수치형 LLM 쿼터를 이 문서에서 임의로 확정하지 않는다.
- access token·refresh token·내부 API key 원문을 로그에 기록하지 않는다.
- 사용자 Bearer token만으로 Admin/Test 권한을 부여하지 않는다.

## 3. 입력 계약

| 입력 | 필수 | 설명 |
| --- | --- | --- |
| Authorization | 보호 API ✓ | `Bearer <access_token>` 형식의 사용자 인증 헤더 |
| X-Internal-Api-Key | Admin/Test API ✓ | 사전 발급된 내부용 secret |
| refresh_token | token 갱신·로그아웃 시 ✓ | 발급된 refresh token |
| resource_id | 리소스 API ✓ | 접근 대상 Simulation 또는 하위 리소스 ID |
| OAuth/OIDC 공급자 식별자 | 로그인 시 조건부 | 공급자와 공급자 사용자 식별자 |
| 사용자 식별자 | 내부 처리 ✓ | 검증된 access token에서 추출하며 요청 body의 값은 신뢰하지 않음 |

## 4. 핵심 설계 결정

구현에서 판단이 필요한 설계 결정을 기록한다. 미정 사항은 `[미정]`으로 명시한다.

### 4.1 사용자 API 인증

- MVP 사용자 API에는 인증을 적용한다.
- 보호 API는 `Authorization: Bearer <access_token>` 헤더를 사용한다.
- 무인증 API는 allowlist로 관리한다.
- 별도 명시가 없는 신규 사용자 API는 보호 API로 간주한다.

### 4.2 사용자별 소유권과 인가

- Simulation, 초기 설정·저장 설정, Replay, 분기 및 사용자별 쿼터 사용량을 보호 리소스로 취급한다.
- Agent·Event·Relationship·Organization 등 하위 리소스는 소속 Simulation의 소유권을 상속한다.
- 하위 리소스 ID만 전달된 요청도 상위 Simulation 소유권을 확인한다.
- 다른 사용자의 비공개 리소스 접근은 403 `FORBIDDEN`을 반환한다.
- 존재하지 않는 리소스는 404 `RESOURCE_NOT_FOUND`를 반환한다.

### 4.3 로그인과 token 발급

1. 사용자가 인증 공급자를 통해 본인 확인을 완료한다.
2. 서버가 공급자 식별자와 `oauth_accounts`를 조회한다.
3. 연결된 사용자가 없으면 확정된 계정 생성·연결 정책에 따라 User와 OAuthAccount를 생성한다.
4. 서버가 application access token과 refresh token을 발급한다.
5. refresh token 원문은 DB에 저장하지 않고 검증 가능한 해시 또는 동등한 비가역 값만 저장한다.

### 4.4 token 갱신·로그아웃·폐기

- 유효한 refresh token 제출 시 새 access token을 발급한다.
- 회전 정책 적용 시 기존 refresh token을 폐기하고 새 refresh token을 함께 발급한다.
- 만료·폐기·재사용 감지된 refresh token은 거부한다.
- 로그아웃 시 해당 refresh token을 폐기한다.
- 전체 기기 로그아웃 지원 시 사용자의 활성 refresh token 전체를 폐기한다.

### 4.5 Admin/Test 및 Internal API

- Admin/Test API는 `X-Internal-Api-Key: <secret>` 헤더를 요구한다.
- 헤더가 없거나 일치하지 않으면 401 `UNAUTHORIZED`를 반환한다.
- `/internal/*`는 외부에서 라우팅할 수 없도록 내부망에서 격리한다.
- Internal API에는 내부망 격리와 내부용 secret 검증을 함께 적용한다.

### 4.6 WebSocket 인증 경계

- MVP의 `wss://{server}/v1/ws/simulations/{simulation_id}` 연결은 기존 API 명세에 따라 무인증이다.
- MVP WebSocket은 공개 Simulation의 읽기 전용 실시간 이벤트만 노출한다.
- 허용 데이터: Tick 번호·진행 상태, 공개 Agent 행동·위치, Event 공개 필드, Relationship 변화량.
- 비노출 데이터: 성격 원본값, Memory 내용·embedding, Decision Explanation, 사용자 식별자, token·secret, 비공개 설정.

### 4.7 인증 데이터 모델

| 엔티티 | 책임 |
| --- | --- |
| users | 서비스 사용자 식별과 계정 상태 관리 |
| oauth_accounts | 외부 인증 공급자 계정과 User 연결. 동일 공급자 내 사용자 식별자는 유일 |
| refresh_tokens | refresh token의 발급·만료·폐기 상태 관리. 원문 대신 비가역 검증 값 저장 |
| simulations | 소유 User 연결. 하위 데이터가 소유권을 상속 |

### 4.8 보안 및 감사 로그

- secret은 환경 변수 또는 secret manager로 주입하고 저장소에 커밋하지 않는다.
- access token, refresh token, 내부 API key를 평문 DB·로그에 남기지 않는다.
- 로그인, token 갱신, 로그아웃, token 폐기와 접근 거부를 감사 가능하게 기록한다.
- 실패 로그에는 trace_id, 시각, 엔드포인트와 실패 분류 등 최소 정보만 남긴다.

### 4.9 LLM 실행 쿼터

- 인증 사용자 기준으로 Simulation 동시 실행 수와 Tick 호출 횟수를 집계한다.
- Simulation 시작 및 Tick 실행 전에 쿼터를 검사한다.
- 초과 시 실행하지 않고 429 `QUOTA_EXCEEDED`를 반환한다.
- LLM 쿼터 검사와 차감은 Redis 원자 연산으로 한 번에 처리한다.
- 제한 수치와 집계 기간은 `[미정]`이다.

### 4.10 확정 보안 정책 (2026-08-06 리뷰 반영)

#### 4.10.1 OAuth 계정 연결

- 동일 이메일이라도 서로 다른 OAuth 공급자 계정을 자동으로 병합하지 않는다.
- 공급자가 이메일 인증 완료 여부를 제공하고 검증에 성공한 경우에만 연결 후보로 취급한다.
- 기존 User와의 연결은 로그인된 사용자가 명시적으로 계정 연결을 승인하는 절차를 통해서만 수행한다.
- OAuth 공급자 계정은 `oauth_accounts`를 통해 내부 `users.id`와 연결한다. 공급자별 사용자 식별자를 User ID로 직접 사용하지 않는다.

#### 4.10.2 Access token

- access token은 JWT 형식을 사용하고 RS256으로 서명한다.
- 필수 claim: `sub`, `roles`, `iss`, `aud`, `iat`, `exp`, `jti`.
- `sub`는 OAuth 공급자 ID가 아니라 내부 `users.id`이다.
- access token 유효기간은 15분. 검증 시 서명 알고리즘·issuer·audience를 명시적으로 고정한다.
- 서명 키는 secret manager에서 관리하고 `kid`를 이용한 키 교체를 지원한다.

#### 4.10.3 Refresh token

- refresh token은 매 갱신 시 회전하고 token family를 기록한다.
- DB에는 원문 대신 서버 비밀키를 사용하는 HMAC-SHA256 검증값만 저장한다.
- 이미 사용되었거나 폐기된 refresh token의 재사용을 감지하면 해당 사용자의 token family 전체를 즉시 폐기한다.

#### 4.10.4 Admin/Test 및 Internal API 보호

- `/internal/*`는 내부망에서만 라우팅하며 `X-Internal-Api-Key` 검증, IP allowlist와 rate limit을 함께 적용한다.
- Internal API key는 용도·발급자·발급 시각·만료 시각을 기록하고 secret manager를 통해 발급·교체한다.
- 저장소·DB·로그에는 평문 키를 남기지 않는다.

#### 4.10.5 Allowlist·쿼터·오류 응답

- 무인증 라우트는 중앙 allowlist로만 등록한다. 신규 라우터는 기본적으로 인증 필수.
- 429 `QUOTA_EXCEEDED` 응답에는 `Retry-After` 헤더로 다음 허용 시점까지의 초 단위 값을 제공한다.

#### 4.10.6 Replay·시점 복원 권한

- 시점 복원은 특정 Tick snapshot의 조회·확인 전용 기능이며 새 Simulation 생성이나 이력 변경을 수행하지 않는다.
- snapshot 조회 권한은 원본 Simulation의 조회 권한을 상속한다.

#### 4.10.7 로그 계약

- 감사 로그: 로그인·로그아웃·token 발급·회전·폐기·재사용 감지·계정 연결·권한 변경 이벤트.
- 실패 로그: `trace_id`, 시각, endpoint, HTTP method, 실패 분류, 내부 `user_id`(확인된 경우), source IP 비식별화 값.
- access token, refresh token, authorization header, Internal API key 원문은 기록하지 않는다.

## 5. 구현 구조

```
app/
├── auth/
│   ├── router.py
│   ├── service.py
│   ├── dependencies.py
│   ├── token.py
│   └── schemas.py
├── authorization/
│   ├── ownership.py
│   └── quota.py
└── models/
    ├── user.py
    ├── oauth_account.py
    └── refresh_token.py
```

- `router`: 로그인·갱신·로그아웃 HTTP 경계
- `service`: 계정 연결과 token 수명주기
- `dependencies`: Bearer token 검증과 현재 사용자 주입
- `ownership`: Simulation 및 하위 리소스 소유권 검사
- `quota`: 사용자별 실행 쿼터 검사
- `models`: 인증 데이터 영속성 모델

## 6. 출력 계약

### 6.1 인증 성공 응답

```json
{
  "data": {
    "access_token": "<token>",
    "token_type": "Bearer",
    "expires_in": 900,
    "refresh_token": "<token>"
  }
}
```

### 6.2 오류 응답

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "인증이 필요합니다.",
    "trace_id": "req_example"
  }
}
```

| HTTP | code | 발생 조건 |
| --- | --- | --- |
| 401 | UNAUTHORIZED | access token 없음·만료·위조·유효하지 않음 |
| 401 | UNAUTHORIZED | Admin/Test secret 없음 또는 불일치 |
| 403 | FORBIDDEN | 인증 성공 후 대상 리소스 권한 없음 |
| 404 | RESOURCE_NOT_FOUND | 대상 리소스가 존재하지 않음 |
| 429 | QUOTA_EXCEEDED | 사용자별 동시 실행 또는 Tick 호출 쿼터 초과 |

## 7. 평가 시나리오

| # | 시나리오 | 기대 결과 |
| --- | --- | --- |
| 1 | Bearer token 없이 보호 API 호출 | 401 UNAUTHORIZED |
| 2 | 만료·위조된 access token으로 보호 API 호출 | 401 UNAUTHORIZED |
| 3 | 소유자가 자신의 Simulation 조회 | 정상 응답 |
| 4 | 다른 사용자의 비공개 Simulation 또는 하위 리소스 접근 | 403 FORBIDDEN |
| 5 | 존재하지 않는 리소스 접근 | 404 RESOURCE_NOT_FOUND |
| 6 | X-Internal-Api-Key 없이 Admin/Test API 호출 | 401 UNAUTHORIZED, Tick 미실행 |
| 7 | 외부 네트워크에서 Internal API 호출 | 라우팅 불가 |
| 8 | 유효한 refresh token으로 갱신 | 새 access token 발급 |
| 9 | 만료·폐기된 refresh token으로 갱신 | 요청 거부 |
| 10 | 사용자별 LLM 실행 쿼터 초과 | 429 QUOTA_EXCEEDED, 실행 미시작 |
| 11 | 로그와 DB의 인증 비밀정보 검사 | refresh token 원문과 내부 API key 미노출 확인 |

## 8. 완료 기준

- 보호 API의 Bearer token 검증 테스트를 통과한다.
- Simulation 및 하위 리소스 소유권 인가 테스트를 통과한다.
- Admin/Test 및 Internal API 접근 제어 테스트를 통과한다.
- refresh token 발급·갱신·폐기 테스트를 통과한다.
- 인증 오류가 공통 API 오류 형식으로 반환된다.
- refresh token 원문과 내부 API key가 DB 및 애플리케이션 로그에 남지 않는다.
- LLM 실행 쿼터 초과 요청이 실행 전에 거부된다.

## 9. 후속 확인 사항

| 항목 | 현재 기준 | 후속 조치 |
| --- | --- | --- |
| OAuth/OIDC 공급자 | [미정] | MVP 공급자와 계정 생성·연결 정책 확정 |
| WebSocket 인증 | MVP 무인증 | 인증 도입 방식과 시점 확정 |
| 설정 공유 권한 | [미정] | 공유 범위와 가져오기 권한 모델 확정 |
| LLM 실행 쿼터 수치 | [미정] | 제한 수치와 집계 기간 확정 |
| Backend 파일 구조 | 권장 구조 제시 | 실제 프로젝트 구조에 맞춰 파일명 확정 |

## 변경 이력

| 버전 | 날짜 | 변경 이력 | 수정자 |
| --- | --- | --- | --- |
| v0.1 | 2026-08-03 | MVP 인증·인가, token 수명주기, API 유형별 접근 정책, 인증 데이터 모델 책임 및 미결 사항 초안 작성 | 박지유 |
| v0.2 | 2026-08-05 | JWT `sub`를 내부 `users.id`로 정의, 필수 claim 명시, 오류 기준(401/403/404) 확정 | 박지유 |
| v0.3 | 2026-08-06 | JWT RS256·15분 만료, HMAC-SHA256 refresh token, token family 전체 폐기, Internal API 보호 강화, WebSocket 노출 범위, Redis 쿼터 처리, 감사 로그 기준, Replay→시점 복원 정합화 | 박지유 |
