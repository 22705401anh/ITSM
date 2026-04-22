"""Asset management API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
import logging
from datetime import datetime

from app.db import get_db
from app.schemas.asset import (
    AssetCreate, AssetUpdate, AssetResponse,
    AssetType, AssetStatus,
    LicenseCreate, LicenseResponse, LicenseAccessHistoryResponse,
    MaintenanceCreate, MaintenanceResponse
)
from app.models.asset import Asset, AssetMaintenance, LicenseRegistration, LicenseAccessHistory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assets", tags=["assets"])


# ============ ASSET MANAGEMENT ============

from app.models.hardware import PC, Monitor, DockingStation, Phone
from app.models.user import User

@router.get("/")
async def list_assets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    asset_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """List all assets with filtering and search, now combining hardware models"""
    logger.info(f"list_assets called with asset_type={asset_type}, status={status}, search={search}")
    try:
        # We will build virtual bundles per user, plus unassigned hardware
        results = []

        try:
            users = db.query(User).all()
        except Exception as e:
            logger.error(f"Error querying users: {str(e)}")
            users = []

        logger.info(f"Found {len(users)} users")
        id_counter = 1

        for u in users:
            try:
                pcs = db.query(PC).filter(PC.current_user_id == u.id).all()
                monitors = db.query(Monitor).filter(Monitor.current_user_id == u.id).all()
                docks = db.query(DockingStation).filter(DockingStation.current_user_id == u.id).all()
                phones = db.query(Phone).filter(Phone.current_user_id == u.id).all()

                pc = pcs[0] if pcs else None
                monitor = monitors[0] if monitors else None
                dock = docks[0] if docks else None
                phone = phones[0] if phones else None

                specs = {
                    "department": getattr(u, 'department', '') or "",
                    "hostname": pc.name if pc else "",
                    "laptop_model": pc.model if pc else "",
                    "laptop_sn": pc.serial_number if pc else "",
                    "monitor_model": monitor.model if monitor else "",
                    "monitor_sn": monitor.serial_number if monitor else "",
                    "docking_sn": dock.serial_number if dock else "",
                    "phone_model": phone.model if phone else "",
                    "phone_number": phone.phone_number if phone else "",
                    "accessories": ""
                }

                bundle = {
                    "id": 1000000 + (pc.id if pc else (monitor.id if monitor else id_counter)),
                    "name": u.full_name,
                    "description": "",
                    "asset_type": "computer" if pc else "other",
                    "status": "in_use" if (pcs or monitors or docks or phones) else "available",
                    "asset_tag": str(u.id),  # Using user ID as asset tag for the UI
                    "serial_number": pc.serial_number if pc else "",
                    "model_number": pc.model if pc else "",
                    "manufacturer": "",
                    "location": "",
                    "assigned_user_id": u.id,
                    "purchase_date": None,
                    "purchase_cost": None,
                    "warranty_expiry": None,
                    "depreciation_rate": None,
                    "specifications": str(specs).replace("'", '"'), # Send as JSON string approximation
                    "license_key": None,
                    "license_expiry": None,
                    "end_of_life_date": None,
                    "notes": "",
                    "is_active": True,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                results.append(bundle)
                id_counter += 1
            except Exception as e:
                logger.error(f"Error processing user {u.id}: {str(e)}")
                continue

        # Include unassigned PCs
        unassigned_pcs = db.query(PC).filter(PC.current_user_id == None).all()
        for pc in unassigned_pcs:
            try:
                specs = {"laptop_model": pc.model, "laptop_sn": pc.serial_number, "hostname": pc.name}
                bundle = {
                    "id": 1000000 + pc.id, 
                    "name": "Unassigned PC", 
                    "description": "", 
                    "asset_type": "computer",
                    "status": "available", 
                    "asset_tag": f"PC-{pc.id}", 
                    "serial_number": pc.serial_number,
                    "model_number": pc.model, 
                    "manufacturer": "", 
                    "location": "", 
                    "assigned_user_id": None,
                    "purchase_date": None, 
                    "purchase_cost": None, 
                    "warranty_expiry": None, 
                    "depreciation_rate": None,
                    "specifications": str(specs).replace("'", '"'), 
                    "license_key": None, 
                    "license_expiry": None,
                    "end_of_life_date": None, 
                    "notes": "", 
                    "is_active": True, 
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                results.append(bundle)
            except Exception as e:
                logger.error(f"Error processing PC {pc.id}: {str(e)}")
                continue

        # Include legacy manual assets
        try:
            legacy_assets = db.query(Asset).filter(Asset.is_active == True).all()
            for la in legacy_assets:
                bundle = {
                    "id": la.id, 
                    "name": la.name, 
                    "description": la.description, 
                    "asset_type": la.asset_type,
                    "status": la.status, 
                    "asset_tag": la.asset_tag, 
                    "serial_number": la.serial_number,
                    "model_number": la.model_number, 
                    "manufacturer": la.manufacturer, 
                    "location": la.location, 
                    "assigned_user_id": la.assigned_user_id,
                    "purchase_date": la.purchase_date.isoformat() if la.purchase_date else None, 
                    "purchase_cost": la.purchase_cost, 
                    "warranty_expiry": la.warranty_expiry.isoformat() if la.warranty_expiry else None, 
                    "depreciation_rate": la.depreciation_rate,
                    "specifications": la.specifications, 
                    "license_key": la.license_key, 
                    "license_expiry": la.license_expiry.isoformat() if la.license_expiry else None,
                    "end_of_life_date": la.end_of_life_date.isoformat() if la.end_of_life_date else None, 
                    "notes": la.notes, 
                    "is_active": la.is_active, 
                    "created_at": la.created_at.isoformat() if la.created_at else datetime.utcnow().isoformat(),
                    "updated_at": la.updated_at.isoformat() if la.updated_at else datetime.utcnow().isoformat()
                }
                results.append(bundle)
        except Exception as e:
            logger.error(f"Error processing legacy assets: {str(e)}")

        return results
    except Exception as e:
        logger.error(f"Error in list_assets: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error loading assets: {str(e)}")


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
):
    """Get specific asset details"""
    if asset_id >= 1000000:
        raise HTTPException(status_code=404, detail="Hardware bundle pseudo-record is not found in Asset table")

    asset = db.query(Asset).filter(Asset.id == asset_id, Asset.is_active == True).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.post("/", response_model=AssetResponse, status_code=201)
async def create_asset(
    asset_create: AssetCreate,
    db: Session = Depends(get_db),
):
    """Create a new asset"""
    try:
        # Check if asset tag already exists and is active
        existing = db.query(Asset).filter(Asset.asset_tag == asset_create.asset_tag, Asset.is_active == True).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Asset tag {asset_create.asset_tag} already exists"
            )

        asset = Asset(
            **asset_create.model_dump()
        )
        db.add(asset)
        db.flush()

        # Synchronize with Hardware Stock tables for new UI
        from app.models.hardware import PC, Monitor, DockingStation, Phone
        stock_model = None
        sn = asset_create.serial_number or asset_create.asset_tag
        hw_status = "Available" if asset_create.status == "available" else "Assigned"

        if asset_create.asset_type in [AssetType.COMPUTER, AssetType.LAPTOP]:
            stock_model = PC(
                name=asset_create.name,
                serial_number=sn,
                model=asset_create.model_number,
                status=hw_status,
                notes="Created via Inventory"
            )
        elif asset_create.asset_type == AssetType.MONITOR:
            stock_model = Monitor(
                serial_number=sn,
                model=asset_create.model_number,
                status=hw_status,
                notes="Created via Inventory"
            )
        elif asset_create.asset_type == AssetType.PHONE:
            stock_model = Phone(
                serial_number=sn,
                phone_number=None,
                model=asset_create.model_number,
                status=hw_status,
                notes="Created via Inventory"
            )
        # Assuming asset type might be passed as string 'docking' from UI even if not in enum sometimes
        elif str(asset_create.asset_type) == "docking":
            stock_model = DockingStation(
                serial_number=sn,
                model=asset_create.model_number,
                status=hw_status,
                notes="Created via Inventory"
            )

        if stock_model:
            db.add(stock_model)

        db.commit()
        db.refresh(asset)

        logger.info(f"Asset created: {asset.name} ({asset.asset_tag})")
        return asset

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating asset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: int,
    asset_update: AssetUpdate,
    db: Session = Depends(get_db),
):
    """Update an asset"""
    if asset_id >= 1000000:
        raise HTTPException(status_code=400, detail="Cannot edit Excel-imported hardware from this form.")

    try:
        asset = db.query(Asset).filter(Asset.id == asset_id).first()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        # Update only provided fields
        update_data = asset_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(asset, field, value)

        db.commit()
        db.refresh(asset)

        logger.info(f"Asset updated: {asset.name}")
        return asset

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating asset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
):
    """Soft delete an asset"""
    if asset_id >= 1000000:
        raise HTTPException(status_code=400, detail="Hardware bundles imported from Excel cannot be deleted here yet.")

    try:
        asset = db.query(Asset).filter(Asset.id == asset_id).first()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        asset.is_active = False
        asset.asset_tag = f"{asset.asset_tag}_deleted_{asset.id}"
        db.commit()

        logger.info(f"Asset deleted: {asset.name}")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting asset: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tag/{asset_tag}", response_model=AssetResponse)
async def get_asset_by_tag(
    asset_tag: str,
    db: Session = Depends(get_db),
):
    """Get asset by tag"""
    asset = db.query(Asset).filter(
        Asset.asset_tag == asset_tag,
        Asset.is_active == True
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


# ============ MAINTENANCE MANAGEMENT ============

@router.post("/{asset_id}/maintenance", response_model=MaintenanceResponse, status_code=201)
async def record_maintenance(
    asset_id: int,
    maintenance: MaintenanceCreate,
    db: Session = Depends(get_db),
):
    """Record maintenance for an asset"""
    try:
        # Verify asset exists
        asset = db.query(Asset).filter(Asset.id == asset_id).first()
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")

        maintenance_record = AssetMaintenance(
            asset_id=asset_id,
            **maintenance.model_dump(exclude={'asset_id'})
        )
        db.add(maintenance_record)
        db.commit()
        db.refresh(maintenance_record)

        logger.info(f"Maintenance recorded for asset {asset_id}")
        return maintenance_record

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error recording maintenance: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{asset_id}/maintenance", response_model=List[MaintenanceResponse])
async def get_asset_maintenance(
    asset_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Get maintenance history for an asset"""
    # Verify asset exists
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    records = db.query(AssetMaintenance).filter(
        AssetMaintenance.asset_id == asset_id
    ).order_by(AssetMaintenance.maintenance_date.desc()).offset(skip).limit(limit).all()

    return records


