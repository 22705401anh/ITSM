"""Documentation models for Problem Resolution and General Documentation"""
from sqlalchemy import String, Integer, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from typing import Optional

from app.db import Base
from app.models.base import TimestampMixin, IsActiveMixin


class ProblemResolution(Base, TimestampMixin, IsActiveMixin):
    """Problem Resolution Documentation model"""

    __tablename__ = "problem_resolutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Basic info
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Problem details
    problem_category: Mapped[str] = mapped_column(String(100), nullable=False)
    problem_description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(50), default="medium")  # low, medium, high, critical

    # Resolution details
    resolution_steps: Mapped[str] = mapped_column(Text, nullable=False)  # Rich text/HTML
    tools_used: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array

    # Timeline
    issue_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolution_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolution_time: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g., "2 hours"

    # Author & Tags
    resolved_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # CSV or JSON
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="documented")  # documented, verified, archived

    # References
    related_problem_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reference_links: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class DocumentAttachment(Base, TimestampMixin):
    """Attachment for Documentation"""

    __tablename__ = "documentation_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Relationship
    problem_resolution_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("problem_resolutions.id"), nullable=True)
    documentation_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("general_documents.id"), nullable=True)

    # File info
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # image, pdf, doc, excel, etc.
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)  # in bytes

    # Description
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Upload info
    uploaded_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)


class GeneralDocument(Base, TimestampMixin, IsActiveMixin):
    """General Documentation model (Audits, Reports, etc.)"""

    __tablename__ = "general_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Basic info
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Rich text/HTML

    # Document type
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)  # audit, report, policy, changelog, etc.
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Details
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0")

    # Status
    status: Mapped[str] = mapped_column(String(50), default="draft")  # draft, published, archived
    is_confidential: Mapped[bool] = mapped_column(Boolean, default=False)

    # Dates
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Tags
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # CSV or JSON
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Approval
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    approval_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
