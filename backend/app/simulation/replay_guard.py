import threading
from contextlib import contextmanager


class ReplayModeError(RuntimeError):
    """Raised when a forbidden operation is attempted during replay."""


_state = threading.local()
_state.in_replay = False


def is_replay_mode() -> bool:
    return getattr(_state, "in_replay", False)


def set_replay_mode(value: bool) -> None:
    _state.in_replay = bool(value)


def assert_not_replay(message: str = "Operation forbidden during replay") -> None:
    if is_replay_mode():
        raise ReplayModeError(message)


@contextmanager
def ReplayGuard():
    """Context manager to enable replay mode within the block.

    Usage:
        with ReplayGuard():
            # replay-mode active
            ...
    """
    prev = is_replay_mode()
    set_replay_mode(True)
    try:
        yield
    finally:
        set_replay_mode(prev)
