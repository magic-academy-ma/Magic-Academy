from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.domain.models import Agent
from app.repositories import dialogues as dialogue_repository
from app.services.dialogue_results import (
    DialogueBatchSaveResult,
    DialogueDraft,
    build_dialogue_drafts,
)
from app.simulation.intent_conflict import TalkConflictResolution


class DialogueParticipantError(ValueError):
    pass


class DatabaseDialogueSink:
    """Persist mutual TALK dialogues without owning commit or rollback."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save_batch(self, resolution: TalkConflictResolution) -> DialogueBatchSaveResult:
        drafts = build_dialogue_drafts(resolution)
        if not drafts:
            return DialogueBatchSaveResult(new_count=0, duplicate_count=0)

        simulation_id = self._resolve_simulation_id(drafts)
        dialogue_ids = {draft: uuid7() for draft in drafts}
        dialogue_rows = [
            {
                "id": dialogue_ids[draft],
                "simulation_id": simulation_id,
                "run_id": draft.run_id,
                "tick_number": draft.tick_number,
                "participant_a_id": draft.participant_a_id,
                "participant_b_id": draft.participant_b_id,
            }
            for draft in drafts
        ]
        inserted_ids = dialogue_repository.insert_dialogues_on_pair_conflict_do_nothing(
            self._session, dialogue_rows
        )
        message_rows = [
            {
                "id": uuid7(),
                "dialogue_id": dialogue_ids[draft],
                "message_order": message.order,
                "speaker_agent_id": message.speaker_agent_id,
                "utterance": message.utterance,
            }
            for draft in drafts
            if dialogue_ids[draft] in inserted_ids
            for message in draft.messages
        ]
        dialogue_repository.insert_messages(self._session, message_rows)
        return DialogueBatchSaveResult(
            new_count=len(inserted_ids),
            duplicate_count=len(drafts) - len(inserted_ids),
        )

    def _resolve_simulation_id(self, drafts: tuple[DialogueDraft, ...]) -> UUID:
        participant_ids = {
            participant_id
            for draft in drafts
            for participant_id in draft.participant_ids
        }
        rows = self._session.execute(
            select(Agent.id, Agent.simulation_id).where(Agent.id.in_(participant_ids))
        ).all()
        if {agent_id for agent_id, _ in rows} != participant_ids:
            raise DialogueParticipantError("dialogue participant Agent is missing")
        simulation_ids = {simulation_id for _, simulation_id in rows}
        if len(simulation_ids) != 1:
            raise DialogueParticipantError(
                "dialogue participants span multiple simulations"
            )
        return simulation_ids.pop()
