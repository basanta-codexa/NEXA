"""Streaming agent service and voice pipeline tests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS

from services.agent_service import stream_agent_engine_service


def test_stream_agent_engine_service_yields_text_then_done(tenant, active_agent, db):
    events = list(
        stream_agent_engine_service(
            db=db,
            agent_id=active_agent["id"],
            tenant_id=tenant["id"],
            user_message="Hello there",
        )
    )

    assert any(event["type"] == "text" for event in events)
    done = events[-1]
    assert done["type"] == "done"
    assert done["result"]["response"]
    assert done["result"]["agent_id"] == active_agent["id"]


def test_stream_voice_turn_yields_audio_per_sentence(monkeypatch):
    from voice import pipeline

    class FakeSTT:
        def transcribe_bytes(self, audio_bytes, sample_rate=16000):
            return "hello there"

    class FakeTTS:
        async def synthesize_stream_async(self, text_chunks):
            async for text in text_chunks:
                yield text.encode(), 22050

    def fake_stream_service(**kwargs):
        yield {"type": "text", "content": "Hi "}
        yield {"type": "text", "content": "there."}
        yield {"type": "done", "result": {"response": "Hi there."}}

    monkeypatch.setattr("voice.stt.get_stt", lambda: FakeSTT())
    monkeypatch.setattr("voice.tts.get_tts", lambda: FakeTTS())
    monkeypatch.setattr(
        "services.agent_service.stream_agent_engine_service", fake_stream_service
    )
    monkeypatch.setattr(
        "database.SessionLocal", lambda: NS(close=lambda: None)
    )

    context = NS(
        agent_id=1, tenant_id=1, session_id="session", user_id=1
    )

    async def collect():
        chunks = []
        async for audio in pipeline.run_voice_turn_stream(
            b"\x00" * 100, 16000, context
        ):
            chunks.append(audio)
        return chunks

    assert asyncio.run(collect()) == [(b"Hi ", 22050), (b"there.", 22050)]
