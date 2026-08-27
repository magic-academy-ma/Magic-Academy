from types import SimpleNamespace

import pytest

from app.services.simulations import (
    InvalidSimulationStatusTransitionError,
    update_simulation_status,
)


class FakeSession:
    def __init__(self) -> None:
        self.flush_count = 0
        self.refresh_count = 0

    def refresh(self, simulation, *, with_for_update: bool) -> None:
        assert with_for_update is True
        self.refresh_count += 1

    def flush(self) -> None:
        self.flush_count += 1


@pytest.mark.parametrize(
    ("current_status", "new_status"),
    [
        ("ready", "running"),
        ("running", "paused"),
        ("running", "completed"),
        ("running", "failed"),
        ("paused", "running"),
        ("paused", "completed"),
        ("paused", "failed"),
    ],
)
def test_update_simulation_status_accepts_documented_transitions(
    current_status: str,
    new_status: str,
) -> None:
    db = FakeSession()
    simulation = SimpleNamespace(status=current_status)

    updated = update_simulation_status(db, simulation, new_status)

    assert updated.status == new_status
    assert db.refresh_count == 1
    assert db.flush_count == 1


@pytest.mark.parametrize(
    ("current_status", "new_status"),
    [
        ("ready", "paused"),
        ("completed", "running"),
        ("failed", "running"),
        ("running", "running"),
    ],
)
def test_update_simulation_status_rejects_invalid_transitions(
    current_status: str,
    new_status: str,
) -> None:
    db = FakeSession()
    simulation = SimpleNamespace(status=current_status)

    with pytest.raises(InvalidSimulationStatusTransitionError):
        update_simulation_status(db, simulation, new_status)

    assert simulation.status == current_status
    assert db.refresh_count == 1
    assert db.flush_count == 0
