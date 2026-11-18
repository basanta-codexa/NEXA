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
import time
import wave

# LiveKit registers plugins (and checks the thread) at import time. Import the
# Silero plugin here, on the main thread, so jobs running in the worker's job
# runner thread don't fail with "Plugins must be registered on the main thread".
try:
    from livekit.agents.vad import VADEventType
    from livekit.plugins import silero
except ImportError:  # voice extras not installed
    VADEventType = None
    silero = None

try:
    # Native, local end-of-turn model shipped with livekit-local-inference.
    from livekit.local_inference import EOT, EOT_MAX_SAMPLES, init_eot
except ImportError:  # local inference extra not installed
    EOT = None
    EOT_MAX_SAMPLES = 0
    init_eot = None

logger = logging.getLogger("nexa.voice.worker")

VAD_SAMPLE_RATE = 16000
OUTPUT_SAMPLE_RATE = 48000
MIN_SPEECH_BYTES = VAD_SAMPLE_RATE * 2 * 0.15  # ignore <150ms blips
_TRUTHY = {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _predict_end_of_turn(detector, pcm: bytes) -> float:
    """P(turn ended) for the tail of an utterance. Called in a worker thread."""
    import numpy as np

    audio = np.frombuffer(pcm, dtype=np.int16)
    tail = audio[-EOT_MAX_SAMPLES:] if EOT_MAX_SAMPLES else audio
    return float(detector.predict(tail))


def _should_wait_for_more_speech(
    probability: float, threshold: float, waited: float, max_wait: float
) -> bool:
    """True when EOT says the user is still speaking and we have time to wait."""
    return probability < threshold and waited < max_wait


async def _warmup_models() -> None:
    """Load models before the first call so a user never pays cold-start cost."""
    from voice.stt import get_stt
    from voice.tts import get_tts

    started_at = time.perf_counter()
    await asyncio.to_thread(get_tts().warmup)
    await asyncio.to_thread(get_stt().warmup)
    if (
        EOT is not None
        and init_eot is not None
        and os.getenv("VAD_EOT_ENABLED", "true").strip().lower() in _TRUTHY
    ):
        await asyncio.to_thread(init_eot)
    logger.info(
        "[Voice] models warmed in %s ms",
        round((time.perf_counter() - started_at) * 1000, 1),
    )


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

    async def _push_pcm(
        self, pcm: bytes, sample_rate: int, generation: int
    ) -> None:
        """Push resampled PCM into the track in 20 ms frames."""
        from livekit import rtc

        pcm = _resample_pcm(pcm, sample_rate, OUTPUT_SAMPLE_RATE)

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

    async def play(self, wav_bytes: bytes) -> None:
        """Play WAV bytes, interrupting any previous playback."""
        pcm, sample_rate, channels = _read_wav(wav_bytes)
        if channels != 1:
            raise ValueError("TTS output must be mono.")

        async with self._lock:
            await self._ensure_started()
            generation = self._generation
            await self._push_pcm(pcm, sample_rate, generation)
            if generation == self._generation:
                await self._source.wait_for_playout()

    async def play_stream(self, chunks) -> None:
        """Play (PCM, sample_rate) chunks as they arrive, without gaps.

        Unlike play(), each chunk is pushed immediately; the single
        wait_for_playout() at the end avoids dead air between sentences.
        """
        async with self._lock:
            await self._ensure_started()
            generation = self._generation
            async for pcm, sample_rate in chunks:
                if generation != self._generation:
                    return
                await self._push_pcm(pcm, sample_rate, generation)
            if generation == self._generation:
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

    from voice.pipeline import run_voice_turn_stream

    if silero is None or VADEventType is None:
        raise RuntimeError(
            "Voice dependencies are missing. "
            "Run: pip install -r requirements-voice.txt"
        )

    vad = silero.VAD.load(
        min_silence_duration=float(os.getenv("VAD_MIN_SILENCE_SECONDS", "0.25")),
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

    eot_enabled = (
        EOT is not None
        and os.getenv("VAD_EOT_ENABLED", "true").strip().lower() in _TRUTHY
    )
    eot_threshold = _env_float("VAD_EOT_THRESHOLD", 0.2)
    eot_max_wait = _env_float("VAD_EOT_MAX_WAIT_SECONDS", 0.8)
    # Model init can load ~100 MB; keep it off the event loop.
    eot_detector = await asyncio.to_thread(EOT) if eot_enabled else None

    pending = bytearray()
    pending_started_at: float | None = None
    pending_generation = 0
    watchdog: asyncio.Task | None = None
    active_turn_task: asyncio.Task | None = None

    async def commit_utterance() -> None:
        nonlocal pending, pending_started_at, pending_generation
        nonlocal watchdog, active_turn_task
        if not pending:
            return
        utterance = bytes(pending)
        pending.clear()
        pending_started_at = None
        pending_generation += 1
        if (
            watchdog is not None
            and not watchdog.done()
            and asyncio.current_task() is not watchdog
        ):
            watchdog.cancel()

        turn_requested_at = time.perf_counter()
        logger.info(
            "[Voice] Speech from %s (%.2fs)",
            participant_identity,
            len(utterance) / 2 / VAD_SAMPLE_RATE,
        )
        first_audio_ms: float | None = None

        async def audio_with_timing():
            nonlocal first_audio_ms
            async for audio_chunk in run_voice_turn_stream(
                utterance, VAD_SAMPLE_RATE, context
            ):
                if first_audio_ms is None:
                    first_audio_ms = round(
                        (time.perf_counter() - turn_requested_at) * 1000, 1
                    )
                yield audio_chunk

        async def play_turn() -> None:
            await publisher.play_stream(audio_with_timing())
            logger.info(
                "[Voice] speech_end_to_first_audio_ms=%s speech_end_to_response_ms=%s",
                first_audio_ms,
                round((time.perf_counter() - turn_requested_at) * 1000, 1),
            )

        task = asyncio.create_task(play_turn())
        active_turn_task = task
        try:
            await task
        except asyncio.CancelledError:
            logger.info("[Voice] Turn cancelled for %s", participant_identity)
        except Exception:
            logger.exception("[Voice] Turn failed for %s", participant_identity)
        finally:
            if active_turn_task is task:
                active_turn_task = None

    async def force_commit(generation: int, deadline: float) -> None:
        remaining = deadline - time.perf_counter()
        if remaining > 0:
            await asyncio.sleep(remaining)
        if generation == pending_generation and pending:
            logger.info("[Voice] EOT max wait reached — committing pending speech.")
            await commit_utterance()

    feed_task = asyncio.create_task(feed_vad())

    try:
        async for event in vad_stream:
            if event.type == VADEventType.START_OF_SPEECH:
                publisher.interrupt()
                if active_turn_task is not None and not active_turn_task.done():
                    active_turn_task.cancel()
                continue

            if event.type != VADEventType.END_OF_SPEECH:
                continue

            frames = event.frames or []
            pcm = b"".join(bytes(frame.data) for frame in frames)
            if not pcm:
                continue

            if not pending:
                pending_started_at = time.perf_counter()
                pending_generation += 1
            pending.extend(pcm)

            if len(pending) < MIN_SPEECH_BYTES:
                continue

            if eot_detector is not None and pending_started_at is not None:
                probability = await asyncio.to_thread(
                    _predict_end_of_turn, eot_detector, bytes(pending)
                )
                waited = time.perf_counter() - pending_started_at
                logger.info(
                    "[Voice] EOT verdict probability=%.3f threshold=%.3f pending_ms=%s",
                    probability,
                    eot_threshold,
                    round(waited * 1000, 1),
                )
                if _should_wait_for_more_speech(
                    probability, eot_threshold, waited, eot_max_wait
                ):
                    # The model thinks the user is still speaking. Keep the
                    # audio and wait for the next utterance, with a hard
                    # deadline so silence can never strand a turn forever.
                    if watchdog is not None and not watchdog.done():
                        watchdog.cancel()
                    watchdog = asyncio.create_task(
                        force_commit(
                            pending_generation, pending_started_at + eot_max_wait
                        )
                    )
                    continue

            await commit_utterance()

    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("[Voice] Listener crashed for %s", participant_identity)
    finally:
        if active_turn_task is not None and not active_turn_task.done():
            active_turn_task.cancel()
        if watchdog is not None and not watchdog.done():
            watchdog.cancel()
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

    await _warmup_models()

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
