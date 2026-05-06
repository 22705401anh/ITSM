"""Asset models for IT inventory management"""
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Boolean, Text, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from typing import Optional, List
from enum import Enum

from app.db import Base
from app.models.base import TimestampMixin, IsActiveMixin


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


class Asset(Base, TimestampMixin, IsActiveMixin):
    """Asset model for IT inventory"""

    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    asset_type: Mapped[AssetType] = mapped_column(SQLEnum(AssetType), nullable=False)
    status: Mapped[AssetStatus] = mapped_column(SQLEnum(AssetStatus), default=AssetStatus.AVAILABLE)

    # Identification
    asset_tag: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    serial_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Location & Assignment
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    assigned_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Financial info
    purchase_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    purchase_cost: Mapped[Optional[Float]] = mapped_column(Float, nullable=True)
    warranty_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    depreciation_rate: Mapped[Optional[Float]] = mapped_column(Float, nullable=True)

    # Specifications (for different asset types)
    specifications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON format

    # License info
    license_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    license_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Lifecycle
    end_of_life_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AssetCategory(Base, TimestampMixin, IsActiveMixin):
    """Asset category for classification"""

    __tablename__ = "asset_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AssetMaintenance(Base, TimestampMixin):
    """Asset maintenance records"""

    __tablename__ = "asset_maintenance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(Integer, ForeignKey("assets.id"), nullable=False)
    maintenance_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    maintenance_type: Mapped[str] = mapped_column(String(100), nullable=False)  # preventive, corrective, etc.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost: Mapped[Optional[Float]] = mapped_column(Float, nullable=True)
    performed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    next_maintenance_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class LicenseRegistration(Base, TimestampMixin, IsActiveMixin):
    """License registration and tracking"""

    __tablename__ = "license_registrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # License info
    license_name: Mapped[str] = mapped_column(String(255), nullable=False)
    license_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)  # Encrypted
    license_type: Mapped[str] = mapped_column(String(100), nullable=False)  # perpetual, subscription, etc.

    # Count
    total_licenses: Mapped[int] = mapped_column(Integer, nullable=False)
    used_licenses: Mapped[int] = mapped_column(Integer, default=0)

    # Dates
    purchase_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Cost
    cost_per_license: Mapped[Optional[Float]] = mapped_column(Float, nullable=True)

    # Supplier
    vendor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    support_contact: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class LicenseAccessHistory(Base, TimestampMixin):
    """Track who accessed license keys and when"""

    __tablename__ = "license_access_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    license_id: Mapped[int] = mapped_column(Integer, ForeignKey("license_registrations.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # viewed, exported, copied
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv6 support
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class LicenseAssignment(Base, TimestampMixin):
    """Tracks assignment of licenses to specific users or devices"""

    __tablename__ = "license_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    license_id: Mapped[int] = mapped_column(Integer, ForeignKey("license_registrations.id"), nullable=False)
    
    # Can be assigned to a user OR a PC
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    pc_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("pcs.id"), nullable=True)
    
    assigned_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    status: Mapped[str] = mapped_column(String(50), default="active")  # active, revoked
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
