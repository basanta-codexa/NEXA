"""
NEXA Voice — one conversational turn.

STT -> agent engine (LLM + tools + memory + RAG) -> TTS.

This module is synchronous and database-aware; the worker runs it in a
thread pool so the LiveKit event loop stays responsive.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from voice.context import VoiceRoomContext

logger = logging.getLogger(__name__)


@dataclass
class VoiceTurnResult:
    transcript: str
    response_text: str
    wav_bytes: bytes


def run_voice_turn(
    pcm_bytes: bytes,
    sample_rate: int,
    context: VoiceRoomContext,
) -> VoiceTurnResult | None:
    """Run one full turn. Returns None when no speech was transcribed."""
    from database import SessionLocal
    from services.agent_service import run_agent_engine_service
    from voice.stt import get_stt
    from voice.tts import get_tts

    transcript = get_stt().transcribe_bytes(pcm_bytes, sample_rate=sample_rate)
    if not transcript:
        logger.debug("STT returned an empty transcript — skipping turn.")
        return None

    logger.info("[Voice] transcript=%r", transcript)

    db = SessionLocal()
    try:
        result = run_agent_engine_service(
            db=db,
            agent_id=context.agent_id,
            tenant_id=context.tenant_id,
            user_message=transcript,
            session_id=context.session_id,
            user_id=context.user_id,
        )
    finally:
        db.close()

    if not result or "error" in result:
        error = (result or {}).get("error", "Agent not found")
        logger.error("[Voice] AgentEngine error: %s", error)
        response_text = "Sorry, I ran into a problem. Please try again."
    else:
        response_text = result.get("response", "")

    if not response_text:
        return None

    logger.info("[Voice] response=%r", response_text[:160])

    return VoiceTurnResult(
        transcript=transcript,
        response_text=response_text,
        wav_bytes=get_tts().synthesize(response_text),
    )
