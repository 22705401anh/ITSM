"""
KOSTAL Print Management Module — Pydantic Schemas

Request/response models for all Phase 1 print management API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ─────────────────────────────────────────────
# Agent Registration & Heartbeat
# ─────────────────────────────────────────────

class AgentRegisterRequest(BaseModel):
    """Request from agent to register itself."""
    hostname: str = Field(..., description="Print server hostname")
    ip_address: Optional[str] = None
    fqdn: Optional[str] = None
    os_version: Optional[str] = None
    agent_version: Optional[str] = None
    location: Optional[str] = None

class AgentRegisterResponse(BaseModel):
    """Response after successful agent registration."""
    agent_id: str
    auth_token: str  # Plaintext token returned ONCE; agent must store it
    server_id: int
    message: str = "Agent registered successfully"

class AgentHeartbeatRequest(BaseModel):
    """Periodic heartbeat from agent."""
    agent_id: str
    status: str = "online"
    queues_count: Optional[int] = None
    jobs_submitted: Optional[int] = None
    last_error: Optional[str] = None
    version: Optional[str] = None

class AgentHeartbeatResponse(BaseModel):
    message: str = "OK"
    server_time: datetime


# ─────────────────────────────────────────────
# Print Job Submission
# ─────────────────────────────────────────────

class PrintJobSubmit(BaseModel):
    """A single print job record submitted by the agent."""
    correlation_id: str
    server_name: str
    queue_name: str
    printer_name: Optional[str] = None
    printer_location: Optional[str] = None
    job_id_windows: Optional[int] = None

    # User
    user_login: Optional[str] = None
    user_display_name: Optional[str] = None
    user_email: Optional[str] = None
    user_department: Optional[str] = None
    user_cost_center: Optional[str] = None
    workstation: Optional[str] = None

    # Document
    document_name: Optional[str] = None

    # Timestamps
    submitted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Status
    status: str = "queued"

    # Pages
    total_pages: Optional[int] = None
    copies: Optional[int] = 1
    total_sheets: Optional[int] = None

    # Properties
    is_color: Optional[bool] = None
    is_duplex: Optional[bool] = None
    paper_size: Optional[str] = None

    # File
    file_size_bytes: Optional[int] = None
    driver_name: Optional[str] = None

class PrintJobSubmitResponse(BaseModel):
    id: int
    correlation_id: str
    status: str
    estimated_cost: Optional[float] = None
    is_duplicate: bool = False
    policy_action: Optional[str] = "allow"
    policy_message: Optional[str] = None

class PrintJobBulkRequest(BaseModel):
    """Bulk submission of print jobs (for offline cache flush)."""
    agent_id: str
    jobs: List[PrintJobSubmit] = Field(..., max_length=500)

class PrintJobBulkResponse(BaseModel):
    total_received: int
    total_created: int
    total_duplicates: int
    errors: List[str] = []


# ─────────────────────────────────────────────
# Print Job Events
# ─────────────────────────────────────────────

class PrintJobEventSubmit(BaseModel):
    """A lifecycle event for a print job."""
    correlation_id: str  # Links to the parent job
    event_type: str
    event_data: Optional[str] = None  # JSON string
    source: Optional[str] = "agent"
    timestamp: Optional[datetime] = None

class PrintJobEventBulkRequest(BaseModel):
    agent_id: str
    events: List[PrintJobEventSubmit]


# ─────────────────────────────────────────────
# Printer / Queue Discovery
# ─────────────────────────────────────────────

class DiscoveredQueueItem(BaseModel):
    """A single queue discovered on a print server."""
    queue_name: str
    printer_name: Optional[str] = None
    share_name: Optional[str] = None
    driver_name: Optional[str] = None
    port_name: Optional[str] = None
    location: Optional[str] = None
    comment: Optional[str] = None
    is_shared: bool = True
    is_network: bool = False
    is_default: bool = False
    status: Optional[str] = "idle"

class PrinterDiscoveryRequest(BaseModel):
    """Agent reports discovered queues/printers."""
    agent_id: str
    server_hostname: str
    queues: List[DiscoveredQueueItem] = []


# ─────────────────────────────────────────────
# Dashboard Responses
# ─────────────────────────────────────────────

class DashboardKPI(BaseModel):
    total_jobs: int = 0
    total_pages: int = 0
    total_cost: float = 0.0
    color_jobs: int = 0
    mono_jobs: int = 0
    duplex_jobs: int = 0
    simplex_jobs: int = 0
    failed_jobs: int = 0
    cancelled_jobs: int = 0
    active_printers: int = 0
    active_servers: int = 0
    active_agents: int = 0

class TopItem(BaseModel):
    name: str
    value: int
    percentage: Optional[float] = None
    item_id: Optional[int] = None

class DashboardResponse(BaseModel):
    kpi: DashboardKPI
    top_users: List[TopItem] = []
    top_printers: List[TopItem] = []
    daily_pages: List[dict] = []  # [{date: "2026-05-01", pages: 500, cost: 25.0}, ...]
    color_ratio: dict = {}  # {color: X, mono: Y}
    duplex_ratio: dict = {}  # {duplex: X, simplex: Y}


# ─────────────────────────────────────────────
# Job List / Detail Responses
# ─────────────────────────────────────────────

class PrintJobResponse(BaseModel):
    id: int
    correlation_id: str
    server_name: Optional[str] = None
    queue_name: Optional[str] = None
    printer_name: Optional[str] = None
    printer_location: Optional[str] = None
    printer_id: Optional[int] = None
    job_id_windows: Optional[int] = None
    user_login: Optional[str] = None
    user_id: Optional[int] = None
    user_display_name: Optional[str] = None
    user_department: Optional[str] = None
    workstation: Optional[str] = None
    document_name: Optional[str] = None
    submitted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str
    total_pages: Optional[int] = None
    copies: Optional[int] = None
    total_sheets: Optional[int] = None
    is_color: Optional[bool] = None
    is_duplex: Optional[bool] = None
    paper_size: Optional[str] = None
    file_size_bytes: Optional[int] = None
    driver_name: Optional[str] = None
    estimated_cost: Optional[float] = None
    validation_status: Optional[str] = None
    created_at: Optional[datetime] = None

class PrintJobEventResponse(BaseModel):
    id: int
    event_type: str
    event_data: Optional[str] = None
    source: Optional[str] = None
    timestamp: Optional[datetime] = None

class PrintJobDetailResponse(PrintJobResponse):
    events: List[PrintJobEventResponse] = []
    user_email: Optional[str] = None
    user_cost_center: Optional[str] = None
    agent_id: Optional[str] = None
    validated_pages: Optional[int] = None
    validated_cost: Optional[float] = None

class PrintJobListResponse(BaseModel):
    jobs: List[PrintJobResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


# ─────────────────────────────────────────────
# Printer Responses
# ─────────────────────────────────────────────

class PrintPrinterResponse(BaseModel):
    id: int
    name: str
    hardware_id: Optional[int] = None
    queue_name: Optional[str] = None
    server_name: Optional[str] = None
    ip_address: Optional[str] = None
    hostname: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    serial_number: Optional[str] = None
    driver: Optional[str] = None
    snmp_enabled: bool = False
    status: Optional[str] = None
    error_state: Optional[str] = None
    last_seen: Optional[datetime] = None
    total_page_counter: Optional[int] = None
    color_counter: Optional[int] = None
    mono_counter: Optional[int] = None
    toner_black: Optional[int] = None
    toner_cyan: Optional[int] = None
    toner_magenta: Optional[int] = None
    toner_yellow: Optional[int] = None

class PrintPrinterUpdate(BaseModel):
    """Admin update for a printer."""
    name: Optional[str] = None
    location: Optional[str] = None
    department: Optional[str] = None
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    serial_number: Optional[str] = None
    ip_address: Optional[str] = None
    snmp_enabled: Optional[bool] = None
    snmp_community: Optional[str] = None
    hardware_validation_enabled: Optional[bool] = None


# ─────────────────────────────────────────────
# Server / Agent Responses
# ─────────────────────────────────────────────

class PrintServerResponse(BaseModel):
    id: int
    hostname: str
    ip_address: Optional[str] = None
    fqdn: Optional[str] = None
    os_version: Optional[str] = None
    location: Optional[str] = None
    status: str
    last_heartbeat: Optional[datetime] = None
    agents: List[dict] = []
    queues_count: int = 0

class PrintAgentResponse(BaseModel):
    id: int
    agent_id: str
    hostname: str
    version: Optional[str] = None
    status: str
    last_heartbeat: Optional[datetime] = None
    last_error: Optional[str] = None
    queues_count: int = 0
    jobs_submitted: int = 0
    registered_at: Optional[datetime] = None


# ─────────────────────────────────────────────
# Policies and Quotas (Phase 4)
# ─────────────────────────────────────────────

class PrintPolicyCreate(BaseModel):
    name: str
    is_active: bool = True
    priority: int = 10
    target_type: str
    target_value: Optional[str] = None
    condition: str
    condition_value: Optional[str] = None
    action: str
    user_message: Optional[str] = None

class PrintPolicyResponse(PrintPolicyCreate):
    id: int
    created_at: datetime

class PrintQuotaCreate(BaseModel):
    target_type: str
    target_value: str
    quota_period: str = "monthly"
    budget_limit: float
    action_when_exceeded: str = "deny"

class PrintQuotaResponse(PrintQuotaCreate):
    id: int
    created_at: datetime
    updated_at: datetime

# ─────────────────────────────────────────────
# Agent Commands (Phase 5)
# ─────────────────────────────────────────────

class AgentCommandResponse(BaseModel):
    id: int
    action: str
    job_id_windows: int
    correlation_id: Optional[str] = None
    
class AgentCommandStatusUpdate(BaseModel):
    status: str # completed, failed
    result_message: Optional[str] = None
