"""Asset schemas for request/response validation"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class AssetType(str, Enum):
    """Asset type enumeration"""
    COMPUTER = "computer"
    LAPTOP = "laptop"
    MONITOR = "monitor"
    KEYBOARD = "keyboard"
    MOUSE = "mouse"
    PRINTER = "printer"
    SCANNER = "scanner"
    PHONE = "phone"
    PHONE_NUMBER = "phone_number"
    SERVER = "server"
    ROUTER = "router"
    SWITCH = "switch"
    FIREWALL = "firewall"
    UPS = "ups"
    RACK = "rack"
    CCTV = "cctv"
    CAMERA = "camera"
    LICENSE = "license"
    SOFTWARE = "software"
    STORAGE = "storage"
    OTHER = "other"


class AssetStatus(str, Enum):
    """Asset status enumeration"""
    AVAILABLE = "available"
    IN_USE = "in_use"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"
    DAMAGED = "damaged"
    LOST = "lost"


class AssetCreate(BaseModel):
    """Schema for creating an asset"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    asset_type: AssetType
    status: AssetStatus = AssetStatus.AVAILABLE
    asset_tag: str = Field(..., min_length=1, max_length=100)
    serial_number: Optional[str] = None
    model_number: Optional[str] = None
    manufacturer: Optional[str] = None
    location: Optional[str] = None
    assigned_user_id: Optional[int] = None
    purchase_date: Optional[datetime] = None
    purchase_cost: Optional[float] = None
    warranty_expiry: Optional[datetime] = None
    depreciation_rate: Optional[float] = None
    specifications: Optional[str] = None
    license_key: Optional[str] = None
    license_expiry: Optional[datetime] = None
    end_of_life_date: Optional[datetime] = None
    notes: Optional[str] = None


class AssetUpdate(BaseModel):
    """Schema for updating an asset"""
    name: Optional[str] = None
    description: Optional[str] = None
    asset_type: Optional[AssetType] = None
    status: Optional[AssetStatus] = None
    asset_tag: Optional[str] = None
    serial_number: Optional[str] = None
    model_number: Optional[str] = None
    manufacturer: Optional[str] = None
    location: Optional[str] = None
    assigned_user_id: Optional[int] = None
    purchase_date: Optional[datetime] = None
    purchase_cost: Optional[float] = None
    warranty_expiry: Optional[datetime] = None
    depreciation_rate: Optional[float] = None
    specifications: Optional[str] = None
    license_key: Optional[str] = None
    license_expiry: Optional[datetime] = None
    end_of_life_date: Optional[datetime] = None
    notes: Optional[str] = None


class AssetResponse(BaseModel):
    """Schema for asset response"""
    id: int
    name: str
    description: Optional[str]
    asset_type: AssetType
    status: AssetStatus
    asset_tag: str
    serial_number: Optional[str]
    model_number: Optional[str]
    manufacturer: Optional[str]
    location: Optional[str]
    assigned_user_id: Optional[int]
    purchase_date: Optional[datetime]
    purchase_cost: Optional[float]
    warranty_expiry: Optional[datetime]
    depreciation_rate: Optional[float]
    specifications: Optional[str]
    license_key: Optional[str]
    license_expiry: Optional[datetime]
    end_of_life_date: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class LicenseCreate(BaseModel):
    """Schema for creating a license"""
    license_name: str = Field(..., min_length=1, max_length=255)
    license_key: str = Field(..., min_length=1, max_length=255)
    license_type: str = Field(..., min_length=1, max_length=100)
    total_licenses: int = Field(..., gt=0)
    purchase_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    cost_per_license: Optional[float] = None
    vendor: Optional[str] = None
    support_contact: Optional[str] = None
    notes: Optional[str] = None


class LicenseAssignmentCreate(BaseModel):
    """Schema for assigning a license"""
    user_id: Optional[int] = None
    pc_id: Optional[int] = None
    notes: Optional[str] = None


class LicenseAssignmentResponse(BaseModel):
    """Schema for license assignment response"""
    id: int
    license_id: int
    user_id: Optional[int]
    pc_id: Optional[int]
    assigned_by_id: Optional[int]
    assigned_date: datetime
    status: str
    notes: Optional[str]
    
    # Extended fields for display
    user_name: Optional[str] = None
    pc_name: Optional[str] = None

    class Config:
        from_attributes = True


class LicenseResponse(BaseModel):
    """Schema for license response"""
    id: int
    license_name: str
    license_key: str  # Will be masked in frontend
    license_type: str
    total_licenses: int
    used_licenses: int
    purchase_date: Optional[datetime]
    expiry_date: Optional[datetime]
    cost_per_license: Optional[float]
    vendor: Optional[str]
    support_contact: Optional[str]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool
    
    assignments: Optional[list[LicenseAssignmentResponse]] = []

    class Config:
        from_attributes = True


class LicenseAccessHistoryResponse(BaseModel):
    """Schema for license access history"""
    id: int
    license_id: int
    user_id: int
    action: str  # viewed, exported, copied, assigned, revoked
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    
    # Extended field
    user_name: Optional[str] = None

    class Config:
        from_attributes = True


class MaintenanceCreate(BaseModel):
    """Schema for creating maintenance record"""
    asset_id: int
    maintenance_type: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    cost: Optional[float] = None
    performed_by: Optional[str] = None
    next_maintenance_date: Optional[datetime] = None


class MaintenanceResponse(BaseModel):
    """Schema for maintenance response"""
    id: int
    asset_id: int
    maintenance_date: datetime
    maintenance_type: str
    description: Optional[str]
    cost: Optional[float]
    performed_by: Optional[str]
    next_maintenance_date: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
