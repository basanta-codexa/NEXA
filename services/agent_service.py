from models import Agent, AgentStatus
from engine.agent_engine import AgentEngine
from schemas import AgentConfig
from tools.default_registry import default_registry
from services.memory_service import (
    get_or_create_conversation,
    add_message,
    get_conversation_history
)

from llm.factory import create_llm_client

def create_agent_service(db, agent_data, tenant_id):
    new_agent = Agent(
        name=agent_data.name,
        role=agent_data.role,
        language=agent_data.language,
        description=agent_data.description,
        system_prompt=agent_data.system_prompt,
        model_name=agent_data.model_name,
        temperature = agent_data.temperature,
        max_tokens = agent_data.max_tokens,
        top_p = agent_data.top_p,
        tools = agent_data.tools or [],
        tenant_id=tenant_id
    )
    db.add(new_agent)

    db.commit()

    db.refresh(new_agent)

    return new_agent


def get_all_agents_service(db, tenant_id):
    agents = db.query(Agent).filter(Agent.tenant_id == tenant_id).all()
    return agents


def get_agent_service(db, agent_id, tenant_id):
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.tenant_id == tenant_id
    ).first()

    return agent


def update_agent_service(db, agent_id, agent_data, tenant_id):
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.tenant_id == tenant_id
    ).first()

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
    new_status: AgentStatus
) -> bool:

    allowed_transitions = {
        AgentStatus.DRAFT: {
            AgentStatus.ACTIVE
        },

        AgentStatus.ACTIVE: {
            AgentStatus.PAUSED,
            AgentStatus.ARCHIVED
        },

        AgentStatus.PAUSED: {
            AgentStatus.ACTIVE,
            AgentStatus.ARCHIVED
        },

        AgentStatus.ARCHIVED: set()
    }

    return new_status in allowed_transitions[current_status]


def update_agent_status_service(db, agent_id,  status, tenant_id):
    agent = db.query(Agent).filter(Agent.id == agent_id,
                                   Agent.tenant_id == tenant_id).first()

    if agent is None:
        return None

    if not is_valid_status_transition(agent.status, status):
        return "Invalid_transition"

    agent.status = status

    db.commit()
    db.refresh(agent)

    return agent


def delete_agent_service(db, agent_id, tenant_id):
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.tenant_id == tenant_id
    ).first()

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
    user_id: int | None = None
):
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.tenant_id == tenant_id
    ).first()

    if agent is None:
        return None

    config = AgentConfig(
        model_name=agent.model_name,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        top_p=agent.top_p,
        system_prompt=agent.system_prompt
    )
    try:
        llm_client = create_llm_client(agent.model_name)
    except ValueError as e:
        return {
            "error" : str(e)
        }
    allowed_tools = agent.tools or []
    scoped_registry = default_registry.create_scoped_registry(allowed_tools)
    engine = AgentEngine(config, llm_client, tool_registry=scoped_registry)

    # 1. Retrieve past conversation history if session_id is provided
    conversation = None
    conversation_history = None
    if session_id:
        conversation = get_or_create_conversation(
            db=db,
            tenant_id=tenant_id,
            agent_id=agent_id,
            session_id=session_id,
            user_id=user_id
        )
        conversation_history = get_conversation_history(
            db=db,
            conversation_id=conversation.id,
            tenant_id=tenant_id,
            limit=20
        )
        # Store user's incoming turn in database
        add_message(
            db=db,
            conversation_id=conversation.id,
            tenant_id=tenant_id,
            role="user",
            content=user_message
        )

    try:
        result = engine.run(
            user_message=user_message,
            conversation_history=conversation_history
        )
    except RuntimeError as e:
        return {
            "error" : str(e)
        }

    # 2. Persist assistant's final response in database
    if conversation and "response" in result:
        add_message(
            db=db,
            conversation_id=conversation.id,
            tenant_id=tenant_id,
            role="assistant",
            content=result["response"]
        )
        result["session_id"] = session_id

    return result