from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.simulation.agent_runtime import AgentRuntimeResult
from app.simulation.intent_conflict import TalkConflictResolution


@dataclass(frozen=True)
class DialogueMessageDraft:
    order: int
    speaker_agent_id: UUID
    utterance: str | None


@dataclass(frozen=True)
class DialogueDraft:
    run_id: str
    tick_number: int
    participant_a_id: UUID
    participant_b_id: UUID
    messages: tuple[DialogueMessageDraft, ...]

    @property
    def participant_ids(self) -> tuple[UUID, ...]:
        return (self.participant_a_id, self.participant_b_id)


@dataclass(frozen=True)
class DialogueBatchSaveResult:
    new_count: int
    duplicate_count: int


def build_dialogue_drafts(
    resolution: TalkConflictResolution,
) -> tuple[DialogueDraft, ...]:
    """One draft per mutual TALK pair, messages ordered [source, target].

    The Runtime emits exactly one utterance per Agent per tick, so each dialogue
    carries at most two messages. ``message_order`` is the position in the pair
    as returned by ``resolve_talk_conflicts`` — a stable order, not real
    turn-taking, which the Runtime does not model.
    """
    results_by_agent: dict[UUID, AgentRuntimeResult] = {
        result.agent_id: result for result in resolution.runtime_results
    }
    drafts: list[DialogueDraft] = []
    for source_id, target_id in resolution.mutual_pairs:
        messages = tuple(
            DialogueMessageDraft(
                order=order,
                speaker_agent_id=agent_id,
                utterance=(
                    results_by_agent[agent_id].intent.utterance
                    if agent_id in results_by_agent
                    else None
                ),
            )
            for order, agent_id in enumerate((source_id, target_id))
        )
        result = results_by_agent.get(source_id) or results_by_agent.get(target_id)
        if result is None:
            continue
        drafts.append(
            DialogueDraft(
                run_id=result.run_id,
                tick_number=result.tick_number,
                participant_a_id=source_id,
                participant_b_id=target_id,
                messages=messages,
            )
        )
    return tuple(drafts)


class DialogueSink(Protocol):
    def save_batch(self, resolution: TalkConflictResolution) -> DialogueBatchSaveResult: ...


class InMemoryDialogueSink:
    def __init__(self) -> None:
        self._drafts: list[DialogueDraft] = []

    def save_batch(self, resolution: TalkConflictResolution) -> DialogueBatchSaveResult:
        drafts = build_dialogue_drafts(resolution)
        seen = {
            (draft.run_id, draft.tick_number, draft.participant_a_id, draft.participant_b_id)
            for draft in self._drafts
        }
        new_drafts = [
            draft
            for draft in drafts
            if (
                draft.run_id,
                draft.tick_number,
                draft.participant_a_id,
                draft.participant_b_id,
            )
            not in seen
        ]
        self._drafts.extend(new_drafts)
        return DialogueBatchSaveResult(
            new_count=len(new_drafts),
            duplicate_count=len(drafts) - len(new_drafts),
        )

    def list_drafts(self) -> Sequence[DialogueDraft]:
        return tuple(self._drafts)
