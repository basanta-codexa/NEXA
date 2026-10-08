from models import Agent, AgentStatus
from engine.agent_engine import AgentEngine
from schemas import AgentConfig

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
    tenant_id, user_message
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
    engine = AgentEngine(config, llm_client)
    try:
        return engine.run(user_message)
    except RuntimeError as e:
        return {
            "error" : str(e)
        }