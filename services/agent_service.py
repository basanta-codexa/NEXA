import logging
import os
import uuid

from models import Agent, AgentStatus
from engine.agent_engine import AgentEngine
from schemas import AgentConfig
from tools.default_registry import default_registry
from services.memory_service import (
    get_or_create_conversation,
    add_message,
    get_conversation_history,
)
from services.rag_service import (
    search_knowledge_service,
    build_grounded_context,
)
from llm.factory import create_llm_client

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def create_agent_service(db, agent_data, tenant_id):
    new_agent = Agent(
        name=agent_data.name,
        role=agent_data.role,
        language=agent_data.language,
        description=agent_data.description,
        system_prompt=agent_data.system_prompt,
        model_name=agent_data.model_name,
        temperature=agent_data.temperature,
        max_tokens=agent_data.max_tokens,
        top_p=agent_data.top_p,
        tools=agent_data.tools or [],
        tenant_id=tenant_id,
    )
    db.add(new_agent)
    db.commit()
    db.refresh(new_agent)

    return new_agent


def get_all_agents_service(db, tenant_id):
    return db.query(Agent).filter(Agent.tenant_id == tenant_id).all()


def get_agent_service(db, agent_id, tenant_id):
    return db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.tenant_id == tenant_id,
    ).first()


def update_agent_service(db, agent_id, agent_data, tenant_id):
    agent = get_agent_service(db, agent_id, tenant_id)

    if agent is None:
        return None

    agent.name = agent_data.name
    agent.role = agent_data.role
    agent.language = agent_data.language
    agent.description = agent_data.description
    agent.system_prompt = agent_data.system_prompt
    agent.model_name = agent_data.model_name
    agent.temperature = agent_data.temperature
    agent.max_tokens = agent_data.max_tokens
    agent.top_p = agent_data.top_p
    if agent_data.tools is not None:
        agent.tools = agent_data.tools

    db.commit()
    db.refresh(agent)

    return agent


def is_valid_status_transition(
    current_status: AgentStatus,
    new_status: AgentStatus,
) -> bool:

    allowed_transitions = {
        AgentStatus.DRAFT: {
            AgentStatus.ACTIVE,
        },
        AgentStatus.ACTIVE: {
            AgentStatus.PAUSED,
            AgentStatus.ARCHIVED,
        },
        AgentStatus.PAUSED: {
            AgentStatus.ACTIVE,
            AgentStatus.ARCHIVED,
        },
        AgentStatus.ARCHIVED: set(),
    }

    return new_status in allowed_transitions[current_status]


def update_agent_status_service(db, agent_id, status, tenant_id):
    agent = get_agent_service(db, agent_id, tenant_id)

    if agent is None:
        return None

    if not is_valid_status_transition(agent.status, status):
        return "Invalid_transition"

    agent.status = status

    db.commit()
    db.refresh(agent)

    return agent


def delete_agent_service(db, agent_id, tenant_id):
    agent = get_agent_service(db, agent_id, tenant_id)

    if agent is None:
        return None

    db.delete(agent)
    db.commit()

    return agent


def run_agent_engine_service(
    db,
    agent_id,
    tenant_id,
    user_message,
    session_id: str | None = None,
    user_id: int | None = None,
):
    agent = get_agent_service(db, agent_id, tenant_id)

    if agent is None:
        return None

    if agent.status != AgentStatus.ACTIVE:
        return {
            "error": (
                f"Agent '{agent.name}' is not active "
                f"(status={agent.status.value}). Activate it before running."
            ),
            "status_code": 409,
        }

    max_iterations = _env_int("AGENT_MAX_ITERATIONS", 5)
    top_k = max(1, min(_env_int("RAG_TOP_K", 3), 20))
    threshold = _env_float("RAG_MIN_SCORE", 0.15)
    history_limit = max(1, min(_env_int("MEMORY_HISTORY_LIMIT", 20), 100))

    # Retrieve verified knowledge base chunks for this tenant.
    retrieved_chunks = search_knowledge_service(
        db=db,
        tenant_id=tenant_id,
        query=user_message,
        top_k=top_k,
        threshold=threshold,
    )

    effective_system_prompt = agent.system_prompt or ""
    if retrieved_chunks:
        grounding_context = build_grounded_context(retrieved_chunks)
        effective_system_prompt = f"{effective_system_prompt}\n\n{grounding_context}".strip()

    config = AgentConfig(
        model_name=agent.model_name,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        top_p=agent.top_p,
        system_prompt=effective_system_prompt,
        tools=agent.tools,
    )

    try:
        llm_client = create_llm_client(
            agent.model_name,
            temperature=agent.temperature,
            max_tokens=agent.max_tokens,
            top_p=agent.top_p,
        )
    except ValueError as exc:
        return {"error": str(exc), "status_code": 400}

    allowed_tools = agent.tools or []
    scoped_registry = default_registry.create_scoped_registry(allowed_tools)
    engine = AgentEngine(
        config,
        llm_client,
        tool_registry=scoped_registry,
        max_iterations=max_iterations,
    )

    # Every run is a session by default so memory works out of the box.
    session_id = session_id or uuid.uuid4().hex
    conversation = get_or_create_conversation(
        db=db,
        tenant_id=tenant_id,
        agent_id=agent_id,
        session_id=session_id,
        user_id=user_id,
    )
    conversation_history = get_conversation_history(
        db=db,
        conversation_id=conversation.id,
        tenant_id=tenant_id,
        limit=history_limit,
    )
    add_message(
        db=db,
        conversation_id=conversation.id,
        tenant_id=tenant_id,
        role="user",
        content=user_message,
    )

    try:
        result = engine.run(
            user_message=user_message,
            conversation_history=conversation_history,
        )
    except RuntimeError as exc:
        logger.warning(
            "agent_run_failed agent_id=%s tenant_id=%s error=%s",
            agent_id,
            tenant_id,
            exc,
        )
        return {"error": str(exc), "status_code": 502}

    add_message(
        db=db,
        conversation_id=conversation.id,
        tenant_id=tenant_id,
        role="assistant",
        content=result.get("response", ""),
    )

    result["session_id"] = session_id
    result["agent_id"] = agent_id
    if retrieved_chunks:
        result["citations"] = retrieved_chunks

    logger.info(
        "agent_run agent_id=%s tenant_id=%s session_id=%s steps=%d",
        agent_id,
        tenant_id,
        session_id,
        len(result.get("steps", [])),
    )

    return result
