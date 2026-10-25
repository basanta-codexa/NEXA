"""
NEXA Voice — Text-to-Speech (TTS)

Uses piper-tts 1.8+, which returns iterable AudioChunks instead of writing to
a wave file. Models are downloaded automatically on first use.
"""
from __future__ import annotations

import io
import logging
import os
import wave
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "en_US-lessac-medium"


class PiperTTS:
    """Wraps piper-tts for synchronous text-to-speech synthesis."""

    def __init__(self, voice: str = DEFAULT_VOICE, speaker_id: Optional[int] = None):
        self.voice = voice
        self.speaker_id = speaker_id
        self._model = None
        self.models_dir = Path(
            os.getenv(
                "PIPER_MODELS_DIR",
                Path(__file__).resolve().parent.parent / "voice_models",
            )
        )

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
        syn_config = SynthesisConfig(speaker_id=self.speaker_id)
        return model.synthesize(text, syn_config=syn_config)

    def synthesize_pcm(self, text: str) -> tuple[bytes, int]:
        """Synthesize text and return (raw 16-bit PCM bytes, sample_rate)."""
        chunks = list(self._synthesize_chunks(text))
        if not chunks:
            return b"", 22050

        sample_rate = chunks[0].sample_rate
        pcm = b"".join(chunk.audio_int16_bytes for chunk in chunks)
        return pcm, sample_rate

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


_default_tts: Optional[PiperTTS] = None


def get_tts(voice: str | None = None) -> PiperTTS:
    """Returns a module-level shared TTS instance."""
    global _default_tts
    if _default_tts is None:
        _default_tts = PiperTTS(voice=voice or os.getenv("PIPER_VOICE", DEFAULT_VOICE))
    return _default_tts
