---
title: 스토리모드 CHAPTER 1 — 거짓 소문의 확산을 막아라
status: implementation-proposal
visibility: public
source: GitHub issue 255 및 사용자 확정 기획
---

# 확정 기획

플레이어는 학생자치위원회의 임시 조정관이다. 학기 초 학생이 수업 중 금지된 마법을 몰래 썼다는 소문이 교수의 적발·징계·퇴학 이야기로 과장된다. 학생들의 진술을 비교하고 출처를 추적하며 당사자·교수에게 사실을 확인한다. 테마는 정보와 판단이다.

완전 해소 / 일부 오해 / 학교 전체 확산을 GOOD / MIXED / BAD에 연결한다. 다른 챕터 결과는 초기 상태·난이도에 영향을 주지 않는다. FINAL 집계·다른 챕터·Langfuse·전역 업적 시스템은 제외한다. 행동은 Agent가 결정한다. 증언·정정 요청은 실행 결과와 별개다.

# 채택한 구현안 (기획 확정값 아님)

## 진실·역할 추첨

학생 5명과 교수 1명은 기존 fixture를 사용한다. 학생을 fixture 순서로 정렬한 후 run seed로 역할을 섞는다. 당사자, 최초 전달자, 재미로 과장하는 학생, 침묵하는 목격자, 믿고 전달하는 학생을 각 1명 배정한다. 교수는 고정 역할이다. 소문이 지목한 당사자의 이름은 도입에서 공개되지만, 최초 전달자·과장자·목격자·전달자 및 속사정은 비공개다.

실제 진실은 교수의 허가를 받은 안전한 보호마법 실습이며 금지 마법·적발·징계·퇴학은 없다. 최초 전달자는 빛 또는 경고음만 보고 오해했다. 목격 경위는 '문틈으로 빛을 봄' / '복도에서 경고음을 들음', 침묵 동기는 '갈등 회피' / '친구에게 불이익이 갈까 걱정' 후보에서 seed로 추첨하여 저장한다. 실행 중 바꾸지 않는다. 같은 seed는 같은 역할·후보를 재현하지만 LLM 대사·행동은 보장하지 않는다. 이어하기는 저장 결과를 읽는다.

당사자·목격자·교수만 진실 정보 F를 안다. 최초 전달자는 R0(금지 마법)과 자신이 출처라는 S 정보를, 과장자는 R0·R1(교수 적발 및 징계), 전달자는 R2(퇴학)를 안다. 전달자는 과장자에게, 과장자는 최초 전달자에게 들었다는 출처를 안다. 최초 전달의 seed 기록에는 시점 0과 정보 원본을 저장한다. R0→R1→R2 변형만 허용하며 변형 가능한 다음 정보만 그 학생 입력에 제공한다. 다른 학생 역할·속사정·보유 정보는 입력하지 않는다.

초기 관계는 기존 Policy의 첫 만남 기본값 0을 사용해 새 simulation의 6명 전체 방향 관계를 만들고 초기값을 run에 저장한다. 이전 챕터 결과를 읽지 않는다. 관계·상태 변경은 기존 Event·Runtime Reaction·Policy 경로로 처리한다.

## 진행·조사·개입

모든 수치와 제한은 이름 있는 상수로 관리하는 임시값이다: ROUND_COUNT=3, TICKS_PER_ROUND=3, TOTAL_TICKS=9, INQUIRIES_PER_ROUND=3, SCHOOL_SPREAD_THRESHOLD=5(소문 인지 범위), SCHOOL_MISUNDERSTANDING_THRESHOLD=3(현재 오해가 남은 학생 수), RUMOR_ACTS_PER_ACTION_LIMIT=3(행동 하나의 구조화 정보 결과 상한). 시간의 기본 단위는 기존 1 Tick=8분을 유지한다.

