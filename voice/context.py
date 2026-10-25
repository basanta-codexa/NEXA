"""
Shared voice-session context.

The API process and the LiveKit worker are separate processes, so room
context must travel with the room itself. We encode it in the room name
(universally supported) and also support room metadata as a forward-compatible
carrier.

Room name format: ``nexa-{tenant_id}-{agent_id}-{session_id}``
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Optional

ROOM_PREFIX = "nexa"
MAX_SESSION_ID_LENGTH = 64
_SAFE_SESSION_CHARS = re.compile(r"[^A-Za-z0-9_.-]")


@dataclass(frozen=True)
class VoiceRoomContext:
    tenant_id: int
    agent_id: int
    session_id: str
    user_id: Optional[int] = None

    def to_metadata(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_metadata(cls, raw_metadata: str | None) -> "VoiceRoomContext | None":
        if not raw_metadata:
            return None
        try:
            data: Any = json.loads(raw_metadata)
            return cls(
                tenant_id=int(data["tenant_id"]),
                agent_id=int(data["agent_id"]),
                session_id=normalize_session_id(str(data["session_id"])),
                user_id=int(data["user_id"]) if data.get("user_id") is not None else None,
            )
        except (TypeError, ValueError, KeyError):
            return None


def normalize_session_id(session_id: str | None) -> str:
    """Return a URL/room-name-safe session id, generating one when needed."""
    if not session_id:
        return uuid.uuid4().hex

    cleaned = _SAFE_SESSION_CHARS.sub("-", str(session_id).strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-._")[:MAX_SESSION_ID_LENGTH]

    return cleaned or uuid.uuid4().hex


def build_room_name(tenant_id: int, agent_id: int, session_id: str) -> str:
    return f"{ROOM_PREFIX}-{int(tenant_id)}-{int(agent_id)}-{normalize_session_id(session_id)}"


def parse_room_name(room_name: str) -> VoiceRoomContext | None:
    if not room_name or not room_name.startswith(f"{ROOM_PREFIX}-"):
        return None

    parts = room_name.split("-", 3)
    if len(parts) != 4:
        return None

    _, raw_tenant, raw_agent, raw_session = parts
    try:
        return VoiceRoomContext(
            tenant_id=int(raw_tenant),
            agent_id=int(raw_agent),
            session_id=normalize_session_id(raw_session),
        )
    except (TypeError, ValueError):
        return None


def resolve_room_context(
    room_name: str,
    room_metadata: str | None = None,
) -> VoiceRoomContext | None:
    """Prefer explicit metadata, fall back to the room-name encoding."""
    return VoiceRoomContext.from_metadata(room_metadata) or parse_room_name(room_name)
