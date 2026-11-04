import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models import AgentStatus

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CreateAgent(BaseModel):
    name: str = Field(min_length=1, max_length=100, strip_whitespace=True)
    role: str = Field(min_length=1, max_length=100)
    language: str = Field(min_length=2, max_length=50)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=4000)
    model_name: str | None = Field(default=None, min_length=3, max_length=100)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=50, le=128_000)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    tools: list[str] | None = Field(default=None, max_length=50)


class UpdateAgent(BaseModel):
    name: str = Field(min_length=1, max_length=100, strip_whitespace=True)
    role: str = Field(min_length=1, max_length=100)
    language: str = Field(min_length=2, max_length=50)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=4000)
    model_name: str | None = Field(default=None, min_length=3, max_length=100)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=50, le=128_000)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    tools: list[str] | None = Field(default=None, max_length=50)


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
    tools: list[str] | None = None
    tenant_id: int

    model_config = ConfigDict(from_attributes=True)


class AgentListResponse(BaseModel):
    agents: list[AgentResponse]


class CreateSignupInvite(BaseModel):
    description: str | None = Field(default=None, max_length=255)
    expires_in_days: int = Field(default=7, ge=0, le=365)


class CreateTenant(BaseModel):
    name: str = Field(min_length=1, max_length=100, strip_whitespace=True)
    description: str = Field(default="", max_length=255)
    admin_email: str | None = Field(default=None, max_length=100)
    admin_password: str | None = Field(default=None, min_length=8, max_length=128)
    invite_code: str = Field(min_length=1, max_length=256, strip_whitespace=True)

    @field_validator("admin_email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return _validate_email(value)

    @model_validator(mode="after")
    def validate_admin_pair(self):
        if bool(self.admin_email) != bool(self.admin_password):
            raise ValueError(
                "admin_email and admin_password must be provided together."
            )
        return self


class CreateUser(BaseModel):
    email: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="member", min_length=1, max_length=100)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


def _validate_email(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not _EMAIL_PATTERN.match(cleaned):
        raise ValueError("Enter a valid email address.")
    return cleaned


class AgentConfig(BaseModel):
    model_name: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    system_prompt: str | None = None
    tools: list[str] | None = None


class AgentRunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000, strip_whitespace=True)
    session_id: str | None = Field(default=None, min_length=1, max_length=64)


class CreateDocument(BaseModel):
    title: str = Field(min_length=1, max_length=255, strip_whitespace=True)
    content: str = Field(min_length=1, max_length=2_000_000, strip_whitespace=True)


class DocumentChunkResponse(BaseModel):
    id: int
    chunk_index: int
    content: str

    model_config = ConfigDict(from_attributes=True)


class DocumentSummaryResponse(BaseModel):
    id: int
    tenant_id: int
    title: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(DocumentSummaryResponse):
    content: str


class DocumentDetailResponse(DocumentResponse):
    chunks: list[DocumentChunkResponse]


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummaryResponse]


class RAGSearchResult(BaseModel):
    chunk_id: int
    document_id: int
    title: str
    chunk_index: int = 0
    content: str
    similarity: float