| 라운드 | 틱 | 흐름 |
|---|---|---|
| 1 | 1~3 | T1 관찰 → 조사 최대 3회 → 개입 제출 → T2·T3 반응 관찰 |
| 2 | 4~6 | T4 관찰 → 조사 최대 3회 → 개입 제출 → T5·T6 반응 관찰 |
| 3 | 7~9 | T7 관찰 → 조사 최대 3회 → 개입 제출 → T8·T9 반응 관찰·종료 |

개입 대기 지점은 tick 1·4·7이다. 각 지점 이후 개입 없이는 전진할 수 없다. 조사 상대는 모든 학생 및 교수, 질문 주제는 '들은 소문', '누구에게 들었나', '직접 본 사실', '사실 확인', '진술 비교'다. 비교 질문은 서로 다른 학생의 저장된 진술 두 개를 명시해야 한다. 사실 확인은 당사자 또는 교수의 실제 F 응답만 인정한다. 질문은 요청일 뿐이며 참여를 거부하면 답변은 없다. 대화 목록에 숨겨진 역할을 표시하지 않는다. 당사자의 이름은 공개된 소문 내용으로 알 수 있고 교수도 기존 인물로 표시한다.

개입 선택은 WATCH / SHARE(들은 정보 전달) / REQUEST_TESTIMONY(증언 요청) / REQUEST_CORRECTION(정정 요청) / PUBLISH_FACT(확인 사실 공지)다. SHARE·요청에는 대상 학생과 플레이어가 아는 정보 ID가 필요하다. 공지는 확인한 F가 있어야 가능하다. 요청은 해당 학생 입력에 기록하며 행동을 지정하지 않는다. SHARE는 들은 R 정보 또는 직접 확인한 F만 전달한다. 출처 당사자의 1인칭 진술 S는 비교 기록으로만 사용하며 전달하지 않는다. 목격자에게 들었으나 아직 직접 확인하지 않은 F를 확정 사실로 주입하지 않는다. SHARE는 수신 정보가 되어 다음 자율 판단에 영향을 준다. 공지는 모두에게 확인 사실을 제공하지만 정정·해소를 자동 확정하지 않는다. 각 개입 지점은 서버 opened_at을 저장하고 제출 시 공통 InterventionRecord 및 is_indecisive로 소요 시간을 판정하므로 새로고침을 포함한다.

## 구조화 결과·판정

Runtime Intent에 선택적 rumor acts(kind, information_id, target, source_id)를 추가한다. 학생 간 TRANSFER/TESTIFY/CORRECT는 PROPOSED 상태, 상호 TALK 성립, intent 대상과 act 대상 일치, 실행 시작 시점의 보유 정보·출처 검증을 모두 통과해야 한다. 후속 반응이 같은 batch에서 새 정보를 미리 사용하지 않도록 시작 snapshot으로 검증한다. 조사 ANSWER는 해당 조사 Event에 실제 PARTICIPATE_EVENT한 학생만 player 대상으로 허용한다. LLM 자유문장·키워드는 게임 상태나 업적의 근거가 아니다. 공개 대사는 검증한 정보의 한국어 문장을 사용한다. 원시 motivation·내부 기억·역할은 공개하지 않는다.

전달은 알려진 R 정보 또는 허용된 다음 변형을 실제 상대에게 말함이다. 전달 시 원본 정보 ID·출처·화자·대상·tick·순서를 기록한다. 이미 성립한 비교 → 확인 → 대응은 이후 재조사·재비교로 취소되지 않는다. 증언은 F를 아는 학생이 자발적으로 F를 실제 상대에게 말함이다. 정정은 과거 소문을 전달한 본인이 F를 알고 자신의 말을 실제 이전 수신자에게 바로잡는 행동이다. 증언·정정은 검증된 실제 TALK에 한해 화자·수신자의 사실 수용과 오해 해소를 기록한다. 조사 중 자발적으로 F를 답한 학생도 사실을 수용한 것으로 기록한다. 요청·공지 수신만으로 이 상태를 바꾸지 않는다. 미해소 소문은 현재 잘못 믿고 있는 정보이며, 단순 청취와 별개다. 당사자·목격자·교수는 시작부터 F를 알므로 R을 들어도 오해가 생기지 않는다. 나머지는 플레이어의 확인 사실 공지를 정보로 받을 수 있지만, 자발적인 사실 답변·증언·정정 또는 검증된 증언/정정 수신이 있어야 오해를 해소한다. 각자의 이전 전달 기록도 개인별 Runtime 입력에 제공하여 본인이 누구에게 한 말을 정정할 수 있는지 알 수 있게 한다. 학생의 알고 있는 정보 / 미해소 소문 / 플레이어가 들은 정보 / 사실 확인 기록을 분리한다.

