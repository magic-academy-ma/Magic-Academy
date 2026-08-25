---
title: Slice 7 Task 5 — 외부 검증 가이드
status: draft
updated: 2026-08-25
issue: "#148"
contract_ref: "docs/04-feature-specs/slice-7-config-sharing-import-deployment.md (§7)"
precondition: "Task 1~4 통합 및 Railway 테스트 환경 준비 완료 후 실행"
---

# Slice 7 Task 5 — 외부 검증 가이드

## 개요

배포된 Railway 환경에서 외부 사용자가 공유·검색·가져오기·실행 흐름을 직접 검증한다.
모든 시나리오는 계약 문서(`slice-7-config-sharing-import-deployment.md`) §7을 기준으로 한다.

---

## 1. 테스트 계정·접근 권한 기준

### 1.1 계정 구성

| 역할 | 설명 | 주의 |
|------|------|------|
| 사용자 A (공유자) | Simulation 설정을 공유하는 계정 | 실제 개인정보·운영 자격증명 사용 금지 |
| 사용자 B (외부 검증자) | 공유를 찾고 가져오는 외부 계정 | 사용자 A와 다른 계정 |

- 두 계정 모두 Railway 테스트 환경에 직접 생성한 테스트 계정을 사용한다.
- 실제 학교 이메일, 실명, 운영 시크릿을 검증 계정에 사용하지 않는다.
- 검증 완료 후 테스트 계정과 생성된 Simulation을 정리한다.

### 1.2 접근 권한 매트릭스 (계약 §3 기준)

| visibility | 사용자 A 조회 | 사용자 B 직접 접근 | 공개 목록·검색 | 사용자 B 가져오기 |
|------------|:---:|:---:|:---:|:---:|
| `private`  | ✓ | ✗ | ✗ | ✗ |
| `unlisted` | ✓ | ✓ (ID 필요) | ✗ | ✓ |
| `public`   | ✓ | ✓ | ✓ | ✓ |

---

## 2. Golden Path 시나리오

계약 §7.1 기준. 각 단계는 순서대로 실행하며 모든 단계가 통과해야 PASS다.

### 전제 조건

- [ ] Railway 배포 환경이 정상 동작 중이다 (`/health` 200 응답)
- [ ] 사용자 A, B 계정이 생성되어 있고 각각 로그인 가능하다
- [ ] 사용자 A 계정으로 Simulation이 하나 이상 생성·설정되어 있다

### 단계별 체크리스트

**Step 1: 공유 생성 (사용자 A)**

- [ ] 사용자 A로 로그인한다
- [ ] 기존 Simulation을 선택하고 visibility `public`으로 공유를 생성한다
- [ ] 응답에 공유 ID가 포함된다
- [ ] 공유 생성 후 사용자 A의 Simulation 원본이 변경되지 않았음을 확인한다

**Step 2: 공유 검색 및 상세 조회 (사용자 B)**

- [ ] 사용자 B로 로그인한다
- [ ] 공개 목록·검색 API에서 Step 1의 공유가 검색된다
- [ ] 공유 상세 조회 응답에 제목, 설명, visibility 정보가 포함된다
- [ ] 응답에 사용자 A의 ID, 이름, 자격증명, Prompt 원문이 포함되지 않는다

**Step 3: 가져오기 idempotency 검증 (사용자 B)**

- [ ] 사용자 B가 동일한 `Idempotency-Key`로 가져오기를 두 번 요청한다
- [ ] 두 번째 요청이 첫 번째와 동일한 결과(Simulation ID)를 반환한다
- [ ] 새 Simulation이 정확히 하나만 생성된다

**Step 4: 새 Simulation 소유권 확인 (사용자 B)**

- [ ] 생성된 Simulation의 `owner_id`가 사용자 B의 ID와 일치한다
- [ ] 원본 Simulation의 `owner_id`는 여전히 사용자 A다
- [ ] 새 Simulation ID가 원본 Simulation ID와 다르다

**Step 5: 설정·Snapshot 일치 확인**

