from fastapi import APIRouter, Depends, HTTPException

from database import get_db
from models import Agent
from schemas import CreateAgent, UpdateAgent

from dependencies.tenant import get_current_tenant_id

from dependencies.roles import require_permission
from dependencies.permissions import Permissions

from services.agent_service import (
    create_agent_service, get_all_agents_service,
    get_agent_service, update_agent_service,
    delete_agent_service
)

router = APIRouter(
    prefix="/agents",
    tags=["Agents"]
)


@router.post("")
def create_agent(agent: CreateAgent, db=Depends(get_db), tenant_id: int = Depends(get_current_tenant_id), current_user=Depends(require_permission(Permissions.AGENT_CREATE))):

    new_agent = create_agent_service(db, agent, tenant_id)

    return {
        "message": "Agent created successfully!",
        "agent": {
            "id": new_agent.id,
            "name": new_agent.name,
            "role": new_agent.role,
            "language": new_agent.language,
            "tenant_id": new_agent.tenant_id
        }
    }


@router.get("")
def get_agents(db=Depends(get_db), tenant_id: int = Depends(get_current_tenant_id), current_user = Depends(require_permission(Permissions.AGENT_READ))):

    agents = get_all_agents_service(db, tenant_id)

    return {
        "agents": [
            {
                "id": agent.id,
                "name": agent.name,
                "role": agent.role,
                "language": agent.language,
                "tenant_id": agent.tenant_id
            }
            for agent in agents
        ]
    }


@router.get("/{agent_id}")
def get_agent(
    agent_id: int,
    db=Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id), current_user = Depends(require_permission(Permissions.AGENT_READ))
):

    existing_agent = get_agent_service(db, agent_id, tenant_id)

    if existing_agent is None:
        raise HTTPException(
            status_code=404,
            detail="Agent not found"
        )

    return {
        "id": existing_agent.id,
        "name": existing_agent.name,
        "role": existing_agent.role,
        "language": existing_agent.language,
        "tenant_id": existing_agent.tenant_id
    }


@router.put("/{agent_id}")
def update_agent(
    agent_id: int,
    agent: UpdateAgent,
    db=Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id), curent_user=Depends(require_permission(Permissions.AGENT_UPDATE))
):

    existing_agent = update_agent_service(db, agent_id, agent, tenant_id)

    if existing_agent is None:
        raise HTTPException(
            status_code=404,
            detail="Agent not found"
        )

    existing_agent.name = agent.name
    existing_agent.role = agent.role
    existing_agent.language = agent.language

    db.commit()
    db.refresh(existing_agent)

    return {
        "message": "Agent updated successfully!",
        "agent": {
            "id": existing_agent.id,
            "name": existing_agent.name,
            "role": existing_agent.role,
            "language": existing_agent.language,
            "tenant_id": existing_agent.tenant_id
        }
    }


@router.delete("/{agent_id}")
def delete_agent(
    agent_id: int,
    db=Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user=Depends(require_permission(Permissions.AGENT_DELETE))
):

    existing_agent = delete_agent_service(db, agent_id, tenant_id)

    if existing_agent is None:
        raise HTTPException(
            status_code=404,
            detail="Agent not found"
        )

    db.delete(existing_agent)
    db.commit()

    return {
        "message": "Agent deleted successfully!"
    }
