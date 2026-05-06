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
    phone_number_id = Column(Integer, ForeignKey("phone_numbers.id"), nullable=True)
    printer_id = Column(Integer, ForeignKey("printers.id"), nullable=True)

    previous_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    new_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    assigned_date = Column(DateTime, default=datetime.utcnow)
    returned_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True) # True = physically assigned right now
    notes = Column(Text, nullable=True)

    # Relationships
    new_user = relationship("User", foreign_keys=[new_user_id])
    previous_user = relationship("User", foreign_keys=[previous_user_id])

    # Back-populates relationships configured in hardware models


class StockAuditLog(Base):
    """Tracks every action performed on stock items for full audit trail."""
    __tablename__ = "stock_audit_log"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(50), nullable=False, index=True)  # created, imported, updated, assigned, returned, deleted, image_uploaded
    asset_type = Column(String(50), nullable=False, index=True)  # pc, monitor, docking_station, phone
    asset_id = Column(Integer, nullable=False)
    serial_number = Column(String(100), nullable=True)  # Denormalized for display convenience
    model = Column(String(100), nullable=True)
    performed_by = Column(String(255), default="System")  # Username or "System"
    details = Column(Text, nullable=True)  # JSON or free-text description
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class PC(Base):
    __tablename__ = "pcs"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), index=True)
    serial_number = Column(String(100), unique=True, index=True, nullable=False)
    model = Column(String(100))
    vendor = Column(String(100), nullable=True)
    ip_address = Column(String(50), nullable=True)
    mac_address = Column(String(50), nullable=True)
    mac_address = Column(String(50), nullable=True)
    status = Column(String(50), default="Available") # Available, Assigned, Maintenance, Retired
    current_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    image_path = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=True)
    windows_version = Column(String(100), nullable=True)
    intune_status = Column(String(50), nullable=True)
    antivirus_status = Column(String(100), nullable=True)
    ram = Column(String(50), nullable=True)
    storage = Column(String(100), nullable=True)
    print_volume_30d = Column(Integer, nullable=True)

    assignments = relationship("AssetAssignment", backref="pc", foreign_keys="AssetAssignment.pc_id")
    current_user = relationship("User", foreign_keys=[current_user_id])


class InstalledSoftware(Base):
    """Tracks software installed on a PC, keeping history when removed."""
    __tablename__ = "installed_software"

    id = Column(Integer, primary_key=True, index=True)
    pc_id = Column(Integer, ForeignKey("pcs.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    version = Column(String(100), nullable=True)
    installed_date = Column(DateTime, default=datetime.utcnow)
    removed_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, index=True)

    pc = relationship("PC", backref="software")

class InstalledPrinter(Base):
    __tablename__ = "installed_printers"

    id = Column(Integer, primary_key=True, index=True)
    pc_id = Column(Integer, ForeignKey("pcs.id"), nullable=False)
    name = Column(String(255), nullable=False)
    driver_name = Column(String(255), nullable=True)
    port_name = Column(String(255), nullable=True)
    is_network = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    discovered_at = Column(DateTime, default=datetime.utcnow)

    pc = relationship("PC", backref="printers")

class Monitor(Base):
    __tablename__ = "monitors"

    id = Column(Integer, primary_key=True)
    serial_number = Column(String(100), unique=True, index=True, nullable=False)
    model = Column(String(100))
    vendor = Column(String(100), nullable=True)
    status = Column(String(50), default="Available")
    current_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    image_path = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=True)
    connected_pc_id = Column(Integer, ForeignKey("pcs.id"), nullable=True)

    assignments = relationship("AssetAssignment", backref="monitor", foreign_keys="AssetAssignment.monitor_id")
    current_user = relationship("User", foreign_keys=[current_user_id])

class DockingStation(Base):
    __tablename__ = "docking_stations"

    id = Column(Integer, primary_key=True)
    serial_number = Column(String(100), unique=True, index=True, nullable=False)
    model = Column(String(100))
    status = Column(String(50), default="Available")
    current_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    image_path = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=True)

    assignments = relationship("AssetAssignment", backref="docking_station", foreign_keys="AssetAssignment.docking_station_id")
    current_user = relationship("User", foreign_keys=[current_user_id])

class Phone(Base):
    __tablename__ = "phones"

    id = Column(Integer, primary_key=True)
    serial_number = Column(String(100), unique=True, index=True, nullable=False)
    phone_number = Column(String(50), index=True)
    model = Column(String(100))
    status = Column(String(50), default="Available")
    current_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    image_path = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    assignments = relationship("AssetAssignment", backref="phone", foreign_keys="AssetAssignment.phone_id")
    current_user = relationship("User", foreign_keys=[current_user_id])

class PhoneNumber(Base):
    __tablename__ = "phone_numbers"

    id = Column(Integer, primary_key=True)
    serial_number = Column(String(100), unique=True, index=True, nullable=False) # e.g. ICCID / SIM Number
    phone_number = Column(String(50), index=True, nullable=False)
    model = Column(String(100)) # e.g. Voice/Data Plan type
    status = Column(String(50), default="Available")
    current_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    image_path = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    assignments = relationship("AssetAssignment", backref="phone_number_asset", foreign_keys="AssetAssignment.phone_number_id")
    current_user = relationship("User", foreign_keys=[current_user_id])

class Printer(Base):
    __tablename__ = "printers"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), index=True, nullable=True)
    serial_number = Column(String(100), unique=True, index=True, nullable=False)
    ip_address = Column(String(50), nullable=True)
    mac_address = Column(String(50), nullable=True)
    model = Column(String(100))
    status = Column(String(50), default="Available")
    current_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    image_path = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=True)

    assignments = relationship("AssetAssignment", backref="printer_asset", foreign_keys="AssetAssignment.printer_id")
    current_user = relationship("User", foreign_keys=[current_user_id])
