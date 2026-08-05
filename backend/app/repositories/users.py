from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import User


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))
