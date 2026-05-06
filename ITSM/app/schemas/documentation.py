"""Documentation schemas"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class ProblemResolutionCreate(BaseModel):
    """Create problem resolution"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    problem_category: str = Field(..., min_length=1, max_length=100)
    problem_description: str
    severity: str = Field(default="medium")  # low, medium, high, critical
    resolution_steps: str
    tools_used: Optional[str] = None
    issue_date: Optional[datetime] = None
    resolution_date: Optional[datetime] = None
    resolution_time: Optional[str] = None
    tags: Optional[str] = None
    keywords: Optional[str] = None
    related_problem_id: Optional[int] = None
    reference_links: Optional[str] = None
    resolved_by: int = 1  # Default to admin user for now


class ProblemResolutionResponse(BaseModel):
    """Problem resolution response"""
    id: int
    title: str
    description: Optional[str]
    problem_category: str
    problem_description: str
    severity: str
    resolution_steps: str
    tools_used: Optional[str]
    issue_date: Optional[datetime]
    resolution_date: Optional[datetime]
    resolution_time: Optional[str]
    resolved_by: int
    tags: Optional[str]
    keywords: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class GeneralDocumentCreate(BaseModel):
    """Create general document"""
    title: str = Field(..., min_length=1, max_length=255)
    content: str
    document_type: str = Field(..., min_length=1, max_length=100)
    category: Optional[str] = None
    version: str = "1.0"
    status: str = "draft"
    is_confidential: bool = False
    effective_date: Optional[datetime] = None
    review_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    tags: Optional[str] = None
    keywords: Optional[str] = None
    author_id: int = 1  # Default to admin user for now


class GeneralDocumentResponse(BaseModel):
    """General document response"""
    id: int
    title: str
    content: str
    document_type: str
    category: Optional[str]
    author_id: int
    version: str
    status: str
    is_confidential: bool
    effective_date: Optional[datetime]
    review_date: Optional[datetime]
    expiry_date: Optional[datetime]
    tags: Optional[str]
    keywords: Optional[str]
    approved_by: Optional[int]
    approval_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class DocumentAttachmentResponse(BaseModel):
    """Document attachment response"""
    id: int
    filename: str
    file_type: str
    file_size: int
    description: Optional[str]
    uploaded_by: int
    created_at: datetime

    class Config:
        from_attributes = True