- [ ] 가져온 Simulation의 설정이 원본 공유 Snapshot과 일치한다
  - `execution_seed`, `model_version`, `prompt_version`, `policy_version`, `resolver_version`
  - 생활 Agent roster와 fixture 식별자
  - Student·Professor Profile과 User Persona fixture 식별자
  - Location, Agent State, Relationship, Organization membership Snapshot

**Step 6: 가져온 Simulation 실행**

- [ ] 사용자 B가 가져온 Simulation을 시작한다
- [ ] 최소 한 Tick이 정상 실행된다
- [ ] 실행 중 원본 Simulation과 공유 Snapshot이 변경되지 않는다

**Step 7: 원본 불변성 최종 확인**

- [ ] 사용자 A의 원본 Simulation 설정이 Step 1 이후 변경되지 않았다
- [ ] 원본 공유 Snapshot 내용이 가져오기 전후로 변경되지 않았다

---

## 3. 실패(음수) 시나리오

계약 §7.2 기준. 각 시나리오는 독립적으로 실행한다.

### 3.1 private 공유 차단

- [ ] 사용자 A가 visibility `private`로 공유를 생성한다
- [ ] 사용자 B로 해당 공유 ID를 직접 조회하면 404가 반환된다
- [ ] 사용자 B로 가져오기를 시도하면 404가 반환된다
- [ ] 공개 목록·검색에 해당 공유가 나타나지 않는다

### 3.2 unlisted 공개 목록 비노출

- [ ] 사용자 A가 visibility `unlisted`로 공유를 생성한다
- [ ] 공개 목록·검색 API에 해당 공유가 나타나지 않는다
- [ ] 사용자 B가 정확한 공유 ID로 직접 조회하면 성공한다
- [ ] 사용자 B가 정확한 공유 ID로 가져오기하면 성공한다

### 3.3 취소된 공유 접근 차단

- [ ] 사용자 A가 공유를 취소한다 (soft delete)
- [ ] 취소 후 공유 상세 조회 시 404가 반환된다
- [ ] 취소 후 가져오기 시도 시 404가 반환된다

### 3.4 지원하지 않는 schema_version 거부

- [ ] 지원하지 않는 `schema_version`을 포함한 payload로 가져오기를 요청한다
- [ ] 422와 `UNSUPPORTED_SHARE_SCHEMA_VERSION`이 반환된다

### 3.5 변조된 payload 거부

- [ ] 필수 필드가 누락되거나 타입이 변조된 payload로 가져오기를 요청한다
- [ ] 422와 `INVALID_SHARE_PAYLOAD`가 반환된다

### 3.6 Persona 대상 불일치 거부

- [ ] User Persona fixture가 roster에 없는 payload로 가져오기를 요청한다
- [ ] 422와 `SHARE_PERSONA_TARGET_INVALID`가 반환된다

### 3.7 가져오기 실패 시 rollback

- [ ] 가져오기 transaction 중간에 강제 실패를 유발한다
- [ ] 새 Simulation과 모든 하위 데이터가 rollback된다
- [ ] DB에 부분 생성된 데이터가 없음을 확인한다

### 3.8 Runtime·LLM·Tick 무호출 검증

- [ ] 가져오기 요청 중 Runtime, LLM, Tick Engine 호출이 0회임을 운영 로그에서 확인한다

### 3.9 로그 민감정보 비노출 검증

- [ ] Golden Path 및 실패 시나리오 실행 후 운영 로그를 확인한다
- [ ] 로그에 JWT, 비밀번호, API key, Secret이 포함되지 않는다
- [ ] 로그에 username, display name, 사용자 자유 입력이 포함되지 않는다
- [ ] 로그에 request/response 전체 payload, Prompt 원문, Chain of Thought가 포함되지 않는다

---

## 4. 비공개 설정 비노출 검증 체크리스트

이 섹션은 §3.1, §3.2 시나리오에서 비공개 설정이 공개 경로로 노출되지 않는지 종합 확인한다.

