"""Sentence-level TTS streaming and continuous playback tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS

from voice.tts import PiperTTS, iter_sentences


def test_sentences_are_emitted_at_boundaries_across_chunks():
    chunks = ["Hello ", "world. How", " are you?"]

    assert list(iter_sentences(chunks)) == ["Hello world.", "How are you?"]


def test_trailing_text_is_emitted_at_end_of_stream():
    assert list(iter_sentences(["One. Two"])) == ["One.", "Two"]


def test_long_clause_splits_on_comma():
    chunks = ["I'm not sure about that one, but our notes", " don't cover it."]

    assert list(iter_sentences(chunks)) == [
        "I'm not sure about that one,",
        "but our notes don't cover it.",
    ]


def test_short_clause_is_not_split():
    assert list(iter_sentences(["Yes, sure."])) == ["Yes, sure."]


def test_synthesis_uses_tuned_prosody(monkeypatch):
    import sys
    import types

    from voice.tts import PiperTTS

    captured = {}

    class FakeSynthesisConfig:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_module = types.ModuleType("piper.config")
    fake_module.SynthesisConfig = FakeSynthesisConfig
    monkeypatch.setitem(sys.modules, "piper.config", fake_module)
    monkeypatch.setenv("PIPER_LENGTH_SCALE", "1.2")

    class FakeModel:
        def synthesize(self, text, syn_config=None):
            return []

    tts = PiperTTS()
    tts._model = FakeModel()
    list(tts.synthesize_stream(["Hello there."]))

    assert captured["length_scale"] == 1.2
    assert "noise_scale" in captured


def test_empty_chunks_are_ignored():
    assert list(iter_sentences(["", "Hi!", ""])) == ["Hi!"]


class _FakeAudioChunk:
    sample_rate = 22050
    audio_int16_bytes = b"\x01\x02"


def test_synthesize_stream_synthesizes_each_sentence():
    tts = PiperTTS()
    synthesized: list[str] = []

    def fake_synthesize(text):
        synthesized.append(text)
        return [_FakeAudioChunk()]

    tts._synthesize_chunks = fake_synthesize

    chunks = list(tts.synthesize_stream(["Hello there. How are", " you? Fine!"]))

    assert synthesized == ["Hello there.", "How are you?", "Fine!"]
    assert chunks == [(b"\x01\x02", 22050)] * 3


def test_warmup_loads_models_before_first_turn(monkeypatch):
    from voice import worker

    calls = []

    class FakeSTT:
        def warmup(self):
            calls.append("stt")

    class FakeTTS:
        def warmup(self):
            calls.append("tts")

    monkeypatch.setattr("voice.stt.get_stt", lambda: FakeSTT())
    monkeypatch.setattr("voice.tts.get_tts", lambda: FakeTTS())
    monkeypatch.setattr(worker, "EOT", object())
    monkeypatch.setattr(worker, "init_eot", lambda: calls.append("eot"))
    monkeypatch.setenv("VAD_EOT_ENABLED", "true")

    asyncio.run(worker._warmup_models())

    assert calls == ["tts", "stt", "eot"]


def test_play_stream_pushes_chunks_then_waits_once():
    from voice.worker import AudioPublisher

    publisher = AudioPublisher(room=None)
    calls = []

    async def ensure_started():
        calls.append("ensure")

    async def push(pcm, sample_rate, generation):
        calls.append((pcm, sample_rate))

    async def wait():
        calls.append("wait")

    publisher._ensure_started = ensure_started
    publisher._push_pcm = push
    publisher._source = NS(wait_for_playout=wait)

    async def audio_chunks():
        yield b"one", 22050
        yield b"two", 22050

    asyncio.run(publisher.play_stream(audio_chunks()))

    assert calls == ["ensure", (b"one", 22050), (b"two", 22050), "wait"]
