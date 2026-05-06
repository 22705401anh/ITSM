from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db import Base
from app.models.user import User

class DiscoveryJob(Base):
    __tablename__ = "discovery_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    target_type = Column(String(50)) # IP_RANGE, SUBNET, TARGET_LIST
    target_value = Column(Text, nullable=False) # e.g., "192.168.1.0/24"
    protocols = Column(String(200)) # "ICMP,SNMP,WMI"
    schedule_cron = Column(String(100), nullable=True)
    status = Column(String(50), default="IDLE") # IDLE, RUNNING, FAILED, COMPLETED
    last_run = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    creator = relationship("User", foreign_keys=[created_by_id])
    logs = relationship("DiscoveryLog", back_populates="job", cascade="all, delete")

class DiscoveredDevice(Base):
    __tablename__ = "discovered_devices"
    
    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String(255), nullable=True)
    ip_address = Column(String(50), index=True, nullable=False)
    mac_address = Column(String(50), index=True, nullable=True)
    device_type = Column(String(50), default="Unknown") # Server, Switch, Printer, PC, Unknown
    os_info = Column(String(255), nullable=True)
    vendor = Column(String(100), nullable=True)
    open_ports = Column(Text, nullable=True) # JSON string
    last_seen = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default="NEW") # NEW, MATCHED, IGNORED
    matched_hw_id = Column(Integer, nullable=True) # FK to actual CMDB if matched
    discovery_source = Column(String(50), default="ICMP")
    snmp_status = Column(String(50), nullable=True) # CONNECTED, FAILED, NOT_ATTEMPTED
    snmp_error = Column(Text, nullable=True)
    serial_number = Column(String(255), nullable=True)
    uptime = Column(String(100), nullable=True)
    site = Column(String(100), nullable=True)
    role = Column(String(100), nullable=True)
    
    telemetry = relationship("DeviceTelemetry", back_populates="device", uselist=False, cascade="all, delete-orphan")
    
class DeviceTelemetry(Base):
    __tablename__ = "device_telemetry"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("discovered_devices.id"), unique=True)
    ports_data_json = Column(Text, nullable=True)
    summary_data_json = Column(Text, nullable=True)
    last_polled_at = Column(DateTime, default=datetime.utcnow)
    
    device = relationship("DiscoveredDevice", back_populates="telemetry")

class DiscoveryLog(Base):
    __tablename__ = "discovery_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("discovery_jobs.id"))
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    devices_found = Column(Integer, default=0)
    status = Column(String(50)) # SUCCESS, PARTIAL, ERROR, RUNNING
    log_output = Column(Text, nullable=True)
    
    job = relationship("DiscoveryJob", back_populates="logs")
