from fastapi import APIRouter, Depends, HTTPException

from database import get_db
from models import Agent
from schemas import CreateAgent, UpdateAgent, AgentResponse, AgentListResponse

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


@router.post("", response_model=AgentResponse)
def create_agent(agent: CreateAgent, db=Depends(get_db), tenant_id: int = Depends(get_current_tenant_id), current_user=Depends(require_permission(Permissions.AGENT_CREATE))):

    new_agent = create_agent_service(db, agent, tenant_id)

    return new_agent


@router.get("", response_description=AgentListResponse)
def get_agents(db=Depends(get_db), tenant_id: int = Depends(get_current_tenant_id), current_user=Depends(require_permission(Permissions.AGENT_READ))):

    agents = get_all_agents_service(db, tenant_id)

    return {
        "agents": agents
    }


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: int,
    db=Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id), current_user=Depends(require_permission(Permissions.AGENT_READ))
):

    existing_agent = get_agent_service(db, agent_id, tenant_id)

    if existing_agent is None:
        raise HTTPException(
            status_code=404,
            detail="Agent not found"
        )

    return existing_agent


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: int,
    agent: UpdateAgent,
    db=Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id), current_user=Depends(require_permission(Permissions.AGENT_UPDATE))
):

    existing_agent = update_agent_service(db, agent_id, agent, tenant_id)

    if existing_agent is None:
        raise HTTPException(
            status_code=404,
            detail="Agent not found"
        )

    return existing_agent



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

    return {
        "message": "Agent deleted successfully!"
    }
