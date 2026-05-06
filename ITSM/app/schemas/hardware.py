from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, field_validator

class HardwareBase(BaseModel):
    serial_number: str
    model: Optional[str] = None
    status: str = "Available"

class PCBase(HardwareBase):
    name: Optional[str] = None

class PhoneBase(HardwareBase):
    phone_number: Optional[str] = None

class PhoneNumberBase(HardwareBase):
    phone_number: str

class AssetAssignmentSchema(BaseModel):
    user_id: int
    asset_type: str
    asset_id: int
    notes: Optional[str] = None

class ReturnAssetSchema(BaseModel):
    asset_type: str
    asset_id: int
    notes: Optional[str] = None

class AssetStatusUpdateSchema(BaseModel):
    status: str

class DiscoveryMonitorSchema(BaseModel):
    serial_number: str
    model: str
    manufacturer: str

class DiscoveryPrinterSchema(BaseModel):
    name: str
    driver_name: Optional[str] = None
    port_name: Optional[str] = None
    is_network: bool = False
    is_default: bool = False

class DiscoveryNetworkPrinterSchema(BaseModel):
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    model: Optional[str] = None
    serial_number: str

class DiscoverySoftwareSchema(BaseModel):
    name: str
    version: Optional[str] = None

class DiscoveryDeviceSchema(BaseModel):
    hostname: str
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    mac_address: Optional[str] = None
    model: Optional[str] = None
    serial_number: str
    vendor: Optional[str] = None
    logged_in_user: Optional[str] = None
    windows_version: Optional[str] = None
    intune_status: Optional[str] = None
    antivirus_status: Optional[str] = None
    ram: Optional[str] = None
    storage: Optional[str] = None
    print_volume_30d: Optional[int] = 0
    monitors: List[DiscoveryMonitorSchema] = []
    software: List[DiscoverySoftwareSchema] = []
    printers: List[DiscoveryPrinterSchema] = []

    @field_validator('monitors', 'software', mode='before')
    @classmethod
    def coerce_arrays(cls, v: Any) -> Any:
        # PowerShell ConvertTo-Json serializes an empty array as {} and a single-item array as a dict.
        if v == {}:
            return []
        if isinstance(v, dict):
            return [v]
        return v

class DiscoveryPayloadSchema(BaseModel):
    devices: List[DiscoveryDeviceSchema]
    network_printers: List[DiscoveryNetworkPrinterSchema] = []

class AssetUpdateSchema(BaseModel):
    name: Optional[str] = None
    serial_number: Optional[str] = None
    mac_address: Optional[str] = None
    ip_address: Optional[str] = None
    model: Optional[str] = None
    phone_number: Optional[str] = None
    notes: Optional[str] = None
