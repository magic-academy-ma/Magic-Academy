from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.models import Dialogue, DialogueMessage


def get_scoped_dialogue(
    session: Session,
    simulation_id: UUID,
    dialogue_id: UUID,
) -> Dialogue | None:
    return session.scalar(
        select(Dialogue).where(
            Dialogue.id == dialogue_id,
            Dialogue.simulation_id == simulation_id,
        )
    )


def list_messages(session: Session, dialogue_id: UUID) -> list[DialogueMessage]:
    return list(
        session.scalars(
            select(DialogueMessage)
            .where(DialogueMessage.dialogue_id == dialogue_id)
            .order_by(DialogueMessage.message_order)
        ).all()
    )


def insert_dialogues_on_pair_conflict_do_nothing(
    session: Session,
    rows: Sequence[dict[str, Any]],
) -> set[UUID]:
    if not rows:
        return set()
    statement = (
        insert(Dialogue)
        .values(list(rows))
        .on_conflict_do_nothing(constraint="uq_dialogues_pair_per_tick")
        .returning(Dialogue.id)
    )
    return set(session.scalars(statement).all())


def insert_messages(session: Session, rows: Sequence[dict[str, Any]]) -> None:
    if not rows:
        return
    session.execute(insert(DialogueMessage).values(list(rows)))
