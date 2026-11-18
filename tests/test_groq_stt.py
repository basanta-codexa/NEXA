"""Groq-backed STT selection and fallback tests (no network calls)."""

from __future__ import annotations

import io
import wave

from voice.stt import GroqSTT, get_stt


def _fake_client(result="hello world"):
    class Transcriptions:
        def __init__(self):
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs
            return result

    class Audio:
        def __init__(self):
            self.transcriptions = Transcriptions()

    class Client:
        def __init__(self):
            self.audio = Audio()

    return Client()


def test_to_wav_writes_valid_16k_mono_pcm():
    pcm = b"\x00\x01" * 16000
    wav = GroqSTT._to_wav(pcm, 16000)

    with wave.open(io.BytesIO(wav), "rb") as f:
        assert f.getnchannels() == 1
        assert f.getsampwidth() == 2
        assert f.getframerate() == 16000
        assert f.readframes(f.getnframes()) == pcm


def test_groq_transcription_returns_text(monkeypatch):
    stt = GroqSTT(language="en")
    client = _fake_client()
    monkeypatch.setattr(stt, "_get_client", lambda: client)

    assert stt.transcribe_bytes(b"\x00\x00" * 16000, 16000) == "hello world"
    assert client.audio.transcriptions.kwargs["model"] == "whisper-large-v3-turbo"
    assert client.audio.transcriptions.kwargs["response_format"] == "text"


def test_groq_failure_falls_back_to_local_stt(monkeypatch):
    stt = GroqSTT()
    monkeypatch.setattr(
        stt, "_get_client", lambda: (_ for _ in ()).throw(RuntimeError("no key"))
    )
    monkeypatch.setattr(
        stt._fallback, "transcribe_bytes", lambda audio_bytes, sample_rate: "local result"
    )

    assert stt.transcribe_bytes(b"\x00\x00" * 16000, 16000) == "local result"


def test_get_stt_selects_groq_when_key_is_set(monkeypatch):
    monkeypatch.setattr("voice.stt._default_stt", None)
    monkeypatch.setenv("STT_PROVIDER", "auto")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    assert isinstance(get_stt(), GroqSTT)


def test_get_stt_uses_local_when_disabled(monkeypatch):
    from voice.stt import WhisperSTT

    monkeypatch.setattr("voice.stt._default_stt", None)
    monkeypatch.setenv("STT_PROVIDER", "local")

    assert isinstance(get_stt(), WhisperSTT)
