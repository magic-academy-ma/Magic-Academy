import threading

_lock = threading.Lock()
_counters = {
    "llm_calls": 0,
    "runtime_calls": 0,
    "tick_calls": 0,
}


def reset_counters() -> None:
    with _lock:
        for k in _counters:
            _counters[k] = 0


def increment_llm() -> None:
    with _lock:
        _counters["llm_calls"] += 1


def increment_runtime() -> None:
    with _lock:
        _counters["runtime_calls"] += 1


def increment_tick() -> None:
    with _lock:
        _counters["tick_calls"] += 1


def get_counts() -> dict:
    with _lock:
        return dict(_counters)
