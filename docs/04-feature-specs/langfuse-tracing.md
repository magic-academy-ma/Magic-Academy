---
title: Langfuse LLM Tracing
status: draft
visibility: public
---

# Langfuse LLM Tracing

사용자 요청에 따른 관찰 전용 계측. 기존 Tick, LangGraph 분기, Runtime 결과,
DB 트랜잭션, replay 무재실행 계약을 유지한다.

- 기본 비활성화. 키 또는 올바른 HTTP(S) base URL이 없으면 계측만 비활성화한다.
- Tick → Agent Runtime → 호출 시도/검증 → Anthropic Generation 계층을 기록한다.
- 스레드별 복사한 context로 동일 Tick의 병렬 Agent를 연결한다.
- retry, FALLBACK, SKIPPED, quota 소진을 구분한다.
- 원문, 예외 메시지, 프롬프트, 메모리, 사용자 입력, 키는 전송하지 않는다.
- 모델과 식별자, 상태, 실제 응답의 토큰 사용량만 기록한다. 비용은 추산하지 않는다.
- SDK 초기화/기록/종료 실패는 실행 결과와 예외 계약에 영향을 주지 않는다.
- Prompt Management, Evaluation, Datasets, Experiments, 피드백 UI는 범위 밖이다.

검증: 비활성/설정 오류, 계층/동시 실행 격리, retry/fallback/skipped/quota,
전송 실패 불변, mock 무네트워크, Runtime/DB/API 회귀. Cloud 수신은 키 발급 후 수동 검증한다.
