from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_user_role
from app.domain.models import User
from app.services.achievements import list_achievements

router = APIRouter(prefix="/achievements", tags=["achievements"])


@router.get("")
def achievements(db: Session = Depends(get_db), owner: User = Depends(require_user_role)) -> dict:
    return {"data": list_achievements(db, owner)}
