from datetime import datetime, timezone
from sqlalchemy.orm import declarative_base, mapped_column, Mapped, relationship

from sqlalchemy import (
    String,
    ForeignKey,
    Table,
    Column,
    Enum,
    JSON,
    DateTime,
    Text,
    UniqueConstraint,
)
from enum import Enum as PyEnum

Base = declarative_base()

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id",
        ForeignKey("roles.id"),
        primary_key=True
    ),
    Column(
        "permission_id",
        ForeignKey("permissions.id"),
        primary_key=True
    )
)


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    roles: Mapped[list["Role"]] = relationship(
        secondary=role_permissions,
        back_populates="permissions"
    )


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True
    )

    tenant: Mapped["Tenant"] = relationship(
        back_populates="roles"
    )
    permissions: Mapped[list["Permission"]] = relationship(
        secondary=role_permissions,
        back_populates="roles"
    )


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255), nullable=True)

    agents: Mapped[list["Agent"]] = relationship(back_populates="tenant")
    users: Mapped[list["User"]] = relationship(back_populates="tenant")

    roles: Mapped[list["Role"]] = relationship(
        back_populates="tenant"
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="tenant"
    )
    documents: Mapped[list["Document"]] = relationship(
        back_populates="tenant"
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="member"
    )
    role_id: Mapped[int | None] = mapped_column(
        ForeignKey("roles.id"), nullable=True
    )
    role_obj: Mapped["Role | None"] = relationship()
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )  # Foreign key to Tenant
    tenant: Mapped["Tenant"] = relationship(back_populates="users")


class AgentStatus(str, PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(
        String(1000), nullable=True)
    # how predictable or creative the model's responses are
    temperature: Mapped[float | None] = mapped_column(
        nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(
        nullable=True 
    )
    # top_p controls how much of that probability distribution the model considers
    top_p: Mapped[float | None] = mapped_column(
        nullable=True
    )
    system_prompt : Mapped[str | None] = mapped_column(String(4000), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100),nullable=True)
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus),
        default=AgentStatus.DRAFT,
        nullable=False
    )
    tools: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
        default=list
    )

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )  # Foreign key to Tenant
    tenant: Mapped["Tenant"] = relationship(back_populates="agents")
    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "agent_id",
            "session_id",
            name="uq_conversations_tenant_agent_session",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    agent: Mapped["Agent"] = relationship(back_populates="conversations")
    tenant: Mapped["Tenant"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(String(50), nullable=False)  # "user", "assistant", "system", "tool"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")
