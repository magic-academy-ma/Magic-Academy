---
title: 공개 보안 원칙
source: confluence/05_TECH/security-design
canonical: https://jehye.atlassian.net/wiki/spaces/MA/pages/27459688
status: draft
visibility: public
updated: 2026-08-25
source_updated: 2026-08-06
---

# 공개 보안 원칙

이 문서는 공개 가능한 애플리케이션·LLM·인프라·운영 보안 원칙만 정의한다. 인증·접근 제어, API 계약, 데이터 모델과 내부 네트워크 상세는 비공개 문서에서 관리한다.

## 기본 원칙

| 원칙 | 기준 |
| --- | --- |
| 최소 권한 | 사용자와 서비스는 필요한 작업만 수행한다. |
| 기본 거부 | 명시적으로 허용하지 않은 동작과 도구는 차단한다. |
| 심층 방어 | 입력·출력 검증, 격리, 저장 경계와 감사 기록을 함께 적용한다. |
| 실패 안전 | 검증 결과가 불명확하면 실행·저장·전송을 중단한다. |
| 최소 노출 | 기능에 필요한 정보만 화면·로그·오류에 제공한다. |

## LLM과 Agent 안전

- Agent 이름, Event 설명, Memory와 사용자 입력은 신뢰할 수 없는 데이터로 취급한다.
- 시스템 지시와 데이터 Context를 분리하고 데이터 속 명령문을 실행 지시로 해석하지 않는다.
- LLM 출력은 구조화된 Schema와 도메인 규칙으로 검증한 뒤 허용된 Intent와 후보만 수용한다.
- Agent와 LLM은 상태를 직접 저장하지 않고 검증·충돌 해결·원자적 Commit 경로를 거친다.
- 도구가 필요하면 allowlist와 최소 입력 Schema를 사용한다.
- 내부 chain-of-thought, raw reasoning과 hidden prompt는 저장하거나 노출하지 않는다. UI에는 Context 기반의 짧은 Decision Explanation만 제공한다.

## Secret·로그·출력

- 자격증명과 secret은 코드, fixture, 문서와 저장소에 포함하지 않는다.
- 로그에는 secret, 전체 prompt·Memory 원문이나 불필요한 개인정보를 남기지 않는다.
- LLM 생성 텍스트는 직접 HTML로 렌더링하지 않고 escape하거나 검증된 sanitizer를 사용한다.
- 오류 메시지는 내부 구현, stack trace와 보호 대상 정보를 노출하지 않는다.
- 감사 기록과 일반 애플리케이션 로그를 분리하고 필요한 기간만 보존한다.

## 공급망·실행 환경

- 의존성과 배포 이미지는 검토 가능한 버전으로 고정하고 취약점·secret 검사를 자동화한다.
- 실행 환경은 비루트와 최소 권한을 기본으로 하며 필요한 서비스만 외부에 노출한다.
- 개발·검증·운영 환경의 설정과 secret을 분리한다.

## Secure SDLC

1. 설계에서 보호 대상, 신뢰 경계와 데이터 흐름을 검토한다.
2. 구현에서 기본 거부, 입력 검증, 최소 권한과 secret 비포함을 확인한다.
3. 테스트에서 prompt injection, 구조 위반 출력, 로그 노출과 격리 실패를 검증한다.
4. CI·배포에서 dependency·container·secret scan을 수행한다.
5. 운영에서 이상 징후를 탐지하고 격리·영향 분석·복구·재발 방지 테스트로 이어간다.

## 공개 검증 기준

- 악성 명령형 Memory·Event가 데이터로만 처리된다.
- Schema 또는 도메인 규칙을 위반한 LLM 출력은 저장 전에 거부된다.
- 로그와 오류에 secret, 전체 prompt·Memory 원문이 없다.
- 저장소와 배포 산출물의 secret scan이 통과한다.
- 의존성·이미지 취약점이 팀의 승인 기준을 넘지 않는다.

구체 보안 설정값, 탐지 규칙, 내부 경로, 권한·소유권 검사와 사고 대응 연락 체계는 공개 범위에서 제외한다.
