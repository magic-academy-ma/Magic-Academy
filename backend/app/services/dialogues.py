from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.models import Dialogue, DialogueMessage
from app.repositories import dialogues as dialogue_repository


class DialogueNotFoundError(LookupError):
    pass


def get_dialogue(
    db: Session, simulation_id: UUID, dialogue_id: UUID
) -> tuple[Dialogue, list[DialogueMessage]]:
    """Fetch a dialogue scoped to its simulation.

    A dialogue that belongs to another simulation is reported as missing so
    callers cannot probe for dialogues outside the simulation they own.
    """
    dialogue = dialogue_repository.get_scoped_dialogue(db, simulation_id, dialogue_id)
    if dialogue is None:
        raise DialogueNotFoundError(str(dialogue_id))
    messages = dialogue_repository.list_messages(db, dialogue.id)
    return dialogue, messages
