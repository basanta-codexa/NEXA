from __future__ import annotations

import time
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from models import Agent, AgentStatus, Conversation
from services.memory_service import (
    add_message,
    clear_conversation,
    get_conversation_history,
    get_or_create_conversation,
)


def _create_agent(db, tenant_id: int, name: str = "Memory Agent") -> Agent:
    agent = Agent(
        name=name,
        role="Support",
        language="English",
        model_name="fake",
        status=AgentStatus.ACTIVE,
        tenant_id=tenant_id,
        tools=[],
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def test_conversation_creation_is_idempotent_and_tenant_isolated(
    db, tenant, tenant_factory
):
    other = tenant_factory("memory-other")
    agent = _create_agent(db, tenant["id"])
    other_agent = _create_agent(db, other["id"], "Other Memory Agent")

    session_id = f"session-{uuid.uuid4().hex[:8]}"
    first = get_or_create_conversation(db, tenant["id"], agent.id, session_id)
    repeated = get_or_create_conversation(db, tenant["id"], agent.id, session_id)
    assert first.id == repeated.id

    isolated = get_or_create_conversation(
        db, other["id"], other_agent.id, session_id
    )
    assert isolated.id != first.id
    assert isolated.tenant_id == other["id"]


def test_message_history_is_chronological_and_limited(db, tenant):
    agent = _create_agent(db, tenant["id"])
    conversation = get_or_create_conversation(db, tenant["id"], agent.id, "history")

    for index in range(5):
        add_message(
            db,
            conversation_id=conversation.id,
            tenant_id=tenant["id"],
            role="user" if index % 2 == 0 else "assistant",
            content=f"message-{index}",
        )
        time.sleep(0.002)

    history = get_conversation_history(
        db, conversation_id=conversation.id, tenant_id=tenant["id"], limit=10
    )
    assert [item["content"] for item in history] == [
        f"message-{index}" for index in range(5)
    ]

    limited = get_conversation_history(
        db, conversation_id=conversation.id, tenant_id=tenant["id"], limit=2
    )
    assert [item["content"] for item in limited] == ["message-3", "message-4"]


def test_clear_conversation_removes_all_messages(db, tenant):
    agent = _create_agent(db, tenant["id"])
    conversation = get_or_create_conversation(db, tenant["id"], agent.id, "clear")
    add_message(db, conversation.id, tenant["id"], "user", "hello")

    assert clear_conversation(db, conversation.id, tenant["id"]) is True
    assert (
        get_conversation_history(db, conversation.id, tenant["id"], limit=10) == []
    )


def test_duplicate_session_is_rejected_by_the_database(db, tenant):
    agent = _create_agent(db, tenant["id"])
    first = Conversation(
        session_id="duplicate-session",
        agent_id=agent.id,
        tenant_id=tenant["id"],
    )
    db.add(first)
    db.commit()

    duplicate = Conversation(
        session_id="duplicate-session",
        agent_id=agent.id,
        tenant_id=tenant["id"],
    )
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_conversation_creation_recovers_from_a_concurrent_insert(
    db, tenant, monkeypatch
):
    from database import SessionLocal

    agent = _create_agent(db, tenant["id"])
    session_id = f"race-{uuid.uuid4().hex[:8]}"

    other_db = SessionLocal()
    try:
        existing = Conversation(
            session_id=session_id,
            agent_id=agent.id,
            tenant_id=tenant["id"],
        )
        other_db.add(existing)
        other_db.commit()
        other_db.refresh(existing)
        existing_id = existing.id
    finally:
        other_db.close()

    real_query = db.query
    state = {"first_query": True}

    class _EmptyQuery:
        def filter(self, *args, **kwargs):
            return self

        def first(self):
            return None

    def fake_query(*args, **kwargs):
        if state["first_query"] and args and args[0] is Conversation:
            state["first_query"] = False
            return _EmptyQuery()
        return real_query(*args, **kwargs)

    monkeypatch.setattr(db, "query", fake_query)

    conversation = get_or_create_conversation(
        db, tenant["id"], agent.id, session_id
    )
    assert conversation.id == existing_id
