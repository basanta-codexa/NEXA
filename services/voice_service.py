"""
NEXA Voice Service — Business Logic
Handles creating LiveKit voice sessions for agents.
"""
from __future__ import annotations

import uuid
import logging
import os
from typing import Optional

from sqlalchemy.orm import Session
from models import Agent

logger = logging.getLogger(__name__)


def create_voice_session_service(
    db: Session,
    agent_id: int,
    tenant_id: int,
    user_id: Optional[int] = None,
    session_id: Optional[str] = None,
) -> dict:
    """
    Creates a LiveKit voice session for a NEXA agent.

    Steps:
    1. Validate the agent exists and belongs to the tenant.
    2. Generate a unique room name.
    3. Register the room in the RoomManager.
    4. Generate a LiveKit access token for the client.
    5. Return the room name, token, and LiveKit URL.

    Args:
        db: Database session.
        agent_id: ID of the NEXA agent to connect.
        tenant_id: Tenant making the request.
        user_id: Optional user ID for conversation tracking.
        session_id: Optional session ID (created if not provided).

    Returns:
        Dict with room_name, token, livekit_url, session_id.

    Raises:
        ValueError: If agent not found or not active.
        RuntimeError: If LiveKit credentials are missing.
    """
    from voice.room_manager import get_room_manager, generate_livekit_token

    # 1. Validate agent
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.tenant_id == tenant_id,
    ).first()

    if agent is None:
        raise ValueError(f"Agent {agent_id} not found for tenant {tenant_id}.")

    if agent.status.value != "active":
        raise ValueError(
            f"Agent '{agent.name}' is not active (status={agent.status.value}). "
            "Activate the agent before starting a voice session."
        )

    # 2. Generate room name + session ID
    if not session_id:
        session_id = str(uuid.uuid4())

    room_name = f"nexa-{tenant_id}-{agent_id}-{session_id[:8]}"

    # 3. Register room
    room_manager = get_room_manager()
    room_manager.register_room(
        room_name=room_name,
        agent_id=agent_id,
        tenant_id=tenant_id,
        session_id=session_id,
        user_id=user_id,
    )

    # 4. Generate LiveKit token for client
    participant_identity = f"user-{user_id or 'anon'}-{session_id[:6]}"
    token = generate_livekit_token(
        room_name=room_name,
        participant_identity=participant_identity,
        participant_name=f"User ({agent.name})",
    )

    livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")

    logger.info(
        f"Voice session created: room={room_name}, agent={agent.name}, "
        f"tenant={tenant_id}, session={session_id}"
    )

    return {
        "room_name": room_name,
        "token": token,
        "livekit_url": livekit_url,
        "session_id": session_id,
        "agent_name": agent.name,
        "agent_id": agent_id,
    }


def list_voice_sessions_service(tenant_id: int) -> list[dict]:
    """
    List active voice sessions for a tenant.

    Args:
        tenant_id: The tenant to list sessions for.

    Returns:
        List of active room info dicts.
    """
    from voice.room_manager import get_room_manager

    room_manager = get_room_manager()
    rooms = room_manager.tenant_rooms(tenant_id)

    return [
        {
            "room_name": r.room_name,
            "agent_id": r.agent_id,
            "session_id": r.session_id,
            "user_id": r.user_id,
            "created_at": r.created_at,
        }
        for r in rooms
    ]


def end_voice_session_service(room_name: str, tenant_id: int) -> bool:
    """
    Ends a voice session by removing it from the room registry.

    Args:
        room_name: The room to end.
        tenant_id: Tenant making the request (for isolation validation).

    Returns:
        True if removed, False if not found.
    """
    from voice.room_manager import get_room_manager

    room_manager = get_room_manager()
    room_info = room_manager.get_room(room_name)

    if room_info is None:
        return False

    if room_info.tenant_id != tenant_id:
        raise ValueError("Room does not belong to this tenant.")

    room_manager.remove_room(room_name)
    return True
