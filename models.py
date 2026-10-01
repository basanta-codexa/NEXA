from sqlalchemy.orm import declarative_base, mapped_column, Mapped, relationship

from sqlalchemy import String, ForeignKey, Table, Column, Enum
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

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id"),
        nullable=False
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
    tenant_id: Mapped[int] = mapped_column(ForeignKey(
        "tenants.id"), nullable=False)  # Foreign key to Tenant
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
    temperature: Mapped[float | None] = mapped_column(
        nullable=True)
    # how predictable or creative the model's responses are
    system_prompt : Mapped[str | None] = mapped_column(String(4000), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100),nullable=True)
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus),
        default=AgentStatus.DRAFT,
        nullable=False
    )

    tenant_id: Mapped[int] = mapped_column(ForeignKey(
        "tenants.id"), nullable=False)  # Foreign key to Tenant
    tenant: Mapped["Tenant"] = relationship(back_populates="agents")