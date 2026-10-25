"""
NEXA Voice — LiveKit Agent Worker

Pipeline:
    LiveKit room audio -> Silero VAD -> faster-whisper STT
    -> NEXA AgentEngine (LLM + tools + memory + RAG) -> Piper TTS
    -> LiveKit room audio

Run as a standalone process:
    python -m voice.worker dev        # or just: python -m voice.worker

Context is resolved from the room name (see voice/context.py) so the worker
works across processes and machines without shared memory.
"""
from __future__ import annotations

import asyncio
import contextlib
import io
import logging
import os
import sys
import wave

logger = logging.getLogger("nexa.voice.worker")

VAD_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 48000
MIN_SPEECH_BYTES = VAD_SAMPLE_RATE * 2 * 0.15  # ignore <150ms blips


# ─────────────────────────────────────────────────────────────────────────────
# Audio output
# ─────────────────────────────────────────────────────────────────────────────

def _read_wav(wav_bytes: bytes) -> tuple[bytes, int, int]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
        if wav_file.getsampwidth() != 2:
            raise ValueError("Only 16-bit PCM WAV is supported.")
        return (
            wav_file.readframes(wav_file.getnframes()),
            wav_file.getframerate(),
            wav_file.getnchannels(),
        )


def _resample_pcm(pcm: bytes, source_rate: int, target_rate: int) -> bytes:
    if source_rate == target_rate:
        return pcm

    import numpy as np

    samples = np.frombuffer(pcm, dtype=np.int16)
    if samples.size == 0:
        return b""

    duration = samples.size / source_rate
    target_count = max(1, int(round(duration * target_rate)))
    source_positions = np.linspace(0.0, samples.size - 1, num=samples.size)
    target_positions = np.linspace(0.0, samples.size - 1, num=target_count)
    resampled = np.interp(target_positions, source_positions, samples.astype(np.float32))
    return np.clip(resampled, -32768, 32767).astype(np.int16).tobytes()


class AudioPublisher:
    """Publishes agent speech on a single reusable audio track."""

    def __init__(self, room):
        self.room = room
        self._source = None
        self._publication = None
        self._generation = 0
        self._lock = asyncio.Lock()

    async def _ensure_started(self) -> None:
        if self._source is not None:
            return

        from livekit import rtc

        self._source = rtc.AudioSource(
            OUTPUT_SAMPLE_RATE, 1, queue_size_ms=1000
        )
        track = rtc.LocalAudioTrack.create_audio_track("nexa-voice", self._source)
        self._publication = await self.room.local_participant.publish_track(
            track,
            rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
        )
        logger.info("[Voice] Published output audio track.")

    async def play(self, wav_bytes: bytes) -> None:
        """Play WAV bytes, interrupting any previous playback."""
        from livekit import rtc

        pcm, sample_rate, channels = _read_wav(wav_bytes)
        if channels != 1:
            raise ValueError("TTS output must be mono.")
        pcm = _resample_pcm(pcm, sample_rate, OUTPUT_SAMPLE_RATE)

        async with self._lock:
            await self._ensure_started()
            generation = self._generation

            samples_per_chunk = int(OUTPUT_SAMPLE_RATE * 0.02)  # 20ms
            chunk_size = samples_per_chunk * 2  # 16-bit mono

            for offset in range(0, len(pcm), chunk_size):
                if generation != self._generation:
                    logger.debug("[Voice] Playback interrupted.")
                    return

                chunk = pcm[offset:offset + chunk_size]
                if len(chunk) < chunk_size:
                    chunk = chunk.ljust(chunk_size, b"\x00")

                frame = rtc.AudioFrame(
                    data=chunk,
                    sample_rate=OUTPUT_SAMPLE_RATE,
                    num_channels=1,
                    samples_per_channel=samples_per_chunk,
                )
                await self._source.capture_frame(frame)

            await self._source.wait_for_playout()

    def interrupt(self) -> None:
        """Stop playback immediately (barge-in)."""
        if self._source is None:
            return
        self._generation += 1
        self._source.clear_queue()

    async def aclose(self) -> None:
        if self._source is not None:
            self._source.clear_queue()
        if self._publication is not None:
            with contextlib.suppress(Exception):
                await self.room.local_participant.unpublish_track(
                    self._publication.sid
                )


# ─────────────────────────────────────────────────────────────────────────────
# Per-participant listening loop
# ─────────────────────────────────────────────────────────────────────────────

