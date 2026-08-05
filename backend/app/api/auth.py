from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.core.database import get_db
from app.services.auth import login_user, register_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)) -> UserResponse:
    return UserResponse.model_validate(register_user(db, request))


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    token, user = login_user(db, request)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))
