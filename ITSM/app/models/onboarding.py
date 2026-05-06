from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base
from app.models.base import TimestampMixin

class OnboardingRequest(Base, TimestampMixin):
    __tablename__ = "onboarding_requests"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    job_title = Column(String(100), nullable=False)
    department = Column(String(100), nullable=True)
    cost_center = Column(String(100), nullable=True)
    location = Column(String(100), nullable=True)
    start_date = Column(DateTime, nullable=False)
    employment_type = Column(String(50), nullable=False) # permanent, contractor, intern
    
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    manager_name = Column(String(255), nullable=True)
    manager_email = Column(String(255), nullable=True) # Fallback if ID not provided
    
    # Status: Draft -> Submitted -> Manager Approval -> IT Provisioning -> Completed
    status = Column(String(50), default="Submitted", index=True)
    
    # Tracking
    submitted_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    manager = relationship("User", foreign_keys=[manager_id])
    approval = relationship("OnboardingApproval", back_populates="request", uselist=False, cascade="all, delete-orphan")
    tasks = relationship("OnboardingTask", back_populates="request", cascade="all, delete-orphan")

class OnboardingApproval(Base, TimestampMixin):
    __tablename__ = "onboarding_approvals"
    
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("onboarding_requests.id"), nullable=False, unique=True)
    
    hardware_selections = Column(JSON, nullable=True) 
    software_selections = Column(JSON, nullable=True) 
    access_selections = Column(JSON, nullable=True)   
    
    comments = Column(Text, nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    request = relationship("OnboardingRequest", back_populates="approval")
    approved_by = relationship("User", foreign_keys=[approved_by_id])

class OnboardingTask(Base, TimestampMixin):
    __tablename__ = "onboarding_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("onboarding_requests.id"), nullable=False)
    
    task_type = Column(String(50), nullable=False) # account, license, hardware, software, access
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    assigned_group = Column(String(100), nullable=True) # Workplace, IAM, Network
    
    # Status: Pending -> Completed
    status = Column(String(50), default="Pending")
    
    completed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    request = relationship("OnboardingRequest", back_populates="tasks")
    completed_by = relationship("User", foreign_keys=[completed_by_id])
