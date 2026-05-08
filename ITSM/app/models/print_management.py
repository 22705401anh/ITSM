"""
KOSTAL Print Management Module — Database Models (Phase 1 MVP)

Tables:
  - print_servers: Registered Windows print server machines
  - print_agents: Agent instances running on print servers
  - print_queues: Discovered print queues on servers
  - print_printers: Physical/network printer inventory
  - print_jobs: Every tracked print job
  - print_job_events: Job lifecycle audit trail
  - print_cost_rules: Cost calculation configuration
  - print_audit_logs: System audit trail for print module
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db import Base


# ─────────────────────────────────────────────
# Print Servers
# ─────────────────────────────────────────────
class PrintServer(Base):
    """A Windows print server machine hosting shared print queues."""
    __tablename__ = "print_servers"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String(255), nullable=False, index=True)
    ip_address = Column(String(50), nullable=True)
    fqdn = Column(String(255), nullable=True)
    os_version = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="unknown")  # online, offline, unknown
    last_heartbeat = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    agents = relationship("PrintAgent", back_populates="server", cascade="all, delete-orphan")
    queues = relationship("PrintQueue", back_populates="server", cascade="all, delete-orphan")
    printers = relationship("PrintPrinter", back_populates="server")


# ─────────────────────────────────────────────
# Print Agents
# ─────────────────────────────────────────────
class PrintAgent(Base):
    """An instance of the KOSTAL Print Agent service running on a print server."""
    __tablename__ = "print_agents"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String(64), unique=True, nullable=False, index=True)  # UUID
    server_id = Column(Integer, ForeignKey("print_servers.id"), nullable=True)
    hostname = Column(String(255), nullable=False)
    auth_token_hash = Column(String(128), nullable=False)  # SHA-256 hash of token
    version = Column(String(50), nullable=True)
    status = Column(String(50), default="registered")  # registered, online, offline, error
    last_heartbeat = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    queues_count = Column(Integer, default=0)
    jobs_submitted = Column(Integer, default=0)
    registered_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    server = relationship("PrintServer", back_populates="agents")


# ─────────────────────────────────────────────
# Print Queues
# ─────────────────────────────────────────────
class PrintQueue(Base):
    """A print queue discovered on a Windows print server."""
    __tablename__ = "print_queues"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("print_servers.id"), nullable=False)
    queue_name = Column(String(255), nullable=False, index=True)
    printer_name = Column(String(255), nullable=True)
    share_name = Column(String(255), nullable=True)
    driver_name = Column(String(255), nullable=True)
    port_name = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    comment = Column(Text, nullable=True)
    is_shared = Column(Boolean, default=True)
    is_network = Column(Boolean, default=False)
    is_default = Column(Boolean, default=False)
    status = Column(String(50), default="idle")  # idle, printing, error, offline, paused
    jobs_count = Column(Integer, default=0)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    server = relationship("PrintServer", back_populates="queues")
    printer = relationship("PrintPrinter", back_populates="queue", uselist=False)

    __table_args__ = (
        UniqueConstraint("server_id", "queue_name", name="uq_server_queue"),
    )


# ─────────────────────────────────────────────
# Print Printers (Physical/Network Inventory)
# ─────────────────────────────────────────────
class PrintPrinter(Base):
    """Physical or network printer inventory for print management."""
    __tablename__ = "print_printers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    queue_id = Column(Integer, ForeignKey("print_queues.id"), nullable=True)
    server_id = Column(Integer, ForeignKey("print_servers.id"), nullable=True)
    ip_address = Column(String(50), nullable=True, index=True)
    hostname = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    department = Column(String(100), nullable=True)
    model = Column(String(255), nullable=True)
    manufacturer = Column(String(255), nullable=True)
    serial_number = Column(String(255), nullable=True, index=True)
    driver = Column(String(255), nullable=True)

    # SNMP configuration
    snmp_enabled = Column(Boolean, default=False)
    snmp_community = Column(String(100), nullable=True)
    snmp_version = Column(String(10), default="2c")  # 2c, 3

    # Status and health
    status = Column(String(50), default="unknown")  # online, offline, error, unknown
    error_state = Column(String(255), nullable=True)
    last_seen = Column(DateTime, nullable=True)

    # Page counters (from SNMP or spooler)
    total_page_counter = Column(Integer, nullable=True)
    color_counter = Column(Integer, nullable=True)
    mono_counter = Column(Integer, nullable=True)

    # Toner levels (percentage, 0-100, null if unknown)
    toner_black = Column(Integer, nullable=True)
    toner_cyan = Column(Integer, nullable=True)
    toner_magenta = Column(Integer, nullable=True)
    toner_yellow = Column(Integer, nullable=True)

    # Hardware validation
    hardware_validation_enabled = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    queue = relationship("PrintQueue", back_populates="printer")
    server = relationship("PrintServer", back_populates="printers")


# ─────────────────────────────────────────────
# Print Jobs
# ─────────────────────────────────────────────
class PrintJob(Base):
    """A single tracked print job from a Windows print server."""
    __tablename__ = "print_jobs"

    id = Column(Integer, primary_key=True, index=True)

    # Deduplication key: hash(server + queue + job_id + submitted_at + user)
    correlation_id = Column(String(128), unique=True, nullable=False, index=True)

    # Agent / server identification
    agent_id = Column(String(64), nullable=True, index=True)
    server_name = Column(String(255), nullable=True, index=True)

    # Queue / printer
    queue_name = Column(String(255), nullable=True, index=True)
    printer_name = Column(String(255), nullable=True, index=True)
    printer_location = Column(String(255), nullable=True)

    # Windows job metadata
    job_id_windows = Column(Integer, nullable=True)

    # User identification
    user_login = Column(String(255), nullable=True, index=True)
    user_display_name = Column(String(255), nullable=True)
    user_email = Column(String(255), nullable=True)
    user_department = Column(String(100), nullable=True, index=True)
    user_cost_center = Column(String(50), nullable=True)

    # Client machine
    workstation = Column(String(255), nullable=True)

    # Document
    document_name = Column(String(500), nullable=True)

    # Timestamps
    submitted_at = Column(DateTime, nullable=True, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Status: queued, printing, printed, cancelled, failed, deleted, held, released
    status = Column(String(50), default="queued", index=True)

    # Page metrics
    total_pages = Column(Integer, nullable=True)
    copies = Column(Integer, default=1)
    total_sheets = Column(Integer, nullable=True)

    # Print properties
    is_color = Column(Boolean, nullable=True)  # True=color, False=mono, None=unknown
    is_duplex = Column(Boolean, nullable=True)  # True=duplex, False=simplex, None=unknown
    paper_size = Column(String(50), nullable=True)  # A4, A3, Letter, etc.

    # File info
    file_size_bytes = Column(Integer, nullable=True)
    driver_name = Column(String(255), nullable=True)

    # Cost
    estimated_cost = Column(Float, nullable=True)

    # Hardware validation (Phase 5, but store columns now)
    validated_pages = Column(Integer, nullable=True)
    validated_cost = Column(Float, nullable=True)
    validation_status = Column(String(50), default="not_enabled")
    # not_enabled, pending, validated, mismatch, failed

    # Record metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    events = relationship("PrintJobEvent", back_populates="job", cascade="all, delete-orphan",
                          order_by="PrintJobEvent.timestamp")

    __table_args__ = (
        Index("idx_pj_user_submitted", "user_login", "submitted_at"),
        Index("idx_pj_server_queue", "server_name", "queue_name"),
        Index("idx_pj_status_submitted", "status", "submitted_at"),
    )


# ─────────────────────────────────────────────
# Print Job Events (Lifecycle Audit)
# ─────────────────────────────────────────────
class PrintJobEvent(Base):
    """Lifecycle events for a print job (submitted, printing, printed, failed, etc.)."""
    __tablename__ = "print_job_events"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("print_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    # submitted, spooling, printing, printed, cancelled, failed, deleted, held, released, paused, resumed, error
    event_data = Column(Text, nullable=True)  # JSON for extra details
    source = Column(String(50), nullable=True)  # agent, backend, policy, quota
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    job = relationship("PrintJob", back_populates="events")


# ─────────────────────────────────────────────
# Print Cost Rules
# ─────────────────────────────────────────────
class PrintCostRule(Base):
    """Configurable cost calculation rules for print jobs."""
    __tablename__ = "print_cost_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Rule scope
    rule_type = Column(String(50), default="global")  # global, department, printer
    department = Column(String(100), nullable=True)
    printer_id = Column(Integer, ForeignKey("print_printers.id"), nullable=True)

    # Cost per page
    cost_per_mono_page = Column(Float, default=0.03)
    cost_per_color_page = Column(Float, default=0.10)

    # Duplex discount (percentage, e.g. 0 means sheet-based counting only)
    duplex_discount_pct = Column(Float, default=0.0)

    # Paper size (null = all sizes)
    paper_size = Column(String(50), nullable=True)

    # Priority (higher = evaluated first)
    priority = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─────────────────────────────────────────────
# Print Audit Logs
# ─────────────────────────────────────────────
class PrintAuditLog(Base):
    """Audit trail for all print management module actions."""
    __tablename__ = "print_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    # agent_registered, agent_heartbeat, job_submitted, job_status_changed,
    # printer_discovered, printer_updated, cost_rule_created, cost_rule_updated,
    # config_changed, export_requested, etc.
    module = Column(String(50), default="print_management")
    entity_type = Column(String(50), nullable=True)  # agent, server, printer, job, cost_rule
    entity_id = Column(Integer, nullable=True)
    user_id = Column(Integer, nullable=True)
    user_name = Column(String(255), nullable=True)
    details = Column(Text, nullable=True)  # JSON
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


# ─────────────────────────────────────────────
# Print Alerts (ITSM Integration)
# ─────────────────────────────────────────────
class PrintAlert(Base):
    """Alerts generated for print issues (e.g. offline, low toner) serving as incident workflow."""
    __tablename__ = "print_alerts"

    id = Column(Integer, primary_key=True, index=True)
    printer_id = Column(Integer, ForeignKey("print_printers.id", ondelete="CASCADE"), nullable=True)
    alert_type = Column(String(100), nullable=False, index=True)
    # e.g., offline, low_toner, paper_jam, agent_offline, queue_stuck
    severity = Column(String(50), default="warning")  # info, warning, critical
    message = Column(Text, nullable=False)
    status = Column(String(50), default="open")  # open, acknowledged, resolved, closed
    
    first_detected = Column(DateTime, default=datetime.utcnow)
    last_detected = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    
    # Tracking related ITSM ticket (if integrated)
    itsm_ticket_id = Column(String(100), nullable=True)
    
    # Relationships
    printer = relationship("PrintPrinter")


# ─────────────────────────────────────────────
# Print Policies and Quotas (Phase 4)
# ─────────────────────────────────────────────
class PrintPolicy(Base):
    """Rule engine for enforcing print behaviors (blocking/warning)."""
    __tablename__ = "print_policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=10)
    
    # Target (who does this apply to)
    target_type = Column(String(50), nullable=False)  # global, department, user, printer
    target_value = Column(String(255), nullable=True) # e.g. "HR", "lamou999", "PRN-01"
    
    # Condition (when does this apply)
    condition = Column(String(50), nullable=False)  # max_pages, deny_color, deny_simplex, outside_hours
    condition_value = Column(String(255), nullable=True) # e.g. "100" (pages)
    
    # Action
    action = Column(String(50), nullable=False) # deny, warn
    user_message = Column(Text, nullable=True) # message sent to user
    
    created_at = Column(DateTime, default=datetime.utcnow)


class PrintQuota(Base):
    """Budget limits for users or departments."""
    __tablename__ = "print_quotas"

    id = Column(Integer, primary_key=True, index=True)
    target_type = Column(String(50), nullable=False) # user, department
    target_value = Column(String(255), nullable=False, index=True) # "lamou999" or "HR"
    
    quota_period = Column(String(50), default="monthly") # monthly, yearly, absolute
    budget_limit = Column(Float, nullable=False, default=0.0) # e.g. 50.00
    action_when_exceeded = Column(String(50), default="deny") # deny, warn, ignore
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentCommand(Base):
    """Commands queued for the Windows Print Agent to execute."""
    __tablename__ = "print_agent_commands"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String(64), ForeignKey("print_agents.agent_id"), nullable=False, index=True)
    action = Column(String(50), nullable=False) # resume, cancel
    job_id_windows = Column(Integer, nullable=False) # Spooler job ID
    correlation_id = Column(String(128), nullable=True) # Our backend ID
    status = Column(String(50), default="pending") # pending, sent, completed, failed
    result_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    agent = relationship("PrintAgent")
