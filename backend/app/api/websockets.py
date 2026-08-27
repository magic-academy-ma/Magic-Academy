import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import authenticate_access_token
from app.services.realtime_events import connection_manager
from app.services.simulations import require_owned_simulation


class AuthenticationFrame(BaseModel):
    type: str
    token: str


router = APIRouter(tags=["websocket"])


@router.websocket("/ws/simulations/{simulation_id}")
async def simulation_events(
    websocket: WebSocket,
    simulation_id: UUID,
    db: Session = Depends(get_db),
) -> None:
    await websocket.accept()
    try:
        raw_frame = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        frame = AuthenticationFrame.model_validate(raw_frame)
        if frame.type != "AUTH":
            raise ValueError("first frame must be AUTH")
        user = authenticate_access_token(db, frame.token)
        require_owned_simulation(db, simulation_id, user)
    except (TimeoutError, ValidationError, ValueError):
        await websocket.close(code=1008, reason="Authentication failed")
        return
    except Exception:
        await websocket.close(code=1008, reason="Authentication failed")
        return

    connection_manager.connect(simulation_id, websocket)
    try:
        await websocket.send_json(
            {"type": "AUTHENTICATED", "data": {"simulation_id": str(simulation_id)}}
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connection_manager.disconnect(simulation_id, websocket)
