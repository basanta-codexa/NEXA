"""
NEXA Voice — one conversational turn.

STT -> agent engine (LLM + tools + memory + RAG) -> TTS.

This module is synchronous and database-aware; the worker runs it in a
thread pool so the LiveKit event loop stays responsive.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
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

    started_at = time.perf_counter()

    transcript = get_stt().transcribe_bytes(pcm_bytes, sample_rate=sample_rate)
    stt_ms = round((time.perf_counter() - started_at) * 1000, 1)
    if not transcript:
        logger.info("[Voice] turn timings stt_ms=%s (empty transcript)", stt_ms)
        return None

    logger.info("[Voice] transcript=%r", transcript)

    agent_started_at = time.perf_counter()
    db = SessionLocal()
    try:
        result = run_agent_engine_service(
            db=db,
            agent_id=context.agent_id,
            tenant_id=context.tenant_id,
            user_message=transcript,
            session_id=context.session_id,
            user_id=context.user_id,
            voice_mode=True,
        )
    finally:
        db.close()
    agent_ms = round((time.perf_counter() - agent_started_at) * 1000, 1)

    if not result or "error" in result:
        error = (result or {}).get("error", "Agent not found")
        logger.error("[Voice] AgentEngine error: %s", error)
        response_text = "Sorry, I ran into a problem. Please try again."
    else:
        response_text = result.get("response", "")

    if not response_text:
        logger.info(
            "[Voice] turn timings stt_ms=%s agent_ms=%s (empty response)",
            stt_ms,
            agent_ms,
        )
        return None

    logger.info("[Voice] response=%r", response_text[:160])

    tts_started_at = time.perf_counter()
    wav_bytes = get_tts().synthesize(response_text)
    tts_ms = round((time.perf_counter() - tts_started_at) * 1000, 1)

    logger.info(
        "[Voice] turn timings stt_ms=%s agent_ms=%s tts_ms=%s total_ms=%s "
        "transcript_chars=%d response_chars=%d",
        stt_ms,
        agent_ms,
        tts_ms,
        round((time.perf_counter() - started_at) * 1000, 1),
        len(transcript),
        len(response_text),
    )

    return VoiceTurnResult(
        transcript=transcript,
        response_text=response_text,
        wav_bytes=wav_bytes,
    )


async def run_voice_turn_stream(
    pcm_bytes: bytes,
    sample_rate: int,
    context: VoiceRoomContext,
) -> AsyncIterator[tuple[bytes, int]]:
    """Yield (PCM, sample_rate) as soon as each sentence has been synthesized.

    Time-to-first-audio is STT + first sentence + first TTS chunk, rather than
    the whole STT -> RAG -> LLM -> TTS chain.
    """
    from database import SessionLocal
    from services.agent_service import stream_agent_engine_service
    from voice.stt import get_stt
    from voice.tts import get_tts

    started_at = time.perf_counter()
    transcript = await asyncio.to_thread(
        get_stt().transcribe_bytes, pcm_bytes, sample_rate=sample_rate
    )
    stt_ms = round((time.perf_counter() - started_at) * 1000, 1)
    if not transcript:
        logger.info("[Voice] streamed turn: empty transcript (stt_ms=%s)", stt_ms)
        return

    logger.info("[Voice] transcript=%r", transcript)

    db = SessionLocal()
    events = stream_agent_engine_service(
        db=db,
        agent_id=context.agent_id,
        tenant_id=context.tenant_id,
        user_message=transcript,
        session_id=context.session_id,
        user_id=context.user_id,
        voice_mode=True,
    )

    final_result: dict | None = None
    response_parts: list[str] = []
    error_text: str | None = None
    first_token_ms: float | None = None
    stt_finished_at = time.perf_counter()

    async def text_deltas() -> AsyncIterator[str]:
        nonlocal final_result, error_text, first_token_ms
        while True:
            try:
                event = await asyncio.to_thread(next, events)
            except StopIteration:
                return
            if event["type"] == "text":
                if first_token_ms is None:
                    first_token_ms = round(
                        (time.perf_counter() - stt_finished_at) * 1000, 1
                    )
                response_parts.append(event["content"])
                yield event["content"]
            elif event["type"] == "error":
                error_text = event.get("error", "Agent error")
                logger.error("[Voice] streamed agent error: %s", error_text)
                return
            elif event["type"] == "done":
                final_result = event["result"]
                return

    tts = get_tts()
    try:
        async for pcm, rate in tts.synthesize_stream_async(text_deltas()):
            yield pcm, rate
    finally:
        db.close()

    response_text = (final_result or {}).get("response", "".join(response_parts))
    if error_text or not response_text:
        logger.error(
            "[Voice] streamed turn produced no answer: %s",
            error_text or "empty response",
        )

        async def fallback_text() -> AsyncIterator[str]:
            yield "Sorry, I ran into a problem. Please try again."

        async for pcm, rate in tts.synthesize_stream_async(fallback_text()):
            yield pcm, rate
        return

    logger.info(
        "[Voice] streamed turn timings stt_ms=%s llm_first_token_ms=%s "
        "total_ms=%s response_chars=%d",
        stt_ms,
        first_token_ms,
        round((time.perf_counter() - started_at) * 1000, 1),
        len(response_text),
    )
