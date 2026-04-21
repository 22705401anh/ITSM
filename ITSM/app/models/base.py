from datetime import datetime
from sqlalchemy import DateTime, Integer, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps to models."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )


class EntityScopedMixin:
    """Mixin for models that are scoped to an entity (company/department)."""

    entity_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )


class IsDeletedMixin:
    """Mixin for soft-delete support."""

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )


class IsActiveMixin:
    """Mixin for active/inactive status."""

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
