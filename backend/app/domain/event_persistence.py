"""Internal Task 3 input: final Event/Memory/State results, never LLM previews."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAGIC_TYPES = {"STUDENT_MISSING", "CURSE_SPREAD", "MAGIC_EXPLOSION", "RITUAL_FAILURE", "MAGICAL_DISCOVERY"}

# Exported so callers that build an EventWrite/StateDelta from a more loosely
# typed upstream `str` (e.g. app/services/manual_tick.py) can `cast()` to the
# exact literal instead of widening these fields back to `str`.
EventTypeLiteral = Literal[
    "CLASS", "GROUP_PROJECT", "EXAM", "MEETING", "MT", "FESTIVAL", "STUDENT_COUNCIL",
    "RANDOM_INCIDENT", "STUDENT_MISSING", "CURSE_SPREAD", "MAGIC_EXPLOSION",
    "RITUAL_FAILURE", "MAGICAL_DISCOVERY",
]
StateMetricLiteral = Literal["hunger", "fatigue", "stress", "satisfaction", "mood"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EventWrite(Contract):
    id: UUID
    event_type: EventTypeLiteral
    event_subtype: str | None = None
    title: str = Field(min_length=1, max_length=100)
    description: str
    participant_agent_ids: tuple[UUID, ...] = Field(min_length=1)
    location_id: UUID
    source: Literal["event_master", "magic_layer"]
    impact_level: Literal["low", "medium", "high"]
    importance: int
    expected_effects: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_event(self):
        """Preserve separate special-event semantics and the importance mapping."""
        if self.importance != {"low": 30, "medium": 50, "high": 80}[self.impact_level]:
            raise ValueError("impact_level/importance mismatch")
        if self.event_type in MAGIC_TYPES and self.source != "magic_layer":
            raise ValueError("special Event must come from magic_layer")
        if self.event_type == "RANDOM_INCIDENT" and not self.event_subtype:
            raise ValueError("RANDOM_INCIDENT needs event_subtype")
        if len(set(self.participant_agent_ids)) != len(self.participant_agent_ids):
            raise ValueError("duplicate Event participant")
        return self


class StateDelta(Contract):
    target_type: Literal["AGENT_STATE"] = "AGENT_STATE"
    source_agent_id: UUID
    target_agent_id: None = None
    metric: StateMetricLiteral
    before: int = Field(strict=True)
    requested_total: int = Field(strict=True)
    applied_delta: int = Field(strict=True)
    after: int = Field(strict=True)
    effect_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_arithmetic(self):
        """Check final clamp arithmetic without using after_preview."""
        minimum = -100 if self.metric == "mood" else 0
        if not minimum <= self.before <= 100:
            raise ValueError("invalid before")
        if self.after != max(minimum, min(100, self.before + self.requested_total)):
            raise ValueError("invalid resolved after")
        if self.after - self.before != self.applied_delta:
            raise ValueError("invalid applied_delta")
        if any(not effect_id for effect_id in self.effect_ids) or len(set(self.effect_ids)) != len(self.effect_ids):
            raise ValueError("invalid effect_ids")
        return self


class MemoryWrite(Contract):
    agent_id: UUID
    event_id: UUID
    content: str = Field(min_length=1)
    memory_type: Literal["observation", "conversation", "reflection", "plan"]
    importance: int = Field(ge=0, le=100)
    occurred_at: datetime

    @model_validator(mode="after")
    def validate_time(self):
        """Require an absolute timestamp for reproducible serialization."""
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must include timezone")
        return self


class EventBatch(Contract):
    simulation_id: UUID
    run_id: str = Field(min_length=1)
    tick_number: int = Field(ge=1)
    policy_version: str = Field(min_length=1)
    resolver_version: str = Field(min_length=1)
    resolution_id: str = Field(min_length=1)
    events: tuple[EventWrite, ...] = ()
    resolved_effects: tuple[StateDelta, ...] = ()
    memories: tuple[MemoryWrite, ...] = ()
    missing_agent_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def validate_unique_targets(self):
        """The Resolver must have combined each target/metric before storage."""
        pairs = [(item.source_agent_id, item.metric) for item in self.resolved_effects]
        if len(set(pairs)) != len(pairs):
            raise ValueError("duplicate resolved target/metric")
        if len({item.id for item in self.events}) != len(self.events):
            raise ValueError("duplicate Event ID")
        if len(set(self.missing_agent_ids)) != len(self.missing_agent_ids):
            raise ValueError("duplicate missing Agent")
        return self
