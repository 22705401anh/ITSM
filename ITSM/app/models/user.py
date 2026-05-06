from sqlalchemy import String, Text, DateTime, Integer, ForeignKey, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List

from app.db import Base
from app.models.base import TimestampMixin, IsActiveMixin


class User(Base, TimestampMixin, IsActiveMixin):
    """User model for authentication and identity."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    profile_image: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="user", server_default="user")
    assigned_pages: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Profile and organization
    entity_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("entities.id"),
        nullable=True,
    )
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    location_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("locations.id"),
        nullable=True,
    )

    # Preferences
    language: Mapped[str] = mapped_column(String(10), default="en")
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")

    # Status tracking
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    ad_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Groups membership (many-to-many)
    groups: Mapped[List["Group"]] = relationship(
        "Group",
        secondary="user_groups",
        back_populates="users",
    )

    # Profiles (many-to-many)
    profiles: Mapped[List["Profile"]] = relationship(
        "Profile",
        secondary="user_profiles",
        back_populates="users",
    )

    __table_args__ = (
        Index("idx_user_entity_id", "entity_id"),
        Index("idx_user_location_id", "location_id"),
    )


class Group(Base, TimestampMixin, IsActiveMixin):
    """Group model for organizing users and permissions."""

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Members (many-to-many)
    users: Mapped[List["User"]] = relationship(
        "User",
        secondary="user_groups",
        back_populates="groups",
    )


class UserGroup(Base):
    """Many-to-many junction table between User and Group."""

    __tablename__ = "user_groups"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
    )


class Entity(Base, TimestampMixin, IsActiveMixin):
    """Entity model for organization hierarchy (company, branch, department)."""

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Hierarchy
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("entities.id"),
        nullable=True,
    )
    code: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)

    # Type can be: company, branch, department, business_unit
    entity_type: Mapped[str] = mapped_column(String(50), default="company")


class Location(Base, TimestampMixin, IsActiveMixin):
    """Location model for physical site information."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Parent hierarchy
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("locations.id"),
        nullable=True,
    )

    # Address info
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)


class Profile(Base, TimestampMixin, IsActiveMixin):
    """Profile model for role/permission templates."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Profile templates: Super Admin, Admin, Technician, Self-Service, Manager, Auditor
    profile_type: Mapped[str] = mapped_column(String(50), nullable=False)

    # Users with this profile (many-to-many)
    users: Mapped[List["User"]] = relationship(
        "User",
        secondary="user_profiles",
        back_populates="profiles",
    )

    # Permissions (one-to-many)
    permissions: Mapped[List["Permission"]] = relationship(
        "Permission",
        back_populates="profile",
        cascade="all, delete-orphan",
    )


class UserProfile(Base):
    """Many-to-many junction table between User and Profile."""

    __tablename__ = "user_profiles"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("profiles.id", ondelete="CASCADE"),
        primary_key=True,
    )


class Permission(Base, TimestampMixin):
    """Permission model for fine-grained access control."""

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Module/domain: ticket, problem, change, asset, contract, kb, admin, etc.
    module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Permission type
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # Examples: read, create, update, delete, assign, approve, export, configure

    # Description for admin UI
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship back to profile
    profile: Mapped["Profile"] = relationship("Profile", back_populates="permissions")

    __table_args__ = (
        Index("idx_permission_profile_module", "profile_id", "module"),
    )
