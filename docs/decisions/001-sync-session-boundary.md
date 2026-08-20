---
authored_with: Codex
features_used:
  - github:github
  - orca-cli
date: 2026-08-20
status: accepted
---

# 001. Tick Memory의 동기 Session 경계

## 배경

현재 인증, Simulation, Runtime 결과와 Memory Repository는 SQLAlchemy 동기 `Session`을 사용한다. Slice 3 계획의 `AsyncSession` 예시만 적용하면 Memory 경로에 별도 세션 체계가 생기며, 하나의 Tick에서 트랜잭션 책임이 분산된다.

## 결정

Slice 3에서는 기존 동기 `Session`을 유지한다. Repository는 `flush`까지만 수행하고 commit과 rollback은 상위 Tick Coordinator가 담당한다. 비동기 API에서 동기 DB 구간을 실행할 때는 해당 worker 안에서 Session을 생성하고 종료하며, Session을 thread 경계 밖으로 전달하지 않는다.

DB snapshot과 최종 commit의 격리 수준은 `tick-engine.md`의 기존 결정인 `REPEATABLE READ`와 `READ COMMITTED`를 따른다. 전체 `AsyncSession` 전환은 백엔드 DB 계층 전체를 대상으로 별도 결정과 migration 계획을 수립한다.

## 이유

- 기존 Repository와 서비스 계층의 일관성을 유지한다.
- 일부 Repository만 async로 전환해 생기는 이중 세션과 트랜잭션 혼용을 피한다.
- 비동기 API의 이벤트 루프 블로킹은 DB 구간을 worker로 분리해 제한할 수 있다.

대안인 MemoryRepository 단독 `AsyncSession` 전환은 변경량은 작지만, Tick 단위 commit 책임과 테스트 fixture를 두 체계로 나누므로 선택하지 않았다. 백엔드 전체 async 전환은 장기 동시성에는 유리하지만 현재 Slice 3 범위를 넘는다.

## 결과

- `TickMemoryService`는 동기 메서드로 UUID 변환과 Repository 호출을 조정한다.
- Runtime과 Policy Engine은 DB Session을 전달받지 않는다.
- 실제 Tick endpoint는 동기 DB 구간을 async route에서 직접 실행하지 않아야 한다.
- 향후 다중 worker Tick 실행은 별도의 PostgreSQL lease와 fencing token 계약을 구현해야 한다.
