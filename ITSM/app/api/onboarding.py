from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.dependencies import check_permission
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

from app.db import get_db
from app.models.onboarding import OnboardingRequest, OnboardingApproval, OnboardingTask
from app.models.user import User

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"], dependencies=[Depends(check_permission("onboarding"))])

# --- Pydantic Schemas ---
class RequestCreate(BaseModel):
    first_name: str
    last_name: str
    job_title: str
    department: Optional[str] = None
    cost_center: Optional[str] = None
    location: Optional[str] = None
    start_date: datetime
    employment_type: str
    manager_id: Optional[int] = None
    manager_name: Optional[str] = None
    manager_email: Optional[str] = None

class ApprovalCreate(BaseModel):
    hardware_selections: List[str] = []
    software_selections: List[str] = []
    access_selections: List[str] = []
    comments: Optional[str] = None

# --- Helpers ---
def generate_provisioning_tasks(db: Session, request: OnboardingRequest, approval: OnboardingApproval):
    # Base task: AD Account
    db.add(OnboardingTask(
        request_id=request.id,
        task_type="account",
        title=f"Create AD Account for {request.first_name} {request.last_name}",
        assigned_group="IAM"
    ))
    
    # Base task: Email
    db.add(OnboardingTask(
        request_id=request.id,
        task_type="account",
        title=f"Create Mailbox for {request.first_name} {request.last_name}",
        assigned_group="Workplace"
    ))

    if approval.hardware_selections:
        for hw in approval.hardware_selections:
            db.add(OnboardingTask(
                request_id=request.id,
                task_type="hardware",
                title=f"Provision Hardware: {hw}",
                assigned_group="Workplace"
            ))
            
    if approval.software_selections:
        for sw in approval.software_selections:
            db.add(OnboardingTask(
                request_id=request.id,
                task_type="software",
                title=f"Assign License & Install: {sw}",
                assigned_group="Workplace"
            ))
            
    if approval.access_selections:
        for acc in approval.access_selections:
            db.add(OnboardingTask(
                request_id=request.id,
                task_type="access",
                title=f"Grant Access: {acc}",
                assigned_group="IAM"
            ))
    db.commit()


# --- API Endpoints ---
@router.post("/request")
def create_onboarding_request(req: RequestCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    new_req = OnboardingRequest(
        first_name=req.first_name,
        last_name=req.last_name,
        job_title=req.job_title,
        department=req.department,
        cost_center=req.cost_center,
        location=req.location,
        start_date=req.start_date,
        employment_type=req.employment_type,
        manager_id=req.manager_id,
        manager_name=req.manager_name,
        manager_email=req.manager_email,
        status="Manager Approval"
    )
    db.add(new_req)
    db.commit()
    db.refresh(new_req)
    
    # Send email/notification to Manager
    if req.manager_email:
        from app.services.email_service import send_manager_approval_email
        employee_full_name = f"{req.first_name} {req.last_name}"
        background_tasks.add_task(
            send_manager_approval_email,
            manager_email=req.manager_email,
            manager_name=req.manager_name,
            request_id=new_req.id,
            employee_name=employee_full_name
        )
        
    return {"status": "success", "request_id": new_req.id}


@router.post("/{req_id}/approve")
def approve_request(req_id: int, approval_data: ApprovalCreate, db: Session = Depends(get_db)):
    # Hardcoding approved_by_id to 1 for MVP if no auth
    req = db.query(OnboardingRequest).filter(OnboardingRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    if req.status != "Manager Approval":
        raise HTTPException(status_code=400, detail="Request is not pending manager approval")

    approval = OnboardingApproval(
        request_id=req_id,
        hardware_selections=approval_data.hardware_selections,
        software_selections=approval_data.software_selections,
        access_selections=approval_data.access_selections,
        comments=approval_data.comments,
        approved_by_id=1 # Mock current user
    )
    db.add(approval)
    
    req.status = "IT Provisioning"
    req.approved_at = datetime.utcnow()
    db.commit()
    
    # Generate tasks
    generate_provisioning_tasks(db, req, approval)
    
    return {"status": "success", "message": "Request approved, IT tasks generated."}


@router.post("/task/{task_id}/complete")
def complete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(OnboardingTask).filter(OnboardingTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    task.status = "Completed"
    task.completed_at = datetime.utcnow()
    task.completed_by_id = 1 # Mock current user
    db.commit()
    
    # Check if all tasks for this request are completed
    pending_tasks = db.query(OnboardingTask).filter(
        OnboardingTask.request_id == task.request_id,
        OnboardingTask.status != "Completed"
    ).count()
    
    if pending_tasks == 0:
        req = db.query(OnboardingRequest).filter(OnboardingRequest.id == task.request_id).first()
        req.status = "Completed"
        req.completed_at = datetime.utcnow()
        db.commit()
        
    return {"status": "success", "message": "Task marked as completed."}

@router.get("/requests")
def get_all_requests(db: Session = Depends(get_db)):
    reqs = db.query(OnboardingRequest).order_by(OnboardingRequest.id.desc()).all()
    return {"items": [
        {
            "id": r.id,
            "employee_name": f"{r.first_name} {r.last_name}",
            "job_title": r.job_title,
            "department": r.department or "N/A",
            "cost_center": r.cost_center,
            "status": r.status,
            "start_date": r.start_date.isoformat(),
            "submitted_at": r.submitted_at.isoformat()
        } for r in reqs
    ]}

@router.get("/{req_id}")
def get_request_detail(req_id: int, db: Session = Depends(get_db)):
    req = db.query(OnboardingRequest).filter(OnboardingRequest.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
        
    return {
        "id": req.id,
        "employee_name": f"{req.first_name} {req.last_name}",
        "first_name": req.first_name,
        "last_name": req.last_name,
        "job_title": req.job_title,
        "department": req.department,
        "cost_center": req.cost_center,
        "location": req.location,
        "start_date": req.start_date.isoformat(),
        "employment_type": req.employment_type,
        "manager_name": req.manager_name,
        "status": req.status,
        "submitted_at": req.submitted_at.isoformat(),
        "tasks": [
            {
                "id": t.id,
                "task_type": t.task_type,
                "title": t.title,
                "assigned_group": t.assigned_group,
                "status": t.status,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None
            } for t in req.tasks
        ] if req.tasks else []
    }
