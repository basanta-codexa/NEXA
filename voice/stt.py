"""
NEXA Voice — Speech-to-Text (STT)

Uses faster-whisper for local, zero-cost, GPU/CPU transcription.
"""
from __future__ import annotations

import io
import logging
import os
import wave

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
        language: str | None = None,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model = None

    def warmup(self) -> None:
        """Load the Whisper model ahead of the first request."""
        self._load_model()

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
        import numpy as np

        model = self._load_model()

        audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if audio_array.size == 0:
            return ""

        segments, info = model.transcribe(
            audio_array,
            language=self.language,
            # The worker already trims each utterance with Silero VAD. A
            # second VAD pass here just adds latency, and beam search is far
            # slower than greedy decoding for these short utterances.
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
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
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        transcript = " ".join(seg.text.strip() for seg in segments).strip()
        logger.debug("STT transcript=%r lang=%s", transcript, info.language)
        return transcript


class GroqSTT:
    """Hosted Whisper transcription via Groq's OpenAI-compatible API.

    Much faster and more accurate on CPU-only machines than running Whisper
    locally. Falls back to the local model if the API is unavailable.
    """

    def __init__(
        self,
        model_name: str = "whisper-large-v3-turbo",
        language: str | None = None,
    ):
        self.model_name = model_name
        self.language = language
        self._client = None
        self._fallback = WhisperSTT(
            model_size=os.getenv("WHISPER_MODEL_SIZE", "tiny.en"),
            device=os.getenv("WHISPER_DEVICE", "cpu"),
            compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
            language=language,
        )

    def warmup(self) -> None:
        """Build the API client ahead of the first request (no network call)."""
        self._get_client()

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise RuntimeError("GROQ_API_KEY is not set.")
            self._client = OpenAI(
                api_key=api_key,
                base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
                timeout=30.0,
            )
        return self._client

    @staticmethod
    def _to_wav(pcm: bytes, sample_rate: int) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm)
        return buffer.getvalue()

    def transcribe_bytes(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        if not audio_bytes:
            return ""
        try:
            response = self._get_client().audio.transcriptions.create(
                model=self.model_name,
                file=("speech.wav", self._to_wav(audio_bytes, sample_rate)),
                language=self.language,
                response_format="text",
            )
            return (response if isinstance(response, str) else response.text).strip()
        except Exception as exc:
            logger.warning("Groq STT failed (%s); using local Whisper.", exc)
            return self._fallback.transcribe_bytes(audio_bytes, sample_rate)

    def transcribe_file(self, file_path: str) -> str:
        try:
            with open(file_path, "rb") as audio_file:
                response = self._get_client().audio.transcriptions.create(
                    model=self.model_name,
                    file=audio_file,
                    language=self.language,
                    response_format="text",
                )
            return (response if isinstance(response, str) else response.text).strip()
        except Exception as exc:
            logger.warning("Groq STT file failed (%s); using local Whisper.", exc)
            return self._fallback.transcribe_file(file_path)


_default_stt: WhisperSTT | GroqSTT | None = None


def get_stt(model_size: str | None = None) -> WhisperSTT | GroqSTT:
    """Returns a module-level shared STT instance."""
    global _default_stt
    if _default_stt is None:
        provider = os.getenv("STT_PROVIDER", "auto").strip().lower()
        language = os.getenv("WHISPER_LANGUAGE") or None
        if provider == "groq" or (
            provider == "auto" and bool(os.getenv("GROQ_API_KEY"))
        ):
            _default_stt = GroqSTT(
                model_name=os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo"),
                language=language,
            )
        else:
            _default_stt = WhisperSTT(
                model_size=model_size or os.getenv("WHISPER_MODEL_SIZE", "tiny.en"),
                device=os.getenv("WHISPER_DEVICE", "cpu"),
                compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
                language=language,
            )
    return _default_stt
