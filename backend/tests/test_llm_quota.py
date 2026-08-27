from concurrent.futures import ThreadPoolExecutor

from app.simulation.agent_runtime import AgentRuntime, LLMInvocationError, RuntimeStatus
from app.simulation.llm_quota import LLM_QUOTA_EXCEEDED_REASON, LLMQuota
from tests.test_agent_runtime_graph import (
    SequenceLLMClient,
    invalid_response,
    make_runtime_input,
    valid_response,
)


# ─── LLMQuota 단위 ────────────────────────────────────────────────────────────


def test_fresh_quota_reports_limit_used_remaining() -> None:
    quota = LLMQuota(limit=12)
    assert quota.limit == 12
    assert quota.used == 0
    assert quota.remaining == 12


def test_consume_up_to_limit_then_refuse_without_extra_charge() -> None:
    quota = LLMQuota(limit=12)

    assert all(quota.try_consume() for _ in range(12))
    assert quota.used == 12
    assert quota.remaining == 0

    # 13번째 요청은 LLM을 호출하지 않고 거부되며 used를 늘리지 않는다.
    assert quota.try_consume() is False
    assert quota.used == 12
    assert quota.remaining == 0


def test_reset_restores_full_quota() -> None:
    quota = LLMQuota(limit=12)
    for _ in range(12):
        quota.try_consume()

    quota.reset()

    assert quota.used == 0
    assert quota.remaining == 12
    assert quota.limit == 12


def test_reset_can_override_limit_for_tests() -> None:
    quota = LLMQuota(limit=12)
    quota.reset(limit=5)
    assert quota.limit == 5
    assert quota.remaining == 5


def test_concurrent_consume_never_exceeds_limit() -> None:
    quota = LLMQuota(limit=12)

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(lambda _: quota.try_consume(), range(50)))

    assert sum(results) == 12
    assert quota.used == 12


# ─── AgentRuntime 연동 ───────────────────────────────────────────────────────


def test_run_with_exhausted_quota_falls_back_without_calling_llm() -> None:
    runtime_input = make_runtime_input()
    quota = LLMQuota(limit=1)
    assert quota.try_consume() is True  # Tick의 유일한 슬롯을 미리 소진

    client = SequenceLLMClient([valid_response(runtime_input)])
    result = AgentRuntime(client, llm_quota=quota).run(runtime_input)

    assert result.status == RuntimeStatus.FALLBACK
    assert result.failure_reason == LLM_QUOTA_EXCEEDED_REASON
    assert client.call_count == 0


def test_retry_consumes_a_separate_quota_slot() -> None:
    runtime_input = make_runtime_input()
    quota = LLMQuota(limit=1)

    # 1번째 시도: 유효하지 않은 응답 → retry 필요. 2번째 시도는 쿼터가 없어 차단.
    client = SequenceLLMClient(
        [invalid_response(runtime_input), valid_response(runtime_input)]
    )
    result = AgentRuntime(client, llm_quota=quota).run(runtime_input)

    assert client.call_count == 1
    assert quota.used == 1
    assert result.status == RuntimeStatus.FALLBACK
    assert result.failure_reason == LLM_QUOTA_EXCEEDED_REASON


def test_each_retry_attempt_decrements_quota() -> None:
    runtime_input = make_runtime_input()
    quota = LLMQuota(limit=2)

    client = SequenceLLMClient(
        [invalid_response(runtime_input), invalid_response(runtime_input)]
    )
    result = AgentRuntime(client, llm_quota=quota).run(runtime_input)

    assert client.call_count == 2
    assert quota.used == 2
    assert result.status == RuntimeStatus.FALLBACK


def test_failed_llm_call_still_consumes_quota() -> None:
    runtime_input = make_runtime_input()
    quota = LLMQuota(limit=12)

    client = SequenceLLMClient(
        [LLMInvocationError("provider down"), valid_response(runtime_input)]
    )
    result = AgentRuntime(client, llm_quota=quota).run(runtime_input)

    assert result.status == RuntimeStatus.PROPOSED
    # 실패한 1번째 호출 + 성공한 2번째 호출 = 2회 차감.
    assert quota.used == 2


def test_runtime_without_quota_keeps_existing_retry_behavior() -> None:
    runtime_input = make_runtime_input()
    client = SequenceLLMClient(
        [invalid_response(runtime_input), invalid_response(runtime_input)]
    )
    result = AgentRuntime(client).run(runtime_input)

    assert client.call_count == 2
    assert result.status == RuntimeStatus.FALLBACK
    assert result.failure_reason != LLM_QUOTA_EXCEEDED_REASON


def test_reset_llm_quota_is_noop_without_quota() -> None:
    runtime_input = make_runtime_input()
    runtime = AgentRuntime(SequenceLLMClient([valid_response(runtime_input)]))
    runtime.reset_llm_quota()  # 예외 없이 통과
    assert runtime.llm_quota is None


def test_reset_llm_quota_clears_used_between_ticks() -> None:
    quota = LLMQuota(limit=12)
    runtime = AgentRuntime(SequenceLLMClient([]), llm_quota=quota)
    for _ in range(12):
        quota.try_consume()

    runtime.reset_llm_quota()

    assert quota.used == 0
    assert quota.remaining == 12
