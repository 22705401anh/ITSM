"""License API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.db import get_db
from app.models.asset import LicenseRegistration, LicenseAccessHistory, LicenseAssignment
from app.models.user import User
from app.models.hardware import PC
from app.schemas.asset import LicenseCreate, LicenseResponse, LicenseAccessHistoryResponse, LicenseAssignmentCreate, LicenseAssignmentResponse
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/licenses", tags=["licenses"])


@router.post("", response_model=LicenseResponse, status_code=201)
async def create_license(
    license_create: LicenseCreate,
    db: Session = Depends(get_db),
):
    """Create a new license"""
    try:
        # Check if license key already exists
        existing = db.query(LicenseRegistration).filter(
            LicenseRegistration.license_key == license_create.license_key
        ).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="License key already registered"
            )

        license_reg = LicenseRegistration(**license_create.model_dump())
        db.add(license_reg)
        db.commit()
        db.refresh(license_reg)

        logger.info(f"License registered: {license_reg.license_name}")
        return license_reg

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating license: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[LicenseResponse])
async def list_licenses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List all licenses"""
    licenses = db.query(LicenseRegistration).filter(
        LicenseRegistration.is_active == True
    ).order_by(LicenseRegistration.created_at.desc()).offset(skip).limit(limit).all()
    return licenses