소문 인지 이력 reached는 학생 5명을 대상으로 하며 당사자·최초 전달자·진실을 아는 목격자도 포함한다. 최초 전달자는 소문 생성자로서 시작 인지 범위에 포함하고 교수는 제외한다. 이것만으로 전교 확산으로 판정하지 않는다. **인지 범위 5명 + 현재 오해 학생 3명 이상 + 그 오해 학생 중 실제 TRANSFER 기록이 있는 사람**을 모두 만족할 때 전교 확산이다. 학생 5명 MVP에서 외부 학생을 새로 만들지 않고 인지 폭과 지속되는 잘못된 믿음·실제 전달을 함께 보는 임시 대리 기준이다. 현재 오해가 남은 전달자의 정정되지 않은 전달은 계속 유효하며 시간 경과만으로 소멸시키지 않는다. 학교 전체 확산의 최초 시점 school_spread_tick은 업적용 이력이며 현재 확산 상태와 분리한다. 단순 청취·요청·공지·대사 키워드만으로 확산을 만들지 않는다.

종료 시 플레이어가 F를 실제 확인했고 현재 오해 학생이 0명이면 RESOLVED/GOOD. 과거 인지·확산 이력이 남아 있어도 GOOD을 막지 않는다. 그렇지 않고 종료 시 현재 전교 확산 조건을 모두 만족하면 SPREAD/BAD. 나머지는 MISUNDERSTANDING/MIXED. 9틱을 마치면 나쁜 엔딩도 클리어다.

## 업적 (챕터 결과에 ID 저장)

- CHAPTER1_CLEAR: tick=9.
- FIRST_SENTENCE: 최초 전달자에게 SOURCE 질문을 하고 실제 S 답변을 받음.
- HEARD_AND_SEEN: 서로 다른 학생의 실제 진술 두 개를 COMPARE로 제출한 후, 당사자/교수에게 F를 실제 확인한 뒤 WATCH 이외의 대응을 제출함. 순서를 기록한다. 이미 성립한 비교 → 확인 → 대응은 이후 재조사·재비교로 취소되지 않는다.
- FAN_THE_FLAME: 플레이어 SHARE로 미확인 소문을 받은 학생이 이후 실제로 그 소문 또는 변형을 해당 정보를 아직 모르고 사실을 수용하지 않은 학생에게 전달함. 신규 수신은 정보 ID·학생 쌍 기준이므로 기존 소문을 아는 학생에게 다른 변형이 추가되는 경로도 포함한다. 플레이어 개입 provenance가 이어져야 하며, 진실을 아는 학생의 단순 청취·중복 수신은 업적을 만들지 않는다.
- SILENT_WITNESS: 증언 요청 이후 원래 침묵하던 목격자가 처음으로 실제 TESTIFY함(요청 전 증언한 이력이 있으면 제외).
- THREE_RUMORS: 플레이어가 실제로 R0·R1·R2 세 정보를 들음.
- AHEAD_OF_RUMOR: 학교 전체 확산 전 F 확인, 종료 GOOD, 학교 전체 확산 이력 없음.
- SELF_CORRECTION: 소문을 실제 전달했던 학생이 이후 실제 CORRECT함.
- INDECISIVE: 공통 is_indecisive(개입 결정 300초 이상).

