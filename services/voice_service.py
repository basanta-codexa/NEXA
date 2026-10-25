"""
NEXA Voice Service — Business Logic
Handles creating LiveKit voice sessions for agents.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from sqlalchemy.orm import Session

from models import Agent
from voice.context import build_room_name, normalize_session_id

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
    1. Validate the agent exists, belongs to the tenant, and is ACTIVE.
    2. Normalize the session id and build a self-describing room name.
    3. Register the room in the API-process registry (for listing).
    4. Mint a LiveKit access token for the client.
    """
    from voice.room_manager import get_room_manager, generate_livekit_token

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

    session_id = normalize_session_id(session_id)
    room_name = build_room_name(tenant_id, agent_id, session_id)

    room_manager = get_room_manager()
    room_manager.register_room(
        room_name=room_name,
        agent_id=agent_id,
        tenant_id=tenant_id,
        session_id=session_id,
        user_id=user_id,
    )

    participant_identity = f"user-{user_id or 'anon'}-{session_id[:6]}"
    token = generate_livekit_token(
        room_name=room_name,
        participant_identity=participant_identity,
        participant_name=f"User ({agent.name})",
        ttl_seconds=int(os.getenv("LIVEKIT_TOKEN_TTL_SECONDS", "3600")),
    )

    livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")

    logger.info(
        "Voice session created: room=%s, agent=%s, tenant=%s, session=%s",
        room_name,
        agent.name,
        tenant_id,
        session_id,
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
    """List active voice sessions for a tenant."""
    from voice.room_manager import get_room_manager

    rooms = get_room_manager().tenant_rooms(tenant_id)

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
    """Remove a session from the registry, enforcing tenant ownership."""
    from voice.room_manager import get_room_manager

    room_manager = get_room_manager()
    room_info = room_manager.get_room(room_name)

    if room_info is None:
        return False

    if room_info.tenant_id != tenant_id:
        raise ValueError("Room does not belong to this tenant.")

    room_manager.remove_room(room_name)
    return True
