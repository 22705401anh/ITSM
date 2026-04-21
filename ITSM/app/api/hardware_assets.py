import os
import uuid
import json
import shutil
import pandas as pd
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from typing import List, Optional
from datetime import datetime

from app.db import get_db
from app.models.user import User
from app.models.hardware import PC, Monitor, DockingStation, Phone, AssetAssignment, StockAuditLog
from app.schemas.hardware import AssetAssignmentSchema

router = APIRouter(prefix="/hardware", tags=["Hardware Asset Tracking"])

# --- Upload directory setup ---
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "hardware")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}


def get_or_create_user(db: Session, full_name: str) -> User:
    user = db.query(User).filter(User.full_name == full_name).first()
    if not user:
        # Create a dummy user for now if missing, based on your logic
        user = User(
            username=full_name.lower().replace(" ", "_"), 
            email=f"{full_name.lower().replace(' ', '.')}@example.com",
            full_name=full_name,
            hashed_password="placeholder" # You will define proper auth
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def log_audit(db: Session, action: str, asset_type: str, asset_id: int,
              serial_number: str = None, model: str = None,
              performed_by: str = "System", details: str = None):
    """Create an audit log entry."""
    entry = StockAuditLog(
        action=action,
        asset_type=asset_type,
        asset_id=asset_id,
        serial_number=serial_number,
        model=model,
        performed_by=performed_by,
        details=details,
        created_at=datetime.utcnow()
    )
    db.add(entry)
    db.flush()


def assign_hardware(db: Session, hardware, new_user: User, asset_type: str, notes: str = None):
    # 1. Close current assignment if exists
    current_assignment_query = db.query(AssetAssignment).filter(
        getattr(AssetAssignment, f"{asset_type}_id") == hardware.id,
        AssetAssignment.is_active == True
    )

    current_assignment = current_assignment_query.first()
    previous_user_id = None

    if current_assignment:
        if current_assignment.new_user_id == new_user.id:
            return  # Already assigned to this user

        previous_user_id = current_assignment.new_user_id
        current_assignment.is_active = False
        current_assignment.returned_date = datetime.utcnow()

    # 2. Create new assignment history entry
    new_assignment = AssetAssignment(
        previous_user_id=previous_user_id,
        new_user_id=new_user.id,
        is_active=True,
        notes=notes
    )

    # Set the dynamic ID based on asset type
    setattr(new_assignment, f"{asset_type}_id", hardware.id)
    db.add(new_assignment)
    db.flush()

    # 3. Update current user on hardware table
    hardware.current_user_id = new_user.id
    hardware.status = "Assigned"
    db.add(hardware)
    db.flush()

    # 4. Log audit
    log_audit(db, "assigned", asset_type, hardware.id,
              serial_number=hardware.serial_number,
              model=hardware.model,
              details=f"Assigned to {new_user.full_name}" + (f" | Notes: {notes}" if notes else ""))


@router.get("/search")
async def global_asset_search(query: str, db: Session = Depends(get_db)):
    """Searches across all asset tables simultaneously."""
    search_term = f"%{query}%"

    pcs = db.query(PC).filter(or_(PC.serial_number.ilike(search_term), PC.name.ilike(search_term), PC.model.ilike(search_term))).all()
    monitors = db.query(Monitor).filter(or_(Monitor.serial_number.ilike(search_term), Monitor.model.ilike(search_term))).all()
    docks = db.query(DockingStation).filter(or_(DockingStation.serial_number.ilike(search_term), DockingStation.model.ilike(search_term))).all()
    phones = db.query(Phone).filter(or_(Phone.serial_number.ilike(search_term), Phone.phone_number.ilike(search_term), Phone.model.ilike(search_term))).all()

    return {
        "pcs": pcs,
        "monitors": monitors,
        "docking_stations": docks,
        "phones": phones
    }


@router.get("/stock")
async def get_available_stock(db: Session = Depends(get_db)):
    """Fetch all available unassigned hardware with full details."""
    pcs = db.query(PC).filter(PC.status == "Available").all()
    monitors = db.query(Monitor).filter(Monitor.status == "Available").all()
    docks = db.query(DockingStation).filter(DockingStation.status == "Available").all()
    phones = db.query(Phone).filter(Phone.status == "Available").all()
    
    return {
        "pcs": [
            {
                "id": p.id,
                "asset_type": "pc",
                "name": p.name,
                "serial_number": p.serial_number,
                "model": p.model,
                "image_path": p.image_path,
                "notes": p.notes,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "status": p.status
            } for p in pcs
        ],
        "monitors": [
            {
                "id": m.id,
                "asset_type": "monitor",
                "serial_number": m.serial_number,
                "model": m.model,
                "image_path": m.image_path,
                "notes": m.notes,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "status": m.status
            } for m in monitors
        ],
        "docking_stations": [
            {
                "id": d.id,
                "asset_type": "docking_station",
                "serial_number": d.serial_number,
                "model": d.model,
                "image_path": d.image_path,
                "notes": d.notes,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "status": d.status
            } for d in docks
        ],
        "phones": [
            {
                "id": ph.id,
                "asset_type": "phone",
                "serial_number": ph.serial_number,
                "model": ph.model,
                "phone_number": ph.phone_number,
                "image_path": ph.image_path,
                "notes": ph.notes,
                "created_at": ph.created_at.isoformat() if ph.created_at else None,
                "status": ph.status
            } for ph in phones
        ]
    }


@router.get("/stock/all")
async def get_all_stock(db: Session = Depends(get_db)):
    """Fetch ALL hardware (all statuses) for a unified view."""
    pcs = db.query(PC).all()
    monitors = db.query(Monitor).all()
    docks = db.query(DockingStation).all()
    phones = db.query(Phone).all()
    
    items = []
    for p in pcs:
        items.append({
            "id": p.id, "asset_type": "pc", "name": p.name,
            "serial_number": p.serial_number, "model": p.model,
            "image_path": p.image_path, "notes": p.notes, "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    for m in monitors:
        items.append({
            "id": m.id, "asset_type": "monitor", "name": None,
            "serial_number": m.serial_number, "model": m.model,
            "image_path": m.image_path, "notes": m.notes, "status": m.status,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    for d in docks:
        items.append({
            "id": d.id, "asset_type": "docking_station", "name": None,
            "serial_number": d.serial_number, "model": d.model,
            "image_path": d.image_path, "notes": d.notes, "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        })
    for ph in phones:
        items.append({
            "id": ph.id, "asset_type": "phone", "name": ph.phone_number,
            "serial_number": ph.serial_number, "model": ph.model,
            "image_path": ph.image_path, "notes": ph.notes, "status": ph.status,
            "created_at": ph.created_at.isoformat() if ph.created_at else None,
        })
    
    return {"items": items, "total": len(items)}


from pydantic import BaseModel
class StockCreateSchema(BaseModel):
    asset_type: str
    model: str
    serial_number: str
    name: Optional[str] = None
    phone_number: Optional[str] = None
    notes: Optional[str] = None

@router.post("/stock")
async def add_stock(item: StockCreateSchema, db: Session = Depends(get_db)):
    """Add a new device directly to available stock."""
    type_map = {
        "pc": PC,
        "monitor": Monitor,
        "docking_station": DockingStation,
        "phone": Phone
    }
    
    if item.asset_type not in type_map:
        raise HTTPException(status_code=400, detail="Invalid asset type")
        
    model_class = type_map[item.asset_type]
    
    # Check duplicate serial
    existing = db.query(model_class).filter(model_class.serial_number == item.serial_number).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Serial number {item.serial_number} already exists")

    new_device = model_class(
        serial_number=item.serial_number,
        model=item.model,
        status="Available",
        notes=item.notes,
        created_at=datetime.utcnow()
    )
    
    if item.asset_type == "pc":
        new_device.name = item.name or ""
    elif item.asset_type == "phone":
        new_device.phone_number = item.phone_number or ""
        
    db.add(new_device)
    db.flush()

    # Log audit
    log_audit(db, "created", item.asset_type, new_device.id,
              serial_number=item.serial_number,
              model=item.model,
              details=f"Manually added to stock. Model: {item.model}, S/N: {item.serial_number}")

    db.commit()
    return {"message": "Item added to stock successfully", "id": new_device.id}


@router.get("/history/{asset_type}/{asset_id}")
async def get_asset_history(asset_type: str, asset_id: int, db: Session = Depends(get_db)):
    """Fetch the assignment timeline of any specific asset type."""
    valid_types = ["pc", "monitor", "docking_station", "phone"]
    if asset_type not in valid_types:
        raise HTTPException(status_code=400, detail="Invalid asset type")

    filter_attr = getattr(AssetAssignment, f"{asset_type}_id")
    history = db.query(AssetAssignment).filter(filter_attr == asset_id).order_by(AssetAssignment.assigned_date.desc()).all()

    return history


@router.post("/assign")
async def assign_specific_hardware(payload: AssetAssignmentSchema, db: Session = Depends(get_db)):
    """Creates a new timeline record and updates the device's current_user_id"""
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    hardware = None
    if payload.asset_type == "pc":
        hardware = db.query(PC).filter(PC.id == payload.asset_id).first()
    elif payload.asset_type == "monitor":
        hardware = db.query(Monitor).filter(Monitor.id == payload.asset_id).first()
    elif payload.asset_type == "docking_station":
        hardware = db.query(DockingStation).filter(DockingStation.id == payload.asset_id).first()
    elif payload.asset_type == "phone":
        hardware = db.query(Phone).filter(Phone.id == payload.asset_id).first()

    if not hardware:
        raise HTTPException(404, "Hardware asset not found")

    assign_hardware(db, hardware, user, payload.asset_type, payload.notes)
    db.commit()
    return {"message": "Hardware assigned successfully and history logged."}


@router.post("/import")
async def import_assets_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Validates and processes an Excel upload to upsert assets and generate history timeline."""

    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "Only Excel files are supported.")

    try:
        df = pd.read_excel(file.file)
    except Exception as e:
        raise HTTPException(400, f"Error reading Excel file: {str(e)}")

    # 2. Validate Required Columns
    expected_columns = [
        "user_name", "pc_name", "pc_serial_number", "pc_model", 
        "assigned_status", "monitor_model", "monitor_serial_number", 
        "docking_station_model", "docking_station_serial_number", 
        "phone_model", "phone_serial_number", "phone_number", "notes"
    ]

    # Make sure all columns exist (even if empty in data) to avoid pandas KeyErrors
    for col in expected_columns:
        if col not in df.columns:
            df[col] = None

    processed_count = 0
    created_count = 0
    skipped_count = 0

    for index, row in df.iterrows():
        # Clean data (convert NaN to None)
        user_name = None if pd.isna(row['user_name']) else str(row['user_name']).strip()
        status = "Available" if pd.isna(row['assigned_status']) else str(row['assigned_status']).strip()
        notes = None if pd.isna(row['notes']) else str(row['notes']).strip()

        user = None
        if user_name:
            user = get_or_create_user(db, user_name)

        # Process PC
        if pd.notna(row['pc_serial_number']):
            sn = str(row['pc_serial_number']).strip()
            pc = db.query(PC).filter(PC.serial_number == sn).first()
            is_new = pc is None
            if not pc:
                pc = PC(
                    serial_number=sn, 
                    name=str(row.get('pc_name', '')) if pd.notna(row.get('pc_name')) else None,
                    model=str(row.get('pc_model', '')) if pd.notna(row.get('pc_model')) else None,
                    status=status,
                    created_at=datetime.utcnow()
                )
                db.add(pc)
                db.flush()
                created_count += 1
            
            log_audit(db, "imported" if is_new else "updated", "pc", pc.id,
                      serial_number=sn,
                      model=pc.model,
                      details=f"{'Created' if is_new else 'Updated'} via Excel import (row {index + 1})")

            if user:
                assign_hardware(db, pc, user, "pc", notes)

        # Process Monitor
        if pd.notna(row['monitor_serial_number']):
            sn = str(row['monitor_serial_number']).strip()
            monitor = db.query(Monitor).filter(Monitor.serial_number == sn).first()
            is_new = monitor is None
            if not monitor:
                monitor = Monitor(
                    serial_number=sn, 
                    model=str(row.get('monitor_model', '')) if pd.notna(row.get('monitor_model')) else None,
                    status=status,
                    created_at=datetime.utcnow()
                )
                db.add(monitor)
                db.flush()
                created_count += 1

            log_audit(db, "imported" if is_new else "updated", "monitor", monitor.id,
                      serial_number=sn,
                      model=monitor.model,
                      details=f"{'Created' if is_new else 'Updated'} via Excel import (row {index + 1})")

            if user:
                assign_hardware(db, monitor, user, "monitor", notes)

        # Process Docking Station
        if pd.notna(row['docking_station_serial_number']):
            sn = str(row['docking_station_serial_number']).strip()
            dock = db.query(DockingStation).filter(DockingStation.serial_number == sn).first()
            is_new = dock is None
            if not dock:
                dock = DockingStation(
                    serial_number=sn, 
                    model=str(row.get('docking_station_model', '')) if pd.notna(row.get('docking_station_model')) else None,
                    status=status,
                    created_at=datetime.utcnow()
                )
                db.add(dock)
                db.flush()
                created_count += 1

            log_audit(db, "imported" if is_new else "updated", "docking_station", dock.id,
                      serial_number=sn,
                      model=dock.model,
                      details=f"{'Created' if is_new else 'Updated'} via Excel import (row {index + 1})")

            if user:
                assign_hardware(db, dock, user, "docking_station", notes)

        # Process Phone
        if pd.notna(row['phone_serial_number']):
            sn = str(row['phone_serial_number']).strip()
            phone = db.query(Phone).filter(Phone.serial_number == sn).first()
            is_new = phone is None
            if not phone:
                phone = Phone(
                    serial_number=sn, 
                    model=str(row.get('phone_model', '')) if pd.notna(row.get('phone_model')) else None,
                    phone_number=str(row.get('phone_number', '')) if pd.notna(row.get('phone_number')) else None,
                    status=status,
                    created_at=datetime.utcnow()
                )
                db.add(phone)
                db.flush()
                created_count += 1

            log_audit(db, "imported" if is_new else "updated", "phone", phone.id,
                      serial_number=sn,
                      model=phone.model,
                      details=f"{'Created' if is_new else 'Updated'} via Excel import (row {index + 1})")

            if user:
                assign_hardware(db, phone, user, "phone", notes)

        processed_count += 1

    db.commit()
    return {
        "message": f"Successfully processed {processed_count} rows from Excel.",
        "processed": processed_count,
        "created": created_count,
    }


# --- Image Upload Endpoints ---

@router.post("/stock/{asset_type}/{asset_id}/image")
async def upload_asset_image(asset_type: str, asset_id: int,
                             file: UploadFile = File(...),
                             db: Session = Depends(get_db)):
    """Upload an image for a specific hardware asset."""
    type_map = {"pc": PC, "monitor": Monitor, "docking_station": DockingStation, "phone": Phone}
    
    if asset_type not in type_map:
        raise HTTPException(400, "Invalid asset type")
    
    model_class = type_map[asset_type]
    asset = db.query(model_class).filter(model_class.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    
    # Validate file extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(400, f"Invalid image format. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}")
    
    # Generate unique filename
    filename = f"{asset_type}_{asset_id}_{uuid.uuid4().hex[:8]}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    # Delete old image if exists
    if asset.image_path:
        old_path = os.path.join(UPLOAD_DIR, os.path.basename(asset.image_path))
        if os.path.exists(old_path):
            os.remove(old_path)
    
    # Save new image
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Update asset
    asset.image_path = f"/uploads/hardware/{filename}"
    
    log_audit(db, "image_uploaded", asset_type, asset_id,
              serial_number=asset.serial_number,
              model=asset.model,
              details=f"Image uploaded: {file.filename}")
    
    db.commit()
    return {"message": "Image uploaded successfully", "image_path": asset.image_path}


@router.delete("/stock/{asset_type}/{asset_id}/image")
async def delete_asset_image(asset_type: str, asset_id: int,
                             db: Session = Depends(get_db)):
    """Remove image from a hardware asset."""
    type_map = {"pc": PC, "monitor": Monitor, "docking_station": DockingStation, "phone": Phone}
    
    if asset_type not in type_map:
        raise HTTPException(400, "Invalid asset type")
    
    model_class = type_map[asset_type]
    asset = db.query(model_class).filter(model_class.id == asset_id).first()
    if not asset:
        raise HTTPException(404, "Asset not found")
    
    if asset.image_path:
        old_path = os.path.join(UPLOAD_DIR, os.path.basename(asset.image_path))
        if os.path.exists(old_path):
            os.remove(old_path)
        asset.image_path = None
        
        log_audit(db, "image_deleted", asset_type, asset_id,
                  serial_number=asset.serial_number,
                  model=asset.model,
                  details="Image removed")
        db.commit()
    
    return {"message": "Image removed successfully"}


# --- Audit Log Endpoint ---

@router.get("/audit-log")
async def get_audit_log(
    asset_type: Optional[str] = None,
    asset_id: Optional[int] = None,
    action: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db)
):
    """Fetch audit log entries with optional filters."""
    query = db.query(StockAuditLog)
    
    if asset_type:
        query = query.filter(StockAuditLog.asset_type == asset_type)
    if asset_id:
        query = query.filter(StockAuditLog.asset_id == asset_id)
    if action:
        query = query.filter(StockAuditLog.action == action)
    
    total = query.count()
    entries = query.order_by(desc(StockAuditLog.created_at)).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "entries": [
            {
                "id": e.id,
                "action": e.action,
                "asset_type": e.asset_type,
                "asset_id": e.asset_id,
                "serial_number": e.serial_number,
                "model": e.model,
                "performed_by": e.performed_by,
                "details": e.details,
                "created_at": e.created_at.isoformat() if e.created_at else None
            } for e in entries
        ]
    }