도달 경로: SOURCE 조사로 첫 문장, R0·R1·R2 조사로 세 소문, 비교→교수 확인→공지로 비교 업적, 미확인 전달→실제 재전달로 불씨, 목격자 요청→자발 증언으로 증인, 전달자에게 F 제공 및 정정 요청→실제 정정으로 한마디, 조기 F 확인→전원 증언/정정으로 선제 해소. 여러 run에 걸쳐 달성할 수 있다. 테스트에서는 같은 Runtime 인터페이스에 Mock LLM을 주입한다.

## 저장·공개 계약

별도 rumor_challenge_runs: owner, simulation_id, 시작 request_id, seed, revision, 비공개 JSON 상태(역할·고정 진실·학생별 정보·개입·조사·전달 provenance·초기 관계·원시 실행 결과), 공개 결과·업적, 개입 opened_at, 명령 영수증. 전용 simulation은 paused로 두어 일반 수동/자동 tick을 막는다. 정보 메모리는 run 비공개 JSON에서 해당 Agent 입력에만 주입하고 자유 생성 memory를 일반 memory 테이블에 기록하지 않는다.

API는 /v1/challenges/rumor: POST 시작(seed, request_id), GET 현재 run 목록의 최신값(/current), GET /{id}, POST /{id}/advance, /investigate, /intervene. 결과·업적은 GET 응답에 포함한다. #249의 simulation + 별도 run 구조를 참고하되 공통 모델은 #252/#254를 따른다. 모든 변경 명령은 request_id와 expected_revision을 필수로 받는다. DB 행을 FOR UPDATE NOWAIT로 잠근 뒤 영수증 및 revision을 확인한다. 예약·LLM 실행·Event/Runtime/Policy 효과·진행·영수증을 **한 트랜잭션으로 커밋**하며 예약만 먼저 커밋하지 않는다. 같은 request 재전송은 저장 응답을 반환하고 다른 동시 명령은 즉시 409다. 예외·전원 LLM fallback은 503 및 롤백으로 처리하여 틱·선택·조사 횟수·관계·상태를 소비하지 않는다. 같은 요청으로 재시도할 수 있다. 일부 Agent만 fallback이면 기존 Runtime 정책대로 성공한 나머지 결과로 틱을 완료한다. 커밋 응답 유실은 DB 영수증을 재조회하여 이미 커밋한 결과를 반환한다. 프로세스 종료 시 DB가 미커밋 transaction과 잠금을 해제한다. 이전 구현에서 남은 pending은 POST /{id}/recover(request_id, expected_revision)로 잠금만 해제할 수 있고, 실행 중인 새 명령의 행 잠금은 복구 요청도 409로 거절한다. 복구는 LLM·틱·선택·관계 효과를 실행하지 않는다. 새 시작의 request_id도 owner별 유일하다.

공개 응답은 진행 위치·revision·조사 잔여·선택지·플레이어가 들은 진술·검증 기록·관찰된 전달/증언/정정·엔딩·업적만 허용 목록으로 구성한다. seed·역할·속사정·진실 원본·개인 보유 정보·초기 전달 seed 기록·원시 Runtime 설명은 반환하지 않는다. 기존 학생 상태/관계 UI를 재사용한다. 재로그인 후 current 조회로 이어간다.

# 구현 및 검증 기록

기준 ref: `origin/feature/issue-253-story-chapter4-festival-booth`, SHA `d3d56e36c0e001e93a766b255008ab0ce8dc590b`. #254가 #252 공통 모델 커밋 `101212f1c424c8502cc98f75bc15db442acb7b58`을 포함한다. 두 PR은 확인 당시 OPEN이며 develop에 미머지다. #249는 서비스·API·화면 구성만 참고했고 병합하지 않았다. 기본 Memory 검색/embedding을 새로 호출하지 않고, 기존 Runtime의 개인별 입력 지점에 run의 정보 기억을 전달한다. 기존 Event·RuntimeOrchestrator·TALK 충돌 해소·Policy·관계 저장 경로를 재사용한다. 일반 수동 tick·상태 변경·밤 스킵은 이 run의 simulation에서 차단한다.

