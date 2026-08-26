import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import (
    Agent,
    AgentState,
    Relationship,
    RuntimeResult,
    Simulation,
    StudentProfile,
    User,
)
from app.services.fixtures import seed_slice_zero
from app.services.manual_tick import advance_manual_tick
from app.simulation.agent_runtime import AgentRuntime, AgentRuntimeInput


@dataclass(frozen=True)
class CampaignTick:
    tick_number: int
    events: tuple[tuple[str, str | None, tuple[str, ...]], ...]
    statuses: tuple[tuple[str, str, int | None, int | None], ...]
    runtime_actions: tuple[tuple[str, str, str, str | None], ...]
    relationship: tuple[int, int, int, str | None]
    reflection_eligible_event_keys: tuple[str, ...]


class CanonicalCampaignLLM:
    def generate(self, runtime_input: AgentRuntimeInput) -> dict:
        fixture_key = runtime_input.agent.fixture_key
        agents_by_name = {agent.name: agent.agent_id for agent in runtime_input.nearby_agents}
        if runtime_input.tick_number == 10 and fixture_key in {
            "student-01",
            "student-02",
            "student-03",
        }:
            target_name = {
                "student-01": "레오",
                "student-02": "아델",
                "student-03": "아델",
            }[fixture_key]
            target_id = agents_by_name[target_name]
            relationship_signals = []
            if fixture_key in {"student-01", "student-03"}:
                relationship_signals = [
                    {
                        "signal_type": "TRUST_UP",
                        "intensity": "LOW",
                        "target_agent_id": str(target_id),
                    }
                ]
            return self._response(
                action_type="TALK",
                target_agent_id=target_id,
                relationship_signals=relationship_signals,
            )
        if runtime_input.tick_number == 10 and fixture_key == "student-05":
            return self._response(
                action_type="WAIT",
                state_signals=[
                    {"signal_type": "STRESS_DOWN", "intensity": "HIGH"}
                ],
            )
        if runtime_input.agent.agent_type == "professor":
            class_event = runtime_input.events[0]
            return self._response(
                action_type="TEACH_CLASS",
                target_location_id=class_event.location_id,
                related_event_id=class_event.event_id,
            )
        return self._response(action_type="WAIT")

    @staticmethod
    def _response(
        *,
        action_type: str,
        target_agent_id: UUID | None = None,
        target_location_id: UUID | None = None,
        related_event_id: UUID | None = None,
        relationship_signals: list[dict] | None = None,
        state_signals: list[dict] | None = None,
    ) -> dict:
        return {
            "action_type": action_type,
            "target_agent_id": str(target_agent_id) if target_agent_id else None,
            "target_location_id": str(target_location_id) if target_location_id else None,
            "related_event_id": str(related_event_id) if related_event_id else None,
            "utterance": "대화하자." if action_type == "TALK" else None,
            "motivation_summary": "Slice 5 canonical campaign",
            "reaction": {
                "valence": "POSITIVE" if action_type == "TALK" else "NEUTRAL",
                "relationship_signals": relationship_signals or [],
                "state_signals": state_signals or [],
            },
            "decision_explanation": {
                "alternatives": [
                    {
                        "action_type": action_type,
                        "description": "canonical action",
                        "relative_priority": "HIGH",
                        "selected": True,
                    }
                ],
                "influencing_factors": [],
            },
            "memory_candidates": [],
        }


