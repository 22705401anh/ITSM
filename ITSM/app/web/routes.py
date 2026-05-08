from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.network import DiscoveredDevice
import os
import json

# Setup templates directory
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Home/Dashboard page."""
    return templates.TemplateResponse(request, "dashboard/index.html", {})


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse(request, "auth/login.html", {})


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration is disabled. Redirect to login."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login")


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """User profile page."""
    return templates.TemplateResponse(request, "auth/profile.html", {})


@router.get("/logout", response_class=HTMLResponse)
async def logout_page(request: Request):
    """Logout: clear client-side tokens and redirect to login."""
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head><title>Logging out...</title></head>
    <body>
        <script>
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            sessionStorage.clear();
            window.location.href = '/login';
        </script>
        <noscript><meta http-equiv="refresh" content="0;url=/login"></noscript>
    </body>
    </html>
    """)


@router.get("/tickets", response_class=HTMLResponse)
async def tickets_list(request: Request):
    """Tickets list page."""
    return templates.TemplateResponse(request, "tickets/list.html", {})


@router.get("/tickets/create", response_class=HTMLResponse)
async def tickets_create(request: Request):
    """Create ticket page."""
    return templates.TemplateResponse(request, "tickets/create.html", {})


@router.get("/tickets/{ticket_id}", response_class=HTMLResponse)
async def tickets_detail(request: Request, ticket_id: int):
    """Ticket detail page."""
    return templates.TemplateResponse(request, "tickets/detail.html", {"ticket_id": ticket_id})


@router.get("/problems", response_class=HTMLResponse)
async def problems_list(request: Request):
    """Problems list page."""
    return templates.TemplateResponse(request, "problems/list.html", {})


@router.get("/problems/create", response_class=HTMLResponse)
async def problems_create(request: Request):
    """Create problem page."""
    return templates.TemplateResponse(request, "problems/create.html", {})


@router.get("/changes", response_class=HTMLResponse)
async def changes_list(request: Request):
    """Changes list page."""
    return templates.TemplateResponse(request, "changes/list.html", {})


@router.get("/changes/create", response_class=HTMLResponse)
async def changes_create(request: Request):
    """Create change page."""
    return templates.TemplateResponse(request, "changes/create.html", {})


@router.get("/users_list", response_class=HTMLResponse)
async def users_list_page(request: Request):
    """Users list page."""
    return templates.TemplateResponse(request, "assets/list.html", {})


@router.get("/assets/create", response_class=HTMLResponse)
async def assets_create(request: Request):
    """Create asset page."""
    return templates.TemplateResponse(request, "assets/create.html", {})


@router.get("/stock", response_class=HTMLResponse)
async def stock_shortcut(request: Request):
    """Stock tracking page shortcut."""
    return templates.TemplateResponse(request, "assets/stock.html", {})


@router.get("/assets/stock", response_class=HTMLResponse)
async def assets_stock(request: Request):
    """Stock tracking page."""
    return templates.TemplateResponse(request, "assets/stock.html", {})


@router.get("/assets/import", response_class=HTMLResponse)
async def assets_import(request: Request):
    """Import excel asset page."""
    return templates.TemplateResponse(request, "assets/import.html", {})


@router.get("/hardware/{asset_type}/{asset_id}", response_class=HTMLResponse)
async def hardware_detail(request: Request, asset_type: str, asset_id: int):
    """Hardware Asset Timeline Detail view."""
    return templates.TemplateResponse(request, "assets/hardware_detail.html", {
        "asset_type": asset_type,
        "asset_id": asset_id
    })


@router.get("/assets/{asset_id}", response_class=HTMLResponse)
async def assets_detail(request: Request, asset_id: int):
    """Asset detail page."""
    return templates.TemplateResponse(request, "assets/detail.html", {"asset_id": asset_id, "request": request})


@router.get("/assets/{asset_id}/edit", response_class=HTMLResponse)
async def assets_edit(request: Request, asset_id: int):
    """Edit asset page."""
    return templates.TemplateResponse(request, "assets/edit.html", {"asset_id": asset_id, "request": request})


