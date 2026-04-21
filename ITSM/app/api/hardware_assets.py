import os
import pandas as pd
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from datetime import datetime

from app.db import get_db
from app.models.user import User
from app.models.hardware import PC, Monitor, DockingStation, Phone, AssetAssignment
from app.schemas.hardware import AssetAssignmentSchema

router = APIRouter(prefix="/hardware", tags=["Hardware Asset Tracking"])

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
            if not pc:
                pc = PC(
                    serial_number=sn, 
                    name=str(row.get('pc_name', '')) if pd.notna(row.get('pc_name')) else None,
                    model=str(row.get('pc_model', '')) if pd.notna(row.get('pc_model')) else None,
                    status=status
                )
                db.add(pc)
                db.flush()

            if user:
                assign_hardware(db, pc, user, "pc", notes)

        # Process Monitor
        if pd.notna(row['monitor_serial_number']):
            sn = str(row['monitor_serial_number']).strip()
            monitor = db.query(Monitor).filter(Monitor.serial_number == sn).first()
            if not monitor:
                monitor = Monitor(
                    serial_number=sn, 
                    model=str(row.get('monitor_model', '')) if pd.notna(row.get('monitor_model')) else None,
                    status=status
                )
                db.add(monitor)
                db.flush()

            if user:
                assign_hardware(db, monitor, user, "monitor", notes)

        # Process Docking Station
        if pd.notna(row['docking_station_serial_number']):
            sn = str(row['docking_station_serial_number']).strip()
            dock = db.query(DockingStation).filter(DockingStation.serial_number == sn).first()
            if not dock:
                dock = DockingStation(
                    serial_number=sn, 
                    model=str(row.get('docking_station_model', '')) if pd.notna(row.get('docking_station_model')) else None,
                    status=status
                )
                db.add(dock)
                db.flush()

            if user:
                assign_hardware(db, dock, user, "docking_station", notes)

        # Process Phone
        if pd.notna(row['phone_serial_number']):
            sn = str(row['phone_serial_number']).strip()
            phone = db.query(Phone).filter(Phone.serial_number == sn).first()
            if not phone:
                phone = Phone(
                    serial_number=sn, 
                    model=str(row.get('phone_model', '')) if pd.notna(row.get('phone_model')) else None,
                    phone_number=str(row.get('phone_number', '')) if pd.notna(row.get('phone_number')) else None,
                    status=status
                )
                db.add(phone)
                db.flush()

            if user:
                assign_hardware(db, phone, user, "phone", notes)

        processed_count += 1

    db.commit()
    return {"message": f"Successfully processed {processed_count} rows from Excel."}
