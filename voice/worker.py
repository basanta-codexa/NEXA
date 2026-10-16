"""
NEXA Voice — LiveKit Agent Worker
The voice pipeline: LiveKit room → STT → AgentEngine → TTS → LiveKit room.

This file is run as a standalone process (not imported by FastAPI):
    python -m voice.worker

Architecture:
    1. Worker connects to LiveKit server and watches for participants joining rooms.
    2. When a participant joins a room that has a registered NEXA agent:
       a. Audio frames are collected until Voice Activity Detection (VAD) detects silence.
       b. Collected frames → STT (faster-whisper) → transcript.
       c. Transcript → AgentEngine.run() → LLM response text.
       d. Response text → TTS (piper) → WAV audio bytes.
       e. WAV bytes → published back to the LiveKit room.
    3. The conversation history is preserved per session_id.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Lazy imports — only loaded when worker actually runs
# ─────────────────────────────────────────────────────────────────────────────

def _require_livekit_agents():
    try:
        import livekit.agents
        import livekit.agents.llm
        import livekit.agents.stt
        import livekit.agents.tts
        import livekit.agents.vad
        import livekit.agents.pipeline
        return True
    except ImportError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# NEXA Voice Pipeline using livekit-agents
# ─────────────────────────────────────────────────────────────────────────────

class NexaVoiceAgent:
    """
    A voice agent session for a single LiveKit room.
    Handles the full STT → LLM → TTS pipeline.
    """

    def __init__(
        self,
        agent_id: int,
        tenant_id: int,
        session_id: str,
        user_id: int | None = None,
    ):
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.user_id = user_id

    async def process_audio_and_respond(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        db_session_factory,
    ) -> bytes | None:
        """
        Full pipeline: audio bytes → transcript → LLM → audio response.

        Args:
            audio_bytes: Raw PCM audio bytes from LiveKit.
            sample_rate: Audio sample rate.
            db_session_factory: SQLAlchemy session factory (from FastAPI dependency).

        Returns:
            WAV audio bytes for the TTS response, or None if no transcript.
        """
        from voice.stt import get_stt
        from voice.tts import get_tts
        from services.agent_service import run_agent_engine_service

        # 1. STT — transcribe audio
        stt = get_stt()
        transcript = stt.transcribe_bytes(audio_bytes, sample_rate=sample_rate)

        if not transcript:
            logger.debug("STT returned empty transcript — skipping.")
            return None

        logger.info(f"[Voice] Transcript: '{transcript}'")

        # 2. AgentEngine — get LLM response
        with db_session_factory() as db:
            result = run_agent_engine_service(
                db=db,
                agent_id=self.agent_id,
                tenant_id=self.tenant_id,
                user_message=transcript,
                session_id=self.session_id,
                user_id=self.user_id,
            )

        if not result or "error" in result:
            error = result.get("error", "Unknown error") if result else "Agent not found"
            logger.error(f"[Voice] AgentEngine error: {error}")
            response_text = "Sorry, I encountered an error. Please try again."
        else:
            response_text = result.get("response", "")

        if not response_text:
            return None

        logger.info(f"[Voice] Response: '{response_text[:100]}...'")

        # 3. TTS — synthesize response
        tts = get_tts()
        wav_bytes = tts.synthesize(response_text)

        return wav_bytes


# ─────────────────────────────────────────────────────────────────────────────
# LiveKit Agents Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

async def entrypoint(ctx):
    """
    LiveKit Agents entrypoint — called when a participant joins a room.
    
    The room name encodes the agent context: "nexa-{agent_id}-{tenant_id}-{session_id}"
    """
    from livekit import rtc
    from livekit.agents import JobContext
    from voice.room_manager import get_room_manager
    from voice.stt import get_stt
    from voice.tts import get_tts
    from database import SessionLocal

    room: rtc.Room = ctx.room
    room_name = room.name

    logger.info(f"[Worker] Connected to room: {room_name}")

    # Look up NEXA agent context from room registry
    room_manager = get_room_manager()
    room_info = room_manager.get_room(room_name)

    if room_info is None:
        logger.error(f"[Worker] No room info found for '{room_name}' — disconnecting.")
        await ctx.disconnect()
        return

    voice_agent = NexaVoiceAgent(
        agent_id=room_info.agent_id,
        tenant_id=room_info.tenant_id,
        session_id=room_info.session_id,
        user_id=room_info.user_id,
    )

    # Collect audio frames per participant
    audio_buffers: dict[str, list[bytes]] = {}
    SAMPLE_RATE = 16000

    @room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"[Worker] Subscribed to audio from: {participant.identity}")
            asyncio.ensure_future(_handle_audio_track(track, participant.identity))

    async def _handle_audio_track(track, participant_identity: str):
        """Stream audio frames from a participant and process when VAD detects speech end."""
        from livekit.agents.vad import VAD, VADEventType

        audio_stream = rtc.AudioStream(track)
        vad = VAD.load()
        stream = vad.stream()

        # Feed audio frames to VAD
        async def feed_audio():
            async for frame_event in audio_stream:
                stream.push_frame(frame_event.frame)
            await stream.aclose()

        asyncio.ensure_future(feed_audio())

        # Process VAD events
        async for event in stream:
            if event.type == VADEventType.END_OF_SPEECH:
                # Collect all frames from this speech segment
                frames = event.frames
                if not frames:
                    continue

                # Concatenate PCM bytes
                pcm_data = b"".join(
                    bytes(frame.data) for frame in frames
                )

                logger.info(f"[Worker] Speech detected ({len(pcm_data)} bytes) from {participant_identity}")

                # Run STT → LLM → TTS in thread pool (all blocking ops)
                try:
                    def _pipeline_sync(_pcm=pcm_data):
                        from voice.stt import get_stt
                        from voice.tts import get_tts
                        from services.agent_service import run_agent_engine_service

                        # STT
                        transcript = get_stt().transcribe_bytes(_pcm, sample_rate=SAMPLE_RATE)
                        if not transcript:
                            return None

                        logger.info(f"[Worker] Transcript: '{transcript}'")

                        # LLM
                        db = SessionLocal()
                        try:
                            result = run_agent_engine_service(
                                db=db,
                                agent_id=room_info.agent_id,
                                tenant_id=room_info.tenant_id,
                                user_message=transcript,
                                session_id=room_info.session_id,
                                user_id=room_info.user_id,
                            )
                        finally:
                            db.close()

                        if not result or "error" in result:
                            err = result.get("error", "Unknown") if result else "Agent not found"
                            logger.error(f"[Worker] AgentEngine error: {err}")
                            response_text = "Sorry, I encountered an error."
                        else:
                            response_text = result.get("response", "")

                        if not response_text:
                            return None

                        logger.info(f"[Worker] Response: '{response_text[:120]}'")

                        # TTS
                        return get_tts().synthesize(response_text)

                    wav_response = await asyncio.get_event_loop().run_in_executor(
                        None, _pipeline_sync
                    )
                except Exception as e:
                    logger.exception(f"[Worker] Pipeline error: {e}")
                    continue

                if wav_response:
                    await _publish_audio_response(wav_response)


    async def _publish_audio_response(wav_bytes: bytes):
        """Publish synthesized audio back to the LiveKit room."""
        import wave
        import io

        try:
            # Parse WAV header
            with io.BytesIO(wav_bytes) as buf:
                with wave.open(buf, "rb") as wf:
                    sample_rate = wf.getframerate()
                    num_channels = wf.getnchannels()
                    pcm_data = wf.readframes(wf.getnframes())

            # Create and publish audio source
            source = rtc.AudioSource(sample_rate, num_channels)
            track = rtc.LocalAudioTrack.create_audio_track("nexa-response", source)

            options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
            await room.local_participant.publish_track(track, options)

            # Push PCM frames (chunks of 960 samples @ 48kHz = 20ms)
            FRAMES_PER_CHUNK = int(sample_rate * 0.02)  # 20ms chunks
            bytes_per_sample = 2  # 16-bit PCM
            chunk_size = FRAMES_PER_CHUNK * num_channels * bytes_per_sample

            for i in range(0, len(pcm_data), chunk_size):
                chunk = pcm_data[i:i + chunk_size]
                if len(chunk) < chunk_size:
                    chunk = chunk.ljust(chunk_size, b"\x00")
                frame = rtc.AudioFrame(
                    data=chunk,
                    sample_rate=sample_rate,
                    num_channels=num_channels,
                    samples_per_channel=FRAMES_PER_CHUNK,
                )
                await source.capture_frame(frame)
                await asyncio.sleep(0.02)  # real-time pacing

            logger.info("[Worker] Audio response published.")

        except Exception as e:
            logger.exception(f"[Worker] Failed to publish audio: {e}")

    # Keep the worker alive until the room disconnects
    await ctx.wait_for_disconnect()
    room_manager.remove_room(room_name)
    logger.info(f"[Worker] Room '{room_name}' disconnected — session ended.")


# ─────────────────────────────────────────────────────────────────────────────
# Worker entrypoint (run as: python -m voice.worker)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv

    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )

    livekit_url = os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")

    if not api_key or not api_secret:
        logger.error("LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in .env")
        sys.exit(1)

    try:
        from livekit.agents import WorkerOptions, cli
    except ImportError:
        logger.error("livekit-agents not installed. Run: pip install 'livekit-agents[silero]'")
        sys.exit(1)

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=api_key,
            api_secret=api_secret,
            ws_url=livekit_url,
        )
    )
