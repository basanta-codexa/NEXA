"""
NEXA Voice — LiveKit Room Manager
Manages the mapping of LiveKit rooms to NEXA agents + tenants.
Generates LiveKit access tokens for clients.
"""
from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RoomInfo:
    """Metadata for an active LiveKit voice session."""
    room_name: str
    agent_id: int
    tenant_id: int
    session_id: str
    user_id: Optional[int] = None
    created_at: float = field(default_factory=time.time)


class RoomManager:
    """
    In-memory registry of active voice rooms.
    Maps room_name → RoomInfo.

    In a production multi-node deployment, this would be backed by Redis.
    For self-hosted single-node NEXA, in-memory is sufficient.
    """

    def __init__(self):
        self._rooms: dict[str, RoomInfo] = {}

    def register_room(
        self,
        room_name: str,
        agent_id: int,
        tenant_id: int,
        session_id: str,
        user_id: Optional[int] = None,
    ) -> RoomInfo:
        """Register a new voice room session."""
        info = RoomInfo(
            room_name=room_name,
            agent_id=agent_id,
            tenant_id=tenant_id,
            session_id=session_id,
            user_id=user_id,
        )
        self._rooms[room_name] = info
        logger.info(f"Room registered: {room_name} (agent={agent_id}, tenant={tenant_id})")
        return info

    def get_room(self, room_name: str) -> Optional[RoomInfo]:
        """Retrieve room info by room name."""
        return self._rooms.get(room_name)

    def remove_room(self, room_name: str) -> None:
        """Remove a room when the session ends."""
        if room_name in self._rooms:
            del self._rooms[room_name]
            logger.info(f"Room removed: {room_name}")

    def list_rooms(self) -> list[RoomInfo]:
        """List all currently active rooms."""
        return list(self._rooms.values())

    def tenant_rooms(self, tenant_id: int) -> list[RoomInfo]:
        """List rooms for a specific tenant."""
        return [r for r in self._rooms.values() if r.tenant_id == tenant_id]


def generate_livekit_token(
    room_name: str,
    participant_identity: str,
    participant_name: str = "user",
    ttl_seconds: int = 3600,
) -> str:
    """
    Generate a LiveKit access token for a client to join a room.

    Reads LIVEKIT_API_KEY and LIVEKIT_API_SECRET from environment.

    Args:
        room_name: The LiveKit room to join.
        participant_identity: Unique identity string for this participant.
        participant_name: Display name for the participant.
        ttl_seconds: Token validity duration in seconds (default 1 hour).

    Returns:
        Signed JWT access token string.

    Raises:
        RuntimeError: If livekit-api is not installed or env vars are missing.
    """
    try:
        from livekit.api import AccessToken, VideoGrants
    except ImportError:
        raise RuntimeError(
            "livekit-api is not installed. Run: pip install livekit-api"
        )

    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not api_key or not api_secret:
        raise RuntimeError(
            "LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in .env"
        )

    grants = VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True,
    )

    token = (
        AccessToken(api_key, api_secret)
        .with_identity(participant_identity)
        .with_name(participant_name)
        .with_grants(grants)
        .with_ttl(ttl_seconds)
        .to_jwt()
    )

    return token


# Module-level singleton
_room_manager: Optional[RoomManager] = None


def get_room_manager() -> RoomManager:
    """Returns the shared room manager instance."""
    global _room_manager
    if _room_manager is None:
        _room_manager = RoomManager()
    return _room_manager
