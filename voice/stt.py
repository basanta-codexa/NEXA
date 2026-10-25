"""
NEXA Voice — Speech-to-Text (STT)

Uses faster-whisper for local, zero-cost, GPU/CPU transcription.
"""
from __future__ import annotations

import logging
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
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError(
                    "faster-whisper is not installed. "
                    "Run: pip install -r requirements-voice.txt"
                ) from exc

            logger.info(
                "Loading faster-whisper model '%s' on %s (%s)...",
                self.model_size,
                self.device,
                self.compute_type,
            )
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("faster-whisper model loaded.")
        return self._model

    def transcribe_bytes(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """Transcribe raw 16-bit signed mono PCM bytes."""
        model = self._load_model()

        audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if audio_array.size == 0:
            return ""

        segments, info = model.transcribe(
            audio_array,
            language=self.language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        transcript = " ".join(seg.text.strip() for seg in segments).strip()
        logger.debug(
            "STT transcript=%r lang=%s prob=%.2f",
            transcript,
            info.language,
            info.language_probability,
        )
        return transcript

    def transcribe_file(self, file_path: str) -> str:
        """Transcribe audio from a file path (.wav, .mp3, .ogg, etc.)."""
        model = self._load_model()
        segments, info = model.transcribe(
            file_path,
            language=self.language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )
        transcript = " ".join(seg.text.strip() for seg in segments).strip()
        logger.debug("STT transcript=%r lang=%s", transcript, info.language)
        return transcript


_default_stt: Optional[WhisperSTT] = None


def get_stt(model_size: str | None = None) -> WhisperSTT:
    """Returns a module-level shared STT instance."""
    global _default_stt
    if _default_stt is None:
        _default_stt = WhisperSTT(
            model_size=model_size or os.getenv("WHISPER_MODEL_SIZE", "base"),
            device=os.getenv("WHISPER_DEVICE", "cpu"),
            compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
        )
    return _default_stt