@router.get("/licenses", response_class=HTMLResponse)
async def licenses_list(request: Request):
    """Licenses management page."""
    return templates.TemplateResponse(request, "licenses/list.html", {})


@router.get("/documentation/problems", response_class=HTMLResponse)
async def documentation_problems(request: Request):
    """Problem resolution documentation page."""
    return templates.TemplateResponse(request, "documentation/problems.html", {})


@router.get("/documentation/problems/create", response_class=HTMLResponse)
async def documentation_problems_create(request: Request):
    """Create problem resolution documentation page."""
    return templates.TemplateResponse(request, "documentation/problems_create.html", {})


@router.get("/documentation/general", response_class=HTMLResponse)
async def documentation_general(request: Request):
    """General documentation page."""
    return templates.TemplateResponse(request, "documentation/general.html", {})


@router.get("/documentation/general/create", response_class=HTMLResponse)
async def documentation_general_create(request: Request):
    """Create general documentation page."""
    return templates.TemplateResponse(request, "documentation/general_create.html", {})


@router.get("/kb", response_class=HTMLResponse)
async def kb_list(request: Request):
    """Knowledge base list page."""
    return templates.TemplateResponse(request, "kb/list.html", {})


@router.get("/kb/create", response_class=HTMLResponse)
async def kb_create(request: Request):
    """Create KB article page."""
    return templates.TemplateResponse(request, "kb/create.html", {})


@router.get("/reservations", response_class=HTMLResponse)
async def reservations_list(request: Request):
    """Reservations list page."""
    return templates.TemplateResponse(request, "reservations/list.html", {})


@router.get("/reservations/create", response_class=HTMLResponse)
async def reservations_create(request: Request):
    """Create reservation page."""
    return templates.TemplateResponse(request, "reservations/create.html", {})


@router.get("/contracts", response_class=HTMLResponse)
async def contracts_list(request: Request):
    """Contracts list page."""
    return templates.TemplateResponse(request, "contracts/list.html", {})


@router.get("/contracts/create", response_class=HTMLResponse)
async def contracts_create(request: Request):
    """Create contract page."""
    return templates.TemplateResponse(request, "contracts/create.html", {})


@router.get("/projects", response_class=HTMLResponse)
async def projects_list(request: Request):
    """Projects list page."""
    return templates.TemplateResponse(request, "projects/list.html", {})


@router.get("/projects/create", response_class=HTMLResponse)
async def projects_create(request: Request):
    """Create project page."""
    return templates.TemplateResponse(request, "projects/create.html", {})


@router.get("/admin/users", response_class=HTMLResponse)
async def admin_users(request: Request):
    """Admin users database page."""
    return templates.TemplateResponse(request, "admin/users.html", {})

@router.get("/admin/access", response_class=HTMLResponse)
async def admin_access(request: Request):
    """Admin platform access management page."""
    return templates.TemplateResponse(request, "admin/access.html", {})


@router.get("/admin/users/{user_id}", response_class=HTMLResponse)
async def admin_user_profile(request: Request, user_id: int):
    """User Profile and Hardware Dashboard."""
    return templates.TemplateResponse(request, "admin/user_profile.html", {"user_id": user_id, "request": request})


@router.get("/admin/ad-users", response_class=HTMLResponse)
async def admin_ad_users(request: Request):
    """Real-time Active Directory users page."""
    return templates.TemplateResponse(request, "admin/ad_users.html", {})

@router.get("/network/discovery", response_class=HTMLResponse)
async def network_discovery(request: Request):
    """Network Discovery page."""
    return templates.TemplateResponse(request, "network/discovery.html", {})

@router.get("/network/topology", response_class=HTMLResponse)
async def network_topology(request: Request):
    """Network Topology map page."""
    return templates.TemplateResponse(request, "network/topology.html", {})


@router.get("/network/discovery/{device_id}", response_class=HTMLResponse)
async def network_discovery_device_360(request: Request, device_id: int):
    """Network Discovery Device 360 page."""
    return templates.TemplateResponse(request, "network/device_360.html", {"device_id": device_id})