공개 대사는 검증된 정보의 표준 한국어 문장이다. 자유 생성 대사의 문장 품질·실제 LLM 행동 분포는 별도 플레이테스트가 필요하다. 모든 완료 테스트는 Mock LLM을 production Runtime에 주입했으며 외부 유료 LLM 호출은 하지 않았다.

검증 명령 (backend 개발 의존성 및 마이그레이션 적용 필요):

```sh
cd backend
python -m pytest -q
# 반드시 별도의 비어 있는 테스트 DB를 지정한다. 기존 데이터 DB를 사용하지 않는다.
TEST_DATABASE_URL='<테스트 PostgreSQL URL>' python -m pytest tests/test_challenge_rumor.py tests/test_rumor_challenge_service.py tests/test_challenge_round_driver.py -q
```

화면 테스트 및 빌드:

```sh
cd frontend
npm test -- --run src/pages/RumorChapterPage.test.jsx
npm run build
E2E_BASE_URL=http://127.0.0.1:5174 E2E_API_URL=http://127.0.0.1:8001 npx playwright test e2e/rumor-chapter.spec.js
```

E2E는 실제 API·DB에 연결한다. 테스트 API 서버는 `get_agent_runtime` dependency만 `AgentRuntime(ChapterClient(), model='browser-test-llm')`로 대체한다(`backend/tests/test_rumor_challenge_service.py`의 ChapterClient). `DATABASE_URL`을 테스트 DB로, `CORS_ORIGINS`를 프론트 주소로 설정하고, 프론트는 `VITE_USE_MOCK=false`, `VITE_API_URL`을 테스트 API 주소로 실행한다. 게임 경로를 바꾸는 별도 Mock 모드는 없다.

검증한 실제 플레이: 회원가입/로그인 → 메인 CHAPTER 1 → 시작 → T1 관찰 → 교수 사실 확인 → 학생 Inspector·관계 그래프 → 새로고침/재로그인/이어하기 → 확인 사실 공지 → T2~T9 및 라운드별 WATCH → MIXED 엔딩·클리어 업적. 별도 실DB 테스트로 자율 증언의 GOOD 경로, 실제 전달의 BAD 경로를 검증했다. 데스크톱과 모바일 폭의 Playwright 검증을 수행했다.

현재 제한: 실제 LLM 입력·응답은 외부 호출이므로 프로세스가 응답을 받은 뒤 DB 커밋 전에 종료되면 재시도에서 LLM 호출이 반복될 수 있다. 외부 LLM의 exactly-once 호출은 보장하지 않지만, 커밋된 틱·선택·관계 효과는 영수증과 단일 transaction으로 중복 반영하지 않는다. 실행 중에는 DB 연결과 행 잠금을 유지하고 SDK 기본 timeout/retry를 사용한다. 구형 예약 선커밋 워커와 혼합 운영하지 말고 구형 프로세스를 종료한 뒤 새 버전에서 이전 pending을 복구한다. 기존 완료 결과는 자동 재판정하지 않는다.

범위 외 발견: 프론트 전체 병렬 테스트의 기존 `App.mock.test.jsx`가 Inspector 위치를 `dd`에서 찾다가 실패한다. 기준 SHA 코드로 별도 복사한 전체 테스트에서도 동일하게 재현했고 해당 기존 테스트/화면은 수정하지 않았다. 이 테스트는 단독 실행에서는 통과했다.

E2E 테스트 서버를 직접 실행하는 명령(테스트 DB 마이그레이션 후):

```sh
cd backend
PYTHONPATH=. DATABASE_URL='<테스트 PostgreSQL URL>' CORS_ORIGINS=http://127.0.0.1:5174 python tests/test_rumor_challenge_service.py
# 다른 터미널, frontend/에서:
VITE_USE_MOCK=false VITE_API_URL=http://127.0.0.1:8001 npm run dev -- --host 127.0.0.1 --port 5174
# Playwright 실행 시 E2E_API_URL도 같은 테스트 API 주소로 지정한다.
E2E_BASE_URL=http://127.0.0.1:5174 E2E_API_URL=http://127.0.0.1:8001 npx playwright test e2e/rumor-chapter.spec.js
```

