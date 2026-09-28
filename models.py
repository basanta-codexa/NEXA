from sqlalchemy.orm import declarative_base, sessionmaker, mapped_column, Mapped, relationship

from sqlalchemy import String, ForeignKey

Base = declarative_base()


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255), nullable=True)

    agents: Mapped[list["Agent"]] = relationship(back_populates="tenant")
    users: Mapped[list["User"]] = relationship(back_populates="tenant")


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
    tenant_id: Mapped[int] = mapped_column(ForeignKey(
        "tenants.id"), nullable=False)  # Foreign key to Tenant
    tenant: Mapped["Tenant"] = relationship(back_populates="users")


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(50))
    tenant_id: Mapped[int] = mapped_column(ForeignKey(
        "tenants.id"), nullable=False)  # Foreign key to Tenant
    tenant: Mapped["Tenant"] = relationship(back_populates="agents")
