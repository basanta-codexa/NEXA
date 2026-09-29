from models import Agent

def create_agent_service(db, agent_data, tenant_id):
    new_agent = Agent(
        name=agent_data.name,
        role=agent_data.role,
        language=agent_data.language,
        description= agent_data.description,
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