from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import DialogueDetailResponse, DialogueMessageResponse
from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import User
from app.services.dialogues import DialogueNotFoundError, get_dialogue
from app.services.simulations import require_owned_simulation

router = APIRouter(prefix="/simulations/{simulation_id}/dialogues", tags=["dialogues"])


@router.get("/{dialogue_id}", response_model=DialogueDetailResponse)
def get_one(
    simulation_id: UUID,
    dialogue_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_role),
) -> DialogueDetailResponse:
    require_owned_simulation(db, simulation_id, current_user)
    try:
        dialogue, messages = get_dialogue(db, simulation_id, dialogue_id)
    except DialogueNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dialogue not found"
        ) from exc
    return DialogueDetailResponse(
        dialogue_id=dialogue.id,
        simulation_id=dialogue.simulation_id,
        tick=dialogue.tick_number,
        participants=[dialogue.participant_a_id, dialogue.participant_b_id],
        messages=[
            DialogueMessageResponse(
                speaker=message.speaker_agent_id,
                utterance=message.utterance,
                order=message.message_order,
            )
            for message in messages
        ],
    )
