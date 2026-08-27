import threading

LLM_QUOTA_EXCEEDED_REASON = "llm_quota_exceeded"


class LLMQuota:
    """활동 Tick 단위 LLM 실행 쿼터.

    새 활동 Tick이 시작되면 ``reset()`` 으로 ``used`` 를 0으로 되돌리고,
    실제 LLM 호출 직전마다 ``try_consume()`` 으로 원자적으로 1회 차감한다.
    한도를 모두 사용하면 ``try_consume()`` 은 ``used`` 를 늘리지 않고 ``False`` 를
    반환한다 (초과 요청은 추가 차감하지 않는다). 여러 스레드가 동시에
    호출해도 실제 차감 횟수가 한도를 넘지 않도록 lock으로 보호한다.
    """

    def __init__(self, limit: int) -> None:
        self._lock = threading.Lock()
        self._limit = limit
        self._used = 0

    def reset(self, limit: int | None = None) -> None:
        """새 활동 Tick 시작 시 ``used`` 를 0으로 되돌린다.

        ``limit`` 인자는 테스트 편의용이며, 일반 경로에서는 생성 시 주입된
        한도를 그대로 유지한다.
        """
        with self._lock:
            if limit is not None:
                self._limit = limit
            self._used = 0

    def try_consume(self) -> bool:
        """LLM 호출 1회를 원자적으로 예약한다.

        잔여 쿼터가 있으면 ``used`` 를 1 증가시키고 ``True``,
        소진된 상태면 ``used`` 를 그대로 두고 ``False`` 를 반환한다.
        """
        with self._lock:
            if self._used >= self._limit:
                return False
            self._used += 1
            return True

    @property
    def limit(self) -> int:
        with self._lock:
            return self._limit

    @property
    def used(self) -> int:
        with self._lock:
            return self._used

    @property
    def remaining(self) -> int:
        with self._lock:
            return max(self._limit - self._used, 0)