def prepare_canonical_campaign(db: Session) -> tuple[Simulation, dict[str, Agent]]:
    user = User(
        id=uuid4(),
        username=str(uuid4()),
        display_name="Slice 5 campaign",
        password_hash="test",
        roles=["USER"],
    )
    db.add(user)
    db.flush()
    simulation = Simulation(
        id=uuid4(),
        owner_id=user.id,
        name="Canonical Tick 10 campaign",
        current_tick=9,
        current_day=3,
    )
    db.add(simulation)
    db.flush()
    seed_slice_zero(db, simulation.id)
    agents = {
        agent.fixture_key: agent
        for agent in db.scalars(
            select(Agent)
            .where(Agent.simulation_id == simulation.id)
            .order_by(Agent.fixture_key)
        )
    }
    profiles = {
        profile.agent_id: profile
        for profile in db.scalars(
            select(StudentProfile).where(
                StudentProfile.agent_id.in_([agent.id for agent in agents.values()])
            )
        )
    }
    profiles[agents["student-01"].id].interest_field = "캠페인 전공"
    profiles[agents["student-02"].id].interest_field = "캠페인 전공"

    states = {
        state.agent_id: state
        for state in db.scalars(
            select(AgentState).where(AgentState.simulation_id == simulation.id)
        )
    }
    for key in ("student-01", "student-02", "student-03", "student-04"):
        states[agents[key].id].fatigue = 85
    states[agents["student-05"].id].stress = 95

    db.add_all(
        [
            Relationship(
                id=uuid4(),
                simulation_id=simulation.id,
                source_agent_id=agents["student-01"].id,
                target_agent_id=agents["student-02"].id,
                trust=49,
                affection=50,
                closeness=50,
            ),
            Relationship(
                id=uuid4(),
                simulation_id=simulation.id,
                source_agent_id=agents["student-02"].id,
                target_agent_id=agents["student-01"].id,
                trust=0,
                affection=0,
                closeness=0,
            ),
        ]
    )
    target = agents["student-05"]
    for tick in range(1, 10):
        run_id = f"campaign-history-{tick}"
        db.add(
            RuntimeResult(
                id=uuid4(),
                run_id=run_id,
                tick_number=tick,
                agent_id=target.id,
                status="PROPOSED",
                action_type="WAIT",
                intent={
                    "action_type": "WAIT",
                    "reaction": {"state_signals": [], "relationship_signals": []},
                },
                retry_count=0,
                failure_reason=None,
                model="campaign-history",
                prompt_version="campaign-v1",
                idempotency_key=f"{run_id}:{tick}:{target.id}",
                result_fingerprint=f"campaign-{tick:02d}".ljust(64, "0"),
            )
        )
    db.commit()
    return simulation, agents


def run_canonical_campaign(db: Session) -> tuple[CampaignTick, ...]:
    simulation, agents = prepare_canonical_campaign(db)
    runtime = AgentRuntime(CanonicalCampaignLLM(), model="slice5-campaign")
    fixture_by_id = {str(agent.id): key for key, agent in agents.items()}
    snapshots: list[CampaignTick] = []
    for _ in range(10):
        result = asyncio.run(advance_manual_tick(db, simulation, runtime=runtime))
        db.commit()
        relationship = db.scalar(
            select(Relationship).where(
                Relationship.source_agent_id == agents["student-01"].id,
                Relationship.target_agent_id == agents["student-02"].id,
            )
        )
        refreshed_agents = list(
            db.scalars(
                select(Agent)
                .where(Agent.simulation_id == simulation.id)
                .order_by(Agent.fixture_key)
            )
        )
        snapshots.append(
            CampaignTick(
                tick_number=result.current_tick,
                events=tuple(
                    (
                        event["event_type"],
                        event.get("event_subtype"),
                        tuple(
                            fixture_by_id[agent_id]
                            for agent_id in event["participant_agent_ids"]
                        ),
                    )
                    for event in result.event_batch_result["events"]
                ),
                statuses=tuple(
                    (
                        agent.fixture_key,
                        agent.active_status,
                        agent.inactive_until_tick,
                        agent.cursed_until_tick,
                    )
                    for agent in refreshed_agents
                ),
                runtime_actions=tuple(
                    (
                        fixture_by_id[str(runtime_result.agent_id)],
                        runtime_result.intent.action_type,
                        runtime_result.status,
                        runtime_result.failure_reason,
                    )
                    for runtime_result in result.runtime_results
                ),
                relationship=(
                    relationship.trust,
                    relationship.affection,
                    relationship.closeness,
                    relationship.relationship_type,
                ),
                reflection_eligible_event_keys=(
                    result.event_and_magic_result.reflection_eligible_event_keys
                ),
            )
        )
    return tuple(snapshots)
