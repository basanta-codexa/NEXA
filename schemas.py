from pydantic import BaseModel, ConfigDict, Field
from models import AgentStatus


class CreateAgent(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100, strip_whitespace=True
    )
    role: str = Field(
        min_length=1,
        max_length=100
    )
    language: str = Field(
        min_length=2,
        max_length=50
    )
    description: str | None = Field(default=None, min_length=1, max_length=500)
    system_prompt: str | None = Field(
        default=None,
        min_length=1,
        max_length=4000
    )
    model_name: str | None = Field(default=None, min_length=3)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=50)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)


class UpdateAgent(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=100, strip_whitespace=True
    )
    role: str = Field(
        min_length=1,
        max_length=100
    )
    language: str = Field(
        min_length=2,
        max_length=50
    )
    description: str | None = Field(default=None, min_length=1, max_length=500)
    system_prompt: str | None = Field(
        default=None,
        min_length=1,
        max_length=4000
    )
    model_name: str | None = Field(default=None, min_length=3)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=50)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)


class UpdateAgentStatus(BaseModel):
    status: AgentStatus


class AgentResponse(BaseModel):
    id: int
    name: str
    role: str
    language: str
    description: str | None = None
    system_prompt: str | None = None
    model_name: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = None
    top_p: float | None = None
    status: AgentStatus
    tenant_id: int

    model_config = ConfigDict(from_attributes=True)


class AgentListResponse(BaseModel):
    agents: list[AgentResponse]


class CreateTenant(BaseModel):
    name: str
    description: str


class CreateUser(BaseModel):
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class AgentConfig(BaseModel):
    model_name: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    system_prompt: str | None = None


class AgentRunRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=5000,
        strip_whitespace=True
    )
