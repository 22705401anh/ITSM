"""
KOSTAL Print Management — API Router (Phase 1 MVP)
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case, extract, or_
from datetime import datetime, timedelta
from typing import Optional
import hashlib, uuid, json, logging, io, math

from app.db import get_db
from app.dependencies import get_current_user, check_permission
from app.models.user import User
from app.models.print_management import (
    PrintServer, PrintAgent, PrintQueue, PrintPrinter,
    PrintJob, PrintJobEvent, PrintCostRule, PrintAuditLog, PrintAlert
)
from app.schemas.print_schemas import (
    AgentRegisterRequest, AgentRegisterResponse,
    AgentHeartbeatRequest, AgentHeartbeatResponse,
    PrintJobSubmit, PrintJobSubmitResponse,
    PrintJobBulkRequest, PrintJobBulkResponse,
    PrintJobEventSubmit, PrintJobEventBulkRequest,
    PrinterDiscoveryRequest, DiscoveredQueueItem,
    DashboardResponse, DashboardKPI, TopItem,
    PrintJobResponse, PrintJobDetailResponse, PrintJobListResponse,
    PrintJobEventResponse,
    PrintPrinterResponse, PrintPrinterUpdate,
    PrintServerResponse, PrintAgentResponse,
)

logger = logging.getLogger(__name__)

# ── Two sub-routers: agent (token auth) and admin (JWT auth) ──
router = APIRouter(prefix="/print", tags=["print_management"])


# ═══════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _verify_agent(agent_id: str, auth_token: str, db: Session) -> PrintAgent:
    agent = db.query(PrintAgent).filter(PrintAgent.agent_id == agent_id).first()
    if not agent or agent.auth_token_hash != _hash_token(auth_token):
        raise HTTPException(status_code=401, detail="Invalid agent credentials")
    return agent

def _enrich_job_with_ad(job: PrintJob, db: Session):
    """Enrich job metadata by querying the local synced Users table instead of slow LDAP."""
    if not job.user_login or job.user_department:
        return  # Already has department or no login
        
    try:
        from app.models.user import User
        # Remove domain prefix if present (e.g., 'DOMAIN\username' -> 'username')
        clean_username = job.user_login.split('\\')[-1]
        
        user = db.query(User).filter(User.username == clean_username).first()
        if user:
            if user.department:
                job.user_department = user.department
            if user.full_name and not job.user_display_name:
                job.user_display_name = user.full_name
            if hasattr(user, 'company') and user.company:
                job.user_cost_center = user.company
    except Exception as e:
        logger.warning(f"Local user enrichment failed for {job.user_login}: {e}")


def _calculate_cost(job: PrintJob, db: Session) -> float:
    """Calculate estimated cost for a print job using cost rules."""
    rules = db.query(PrintCostRule).filter(
        PrintCostRule.is_active == True
    ).order_by(desc(PrintCostRule.priority)).all()

    mono_rate = 0.03
    color_rate = 0.10
    duplex_discount_pct = 0.0

    # Attempt to resolve the printer_id if not present but we have a printer_name
    resolved_printer_id = None
    if job.printer_name:
        printer = db.query(PrintPrinter).filter(PrintPrinter.name == job.printer_name).first()
        if printer:
            resolved_printer_id = printer.id

    for rule in rules:
        match = True
        
        # 1. Department Rule
        if rule.rule_type == "department" and rule.department:
            if job.user_department != rule.department:
                match = False
                
        # 2. Printer Rule
        if rule.rule_type == "printer" and rule.printer_id:
            if not resolved_printer_id or resolved_printer_id != rule.printer_id:
                match = False
                
        # 3. Paper Size Rule
        if rule.paper_size and job.paper_size and rule.paper_size.lower() != job.paper_size.lower() and rule.paper_size != "All Sizes":
            match = False
            
        if match:
            mono_rate = rule.cost_per_mono_page
            color_rate = rule.cost_per_color_page
            duplex_discount_pct = rule.duplex_discount_pct or 0.0
            break

    pages = job.total_pages or 0
    copies = job.copies or 1
    total = pages * copies

    # Base cost based on color vs mono
    base_cost = total * color_rate if job.is_color else total * mono_rate

    # Apply Duplex Discount
    # Duplex is typically printed on both sides of a sheet. 
    # If the rule gives a discount for duplexing (e.g. 10% off the total), we apply it here.
    if job.is_duplex and duplex_discount_pct > 0:
        discount_amount = base_cost * (duplex_discount_pct / 100.0)
        base_cost -= discount_amount

    return round(base_cost, 4)


def _evaluate_policies(job: PrintJob, db: Session) -> tuple[str, str]:
    """Evaluate policies and quotas for a given job. Returns (action, message)."""
    from app.models.print_management import PrintPolicy, PrintQuota
    
    # 1. Structural Policies
    policies = db.query(PrintPolicy).filter(PrintPolicy.is_active == True).order_by(desc(PrintPolicy.priority)).all()
    for policy in policies:
        # Match Target
        match = False
        if policy.target_type == "global": match = True
        elif policy.target_type == "department" and job.user_department == policy.target_value: match = True
        elif policy.target_type == "user" and job.user_login == policy.target_value: match = True
        elif policy.target_type == "printer" and job.printer_name == policy.target_value: match = True
        
        if not match: continue
        
        # Evaluate Condition
        condition_met = False
        if policy.condition == "deny_color" and job.is_color: condition_met = True
        elif policy.condition == "deny_simplex" and not job.is_duplex: condition_met = True
        elif policy.condition == "max_pages" and job.total_pages:
            try:
                if job.total_pages > int(policy.condition_value): condition_met = True
            except: pass
            
        if condition_met:
            return policy.action, policy.user_message or f"Job blocked by policy: {policy.name}"

    # 2. Financial Quotas
    # Check if this user or department has a quota and if they've exceeded it.
    quotas = db.query(PrintQuota).filter(
        ((PrintQuota.target_type == "department") & (PrintQuota.target_value == job.user_department)) |
        ((PrintQuota.target_type == "user") & (PrintQuota.target_value == job.user_login))
    ).all()
    
    if not quotas:
        return "allow", "OK"
        
    for quota in quotas:
        # Calculate consumption for the current period (simplified to always check monthly for now)
        from sqlalchemy import func
        from datetime import datetime
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        consumption = 0.0
        if quota.target_type == "user":
            consumption = db.query(func.sum(PrintJob.estimated_cost)).filter(
                PrintJob.user_login == job.user_login,
                PrintJob.status == "printed",
                PrintJob.completed_at >= start_of_month
            ).scalar() or 0.0
        elif quota.target_type == "department":
            consumption = db.query(func.sum(PrintJob.estimated_cost)).filter(
                PrintJob.user_department == job.user_department,
                PrintJob.status == "printed",
                PrintJob.completed_at >= start_of_month
            ).scalar() or 0.0
            
        if consumption + (job.estimated_cost or 0.0) > quota.budget_limit:
            return quota.action_when_exceeded, f"Budget exceeded. Limit: €{quota.budget_limit}, Used: €{consumption:.2f}"
            
    return "allow", "OK"


# ═══════════════════════════════════════════════
# AGENT APIs (token-authenticated)
# ═══════════════════════════════════════════════

@router.post("/agent/register", response_model=AgentRegisterResponse)
async def agent_register(req: AgentRegisterRequest, db: Session = Depends(get_db)):
    """Register a new print agent. Returns agent_id + auth_token."""
    # Find or create server
    server = db.query(PrintServer).filter(
        PrintServer.hostname == req.hostname
    ).first()
    if not server:
        server = PrintServer(
            hostname=req.hostname,
            ip_address=req.ip_address,
            fqdn=req.fqdn,
            os_version=req.os_version,
            location=req.location,
            status="online",
            last_heartbeat=datetime.utcnow(),
        )
        db.add(server)
        db.flush()

    agent_id = str(uuid.uuid4())
    auth_token = str(uuid.uuid4()) + "-" + str(uuid.uuid4())

    agent = PrintAgent(
        agent_id=agent_id,
        server_id=server.id,
        hostname=req.hostname,
        auth_token_hash=_hash_token(auth_token),
        version=req.agent_version,
        status="online",
        last_heartbeat=datetime.utcnow(),
    )
    db.add(agent)
    db.commit()

    logger.info(f"Print agent registered: {agent_id} on {req.hostname}")
    return AgentRegisterResponse(
        agent_id=agent_id, auth_token=auth_token, server_id=server.id
    )


@router.post("/agent/heartbeat", response_model=AgentHeartbeatResponse)
async def agent_heartbeat(req: AgentHeartbeatRequest, request: Request, db: Session = Depends(get_db)):
    """Agent heartbeat — updates status and timestamp."""
    auth = request.headers.get("X-Agent-Token", "")
    agent = _verify_agent(req.agent_id, auth, db)

    agent.status = req.status or "online"
    agent.last_heartbeat = datetime.utcnow()
    if req.queues_count is not None:
        agent.queues_count = req.queues_count
    if req.jobs_submitted is not None:
        agent.jobs_submitted = req.jobs_submitted
    if req.last_error is not None:
        agent.last_error = req.last_error
    if req.version:
        agent.version = req.version

    if agent.server:
        agent.server.status = "online"
        agent.server.last_heartbeat = datetime.utcnow()

    db.commit()
    return AgentHeartbeatResponse(message="OK", server_time=datetime.utcnow())


@router.post("/jobs", response_model=PrintJobSubmitResponse)
async def submit_job(job_data: PrintJobSubmit, request: Request, db: Session = Depends(get_db)):
    """Submit a single print job record."""
    # Deduplication check
    existing = db.query(PrintJob).filter(
        PrintJob.correlation_id == job_data.correlation_id
    ).first()
    if existing:
        return PrintJobSubmitResponse(
            id=existing.id, correlation_id=existing.correlation_id,
            status=existing.status, estimated_cost=existing.estimated_cost,
            is_duplicate=True,
        )

    job = PrintJob(**job_data.model_dump())
    _enrich_job_with_ad(job, db)
    cost = _calculate_cost(job, db)
    job.estimated_cost = cost
    
    # Evaluate Policies
    action, message = _evaluate_policies(job, db)
    if action == "deny":
        job.status = "denied"
    elif action == "hold":
        job.status = "held"
        
    db.add(job)
    db.flush()

    # Create initial event
    db.add(PrintJobEvent(
        job_id=job.id, event_type="submitted",
        event_data=json.dumps({"policy_action": action, "policy_message": message}),
        source="agent", timestamp=job.submitted_at or datetime.utcnow(),
    ))
    db.commit()

    return PrintJobSubmitResponse(
        id=job.id, correlation_id=job.correlation_id,
        status=job.status, estimated_cost=cost,
        policy_action=action, policy_message=message
    )


@router.post("/jobs/bulk", response_model=PrintJobBulkResponse)
async def submit_jobs_bulk(req: PrintJobBulkRequest, request: Request, db: Session = Depends(get_db)):
    """Bulk submit print jobs (offline cache flush)."""
    auth = request.headers.get("X-Agent-Token", "")
    _verify_agent(req.agent_id, auth, db)

    created, duplicates, errors = 0, 0, []
    for jd in req.jobs:
        try:
            existing = db.query(PrintJob).filter(
                PrintJob.correlation_id == jd.correlation_id
            ).first()
            if existing:
                duplicates += 1
                continue

            job = PrintJob(**jd.model_dump())
            job.agent_id = req.agent_id
            _enrich_job_with_ad(job, db)
            job.estimated_cost = _calculate_cost(job, db)
            
            action, message = _evaluate_policies(job, db)
            if action == "deny":
                job.status = "denied"
            elif action == "hold":
                job.status = "held"
                
            db.add(job)
            db.flush()
            db.add(PrintJobEvent(
                job_id=job.id, event_type="submitted",
                event_data=json.dumps({"policy_action": action, "policy_message": message}),
                source="agent", timestamp=job.submitted_at or datetime.utcnow(),
            ))
            created += 1
        except Exception as e:
            errors.append(f"{jd.correlation_id}: {str(e)}")

    db.commit()
    return PrintJobBulkResponse(
        total_received=len(req.jobs), total_created=created,
        total_duplicates=duplicates, errors=errors[:20],
    )


@router.post("/job-events")
async def submit_job_events(req: PrintJobEventBulkRequest, request: Request, db: Session = Depends(get_db)):
    """Submit job lifecycle events."""
    auth = request.headers.get("X-Agent-Token", "")
    _verify_agent(req.agent_id, auth, db)

    processed = 0
    for ev in req.events:
        job = db.query(PrintJob).filter(
            PrintJob.correlation_id == ev.correlation_id
        ).first()
        if not job:
            continue
        db.add(PrintJobEvent(
            job_id=job.id, event_type=ev.event_type,
            event_data=ev.event_data, source=ev.source or "agent",
            timestamp=ev.timestamp or datetime.utcnow(),
        ))
        # Update job status
        if ev.event_type in ("printing", "printed", "cancelled", "failed", "deleted", "held", "released"):
            job.status = ev.event_type
            if ev.event_type == "printed" and not job.completed_at:
                job.completed_at = ev.timestamp or datetime.utcnow()
            if ev.event_type == "printing" and not job.started_at:
                job.started_at = ev.timestamp or datetime.utcnow()
        processed += 1

    db.commit()
    return {"processed": processed}


@router.post("/printers/discovered")
async def report_discovered_printers(req: PrinterDiscoveryRequest, request: Request, db: Session = Depends(get_db)):
    """Agent reports discovered print queues."""
    auth = request.headers.get("X-Agent-Token", "")
    _verify_agent(req.agent_id, auth, db)

    server = db.query(PrintServer).filter(
        PrintServer.hostname == req.server_hostname
    ).first()
    if not server:
        raise HTTPException(status_code=404, detail="Server not registered")

    created, updated = 0, 0
    for q in req.queues:
        existing = db.query(PrintQueue).filter(
            PrintQueue.server_id == server.id,
            PrintQueue.queue_name == q.queue_name,
        ).first()
        if existing:
            for field in ("printer_name", "share_name", "driver_name", "port_name",
                          "location", "comment", "is_shared", "is_network", "status"):
                val = getattr(q, field, None)
                if val is not None:
                    setattr(existing, field, val)
            existing.last_seen = datetime.utcnow()
            updated += 1
        else:
            new_q = PrintQueue(server_id=server.id, **q.model_dump())
            db.add(new_q)
            created += 1

    db.commit()
    return {"created": created, "updated": updated}


from app.schemas.print_schemas import AgentCommandResponse, AgentCommandStatusUpdate
from app.models.print_management import AgentCommand

@router.get("/agent/commands", response_model=list[AgentCommandResponse])
async def get_agent_commands(request: Request, agent_id: str, db: Session = Depends(get_db)):
    """Agent fetches pending commands (e.g., resume held jobs)."""
    auth = request.headers.get("X-Agent-Token", "")
    _verify_agent(agent_id, auth, db)
    
    commands = db.query(AgentCommand).filter(
        AgentCommand.agent_id == agent_id,
        AgentCommand.status == "pending"
    ).all()
    
    for c in commands:
        c.status = "sent"
        c.sent_at = datetime.utcnow()
    db.commit()
    return commands

@router.post("/agent/commands/{command_id}/status")
async def update_agent_command(command_id: int, req: AgentCommandStatusUpdate, request: Request, agent_id: str, db: Session = Depends(get_db)):
    """Agent reports command execution status."""
    auth = request.headers.get("X-Agent-Token", "")
    _verify_agent(agent_id, auth, db)
    
    cmd = db.query(AgentCommand).filter(AgentCommand.id == command_id, AgentCommand.agent_id == agent_id).first()
    if not cmd:
        raise HTTPException(status_code=404, detail="Command not found")
        
    cmd.status = req.status
    cmd.result_message = req.result_message
    cmd.completed_at = datetime.utcnow()
    
    # If the command was to resume/cancel, update the job status
    job = db.query(PrintJob).filter(PrintJob.job_id_windows == cmd.job_id_windows, PrintJob.agent_id == agent_id).first()
    if job:
        if cmd.action == "resume" and req.status == "completed":
            job.status = "printing"
        elif cmd.action == "cancel" and req.status == "completed":
            job.status = "cancelled"
            
    db.commit()
    return {"status": "ok"}


# ═══════════════════════════════════════════════
# USER APIs (JWT user-authenticated)
# ═══════════════════════════════════════════════

@router.post("/user/jobs/{job_id}/release")
async def release_print_job(job_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """User releases their own held print job."""
    job = db.query(PrintJob).filter(PrintJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    # Security: Ensure the user owns the job (match login or display name)
    if job.user_login != current_user.username and job.user_display_name != current_user.full_name:
        if not current_user.has_permission("admin"): # Admin override
            raise HTTPException(status_code=403, detail="You do not own this print job")
            
    if job.status != "held":
        raise HTTPException(status_code=400, detail=f"Job is not held (status: {job.status})")
        
    # Queue the command for the agent
    if not job.agent_id:
        raise HTTPException(status_code=400, detail="Job has no associated agent")
        
    cmd = AgentCommand(
        agent_id=job.agent_id,
        action="resume",
        job_id_windows=job.job_id_windows,
        correlation_id=job.correlation_id,
        status="pending"
    )
    db.add(cmd)
    
    # Update job state optimistically
    job.status = "queued" # Will become printing once agent confirms
    db.commit()
    return {"status": "success", "message": "Release command queued"}


@router.post("/user/jobs/{job_id}/cancel")
async def cancel_held_job(job_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """User cancels their own held print job."""
    job = db.query(PrintJob).filter(PrintJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job.user_login != current_user.username and job.user_display_name != current_user.full_name:
        if not current_user.has_permission("admin"):
            raise HTTPException(status_code=403, detail="You do not own this print job")
            
    if job.status != "held":
        raise HTTPException(status_code=400, detail=f"Job is not held (status: {job.status})")
        
    cmd = AgentCommand(
        agent_id=job.agent_id,
        action="cancel",
        job_id_windows=job.job_id_windows,
        correlation_id=job.correlation_id,
        status="pending"
    )
    db.add(cmd)
    
    job.status = "cancelled"
    db.commit()
    return {"status": "success", "message": "Cancel command queued"}


# ═══════════════════════════════════════════════
# ADMIN APIs (JWT user-authenticated)
# ═══════════════════════════════════════════════

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    days: int = Query(30, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Dashboard KPIs and chart data."""
    since = datetime.utcnow() - timedelta(days=days)

    base = db.query(PrintJob).filter(PrintJob.submitted_at >= since)

    total_jobs = base.count()
    total_pages = db.query(func.coalesce(func.sum(PrintJob.total_pages), 0)).filter(
        PrintJob.submitted_at >= since
    ).scalar()
    total_cost = db.query(func.coalesce(func.sum(PrintJob.estimated_cost), 0)).filter(
        PrintJob.submitted_at >= since
    ).scalar()
    color_jobs = base.filter(PrintJob.is_color == True).count()
    mono_jobs = base.filter(PrintJob.is_color == False).count()
    duplex_jobs = base.filter(PrintJob.is_duplex == True).count()
    simplex_jobs = base.filter(PrintJob.is_duplex == False).count()
    failed_jobs = base.filter(PrintJob.status == "failed").count()
    cancelled_jobs = base.filter(PrintJob.status == "cancelled").count()
    active_printers = db.query(PrintPrinter).filter(PrintPrinter.status == "online").count()
    active_servers = db.query(PrintServer).filter(PrintServer.status == "online").count()
    active_agents = db.query(PrintAgent).filter(PrintAgent.status == "online").count()

    # Top users
    top_users_q = db.query(
        PrintJob.user_display_name, 
        func.sum(PrintJob.total_pages).label("pages"),
        func.max(User.id).label("user_id")
    ).outerjoin(
        User, 
        or_(
            User.username == PrintJob.user_login,
            User.full_name == PrintJob.user_display_name
        )
    ).filter(
        PrintJob.submitted_at >= since,
        PrintJob.user_display_name.isnot(None),
    ).group_by(PrintJob.user_display_name).order_by(desc("pages")).limit(10).all()

    top_users = [TopItem(name=u[0] or "Unknown", value=int(u[1] or 0), item_id=u[2]) for u in top_users_q]

    from app.models.hardware import Printer

    # Top printers
    top_printers_q = db.query(
        PrintJob.printer_name, 
        func.sum(PrintJob.total_pages).label("pages"),
        func.max(Printer.id).label("printer_id")
    ).outerjoin(
        Printer, 
        Printer.name == PrintJob.printer_name
    ).filter(
        PrintJob.submitted_at >= since,
        PrintJob.printer_name.isnot(None),
    ).group_by(PrintJob.printer_name).order_by(desc("pages")).limit(10).all()

    top_printers = [TopItem(name=p[0] or "Unknown", value=int(p[1] or 0), item_id=p[2]) for p in top_printers_q]

    # Daily pages (last N days)
    daily = db.query(
        func.date(PrintJob.submitted_at).label("day"),
        func.coalesce(func.sum(PrintJob.total_pages), 0).label("pages"),
        func.coalesce(func.sum(PrintJob.estimated_cost), 0).label("cost"),
    ).filter(
        PrintJob.submitted_at >= since,
    ).group_by(func.date(PrintJob.submitted_at)).order_by("day").all()

    daily_pages = [{"date": str(d[0]), "pages": int(d[1]), "cost": round(float(d[2]), 2)} for d in daily]

    return DashboardResponse(
        kpi=DashboardKPI(
            total_jobs=total_jobs, total_pages=int(total_pages), total_cost=round(float(total_cost), 2),
            color_jobs=color_jobs, mono_jobs=mono_jobs,
            duplex_jobs=duplex_jobs, simplex_jobs=simplex_jobs,
            failed_jobs=failed_jobs, cancelled_jobs=cancelled_jobs,
            active_printers=active_printers, active_servers=active_servers, active_agents=active_agents,
        ),
        top_users=top_users,
        top_printers=top_printers,
        daily_pages=daily_pages,
        color_ratio={"color": color_jobs, "mono": mono_jobs},
        duplex_ratio={"duplex": duplex_jobs, "simplex": simplex_jobs},
    )


