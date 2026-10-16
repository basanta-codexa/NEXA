"""
NEXA Voice — Text-to-Speech (TTS)
Uses piper-tts for local, zero-cost, high-quality voice synthesis.
"""
from __future__ import annotations

import io
import logging
import os
import struct
import wave
from typing import Optional

logger = logging.getLogger(__name__)

# Default piper voice model (English).
# Models auto-download from HuggingFace on first use.
DEFAULT_VOICE = "en_US-lessac-medium"


class PiperTTS:
    """
    Wraps piper-tts for synchronous text-to-speech synthesis.
    Lazy-loads the voice model on first use.

    Piper is the production-ready open-source TTS from the Rhasspy/Coqui lineage.
    Models are downloaded automatically from HuggingFace on first use.
    """

    def __init__(self, voice: str = DEFAULT_VOICE, speaker_id: Optional[int] = None):
        """
        Args:
            voice: Piper voice model name (e.g. "en_US-lessac-medium").
                   Full list: https://rhasspy.github.io/piper-samples/
            speaker_id: For multi-speaker models, the speaker index. None = default.
        """
        self.voice = voice
        self.speaker_id = speaker_id
        self._model = None  # lazy-loaded

    def _load_model(self):
        """Lazy-load piper voice model on first synthesis call."""
        if self._model is None:
            try:
                from piper.voice import PiperVoice
                import piper.download as piper_dl
                import piper
            except ImportError:
                raise RuntimeError(
                    "piper-tts is not installed. "
                    "Run: pip install piper-tts"
                )

            # Resolve model path — download if not cached
            models_dir = os.path.join(os.path.dirname(__file__), "..", "voice_models")
            os.makedirs(models_dir, exist_ok=True)

            model_path = os.path.join(models_dir, f"{self.voice}.onnx")
            config_path = os.path.join(models_dir, f"{self.voice}.onnx.json")

            if not os.path.exists(model_path):
                logger.info(f"Downloading piper voice model '{self.voice}'...")
                piper_dl.ensure_voice_exists(
                    self.voice,
                    data_dirs=[models_dir],
                    download_dir=models_dir,
                )
                logger.info(f"Voice model '{self.voice}' downloaded.")

            logger.info(f"Loading piper voice '{self.voice}'...")
            self._model = PiperVoice.load(model_path, config_path=config_path, use_cuda=False)
            logger.info("Piper TTS model loaded.")

        return self._model

    def synthesize(self, text: str, sample_rate: int = 22050) -> bytes:
        """
        Synthesize text to raw PCM WAV audio bytes.

        Args:
            text: The text to synthesize.
            sample_rate: Output sample rate. Piper uses 22050 Hz by default.

        Returns:
            WAV audio bytes (16-bit PCM, mono).
        """
        model = self._load_model()

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            model.synthesize(
                text,
                wav_file,
                speaker_id=self.speaker_id,
            )

        return wav_buffer.getvalue()

    def synthesize_pcm(self, text: str) -> tuple[bytes, int]:
        """
        Synthesize text and return raw PCM bytes + sample rate.
        Useful when you need to send raw audio (e.g., to LiveKit).

        Returns:
            Tuple of (pcm_bytes, sample_rate).
        """
        wav_bytes = self.synthesize(text)

        # Strip the WAV header — return raw PCM
        with io.BytesIO(wav_bytes) as buf:
            with wave.open(buf, "rb") as wf:
                sample_rate = wf.getframerate()
                pcm_bytes = wf.readframes(wf.getnframes())

        return pcm_bytes, sample_rate


# Module-level singleton (lazy-initialized)
_default_tts: Optional[PiperTTS] = None


def get_tts(voice: str = DEFAULT_VOICE) -> PiperTTS:
    """Returns a module-level shared TTS instance."""
    global _default_tts
    if _default_tts is None:
        _default_tts = PiperTTS(voice=voice)
    return _default_tts
