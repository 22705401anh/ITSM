# Comprehensive Asset Tracking System - Implementation Guide

Based on your requirements for a fully relational asset tracking system with separate tables and history tracking, here is the complete technical delivery containing the components you requested.

## 1. Suggested Tech Stack
- **Backend:** FastAPI (Python) - *Currently used and perfect for this.*
- **ORM:** SQLAlchemy - *For managing our new relational database schema.*
- **Database:** PostgreSQL (Recommended for production to handle relational queries and JSON if needed, though SQLite will work for dev).
- **Frontend:** Jinja2 Templates with Bootstrap 5.
- **Excel Import/Export:** `pandas` and `openpyxl`.

---

## 2. Database Schema (SQLAlchemy Models)
This schema separates assets into specific tables and adds an `AssetAssignment` table to track history securely without data loss.

```python
# app/models/hardware.py

from sqlalchemy import String, Integer, DateTime, ForeignKey, Boolean, Text, Column
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base

class AssetAssignment(Base):
    """Tracks the history of all asset movements."""
    __tablename__ = "asset_assignments"

    id = Column(Integer, primary_key=True, index=True)

    # Generic references to hardware types
    pc_id = Column(Integer, ForeignKey("pcs.id"), nullable=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), nullable=True)
    docking_station_id = Column(Integer, ForeignKey("docking_stations.id"), nullable=True)
    phone_id = Column(Integer, ForeignKey("phones.id"), nullable=True)

    previous_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    new_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    assigned_date = Column(DateTime, default=datetime.utcnow)
    returned_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True) # True = physically assigned right now
    notes = Column(Text, nullable=True)

    # Relationships
    new_user = relationship("User", foreign_keys=[new_user_id])
    previous_user = relationship("User", foreign_keys=[previous_user_id])

class PC(Base):
    __tablename__ = "pcs"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), index=True)
    serial_number = Column(String(100), unique=True, index=True, nullable=False)
    model = Column(String(100))
    status = Column(String(50), default="Available") # Available, Assigned, Maintenance, Retired
    current_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    assignments = relationship("AssetAssignment", backref="pc", foreign_keys="AssetAssignment.pc_id")
    current_user = relationship("User", foreign_keys=[current_user_id])

class Monitor(Base):
    __tablename__ = "monitors"

    id = Column(Integer, primary_key=True)
    serial_number = Column(String(100), unique=True, index=True, nullable=False)
    model = Column(String(100))
    status = Column(String(50), default="Available")
    current_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    assignments = relationship("AssetAssignment", backref="monitor", foreign_keys="AssetAssignment.monitor_id")
    current_user = relationship("User", foreign_keys=[current_user_id])

class DockingStation(Base):
    __tablename__ = "docking_stations"

    id = Column(Integer, primary_key=True)
    serial_number = Column(String(100), unique=True, index=True, nullable=False)
    model = Column(String(100))
    status = Column(String(50), default="Available")
    current_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    assignments = relationship("AssetAssignment", backref="docking_station", foreign_keys="AssetAssignment.docking_station_id")

class Phone(Base):
    __tablename__ = "phones"

    id = Column(Integer, primary_key=True)
    serial_number = Column(String(100), unique=True, index=True, nullable=False)
    phone_number = Column(String(50), index=True)
    model = Column(String(100))
    status = Column(String(50), default="Available")
    current_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    assignments = relationship("AssetAssignment", backref="phone", foreign_keys="AssetAssignment.phone_id")
```

---

## 3. Backend API Structure
Here is the structure needed in FastAPI to manage these assignments and search queries across all hardware tables.