@router.get("/jobs/export")
async def export_jobs(
    status: Optional[str] = None,
    user: Optional[str] = None,
    printer: Optional[str] = None,
    department: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Export filtered jobs as CSV."""
    from fastapi.responses import StreamingResponse

    q = db.query(PrintJob).order_by(desc(PrintJob.submitted_at))
    if status:
        q = q.filter(PrintJob.status == status)
    if user:
        q = q.filter(PrintJob.user_login.ilike(f"%{user}%"))
    if printer:
        q = q.filter(PrintJob.printer_name.ilike(f"%{printer}%"))
    if department:
        q = q.filter(PrintJob.user_department.ilike(f"%{department}%"))
    if date_from:
        q = q.filter(PrintJob.submitted_at >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(PrintJob.submitted_at <= datetime.fromisoformat(date_to))

    jobs = q.limit(50000).all()

    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Status", "User", "Display Name", "Department", "Printer",
        "Queue", "Server", "Document", "Pages", "Copies", "Color",
        "Duplex", "Paper Size", "Cost", "Submitted", "Completed",
    ])
    for j in jobs:
        writer.writerow([
            j.id, j.status, j.user_login, j.user_display_name, j.user_department,
            j.printer_name, j.queue_name, j.server_name, j.document_name,
            j.total_pages, j.copies,
            "Color" if j.is_color else ("Mono" if j.is_color is False else ""),
            "Duplex" if j.is_duplex else ("Simplex" if j.is_duplex is False else ""),
            j.paper_size, j.estimated_cost,
            j.submitted_at.isoformat() if j.submitted_at else "",
            j.completed_at.isoformat() if j.completed_at else "",
        ])

    output.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="print_jobs_{datetime.now().strftime("%Y%m%d_%H%M")}.csv"'}
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv", headers=headers,
    )


@router.get("/jobs/list", response_model=PrintJobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=200),
    status: Optional[str] = None,
    user: Optional[str] = None,
    printer: Optional[str] = None,
    department: Optional[str] = None,
    search: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort_by: str = "submitted_at",
    sort_dir: str = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Paginated, filterable print job list."""
    q = db.query(PrintJob)

    if status:
        q = q.filter(PrintJob.status == status)
    if user:
        q = q.filter(
            (PrintJob.user_login.ilike(f"%{user}%")) |
            (PrintJob.user_display_name.ilike(f"%{user}%"))
        )
    if printer:
        q = q.filter(PrintJob.printer_name.ilike(f"%{printer}%"))
    if department:
        q = q.filter(PrintJob.user_department.ilike(f"%{department}%"))
    if search:
        q = q.filter(
            (PrintJob.document_name.ilike(f"%{search}%")) |
            (PrintJob.user_login.ilike(f"%{search}%")) |
            (PrintJob.printer_name.ilike(f"%{search}%"))
        )
    if date_from:
        q = q.filter(PrintJob.submitted_at >= datetime.fromisoformat(date_from))
    if date_to:
        q = q.filter(PrintJob.submitted_at <= datetime.fromisoformat(date_to))

    total = q.count()

    # Sorting
    sort_col = getattr(PrintJob, sort_by, PrintJob.submitted_at)
    q = q.order_by(desc(sort_col) if sort_dir == "desc" else sort_col)

    # We need to outerjoin User here to get User.id
    from app.models.user import User
    from app.models.hardware import Printer
    from sqlalchemy import or_
    q = q.outerjoin(User, or_(User.username == PrintJob.user_login, User.full_name == PrintJob.user_display_name)).add_columns(User.id.label("user_id"))
    q = q.outerjoin(Printer, Printer.name == PrintJob.printer_name).add_columns(Printer.id.label("printer_id"))

    results = q.offset((page - 1) * per_page).limit(per_page).all()
    
    jobs_response = []
    for row in results:
        j = row[0]
        user_id = row[1]
        printer_id = row[2]
        jobs_response.append(PrintJobResponse(
            id=j.id, correlation_id=j.correlation_id, server_name=j.server_name,
            queue_name=j.queue_name, printer_name=j.printer_name,
            printer_location=j.printer_location, printer_id=printer_id, job_id_windows=j.job_id_windows,
            user_login=j.user_login, user_id=user_id, user_display_name=j.user_display_name,
            user_department=j.user_department, workstation=j.workstation,
            document_name=j.document_name, submitted_at=j.submitted_at,
            started_at=j.started_at, completed_at=j.completed_at,
            status=j.status, total_pages=j.total_pages, copies=j.copies,
            total_sheets=j.total_sheets, is_color=j.is_color, is_duplex=j.is_duplex,
            paper_size=j.paper_size, file_size_bytes=j.file_size_bytes,
            driver_name=j.driver_name, estimated_cost=j.estimated_cost,
            validation_status=j.validation_status, created_at=j.created_at,
        ))

    return PrintJobListResponse(
        jobs=jobs_response,
        total=total, page=page, per_page=per_page,
        total_pages=math.ceil(total / per_page) if total > 0 else 0,
    )


@router.get("/jobs/{job_id}", response_model=PrintJobDetailResponse)
async def get_job_detail(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Get single job detail with events."""
    job = db.query(PrintJob).filter(PrintJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    events = [PrintJobEventResponse(
        id=e.id, event_type=e.event_type, event_data=e.event_data,
        source=e.source, timestamp=e.timestamp,
    ) for e in (job.events or [])]

    return PrintJobDetailResponse(
        id=job.id, correlation_id=job.correlation_id, server_name=job.server_name,
        queue_name=job.queue_name, printer_name=job.printer_name,
        printer_location=job.printer_location, job_id_windows=job.job_id_windows,
        user_login=job.user_login, user_display_name=job.user_display_name,
        user_email=job.user_email, user_department=job.user_department,
        user_cost_center=job.user_cost_center, workstation=job.workstation,
        document_name=job.document_name, submitted_at=job.submitted_at,
        started_at=job.started_at, completed_at=job.completed_at,
        status=job.status, total_pages=job.total_pages, copies=job.copies,
        total_sheets=job.total_sheets, is_color=job.is_color, is_duplex=job.is_duplex,
        paper_size=job.paper_size, file_size_bytes=job.file_size_bytes,
        driver_name=job.driver_name, estimated_cost=job.estimated_cost,
        validated_pages=job.validated_pages, validated_cost=job.validated_cost,
        validation_status=job.validation_status, agent_id=job.agent_id,
        created_at=job.created_at, events=events,
    )


@router.post("/jobs/{job_id}/release")
async def release_held_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Release a held print job."""
    job = db.query(PrintJob).filter(PrintJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job.status != "held":
        raise HTTPException(status_code=400, detail="Job is not in held status")
        
    cmd = AgentCommand(
        agent_id=job.agent_id,
        action="resume",
        job_id_windows=job.job_id_windows,
        correlation_id=job.correlation_id
    )
    db.add(cmd)
    
    # Log event
    db.add(PrintJobEvent(job_id=job.id, event_type="released", source="web", timestamp=datetime.utcnow()))
    
    db.commit()
    return {"status": "command_queued", "command_id": cmd.id}


@router.post("/jobs/{job_id}/cancel")
async def cancel_held_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Cancel a held print job."""
    job = db.query(PrintJob).filter(PrintJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job.status not in ["held", "queued"]:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled")
        
    cmd = AgentCommand(
        agent_id=job.agent_id,
        action="cancel",
        job_id_windows=job.job_id_windows,
        correlation_id=job.correlation_id
    )
    db.add(cmd)
    
    # Log event
    db.add(PrintJobEvent(job_id=job.id, event_type="cancellation_requested", source="web", timestamp=datetime.utcnow()))
    
    db.commit()
    return {"status": "command_queued", "command_id": cmd.id}


@router.get("/printers/list")
async def list_printers(
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """List all print printers in inventory."""
    from app.models.hardware import Printer
    printers = db.query(PrintPrinter, Printer.id.label("hardware_id"))\
                 .outerjoin(Printer, Printer.name == PrintPrinter.name)\
                 .order_by(PrintPrinter.name).all()
                 
    return [PrintPrinterResponse(
        id=p.PrintPrinter.id, name=p.PrintPrinter.name,
        hardware_id=p.hardware_id,
        queue_name=p.PrintPrinter.queue.queue_name if p.PrintPrinter.queue else None,
        server_name=p.PrintPrinter.server.hostname if p.PrintPrinter.server else None,
        ip_address=p.PrintPrinter.ip_address, hostname=p.PrintPrinter.hostname,
        location=p.PrintPrinter.location, department=p.PrintPrinter.department,
        model=p.PrintPrinter.model, manufacturer=p.PrintPrinter.manufacturer,
        serial_number=p.PrintPrinter.serial_number, driver=p.PrintPrinter.driver,
        snmp_enabled=p.PrintPrinter.snmp_enabled, status=p.PrintPrinter.status,
        error_state=p.PrintPrinter.error_state, last_seen=p.PrintPrinter.last_seen,
        total_page_counter=p.PrintPrinter.total_page_counter,
        color_counter=p.PrintPrinter.color_counter, mono_counter=p.PrintPrinter.mono_counter,
        toner_black=p.PrintPrinter.toner_black, toner_cyan=p.PrintPrinter.toner_cyan,
        toner_magenta=p.PrintPrinter.toner_magenta, toner_yellow=p.PrintPrinter.toner_yellow,
    ) for p in printers]


@router.patch("/printers/{printer_id}")
async def update_printer(
    printer_id: int,
    update: PrintPrinterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Update printer metadata."""
    printer = db.query(PrintPrinter).filter(PrintPrinter.id == printer_id).first()
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(printer, field, value)

    db.commit()
    return {"status": "success", "id": printer.id}


@router.get("/servers/list")
async def list_servers(
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """List print servers and their agents."""
    servers = db.query(PrintServer).order_by(PrintServer.hostname).all()
    result = []
    for s in servers:
        agents = [{
            "id": a.id, "agent_id": a.agent_id, "status": a.status,
            "version": a.version, "last_heartbeat": a.last_heartbeat.isoformat() if a.last_heartbeat else None,
            "queues_count": a.queues_count, "jobs_submitted": a.jobs_submitted,
        } for a in s.agents]
        result.append(PrintServerResponse(
            id=s.id, hostname=s.hostname, ip_address=s.ip_address,
            fqdn=s.fqdn, os_version=s.os_version, location=s.location,
            status=s.status,
            last_heartbeat=s.last_heartbeat,
            agents=agents,
            queues_count=len(s.queues),
        ))
    return result


@router.get("/queues/list")
async def list_queues(
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """List all discovered print queues."""
    queues = db.query(PrintQueue).order_by(PrintQueue.queue_name).all()
    return [{
        "id": q.id, "queue_name": q.queue_name, "printer_name": q.printer_name,
        "share_name": q.share_name, "driver_name": q.driver_name,
        "port_name": q.port_name, "location": q.location,
        "is_shared": q.is_shared, "is_network": q.is_network,
        "status": q.status, "server": q.server.hostname if q.server else None,
        "last_seen": q.last_seen.isoformat() if q.last_seen else None,
    } for q in queues]


@router.get("/alerts")
async def list_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """List all open printer alerts."""
    alerts = db.query(PrintAlert).filter(PrintAlert.status == "open").order_by(desc(PrintAlert.last_detected)).all()
    return [{
        "id": a.id,
        "printer_id": a.printer_id,
        "printer_name": a.printer.name if a.printer else "Unknown",
        "printer_ip": a.printer.ip_address if a.printer else "",
        "alert_type": a.alert_type,
        "severity": a.severity,
        "message": a.message,
        "first_detected": a.first_detected.isoformat() if a.first_detected else None,
        "last_detected": a.last_detected.isoformat() if a.last_detected else None,
        "itsm_ticket_id": a.itsm_ticket_id
    } for a in alerts]


# ═══════════════════════════════════════════════
# REPORTING APIs (Phase 3)
# ═══════════════════════════════════════════════
from fastapi.responses import StreamingResponse
import csv
import io

@router.get("/reports/costs")
async def report_costs(
    days: int = Query(30, description="Days to look back"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Cost breakdown by department."""
    since = datetime.utcnow() - timedelta(days=days)
    
    # Group by department
    results = db.query(
        PrintJob.user_department,
        func.sum(PrintJob.total_pages).label("total_pages"),
        func.sum(case((PrintJob.is_color == True, PrintJob.total_pages), else_=0)).label("color_pages"),
        func.sum(PrintJob.estimated_cost).label("total_cost")
    ).filter(
        PrintJob.status == "printed",
        PrintJob.completed_at >= since
    ).group_by(PrintJob.user_department).order_by(desc("total_cost")).all()
    
    return [{
        "department": r.user_department or "Unassigned",
        "total_pages": int(r.total_pages or 0),
        "color_pages": int(r.color_pages or 0),
        "mono_pages": int((r.total_pages or 0) - (r.color_pages or 0)),
        "total_cost": float(r.total_cost or 0.0)
    } for r in results]


@router.get("/reports/users")
async def report_users(
    days: int = Query(30, description="Days to look back"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Top users by cost."""
    since = datetime.utcnow() - timedelta(days=days)
    
    results = db.query(
        PrintJob.user_login,
        PrintJob.user_display_name,
        func.sum(PrintJob.total_pages).label("total_pages"),
        func.sum(PrintJob.estimated_cost).label("total_cost")
    ).filter(
        PrintJob.status == "printed",
        PrintJob.completed_at >= since
    ).group_by(PrintJob.user_login, PrintJob.user_display_name).order_by(desc("total_cost")).limit(20).all()
    
    return [{
        "user_login": r.user_login,
        "display_name": r.user_display_name or r.user_login,
        "total_pages": int(r.total_pages or 0),
        "total_cost": float(r.total_cost or 0.0)
    } for r in results]


@router.get("/reports/export")
async def export_cost_report(
    request: Request,
    days: int = Query(30, description="Days to look back"),
    token: str = Query(None, description="Auth token for direct browser downloads"),
    db: Session = Depends(get_db)
):
    """Export Department Cost Report as CSV."""
    from app.core.security import decode_token
    from app.models.user import User
    
    # Try query param first, then header
    auth_token = token
    if not auth_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            auth_token = auth_header.split(" ")[1]
            
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    payload = decode_token(auth_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    # We could check permissions here, but for now just verify they are a valid user
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    since = datetime.utcnow() - timedelta(days=days)
    
    results = db.query(
        PrintJob.user_department,
        PrintJob.user_cost_center,
        func.sum(PrintJob.total_pages).label("total_pages"),
        func.sum(case((PrintJob.is_color == True, PrintJob.total_pages), else_=0)).label("color_pages"),
        func.sum(PrintJob.estimated_cost).label("total_cost")
    ).filter(
        PrintJob.status == "printed",
        PrintJob.completed_at >= since
    ).group_by(PrintJob.user_department, PrintJob.user_cost_center).order_by(desc("total_cost")).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Department", "Cost Center", "Total Pages", "Color Pages", "Mono Pages", "Total Cost (€)"])
    
    for r in results:
        t_pages = int(r.total_pages or 0)
        c_pages = int(r.color_pages or 0)
        writer.writerow([
            r.user_department or "Unassigned",
            r.user_cost_center or "N/A",
            t_pages,
            c_pages,
            t_pages - c_pages,
            f"{float(r.total_cost or 0.0):.2f}"
        ])
        
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=print_cost_report_last_{days}_days.csv"}
    )


# ═══════════════════════════════════════════════
# SETTINGS APIs (cost rules, audit, config)
# ═══════════════════════════════════════════════

@router.get("/cost-rules/list")
async def list_cost_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """List all cost calculation rules."""
    rules = db.query(PrintCostRule).order_by(desc(PrintCostRule.priority), PrintCostRule.id).all()
    return [{
        "id": r.id, "name": r.name, "description": r.description,
        "rule_type": r.rule_type, "department": r.department,
        "printer_id": r.printer_id,
        "cost_per_mono_page": r.cost_per_mono_page,
        "cost_per_color_page": r.cost_per_color_page,
        "duplex_discount_pct": r.duplex_discount_pct,
        "paper_size": r.paper_size, "priority": r.priority,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    } for r in rules]


@router.post("/cost-rules")
async def create_cost_rule(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Create a new cost rule."""
    data = await request.json()
    rule = PrintCostRule(
        name=data.get("name", "New Rule"),
        description=data.get("description"),
        rule_type=data.get("rule_type", "global"),
        department=data.get("department"),
        printer_id=data.get("printer_id"),
        cost_per_mono_page=float(data.get("cost_per_mono_page", 0.03)),
        cost_per_color_page=float(data.get("cost_per_color_page", 0.10)),
        duplex_discount_pct=float(data.get("duplex_discount_pct", 0)),
        paper_size=data.get("paper_size"),
        priority=int(data.get("priority", 0)),
        is_active=data.get("is_active", True),
    )
    db.add(rule)
    db.flush()

    # Audit
    db.add(PrintAuditLog(
        action="cost_rule_created", entity_type="cost_rule", entity_id=rule.id,
        user_id=current_user.id, user_name=current_user.username,
        details=json.dumps({"name": rule.name, "rule_type": rule.rule_type}),
    ))
    db.commit()
    return {"status": "created", "id": rule.id}


@router.patch("/cost-rules/{rule_id}")
async def update_cost_rule(
    rule_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Update an existing cost rule."""
    rule = db.query(PrintCostRule).filter(PrintCostRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Cost rule not found")

    data = await request.json()
    for field in ("name", "description", "rule_type", "department", "paper_size"):
        if field in data:
            setattr(rule, field, data[field])
    for field in ("cost_per_mono_page", "cost_per_color_page", "duplex_discount_pct"):
        if field in data:
            setattr(rule, field, float(data[field]))
    if "priority" in data:
        rule.priority = int(data["priority"])
    if "is_active" in data:
        rule.is_active = bool(data["is_active"])
    if "printer_id" in data:
        rule.printer_id = data["printer_id"]

    db.add(PrintAuditLog(
        action="cost_rule_updated", entity_type="cost_rule", entity_id=rule.id,
        user_id=current_user.id, user_name=current_user.username,
        details=json.dumps({"name": rule.name, "changes": list(data.keys())}),
    ))
    db.commit()
    return {"status": "updated", "id": rule.id}


@router.delete("/cost-rules/{rule_id}")
async def delete_cost_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Delete a cost rule."""
    rule = db.query(PrintCostRule).filter(PrintCostRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Cost rule not found")

    db.add(PrintAuditLog(
        action="cost_rule_deleted", entity_type="cost_rule", entity_id=rule.id,
        user_id=current_user.id, user_name=current_user.username,
        details=json.dumps({"name": rule.name}),
    ))
    db.delete(rule)
    db.commit()
    return {"status": "deleted"}


@router.get("/audit-logs")
async def list_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Paginated audit log."""
    q = db.query(PrintAuditLog).order_by(desc(PrintAuditLog.timestamp))
    total = q.count()
    logs = q.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "logs": [{
            "id": l.id, "action": l.action, "module": l.module,
            "entity_type": l.entity_type, "entity_id": l.entity_id,
            "user_name": l.user_name, "details": l.details,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
        } for l in logs],
        "total": total, "page": page, "per_page": per_page,
    }


@router.get("/stats/summary")
async def get_stats_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Summary statistics for settings page."""
    total_servers = db.query(PrintServer).count()
    total_agents = db.query(PrintAgent).count()
    online_agents = db.query(PrintAgent).filter(PrintAgent.status == "online").count()
    total_queues = db.query(PrintQueue).count()
    total_printers = db.query(PrintPrinter).count()
    total_jobs = db.query(PrintJob).count()
    total_rules = db.query(PrintCostRule).count()
    active_rules = db.query(PrintCostRule).filter(PrintCostRule.is_active == True).count()

    return {
        "servers": total_servers, "agents": total_agents,
        "online_agents": online_agents, "queues": total_queues,
        "printers": total_printers, "jobs": total_jobs,
        "cost_rules": total_rules, "active_rules": active_rules,
    }


# ═══════════════════════════════════════════════
# POLICIES AND QUOTAS APIs (Phase 4)
# ═══════════════════════════════════════════════
from app.models.print_management import PrintPolicy, PrintQuota
from app.schemas.print_schemas import PrintPolicyCreate, PrintPolicyResponse, PrintQuotaCreate, PrintQuotaResponse

@router.get("/policies", response_model=list[PrintPolicyResponse])
async def list_policies(
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """List all print policies."""
    policies = db.query(PrintPolicy).order_by(desc(PrintPolicy.priority)).all()
    return policies

@router.post("/policies", response_model=PrintPolicyResponse)
async def create_policy(
    policy_in: PrintPolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Create a new print policy."""
    policy = PrintPolicy(**policy_in.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy

@router.delete("/policies/{policy_id}")
async def delete_policy(
    policy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Delete a print policy."""
    policy = db.query(PrintPolicy).filter(PrintPolicy.id == policy_id).first()
    if not policy: raise HTTPException(status_code=404, detail="Policy not found")
    db.delete(policy)
    db.commit()
    return {"status": "deleted"}


@router.get("/quotas", response_model=list[PrintQuotaResponse])
async def list_quotas(
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """List all print quotas."""
    quotas = db.query(PrintQuota).all()
    return quotas

@router.post("/quotas", response_model=PrintQuotaResponse)
async def create_quota(
    quota_in: PrintQuotaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Create a new print quota."""
    quota = PrintQuota(**quota_in.model_dump())
    db.add(quota)
    db.commit()
    db.refresh(quota)
    return quota

@router.delete("/quotas/{quota_id}")
async def delete_quota(
    quota_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_permission("print")),
):
    """Delete a print quota."""
    quota = db.query(PrintQuota).filter(PrintQuota.id == quota_id).first()
    if not quota: raise HTTPException(status_code=404, detail="Quota not found")
    db.delete(quota)
    db.commit()
    return {"status": "deleted"}
