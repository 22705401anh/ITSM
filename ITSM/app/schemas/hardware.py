from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel

class HardwareBase(BaseModel):
    serial_number: str
    model: Optional[str] = None
    status: str = "Available"

class PCBase(HardwareBase):
    name: Optional[str] = None

class PhoneBase(HardwareBase):
    phone_number: Optional[str] = None

class AssetAssignmentSchema(BaseModel):
    user_id: int
    asset_type: str
    asset_id: int
    notes: Optional[str] = None
