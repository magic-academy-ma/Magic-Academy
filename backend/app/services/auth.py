from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.api.schemas import LoginRequest, RegisterRequest
from app.core.security import create_access_token, hash_password, verify_password
from app.domain.models import User
from app.repositories.users import get_user_by_username


def normalize_username(username: str) -> str:
    return username.strip().lower()


def register_user(db: Session, request: RegisterRequest) -> User:
    username = normalize_username(request.username)
    if get_user_by_username(db, username) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    user = User(
        id=uuid7(),
        username=username,
        display_name=request.display_name.strip(),
        password_hash=hash_password(request.password),
        roles=["USER"],
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists") from None
    db.refresh(user)
    return user


def login_user(db: Session, request: LoginRequest) -> tuple[str, User]:
    user = get_user_by_username(db, normalize_username(request.username))
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return create_access_token(user), user
