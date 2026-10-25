"""
NEXA Voice Router — REST API for voice session management.

Endpoints:
    POST   /agents/{agent_id}/voice/session   — Start a voice session
    GET    /agents/{agent_id}/voice/sessions  — List active voice sessions
    DELETE /agents/{agent_id}/voice/session/{room_name} — End a voice session
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from dependencies.permissions import Permissions
from dependencies.roles import require_permission
from dependencies.tenant import get_current_tenant_id
from services.voice_service import (
    create_voice_session_service,
    list_voice_sessions_service,
    end_voice_session_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/agents",
    tags=["Voice"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────

class VoiceSessionRequest(BaseModel):
    session_id: Optional[str] = None


class VoiceSessionResponse(BaseModel):
    room_name: str
    token: str
    livekit_url: str
    session_id: str
    agent_name: str
    agent_id: int


class VoiceSessionInfo(BaseModel):
    room_name: str
    agent_id: int
    session_id: str
    user_id: Optional[int] = None
    created_at: float


class VoiceSessionListResponse(BaseModel):
    sessions: list[VoiceSessionInfo]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/{agent_id}/voice/session",
    response_model=VoiceSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a voice session",
    description=(
        "Creates a LiveKit room for real-time voice interaction with an agent. "
        "Returns a signed access token for the client to join the LiveKit room. "
        "The client connects using the LiveKit JS/Mobile SDK with this token. "
        "Agent must be in ACTIVE status."
    ),
)
def start_voice_session(
    agent_id: int,
    body: VoiceSessionRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_permission(Permissions.AGENT_READ)),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """
    Start a real-time voice session with a NEXA agent.

    The returned `token` should be passed to the LiveKit client SDK:
    ```js
    const room = new Room();
    await room.connect(livekit_url, token);
    ```
    """
    try:
        result = create_voice_session_service(
            db=db,
            agent_id=agent_id,
            tenant_id=tenant_id,
            user_id=current_user.id if current_user else None,
            session_id=body.session_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Voice service unavailable: {str(e)}",
        )

    return VoiceSessionResponse(**result)


@router.get(
    "/{agent_id}/voice/sessions",
    response_model=VoiceSessionListResponse,
    summary="List active voice sessions",
    description="Returns all currently active voice sessions for this tenant.",
)
def list_voice_sessions(
    agent_id: int,
    tenant_id: int = Depends(get_current_tenant_id),
    current_user=Depends(require_permission(Permissions.AGENT_READ)),
):
    sessions = list_voice_sessions_service(tenant_id=tenant_id)
    # Filter to only this agent's sessions
    agent_sessions = [s for s in sessions if s["agent_id"] == agent_id]
    return VoiceSessionListResponse(sessions=agent_sessions)


@router.delete(
    "/{agent_id}/voice/session/{room_name}",
    status_code=status.HTTP_200_OK,
    summary="End a voice session",
    description="Ends a voice session and removes it from the active session registry.",
)
def end_voice_session(
    agent_id: int,
    room_name: str,
    tenant_id: int = Depends(get_current_tenant_id),
    current_user=Depends(require_permission(Permissions.AGENT_READ)),
):
    try:
        removed = end_voice_session_service(
            room_name=room_name,
            tenant_id=tenant_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voice session '{room_name}' not found.",
        )

    return {"message": f"Voice session '{room_name}' ended successfully."}