- [ ] `private` 공유가 공개 목록 API 응답에 없다
- [ ] `unlisted` 공유가 공개 목록 API 응답에 없다
- [ ] 접근 불가·취소된 공유의 존재 여부를 알 수 없다 (모두 404)
- [ ] 공개 목록·검색 응답에 비공개 설정의 제목·설명·소유자 정보가 없다

**비노출 건수 기록:**
- private 공유 공개 노출: ___ 건 (0건이어야 PASS)
- unlisted 공유 공개 노출: ___ 건 (0건이어야 PASS)

---

## 5. 외부 피드백 수집 양식

외부 검증자(사용자 B 역할)에게 제공하는 피드백 양식. GitHub Issue 코멘트 또는 별도 양식으로 수집한다.

---

### 피드백 양식 템플릿

```
검증 환경: Railway 테스트 환경 (URL: ___)
검증 일시: YYYY-MM-DD
검증자 역할: 외부 사용자 B

[Golden Path 완료 여부]
- 완료 / 미완료 (미완료 시 중단 단계: Step ___)
- 막힌 지점 설명 (있으면):

[UI/UX 피드백]
- 공유 목록 화면:
- 공유 상세 화면:
- 가져오기 결과 화면:
- 오류 메시지 이해도 (1=전혀 이해 못함, 5=바로 이해):

[실패 시나리오 경험]
- 오류 메시지가 명확하지 않은 경우:
- 예상과 다른 동작:

[기타 자유 의견]

[전반적인 완성도] (1=미완성, 5=배포 가능)
```

---

## 6. 피드백 Must·선택 개선 분류 기준

수집된 피드백은 아래 기준으로 분류한다.

### Must (완료 전 필수 반영)

다음 중 하나라도 해당하면 Must다.

- Golden Path를 완료하지 못하게 막는 오류·UI 문제
- 비공개 설정이 노출되는 보안 문제
- 주요 실패 상태의 메시지가 없거나 서버 내부 오류 그대로 노출
- 데이터 무결성 문제 (원본 변경, rollback 실패 등)

### 선택 개선 (PASS 후 처리 가능)

- 오류 메시지가 있지만 더 친절하게 개선 가능한 경우
- UI 레이아웃·디자인 개선 제안
- 성능 개선 제안 (기능은 정상 동작)
- 문서 보완 제안

---

## 7. 피드백 반영 결과 기록

피드백 1회 수집 후 아래 표를 작성한다.

| # | 피드백 요약 | 분류 | 처리 결과 | 담당 | 비고 |
|---|------------|------|----------|------|------|
| 1 | | Must/선택 | 반영/미반영 | | 미반영 시 사유 |
| 2 | | | | | |

**Must 미해결 건수:** ___ 건 (0건이어야 PASS)

---

## 8. 최종 PASS 판정 기준 (Issue #148 완료 기준 매핑)

| 완료 기준 | 검증 방법 | 결과 |
|----------|----------|------|
| 외부 사용자가 문서만으로 Golden Path 완료 | §2 Golden Path 체크리스트 전 단계 PASS | ☐ |
| 비공개 설정 노출 0건 | §4 비노출 검증 결과 | ☐ |
| 주요 실패 상태 이해 가능한 메시지 표시 | §3 음수 시나리오 오류 응답 확인 | ☐ |
| 외부 피드백 1회 이상 수집·분류 | §5 양식 제출 완료 + §6 분류 기록 | ☐ |
| 반영 대상 피드백의 수정 또는 미반영 사유 기록 | §7 반영 결과 표 완성 | ☐ |
| 미해결 Must blocker 없음 | §7 Must 미해결 건수 = 0 | ☐ |

---

## 9. 진행 현황

| 단계 | 상태 | 날짜 | 비고 |
|------|------|------|------|
| 문서 초안 작성 | 완료 | 2026-08-25 | |
| Task 1~4 통합 대기 | 대기 중 | | |
| Railway 환경 준비 대기 | 대기 중 | | |
| Golden Path 실제 검증 | 미시작 | | |
| 음수 시나리오 실제 검증 | 미시작 | | |
| 외부 피드백 수집 | 미시작 | | |
| 피드백 반영 결과 기록 | 미시작 | | |
