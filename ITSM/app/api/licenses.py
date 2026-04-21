"""License API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.db import get_db
from app.models.asset import LicenseRegistration, LicenseAccessHistory
from app.schemas.asset import LicenseCreate, LicenseResponse, LicenseAccessHistoryResponse

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
                user_id=1,  # TODO: Get from current user
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

        return license_reg

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

    history = db.query(LicenseAccessHistory).filter(
        LicenseAccessHistory.license_id == license_id
    ).order_by(LicenseAccessHistory.created_at.desc()).offset(skip).limit(limit).all()

    return history
