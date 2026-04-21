from fastapi import APIRouter, Request
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

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
    """Registration page."""
    return templates.TemplateResponse(request, "auth/register.html", {})


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """User profile page."""
    return templates.TemplateResponse(request, "auth/profile.html", {})


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


@router.get("/assets", response_class=HTMLResponse)
async def assets_list(request: Request):
    """Assets list page."""
    return templates.TemplateResponse(request, "assets/list.html", {})


@router.get("/assets/create", response_class=HTMLResponse)
async def assets_create(request: Request):
    """Create asset page."""
    return templates.TemplateResponse(request, "assets/create.html", {})

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
    """Admin users management page."""
    return templates.TemplateResponse(request, "admin/users.html", {})


@router.get("/admin/ad-users", response_class=HTMLResponse)
async def admin_ad_users(request: Request):
    """Real-time Active Directory users page."""
    return templates.TemplateResponse(request, "admin/ad_users.html", {})


@router.get("/admin/entities", response_class=HTMLResponse)
async def admin_entities(request: Request):
    """Admin entities management page."""
    return templates.TemplateResponse(request, "admin/entities.html", {})


@router.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings(request: Request):
    """Admin settings page."""
    return templates.TemplateResponse(request, "admin/settings.html", {})
