from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import ShareImport


def get_by_identity(db: Session, request_user_id: UUID, idempotency_key: str) -> ShareImport | None:
    return db.scalar(
        select(ShareImport).where(
            ShareImport.request_user_id == request_user_id,
            ShareImport.idempotency_key == idempotency_key,
        )
    )