## 변경 파일

| 위치 | 변경 이유 |
|---|---|
| `docs/04-feature-specs/challenge-mode-rumor.md` | 확정 기획·구현 규칙·공개 계약·검증 기록 |
| `backend/app/simulation/challenge/rumor.py`, `rumor_runtime.py` | 정보 상태·추첨·전달/증언/정정·엔딩/업적 및 개인별 Runtime 입력/결과 검증 |
| `backend/app/simulation/agent_runtime.py`, `anthropic_llm_client.py` | 선택적인 챕터 맥락과 구조화 응답 추가 |
| `backend/app/services/rumor_challenge.py`, `backend/app/api/rumor_challenge.py`, `backend/app/api/router.py` | 저장·소유권·명령 예약·API |
| `backend/app/domain/models.py`, `backend/alembic/versions/20261017_0001_add_rumor_challenge.py` | 비공개 run·명령 영수증 모델 및 마이그레이션 |
| `backend/app/services/manual_tick.py`, `night_transition.py`, `simulations.py` | 일반 API를 통한 챕터 진행 우회 차단 |
| `backend/tests/test_challenge_rumor.py`, `test_rumor_challenge_service.py` | 순수 로직·업적 경로·실DB·API·동시성·대표 엔딩 검증 |
| `backend/tests/test_mvp_tick_event_policy.py`, `test_simulation_status.py`, `test_schema_models.py` | 새 run 조회와 스키마를 기존 테스트 더블/기대값에 반영 |
| `frontend/src/pages/RumorChapterPage.jsx`, `RumorChapterPage.css`, `RumorChapterPage.test.jsx` | 실제 플레이 화면 및 상태/관계 컴포넌트 재사용·화면 테스트 |
| `frontend/src/App.jsx`, `frontend/src/pages/MainPage.jsx` | 메인 화면 진입 연결 |
| `frontend/e2e/rumor-chapter.spec.js` | 실제 API를 사용하는 데스크톱/모바일 브라우저 검증 |

최초 #255 구현 검증 결과(최종 점검 이전): 백엔드 전체 697 passed / 252 skipped(DB 미지정 실행), 별도 PostgreSQL의 CHAPTER 1·공통 드라이버 검증 24 passed, 새 화면 테스트 4 passed, Playwright 2 passed, 새 화면 oxlint 경고 없음, 프론트 빌드 통과, `git diff --check` 통과. 프론트 전체 실행은 142 passed / 기존 테스트 1 failed이며 기준 코드에서도 같은 실패를 재현했다. 테스트용 DB는 기존 개발 데이터와 분리하여 생성했고 기존 개발 DB에는 마이그레이션을 적용하지 않았다.

# 커밋 전 최종 점검 (2026-10-18)

- 기존 브랜치·미커밋 변경을 유지하고 관련 로직·서비스·복구 API/화면·회귀 테스트만 갱신했다. 스키마 변경은 없으며 기존 개발 DB에는 마이그레이션을 적용하지 않았다.
- 실제 연결 경로: FastAPI `get_agent_runtime` → `create_agent_runtime` → `AnthropicLLMClient.messages.parse(IntentCandidate)` → `AgentRuntime` → `RumorRuntime` → 기존 round_driver/Orchestrator/TALK 충돌 해소/Policy. 설정의 인증 정보 존재 여부만 확인했으며 현재 `ANTHROPIC_API_KEY`가 설정되어 있지 않아 실제 LLM 호출은 수행하지 못했다. 키를 출력·새 파일에 기록하지 않았다. 아래 실제 서비스 검증과 달리 자동 통합 테스트는 Mock LLM이다.
- 발견·수정: 단순 수신을 오해로 계산하던 문제, 최초 발신자에 대한 공지와 학생의 실제 사실 수용이 섞이던 문제, 학생이 본인의 이전 전달 상대를 입력으로 받지 못하던 문제, 예약 선커밋 뒤 영구 잠금 문제를 수정했다.
- 회귀 검증: LLM timeout/예외 및 전원 fallback, 실제 PostgreSQL 오류/flush 실패, 커밋 전 실패, 커밋 후 응답 유실, 별도 실행 프로세스의 강제 종료 후 재시도, 중복/동시 명령, 실행 중 복구 거부, 이전 pending 복구를 검증한다. 롤백 전후의 상태와 관계 값을 비교하고 최종 1회 delta만 반영하는지 확인한다.
- 모든 업적은 실제 서비스의 3회/라운드 조사 한도와 9틱 진행 안에서 도달하는 두 대표 run으로 검증한다. 하나는 출처·진술 비교·세 소문·5분 선택 업적, 다른 하나는 미확인 전달→실제 추가 전달→실제 정정→목격자의 자발적 증언→GOOD/선제 해소다. BAD/MIXED는 별도 대표 run으로 검증한다. 증언/정정 요청 뒤 실제 학생이 REST를 고르는 거절 경로에서는 해당 행동/업적을 만들지 않는다.

