"""
NEXA Voice — LiveKit room registry and token minting.

The registry is intentionally in-memory: it only backs the "list active
sessions" API in the API process. The voice worker is a separate process and
does not rely on it — it resolves context from the room name/metadata (see
voice/context.py). For multi-instance API deployments, move this registry to
Redis.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from voice.context import VoiceRoomContext

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

    @classmethod
    def from_context(cls, room_name: str, context: VoiceRoomContext) -> "RoomInfo":
        return cls(
            room_name=room_name,
            agent_id=context.agent_id,
            tenant_id=context.tenant_id,
            session_id=context.session_id,
            user_id=context.user_id,
        )


class RoomManager:
    """In-memory registry of active voice rooms (single API process)."""

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
        info = RoomInfo(
            room_name=room_name,
            agent_id=agent_id,
            tenant_id=tenant_id,
            session_id=session_id,
            user_id=user_id,
        )
        self._rooms[room_name] = info
        logger.info(
            "Room registered: %s (agent=%s, tenant=%s)", room_name, agent_id, tenant_id
        )
        return info

    def get_room(self, room_name: str) -> Optional[RoomInfo]:
        return self._rooms.get(room_name)

    def remove_room(self, room_name: str) -> None:
        if room_name in self._rooms:
            del self._rooms[room_name]
            logger.info("Room removed: %s", room_name)

    def list_rooms(self) -> list[RoomInfo]:
        return list(self._rooms.values())

    def tenant_rooms(self, tenant_id: int) -> list[RoomInfo]:
        return [r for r in self._rooms.values() if r.tenant_id == tenant_id]


def generate_livekit_token(
    room_name: str,
    participant_identity: str,
    participant_name: str = "user",
    ttl_seconds: int = 3600,
) -> str:
    """
    Generate a LiveKit access token for a client to join a room.

    Reads LIVEKIT_API_KEY and LIVEKIT_API_SECRET from the environment.
    """
    try:
        from livekit.api import AccessToken, VideoGrants
    except ImportError as exc:
        raise RuntimeError(
            "livekit-api is not installed. Run: pip install livekit-api"
        ) from exc

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

    return (
        AccessToken(api_key, api_secret)
        .with_identity(participant_identity)
        .with_name(participant_name)
        .with_grants(grants)
        .with_ttl(timedelta(seconds=ttl_seconds))
        .to_jwt()
    )


_room_manager: Optional[RoomManager] = None


def get_room_manager() -> RoomManager:
    """Returns the shared room manager instance."""
    global _room_manager
    if _room_manager is None:
        _room_manager = RoomManager()
    return _room_manager
