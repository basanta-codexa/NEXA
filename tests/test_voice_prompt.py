"""Voice-only prompt shaping tests."""

from __future__ import annotations

from types import SimpleNamespace as NS

from services.agent_service import _prepare_agent_run
from voice.prompts import build_voice_system_prompt


def test_voice_prompt_uses_agent_identity():
    agent = NS(
        name="NEXA HR Agent",
        role="Human Resources",
        description="AI assistant for employee HR questions",
    )

    prompt = build_voice_system_prompt(agent)

    assert "You are NEXA HR Agent" in prompt
    assert "a Human Resources assistant" in prompt
    assert "employee HR questions" in prompt
    assert "live voice call" in prompt


def test_voice_prompt_avoid_the_canned_refusal():
    agent = NS(name="Ava", role=None, description=None)

    prompt = build_voice_system_prompt(agent)

    assert "I don't have enough information to answer that" not in prompt
    assert "clarifying question" in prompt


def test_voice_prompt_can_be_overridden(monkeypatch):
    monkeypatch.setenv("VOICE_SYSTEM_PROMPT", "Custom voice instructions")

    assert build_voice_system_prompt(NS(name="Ava")) == "Custom voice instructions"


def test_voice_mode_changes_only_the_voice_prompt(tenant, active_agent, db):
    voice_setup = _prepare_agent_run(
        db,
        active_agent["id"],
        tenant["id"],
        "hello",
        voice_mode=True,
    )
    text_setup = _prepare_agent_run(
        db,
        active_agent["id"],
        tenant["id"],
        "hello",
        voice_mode=False,
    )

    assert "live voice call" in voice_setup.engine.config.system_prompt
    assert "live voice call" not in text_setup.engine.config.system_prompt
