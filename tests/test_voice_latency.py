"""Voice latency regressions for the STT stage."""

from __future__ import annotations

import numpy as np

from voice.stt import WhisperSTT


class _FakeWhisperModel:
    """Captures transcribe() options without running a real model."""

    def __init__(self):
        self.call_kwargs: dict | None = None

    def transcribe(self, _audio, **kwargs):
        self.call_kwargs = kwargs
        info = type("FakeInfo", (), {"language": "en", "language_probability": 1.0})()
        return [], info


def _assert_low_latency_options(kwargs: dict | None) -> None:
    assert kwargs is not None
    # Greedy decoding: beam search adds seconds for short utterances.
    assert kwargs["beam_size"] == 1
    # The LiveKit worker already trims with Silero VAD; a second pass is wasted time.
    assert kwargs["vad_filter"] is False
    # Each utterance is independent; carrying prior text also causes repetition loops.
    assert kwargs["condition_on_previous_text"] is False


def test_transcribe_bytes_uses_low_latency_options():
    stt = WhisperSTT()
    fake = _FakeWhisperModel()
    stt._model = fake

    pcm = np.zeros(1600, dtype=np.int16).tobytes()  # 100 ms of silence at 16 kHz

    assert stt.transcribe_bytes(pcm, sample_rate=16000) == ""
    _assert_low_latency_options(fake.call_kwargs)


def test_transcribe_file_uses_low_latency_options():
    stt = WhisperSTT()
    fake = _FakeWhisperModel()
    stt._model = fake

    assert stt.transcribe_file("unused.wav") == ""
    _assert_low_latency_options(fake.call_kwargs)


class _FakeEOT:
    def __init__(self):
        self.seen = None

    def predict(self, pcm):
        self.seen = pcm
        return 0.75


def test_eot_predicts_on_only_the_audio_tail():
    from voice import worker

    fake = _FakeEOT()
    pcm = np.arange(30000, dtype=np.int16).tobytes()

    probability = worker._predict_end_of_turn(fake, pcm)

    assert probability == 0.75
    assert len(fake.seen) == worker.EOT_MAX_SAMPLES
    assert fake.seen[0] == 30000 - worker.EOT_MAX_SAMPLES


def test_eot_veto_and_hard_deadline():
    from voice.worker import _should_wait_for_more_speech

    # Low probability -> keep accumulating.
    assert _should_wait_for_more_speech(0.2, 0.5, 0.3, 3.0) is True
    # High probability -> respond now.
    assert _should_wait_for_more_speech(0.8, 0.5, 0.3, 3.0) is False
    # Hard deadline wins even if the model is unsure.
    assert _should_wait_for_more_speech(0.2, 0.5, 3.1, 3.0) is False
