from datetime import datetime, timezone
from typing import Any
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from models import Conversation, Message


def get_or_create_conversation(
    db: Session,
    tenant_id: int,
    agent_id: int,
    session_id: str,
    user_id: int | None = None
) -> Conversation:
    """
    Retrieves an existing conversation session or creates a new one,
    strictly isolated by tenant_id and agent_id.
    """
    conversation = db.query(Conversation).filter(
        Conversation.tenant_id == tenant_id,
        Conversation.agent_id == agent_id,
        Conversation.session_id == session_id
    ).first()

    if conversation is None:
        conversation = Conversation(
            session_id=session_id,
            agent_id=agent_id,
            tenant_id=tenant_id,
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(conversation)
        try:
            db.commit()
            db.refresh(conversation)
        except IntegrityError:
            # Another request created the same tenant/agent/session row
            # between our SELECT and INSERT. Reuse it.
            db.rollback()
            conversation = db.query(Conversation).filter(
                Conversation.tenant_id == tenant_id,
                Conversation.agent_id == agent_id,
                Conversation.session_id == session_id,
            ).one()

    return conversation


def add_message(
    db: Session,
    conversation_id: int,
    tenant_id: int,
    role: str,
    content: str,
    tool_calls: list[dict[str, Any]] | None = None,
    tool_name: str | None = None
) -> Message:
    """
    Appends a new turn to the conversation history.
    """
    message = Message(
        conversation_id=conversation_id,
        tenant_id=tenant_id,
        role=role,
        content=content,
        tool_calls=tool_calls,
        tool_name=tool_name,
        created_at=datetime.now(timezone.utc)
    )
    db.add(message)

    # Touch conversation updated_at
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.tenant_id == tenant_id
    ).first()
    if conversation:
        conversation.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(message)
    return message


def get_conversation_history(
    db: Session,
    conversation_id: int,
    tenant_id: int,
    limit: int = 20
) -> list[dict[str, Any]]:
    """
    Fetches the most recent turns up to limit and formats them
    for LLM input: [{"role": "user"|"assistant"|"tool", "content": ...}]
    """
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.tenant_id == tenant_id
    ).order_by(Message.created_at.desc()).limit(limit).all()

    # Reverse to chronological order (oldest -> newest)
    messages = list(reversed(messages))

    history: list[dict[str, Any]] = []
    for msg in messages:
        entry: dict[str, Any] = {
            "role": msg.role,
            "content": msg.content
        }
        if msg.tool_calls:
            entry["tool_calls"] = msg.tool_calls
        if msg.tool_name:
            entry["tool_name"] = msg.tool_name
        history.append(entry)

    return history


def clear_conversation(
    db: Session,
    conversation_id: int,
    tenant_id: int
) -> bool:
    """
    Clears all messages within a conversation.
    """
    db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.tenant_id == tenant_id
    ).delete()
    db.commit()
    return True