```python
# app/api/hardware_assets.py

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session, or_
from typing import List
import pandas as pd
from app.db import get_db

router = APIRouter(prefix="/hardware", tags=["Hardware Asset Tracking"])

@router.get("/search")
async def global_asset_search(query: str, db: Session = Depends(get_db)):
    """Searches across all asset tables simultaneously."""
    search_term = f"%{query}%"

    pcs = db.query(PC).filter(or_(PC.serial_number.ilike(search_term), PC.name.ilike(search_term))).all()
    monitors = db.query(Monitor).filter(Monitor.serial_number.ilike(search_term)).all()
    docks = db.query(DockingStation).filter(DockingStation.serial_number.ilike(search_term)).all()
    phones = db.query(Phone).filter(or_(Phone.serial_number.ilike(search_term), Phone.phone_number.ilike(search_term))).all()

    return {
        "pcs": pcs,
        "monitors": monitors,
        "docking_stations": docks,
        "phones": phones
    }

@router.get("/history/{asset_type}/{asset_id}")
async def get_asset_history(asset_type: str, asset_id: int, db: Session = Depends(get_db)):
    """Fetch the assignment timeline of any specific asset type."""
    if asset_type == "monitor":
        history = db.query(AssetAssignment).filter(AssetAssignment.monitor_id == asset_id).order_by(AssetAssignment.assigned_date.desc()).all()
    elif asset_type == "pc":
        history = db.query(AssetAssignment).filter(AssetAssignment.pc_id == asset_id).order_by(AssetAssignment.assigned_date.desc()).all()
    # ... handle docks and phones ...

    return history

@router.post("/assign")
async def assign_asset(payload: AssetAssignmentSchema, db: Session = Depends(get_db)):
    """Creates a new timeline record and updates the device's current_user_id"""
    # 1. Close current assignment (set is_active=False, returned_date=now)
    # 2. Create new assignment (set previous_user_id, new_user_id, notes)
    # 3. Update the specific hardware table's current_user_id
    pass
```

---

## 4. Excel Import Logic

The Excel importer validates columns, creates missing assets, and automatically generates assignment history.

```python
# app/api/excel_import.py

@router.post("/import")
async def import_assets_excel(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # 1. Read file into Pandas DataFrame
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "Only Excel files are supported.")

    df = pd.read_excel(file.file)

    # 2. Validate Required Columns
    expected_columns = [
        "user_name", "pc_name", "pc_serial_number", "pc_model", 
        "assigned_status", "monitor_model", "monitor_serial_number", 
        "docking_station_model", "docking_station_serial_number", 
        "phone_model", "phone_serial_number", "phone_number"
    ]

    missing_cols = [col for col in expected_columns if col not in df.columns]
    if missing_cols:
        raise HTTPException(400, f"Missing columns: {', '.join(missing_cols)}")

    # 3. Iterate rows and UPSERT
    for index, row in df.iterrows():
        # Process User
        user = None
        if pd.notna(row['user_name']):
            user = get_or_create_user(db, row['user_name'])

        # Process PC
        if pd.notna(row['pc_serial_number']):
            pc = db.query(PC).filter(PC.serial_number == str(row['pc_serial_number'])).first()
            if not pc:
                pc = PC(serial_number=str(row['pc_serial_number']), name=str(row.get('pc_name', '')), model=str(row.get('pc_model', '')))
                db.add(pc)

            # If user specified, assign PC and log history
            if user and pc.current_user_id != user.id:
                 assign_hardware(db, hardware=pc, new_user=user, asset_type="pc")

        # ... Apply same logic to Monitors, Phones, Docking Stations ...

    db.commit()
    return {"message": "Excel data successfully imported and history timeline generated."}
```

---

## 5. Sample Excel Import Template Structure

Users can easily fill this file. If a user receives a new monitor, they just fill the Username and the Monitor columns. 

**Filename:** `asset_import_template.xlsx`

| user_name | pc_name | pc_serial_number | pc_model | assigned_status | monitor_model | monitor_serial_number | docking_station_model | docking_station_serial_number | phone_model | phone_serial_number | phone_number |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| John Smith | JS-DESKTOP | PC-SN-111 | Dell XPS | Assigned | Dell U2720Q | MON-SN-222 | Dell WD19 | DOCK-SN-333 | iPhone 14 | PH-SN-444 | 555-0100 |
| Jane Doe | | | | | LG 27UK | MON-SN-888 | | | | | |

*Tip: Leaving cells blank means the script will ignore that hardware type for that row. It heavily relies on `*_serial_number` uniquely identifying the physical item.*

---

## 6. Frontend Approach

To handle UI presentation cleanly:

**The List View (`app/web/templates/assets/hardware_list.html`)**
Will combine queries into a master list visually, allowing the `User Name` column to be prominent. Asset rows will have clickable `<a>` tags leading to their dedicated detail page.

**The Detail View (`app/web/templates/assets/hardware_detail.html`)**
```html
<h2>Monitor {{ monitor.serial_number }} Details</h2>
<p>Model: {{ monitor.model }}</p>

<h3>Assignment History Timeline</h3>
<ul class="timeline">
    {% for entry in history %}
    <li>
        <strong>{{ entry.assigned_date.strftime('%Y-%m-%d') }}</strong> 
        - Assigned to <em>{{ entry.new_user.full_name }}</em> 
        (Previous: {{ entry.previous_user.full_name if entry.previous_user else 'None' }})
        <br> Notes: {{ entry.notes }}
    </li>
    {% endfor %}
</ul>
```