async def _listen_to_participant(
    track,
    participant_identity: str,
    context,
    publisher: AudioPublisher,
) -> None:
    from livekit import rtc
    from livekit.agents.vad import VADEventType
    from livekit.plugins import silero

    from voice.pipeline import run_voice_turn

    vad = silero.VAD.load(
        min_silence_duration=float(os.getenv("VAD_MIN_SILENCE_SECONDS", "0.55")),
        activation_threshold=float(os.getenv("VAD_ACTIVATION_THRESHOLD", "0.5")),
    )
    vad_stream = vad.stream()
    audio_stream = rtc.AudioStream(
        track,
        sample_rate=VAD_SAMPLE_RATE,
        num_channels=1,
    )

    async def feed_vad() -> None:
        try:
            async for frame_event in audio_stream:
                vad_stream.push_frame(frame_event.frame)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("[Voice] Audio stream failed for %s", participant_identity)
        finally:
            vad_stream.end_input()

    feed_task = asyncio.create_task(feed_vad())

    try:
        async for event in vad_stream:
            if event.type == VADEventType.START_OF_SPEECH:
                publisher.interrupt()
                continue

            if event.type != VADEventType.END_OF_SPEECH:
                continue

            frames = event.frames or []
            pcm = b"".join(bytes(frame.data) for frame in frames)
            if len(pcm) < MIN_SPEECH_BYTES:
                continue

            logger.info("[Voice] Speech from %s (%.2fs)", participant_identity, len(pcm) / 2 / VAD_SAMPLE_RATE)

            try:
                result = await asyncio.to_thread(
                    run_voice_turn, pcm, VAD_SAMPLE_RATE, context
                )
            except Exception:
                logger.exception("[Voice] Turn failed for %s", participant_identity)
                continue

            if result is None:
                continue

            await publisher.play(result.wav_bytes)

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("[Voice] Listener crashed for %s", participant_identity)
    finally:
        feed_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await feed_task
        with contextlib.suppress(Exception):
            await vad_stream.aclose()
        with contextlib.suppress(Exception):
            await audio_stream.aclose()
        logger.info("[Voice] Stopped listening to %s", participant_identity)


# ─────────────────────────────────────────────────────────────────────────────
# LiveKit entrypoint
# ─────────────────────────────────────────────────────────────────────────────

async def entrypoint(ctx) -> None:
    from dataclasses import replace

    from livekit import rtc

    from voice.context import resolve_room_context
    from voice.room_manager import get_room_manager

    room = ctx.room
    await ctx.connect()
    logger.info("[Voice] Worker connected to room %s", room.name)

    context = resolve_room_context(room.name, room.metadata)
    if context is None:
        logger.error(
            "[Voice] Room '%s' has no NEXA context. Use POST /agents/{id}/voice/session.",
            room.name,
        )
        ctx.shutdown("missing_nexa_context")
        return

    # Same-process convenience: the API registry can carry user_id.
    room_info = get_room_manager().get_room(room.name)
    if room_info is not None and room_info.user_id is not None:
        context = replace(context, user_id=room_info.user_id)

    logger.info(
        "[Voice] Session agent=%s tenant=%s session=%s",
        context.agent_id,
        context.tenant_id,
        context.session_id,
    )

    publisher = AudioPublisher(room)
    listener_tasks: set[asyncio.Task] = set()
    handled_tracks: set[str] = set()

    def handle_track(track, participant_identity: str) -> None:
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return
        if track.sid in handled_tracks:
            return

        handled_tracks.add(track.sid)
        task = asyncio.create_task(
            _listen_to_participant(track, participant_identity, context, publisher)
        )
        listener_tasks.add(task)
        task.add_done_callback(listener_tasks.discard)
        logger.info("[Voice] Listening to %s", participant_identity)

    @room.on("track_subscribed")
    def on_track_subscribed(track, publication, participant):
        handle_track(track, participant.identity)

    # Handle tracks that were already subscribed before our handler registered.
    for participant in list(room.remote_participants.values()):
        for publication in list(participant.track_publications.values()):
            if publication.track is not None:
                handle_track(publication.track, participant.identity)

    shutdown_event = asyncio.Event()

    async def on_shutdown(*_args) -> None:
        shutdown_event.set()

    ctx.add_shutdown_callback(on_shutdown)
    await shutdown_event.wait()

    logger.info("[Voice] Room %s shutting down", room.name)
    for task in list(listener_tasks):
        task.cancel()
    if listener_tasks:
        await asyncio.gather(*listener_tasks, return_exceptions=True)
    await publisher.aclose()
    get_room_manager().remove_room(room.name)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
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
        logger.error(
            "livekit-agents is not installed. "
            "Run: pip install -r requirements-voice.txt"
        )
        sys.exit(1)

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            ws_url=livekit_url,
            api_key=api_key,
            api_secret=api_secret,
        )
    )
