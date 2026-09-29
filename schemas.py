from pydantic import BaseModel, ConfigDict


class CreateAgent(BaseModel):
    name: str
    role: str
    language: str
    description: str | None = None


class UpdateAgent(BaseModel):
    name: str
    role: str
    language: str
    description: str | None = None


class AgentResponse(BaseModel):
    id: int
    name: str
    role: str
    language: str
    description: str | None = None
    tenant_id: int

    model_config= ConfigDict(from_attributes=True)

class AgentListResponse(BaseModel):
    agents : list[AgentResponse]

class CreateTenant(BaseModel):
    name: str
    description: str


class CreateUser(BaseModel):
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str
