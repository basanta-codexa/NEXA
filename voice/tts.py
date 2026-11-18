"""
NEXA Voice — Text-to-Speech (TTS)

Uses piper-tts 1.8+, which returns iterable AudioChunks instead of writing to
a wave file. Models are downloaded automatically on first use.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import wave
from collections.abc import AsyncIterator, Iterable, Iterator
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "en_US-lessac-medium"

_SENTENCE_BOUNDARY = re.compile(r"[.!?]+[\"')\]]*(?:\s|$)")
_CLAUSE_BOUNDARY = re.compile(r",\s+")
# Ignore short leading clauses so "Yes, sure." is not chopped into two chunks.
_MIN_CLAUSE_CHARS = 18


def _find_boundary(buffer: str):
    """Prefer the first sentence end, or a late enough comma before it."""
    sentence = _SENTENCE_BOUNDARY.search(buffer)
    for comma in _CLAUSE_BOUNDARY.finditer(buffer):
        if sentence is not None and comma.start() >= sentence.start():
            break
        if comma.start() >= _MIN_CLAUSE_CHARS:
            return comma
    return sentence


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def iter_sentences(text_chunks: Iterable[str]) -> Iterator[str]:
    """Yield complete sentences as soon as they can be identified.

    Incomplete trailing text is held until the next chunk or the end of the
    stream, so playback can start before the full response has been written.
    """
    buffer = ""
    for chunk in text_chunks:
        if not chunk:
            continue
        buffer += chunk
        while True:
            match = _find_boundary(buffer)
            if match is None:
                break
            sentence = buffer[: match.end()].strip()
            buffer = buffer[match.end() :]
            if sentence:
                yield sentence
    if buffer.strip():
        yield buffer.strip()


async def aiter_sentences(text_chunks) -> AsyncIterator[str]:
    """Async counterpart of iter_sentences for streamed text deltas."""
    buffer = ""
    async for chunk in text_chunks:
        if not chunk:
            continue
        buffer += chunk
        while True:
            match = _find_boundary(buffer)
            if match is None:
                break
            sentence = buffer[: match.end()].strip()
            buffer = buffer[match.end() :]
            if sentence:
                yield sentence
    if buffer.strip():
        yield buffer.strip()


class PiperTTS:
    """Wraps piper-tts for synchronous text-to-speech synthesis."""

    def __init__(self, voice: str = DEFAULT_VOICE, speaker_id: int | None = None):
        self.voice = voice
        self.speaker_id = speaker_id
        self._model = None
        self.models_dir = Path(
            os.getenv(
                "PIPER_MODELS_DIR",
                Path(__file__).resolve().parent.parent / "voice_models",
            )
        )

    def warmup(self) -> None:
        """Load the voice model ahead of the first request."""
        self._load_model()

    def _load_model(self):
        if self._model is not None:
            return self._model

        try:
            from piper import PiperVoice
        except ImportError as exc:
            raise RuntimeError(
                "piper-tts is not installed. Run: pip install -r requirements-voice.txt"
            ) from exc

        self.models_dir.mkdir(parents=True, exist_ok=True)
        model_path = self.models_dir / f"{self.voice}.onnx"
        config_path = self.models_dir / f"{self.voice}.onnx.json"

        if not model_path.exists():
            try:
                from piper.download_voices import download_voice
            except ImportError as exc:
                raise RuntimeError(
                    "piper download helper is unavailable. "
                    f"Download '{self.voice}' into {self.models_dir} manually."
                ) from exc

            logger.info("Downloading piper voice model '%s'...", self.voice)
            download_voice(self.voice, self.models_dir)
            logger.info("Piper voice model downloaded.")

        logger.info("Loading piper voice '%s'...", self.voice)
        self._model = PiperVoice.load(
            model_path,
            config_path=config_path if config_path.exists() else None,
            use_cuda=False,
        )
        logger.info("Piper TTS model loaded.")
        return self._model

    def _synthesize_chunks(self, text: str):
        from piper.config import SynthesisConfig

        model = self._load_model()
        syn_config = SynthesisConfig(
            speaker_id=self.speaker_id,
            # Slightly slower with a little variation sounds less mechanical.
            length_scale=_env_float("PIPER_LENGTH_SCALE", 1.05),
            noise_scale=_env_float("PIPER_NOISE_SCALE", 0.75),
            noise_w_scale=_env_float("PIPER_NOISE_W_SCALE", 0.85),
        )
        return model.synthesize(text, syn_config=syn_config)

    def synthesize_pcm(self, text: str) -> tuple[bytes, int]:
        """Synthesize text and return (raw 16-bit PCM bytes, sample_rate)."""
        chunks = list(self._synthesize_chunks(text))
        if not chunks:
            return b"", 22050

        sample_rate = chunks[0].sample_rate
        pcm = b"".join(chunk.audio_int16_bytes for chunk in chunks)
        return pcm, sample_rate

    def synthesize_stream(
        self, text_chunks: Iterable[str]
    ) -> Iterator[tuple[bytes, int]]:
        """Yield (PCM, sample_rate) per sentence as text arrives.

        Lets the caller play the first sentence while later ones are still
        being generated, instead of waiting for the whole reply to finish.
        """
        for sentence in iter_sentences(text_chunks):
            chunks = list(self._synthesize_chunks(sentence))
            if not chunks:
                continue
            sample_rate = chunks[0].sample_rate
            pcm = b"".join(chunk.audio_int16_bytes for chunk in chunks)
            yield pcm, sample_rate

    async def synthesize_stream_async(self, text_chunks) -> AsyncIterator[tuple[bytes, int]]:
        """Async streaming counterpart of synthesize_stream for voice turns."""
        async for sentence in aiter_sentences(text_chunks):
            chunks = await asyncio.to_thread(
                lambda text=sentence: list(self._synthesize_chunks(text))
            )
            if not chunks:
                continue
            sample_rate = chunks[0].sample_rate
            pcm = b"".join(chunk.audio_int16_bytes for chunk in chunks)
            yield pcm, sample_rate

    def synthesize(self, text: str) -> bytes:
        """Synthesize text and return mono 16-bit WAV bytes."""
        chunks = list(self._synthesize_chunks(text))
        if not chunks:
            return b""

        sample_rate = chunks[0].sample_rate
        sample_width = chunks[0].sample_width
        channels = chunks[0].sample_channels
        pcm = b"".join(chunk.audio_int16_bytes for chunk in chunks)

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm)

        return buffer.getvalue()


_default_tts: PiperTTS | None = None


def get_tts(voice: str | None = None) -> PiperTTS:
    """Returns a module-level shared TTS instance."""
    global _default_tts
    if _default_tts is None:
        _default_tts = PiperTTS(voice=voice or os.getenv("PIPER_VOICE", DEFAULT_VOICE))
    return _default_tts