# ============ LICENSE MANAGEMENT ============

@router.post("/licenses", response_model=LicenseResponse, status_code=201)
async def create_license(
    license_create: LicenseCreate,
    db: Session = Depends(get_db),
):
    """Register a new license"""
    try:
        # Check if license key already exists
        existing = db.query(LicenseRegistration).filter(
            LicenseRegistration.license_key == license_create.license_key
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="License key already registered")

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
        logger.error(f"Error registering license: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/licenses", response_model=List[LicenseResponse])
async def list_licenses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List all registered licenses"""
    licenses = db.query(LicenseRegistration).filter(
        LicenseRegistration.is_active == True
    ).offset(skip).limit(limit).all()
    return licenses


@router.get("/licenses/{license_id}", response_model=LicenseResponse)
async def get_license(
    license_id: int,
    db: Session = Depends(get_db),
):
    """Get specific license details"""
    license_reg = db.query(LicenseRegistration).filter(
        LicenseRegistration.id == license_id,
        LicenseRegistration.is_active == True
    ).first()
    if not license_reg:
        raise HTTPException(status_code=404, detail="License not found")
    return license_reg


@router.put("/licenses/{license_id}", response_model=LicenseResponse)
async def update_license(
    license_id: int,
    license_update: LicenseCreate,
    db: Session = Depends(get_db),
):
    """Update license information"""
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


@router.post("/licenses/{license_id}/allocate")
async def allocate_license(
    license_id: int,
    count: int = Query(..., ge=1),
    db: Session = Depends(get_db),
):
    """Allocate licenses"""
    try:
        license_reg = db.query(LicenseRegistration).filter(
            LicenseRegistration.id == license_id
        ).first()
        if not license_reg:
            raise HTTPException(status_code=404, detail="License not found")

        available = license_reg.total_licenses - license_reg.used_licenses
        if available < count:
            raise HTTPException(
                status_code=400,
                detail=f"Only {available} licenses available"
            )

        license_reg.used_licenses += count
        db.commit()

        logger.info(f"Allocated {count} licenses from {license_reg.license_name}")
        return {
            "message": "Licenses allocated successfully",
            "allocated": count,
            "remaining": license_reg.total_licenses - license_reg.used_licenses
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error allocating licenses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ STATISTICS ============

@router.get("/stats/summary", tags=["assets"])
async def get_asset_statistics(
    db: Session = Depends(get_db),
):
    """Get asset management statistics"""
    try:
        total_assets = db.query(Asset).filter(Asset.is_active == True).count()

        by_type = {}
        for asset_type in AssetType:
            count = db.query(Asset).filter(
                Asset.asset_type == asset_type,
                Asset.is_active == True
            ).count()
            by_type[asset_type.value] = count

        by_status = {}
        for asset_status in AssetStatus:
            count = db.query(Asset).filter(
                Asset.status == asset_status,
                Asset.is_active == True
            ).count()
            by_status[asset_status.value] = count

        total_licenses = db.query(LicenseRegistration).filter(
            LicenseRegistration.is_active == True
        ).count()

        return {
            "total_assets": total_assets,
            "by_type": by_type,
            "by_status": by_status,
            "total_licenses": total_licenses,
        }

    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

