import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from tests.slice5_campaign import run_canonical_campaign


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required",
)


def run_once():
    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        outer = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as db:
            result = run_canonical_campaign(db)
        outer.rollback()
    engine.dispose()
    return result


def test_canonical_tick10_campaign_covers_eight_production_scenarios() -> None:
    campaign = run_once()
    events = [event for tick in campaign for event in tick.events]

    assert len(campaign) == 10
    assert campaign[0].tick_number == 10
    assert campaign[-1].tick_number == 19
    assert any(event[0] == "CLASS" for event in events)
    assert any(event[0] == "GROUP_PROJECT" for event in events)
    assert any(event[0] == "MAGIC_EXPLOSION" for event in events)
    assert any(event[0] == "STUDENT_MISSING" for event in events)
    assert any(event[0] == "CURSE_SPREAD" for event in events)

    tick10_actions = {item[0]: item[1:] for item in campaign[0].runtime_actions}
    assert tick10_actions["student-01"][0] == "TALK"
    assert tick10_actions["student-02"][0] == "TALK"
    assert tick10_actions["student-03"] == (
        "WAIT",
        "FALLBACK",
        "WAIT_FALLBACK",
    )
    assert campaign[0].relationship == (50, 50, 50, "friend")
    assert any(tick.reflection_eligible_event_keys for tick in campaign)

    statuses = {
        tick.tick_number: {status[0]: status[1:] for status in tick.statuses}
        for tick in campaign
    }
    assert statuses[10]["student-05"] == ("inactive_temporary", 13, None)
    assert statuses[13]["student-05"] == ("active", None, 16)
    assert statuses[16]["student-05"] == ("active", None, None)


def test_canonical_tick10_campaign_is_semantically_deterministic_twice() -> None:
    assert run_once() == run_once()