@router.get("/{license_id}", response_model=LicenseResponse)
async def get_license(
    license_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get license details and log access"""
    try:
        license_reg = db.query(LicenseRegistration).filter(
            LicenseRegistration.id == license_id,
            LicenseRegistration.is_active == True
        ).first()

        if not license_reg:
            raise HTTPException(status_code=404, detail="License not found")

        # Log license access
        try:
            client_ip = request.client.host if request.client else "unknown"
            user_agent = request.headers.get("user-agent", "unknown")

            access_log = LicenseAccessHistory(
                license_id=license_id,
                user_id=current_user.id,
                action="viewed",
                ip_address=client_ip,
                user_agent=user_agent
            )
            db.add(access_log)
            db.commit()
            logger.info(f"License {license_id} accessed by {client_ip}")
        except Exception as log_error:
            logger.warning(f"Could not log license access: {str(log_error)}")
            db.rollback()

        # Fetch active assignments
        active_assignments = db.query(LicenseAssignment).filter(
            LicenseAssignment.license_id == license_id,
            LicenseAssignment.status == "active"
        ).all()
        
        # Hydrate assignments with names
        hydrated_assignments = []
        for assgn in active_assignments:
            user_name = None
            pc_name = None
            if assgn.user_id:
                user = db.query(User).filter(User.id == assgn.user_id).first()
                if user:
                    user_name = user.full_name
            if assgn.pc_id:
                pc = db.query(PC).filter(PC.id == assgn.pc_id).first()
                if pc:
                    pc_name = pc.name or pc.model
            
            assgn_dict = {
                "id": assgn.id,
                "license_id": assgn.license_id,
                "user_id": assgn.user_id,
                "pc_id": assgn.pc_id,
                "assigned_by_id": assgn.assigned_by_id,
                "assigned_date": assgn.assigned_date,
                "status": assgn.status,
                "notes": assgn.notes,
                "user_name": user_name,
                "pc_name": pc_name
            }
            hydrated_assignments.append(assgn_dict)
            
        return {
            **license_reg.__dict__,
            "assignments": hydrated_assignments
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting license: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{license_id}", response_model=LicenseResponse)
async def update_license(
    license_id: int,
    license_update: LicenseCreate,
    db: Session = Depends(get_db),
):
    """Update license"""
    try:
        license_reg = db.query(LicenseRegistration).filter(
            LicenseRegistration.id == license_id
        ).first()

        if not license_reg:
            raise HTTPException(status_code=404, detail="License not found")

        for field, value in license_update.model_dump(exclude_unset=True).items():
            setattr(license_reg, field, value)

        db.commit()
        db.refresh(license_reg)

        logger.info(f"License updated: {license_reg.license_name}")
        return license_reg

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating license: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{license_id}", status_code=204)
async def delete_license(
    license_id: int,
    db: Session = Depends(get_db),
):
    """Delete license"""
    try:
        license_reg = db.query(LicenseRegistration).filter(
            LicenseRegistration.id == license_id
        ).first()

        if not license_reg:
            raise HTTPException(status_code=404, detail="License not found")

        license_reg.is_active = False
        db.commit()

        logger.info(f"License deleted: {license_reg.license_name}")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting license: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{license_id}/access-history", response_model=List[LicenseAccessHistoryResponse])
async def get_license_access_history(
    license_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get who viewed this license and when"""
    # Verify license exists
    license_reg = db.query(LicenseRegistration).filter(
        LicenseRegistration.id == license_id
    ).first()

    if not license_reg:
        raise HTTPException(status_code=404, detail="License not found")

    history_records = db.query(LicenseAccessHistory, User.full_name, User.username).join(
        User, LicenseAccessHistory.user_id == User.id, isouter=True
    ).filter(
        LicenseAccessHistory.license_id == license_id
    ).order_by(LicenseAccessHistory.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for h, full_name, username in history_records:
        h_dict = {c.name: getattr(h, c.name) for c in h.__table__.columns}
        h_dict['user_name'] = full_name or username or "System"
        result.append(h_dict)

    return result


@router.post("/{license_id}/assign", response_model=LicenseAssignmentResponse)
async def assign_license(
    license_id: int,
    assignment_data: LicenseAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Assign a license to a user or PC"""
    try:
        license_reg = db.query(LicenseRegistration).filter(
            LicenseRegistration.id == license_id,
            LicenseRegistration.is_active == True
        ).first()

        if not license_reg:
            raise HTTPException(status_code=404, detail="License not found")

        if not assignment_data.user_id and not assignment_data.pc_id:
            raise HTTPException(status_code=400, detail="Must assign to either a user or a PC")

        if license_reg.used_licenses >= license_reg.total_licenses:
            raise HTTPException(status_code=400, detail="No available licenses left")

        # Create assignment
        assignment = LicenseAssignment(
            license_id=license_id,
            user_id=assignment_data.user_id,
            pc_id=assignment_data.pc_id,
            notes=assignment_data.notes,
            assigned_by_id=current_user.id,
            status="active"
        )
        db.add(assignment)
        
        # Hydrate for response and history
        user_name = None
        pc_name = None
        if assignment.user_id:
            user = db.query(User).filter(User.id == assignment.user_id).first()
            if user:
                user_name = user.full_name or user.username
        if assignment.pc_id:
            pc = db.query(PC).filter(PC.id == assignment.pc_id).first()
            if pc:
                pc_name = pc.name or pc.model
                
        # Log to access history
        history = LicenseAccessHistory(
            license_id=license_id,
            user_id=current_user.id,
            action=f"Assigned to {user_name}" if user_name else f"Assigned to PC {pc_name}",
            ip_address="internal",
            user_agent="ITSM API"
        )
        db.add(history)
        
        # Increment used licenses
        license_reg.used_licenses += 1
        
        db.commit()
        db.refresh(assignment)
                
        return {
            "id": assignment.id,
            "license_id": assignment.license_id,
            "user_id": assignment.user_id,
            "pc_id": assignment.pc_id,
            "assigned_by_id": assignment.assigned_by_id,
            "assigned_date": assignment.assigned_date,
            "status": assignment.status,
            "notes": assignment.notes,
            "user_name": user_name,
            "pc_name": pc_name
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error assigning license: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/assignments/{assignment_id}/revoke", status_code=204)
async def revoke_license(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Revoke a license assignment"""
    try:
        assignment = db.query(LicenseAssignment).filter(
            LicenseAssignment.id == assignment_id,
            LicenseAssignment.status == "active"
        ).first()

        if not assignment:
            raise HTTPException(status_code=404, detail="Active assignment not found")

        assignment.status = "revoked"
        
        # Decrement used licenses
        license_reg = db.query(LicenseRegistration).filter(
            LicenseRegistration.id == assignment.license_id
        ).first()
        if license_reg and license_reg.used_licenses > 0:
            license_reg.used_licenses -= 1
            
        # Hydrate assignment details for history
        target_name = "Unknown"
        if assignment.user_id:
            user = db.query(User).filter(User.id == assignment.user_id).first()
            if user:
                target_name = user.full_name or user.username
        elif assignment.pc_id:
            pc = db.query(PC).filter(PC.id == assignment.pc_id).first()
            if pc:
                target_name = pc.name or pc.model
                
        # Log to access history
        history = LicenseAccessHistory(
            license_id=assignment.license_id,
            user_id=current_user.id,
            action=f"Revoked from {target_name}",
            ip_address="internal",
            user_agent="ITSM API"
        )
        db.add(history)
            
        db.commit()

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error revoking license assignment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