@router.get("/network/discovery/{device_id}/ports/{port_index}/history", response_class=HTMLResponse)
async def network_port_history_view(request: Request, device_id: int, port_index: str, db: Session = Depends(get_db)):
    """Full screen port traffic history."""
    device_name = f"DEVICE_ID: {device_id}"
    port_name = f"PORT_INDEX: {port_index}"
    
    device = db.query(DiscoveredDevice).filter(DiscoveredDevice.id == device_id).first()
    if device:
        device_name = device.hostname or device.ip_address or device_name
        
        if getattr(device, 'telemetry', None) and device.telemetry.ports_data_json:
            try:
                ports_data = json.loads(device.telemetry.ports_data_json)
                for p in ports_data:
                    if str(p.get("index", "")) == str(port_index):
                        port_name = p.get("name") or port_name
                        break
            except Exception:
                pass
                
    return templates.TemplateResponse(request, "network/port_history.html", {
        "device_id": device_id, 
        "port_index": port_index,
        "device_name": device_name,
        "port_name": port_name
    })


@router.get("/admin/entities", response_class=HTMLResponse)
async def admin_entities(request: Request):
    """Admin entities management page."""
    return templates.TemplateResponse(request, "admin/entities.html", {})


@router.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings(request: Request):
    """Admin settings page."""
    return templates.TemplateResponse(request, "admin/settings.html", {})


# --- Onboarding Workflow Routes ---

@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_dashboard(request: Request):
    """Onboarding Dashboard."""
    return templates.TemplateResponse(request, "onboarding/dashboard.html", {})

@router.get("/onboarding/new", response_class=HTMLResponse)
async def onboarding_new(request: Request):
    """HR New Request Form."""
    return templates.TemplateResponse(request, "onboarding/new_request.html", {})

@router.get("/onboarding/{request_id}", response_class=HTMLResponse)
async def onboarding_detail(request: Request, request_id: int):
    """Dynamic Manager Approval / IT Provisioning View."""
    return templates.TemplateResponse(request, "onboarding/detail.html", {"request_id": request_id})


# --- Print Management Routes ---

@router.get("/print", response_class=HTMLResponse)
async def print_dashboard(request: Request):
    """Print Management Dashboard."""
    return templates.TemplateResponse(request, "print/dashboard.html", {})

@router.get("/print/jobs", response_class=HTMLResponse)
async def print_jobs(request: Request):
    """Print Job Logs."""
    return templates.TemplateResponse(request, "print/jobs.html", {})

@router.get("/print/jobs/{job_id}", response_class=HTMLResponse)
async def print_job_detail(request: Request, job_id: int):
    """Print Job Detail."""
    return templates.TemplateResponse(request, "print/job_detail.html", {"job_id": job_id})

@router.get("/print/printers", response_class=HTMLResponse)
async def print_printers(request: Request):
    """Print Printers Inventory."""
    return templates.TemplateResponse(request, "print/printers.html", {})

@router.get("/print/servers", response_class=HTMLResponse)
async def print_servers(request: Request):
    """Print Servers & Agents."""
    return templates.TemplateResponse(request, "print/servers.html", {})

@router.get("/print/alerts", response_class=HTMLResponse)
async def print_alerts(request: Request):
    """Print System Alerts."""
    return templates.TemplateResponse(request, "print/alerts.html", {})

@router.get("/print/reports", response_class=HTMLResponse)
async def print_reports(request: Request):
    """Print Management Reports."""
    return templates.TemplateResponse(request, "print/reports.html", {})

@router.get("/print/policies", response_class=HTMLResponse)
async def print_policies(request: Request):
    """Print Management Policies and Quotas."""
    return templates.TemplateResponse(request, "print/policies.html", {})

@router.get("/print/release", response_class=HTMLResponse)
async def print_release_station(request: Request):
    """Secure Print Release Station."""
    return templates.TemplateResponse(request, "print/release_station.html", {})

@router.get("/print/settings", response_class=HTMLResponse)
async def print_settings(request: Request):
    """Print Management Settings — Cost rules, quotas, and configuration."""
    return templates.TemplateResponse(request, "print/settings.html", {})