## 실제 LLM을 로컬에서 확인하는 절차

기존 `ANTHROPIC_API_KEY` 인증이 설정된 셸에서 실행한다. 키 값은 명령 인자·문서·테스트 파일에 넣지 않는다. 실제 검증에서는 Mock 의존성으로 덮어쓰는 `tests/test_rumor_challenge_service.py` 서버를 사용하지 않는다.

```sh
# 별도 테스트 DB에만 기존 마이그레이션을 적용한다.
cd backend
DATABASE_URL='<분리된 테스트 DB URL>' python -m alembic upgrade head
DATABASE_URL='<분리된 테스트 DB URL>' CORS_ORIGINS=http://127.0.0.1:5174 python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
# 다른 셸에서 frontend/
VITE_USE_MOCK=false VITE_API_URL=http://127.0.0.1:8001 npm run dev -- --host 127.0.0.1 --port 5174
```

로그인 → CHAPTER 1 시작 → T1 관찰 → 서로 다른 학생 진술 기록 → 다음 라운드 진술 비교 및 교수/당사자 확인 → 미확인 정보 전달/확인 사실 공지/증언·정정 요청 → 다음 틱의 실제 TALK/증언/정정과 관계 변화 확인 → T9 엔딩을 확인한다. 요청 직후 행동이 완료됐다고 표시되지 않아야 한다. 학생 상태·관계 Inspector와 공개 전달 이력, 현재 오해 수를 함께 본다. 같은 seed도 실제 LLM 대사·행동·업적은 달라질 수 있어 한 run에서 특정 엔딩·업적을 보장하지 않는다. 오류 시 같은 요청 재확인 또는 진행 기록 새로고침으로 이어가며, 이전 pending이 표시되면 ‘중단된 실행 복구’를 사용한다.

최종 재점검 실행 결과: 백엔드 전체 **702 passed / 266 skipped**(DB 미지정 실행), 별도 PostgreSQL의 챕터·공통 드라이버 **43 passed**, 화면 **5 passed**, 프론트 빌드 통과. 전체 oxlint는 기준 코드와 동일한 경고 3개이며 신규 경고는 없다. `git diff --check`와 신규 파일 12개의 공백 검사도 통과했다. 반복 VERIFY/COMPARE로 이미 달성한 HEARD_AND_SEEN이 취소되는 오류를 실패 테스트 2건으로 재현한 뒤, 전체 비교·확인·대응 기록을 검사하도록 수정했다. Playwright 데스크톱/모바일 **2 passed**, 별도 중단 예약 주입 후 브라우저 복구→조사→새로고침 이어하기→엔딩 **1 passed**를 현재 코드로 재실행했다. 빈 분리 DB에 전체 Alembic 체인과 `20261017_0001` 적용을 확인했고 개발 DB는 변경하지 않았다. 실제 LLM은 인증 설정 부재로 미실행이며 모든 이번 Runtime 실행은 Mock이다. 기존 `App.mock.test.jsx`의 기준 SHA 전체 실행 실패 로그를 재확인했고 해당 테스트와 Inspector 구현은 수정하지 않았다.
