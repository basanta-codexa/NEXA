"""
NEXA Voice — Speech-to-Text (STT)
Uses faster-whisper for local, zero-cost, GPU/CPU transcription.
"""
from __future__ import annotations

import io
import logging
import tempfile
import os
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class WhisperSTT:
    """
    Wraps faster-whisper for synchronous transcription.
    Lazy-loads the model on first use to avoid startup delay.
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        language: Optional[str] = None,
    ):
        """
        Args:
            model_size: Whisper model size — "tiny", "base", "small", "medium", "large-v3"
                        "base" is a good balance of speed/accuracy on CPU.
            device: "cpu" or "cuda" (GPU).
            compute_type: "int8" (fast CPU), "float16" (GPU), "float32" (fallback).
            language: ISO 639-1 language code (e.g. "en"). None = auto-detect.
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model = None  # lazy-loaded

    def _load_model(self):
        """Lazy-load faster-whisper model on first transcription call."""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
                logger.info(
                    f"Loading faster-whisper model '{self.model_size}' "
                    f"on {self.device} ({self.compute_type})..."
                )
                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type
                )
                logger.info("faster-whisper model loaded.")
            except ImportError:
                raise RuntimeError(
                    "faster-whisper is not installed. "
                    "Run: pip install faster-whisper"
                )
        return self._model

    def transcribe_bytes(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribe raw PCM audio bytes (16-bit signed, mono).

        Args:
            audio_bytes: Raw PCM audio data.
            sample_rate: Sample rate in Hz (faster-whisper expects 16000 Hz).

        Returns:
            Transcribed text string.
        """
        model = self._load_model()

        # Convert raw PCM bytes → numpy float32 array (faster-whisper expects this)
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # faster-whisper transcribes from a numpy array or a file path
        # We write to a temp wav file for reliability
        import soundfile as sf
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            sf.write(tmp_path, audio_array, sample_rate, format="WAV", subtype="PCM_16")
            segments, info = model.transcribe(
                tmp_path,
                language=self.language,
                beam_size=5,
                vad_filter=True,          # Voice Activity Detection — skip silence
                vad_parameters=dict(min_silence_duration_ms=500),
            )
            transcript = " ".join(seg.text.strip() for seg in segments).strip()
            logger.debug(f"STT transcript: '{transcript}' (lang={info.language}, prob={info.language_probability:.2f})")
            return transcript
        finally:
            os.unlink(tmp_path)

    def transcribe_file(self, file_path: str) -> str:
        """
        Transcribe audio from a file path (.wav, .mp3, .ogg, etc.).

        Args:
            file_path: Path to the audio file.

        Returns:
            Transcribed text string.
        """
        model = self._load_model()
        segments, info = model.transcribe(
            file_path,
            language=self.language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        transcript = " ".join(seg.text.strip() for seg in segments).strip()
        logger.debug(f"STT transcript: '{transcript}' (lang={info.language})")
        return transcript


# Module-level singleton (lazy-initialized)
_default_stt: Optional[WhisperSTT] = None


def get_stt(model_size: str = "base") -> WhisperSTT:
    """Returns a module-level shared STT instance."""
    global _default_stt
    if _default_stt is None:
        _default_stt = WhisperSTT(model_size=model_size)
    return _default_stt
