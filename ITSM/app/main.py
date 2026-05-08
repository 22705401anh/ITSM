from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
import os
import asyncio

from app.config import settings
from app.db import init_db
from app.api import auth, assets, documentation, licenses, hardware_assets, onboarding
from app.models import onboarding as onboarding_models
from app.models import settings as settings_models
from app.models import network as network_models
from app.models import print_management as print_management_models
from app.web import routes as web_routes

# Configure logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def background_sync_routine():
    """Periodically mirrors Primary DB to the local SQLite Fallback DB."""
    while True:
        # Run sync every 10 minutes (600 seconds)
        await asyncio.sleep(600)
        try:
            from app.db import engine, sqlite_engine, Base, create_engine_for_url
            
            if engine and engine.name != "sqlite":
                logger.info("Executing periodic Background Sync (Primary -> SQLite Mirror)...")
                
                local_sqlite = sqlite_engine
                if not local_sqlite:
                    local_sqlite = create_engine_for_url(settings.DATABASE_URL)
                    
                with local_sqlite.connect() as tgt_conn:
                    with engine.connect() as src_conn:
                        # Iterate through all tables in foreign-key dependency order
                        for table in Base.metadata.sorted_tables:
                            try:
                                # Overwrite Strategy
                                tgt_conn.execute(table.delete())
                                rows = src_conn.execute(table.select()).fetchall()
                                if rows:
                                    dict_rows = [row._mapping for row in rows]
                                    tgt_conn.execute(table.insert(), dict_rows)
                                tgt_conn.commit()
                            except Exception as table_err:
                                tgt_conn.rollback()
                                logger.error(f"Sync failed for table {table.name}: {table_err}")
                logger.info("Background Sync completed successfully.")
        except Exception as e:
            logger.error(f"Background Sync Routine encountered an error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    logger.info("Starting up application...")
    init_db()
    logger.info("Database initialized")
    
    # Start background replication mirror
    sync_task = asyncio.create_task(background_sync_routine())
    

    yield

    # Shutdown
    logger.info("Shutting down application...")
    if sync_task:
        sync_task.cancel()
    

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)


# Exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError exceptions."""
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    # In debug mode return the exception message to help debugging
    if settings.DEBUG:
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc)},
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Mount static files BEFORE including routers (order matters)
static_dir = os.path.join(os.path.dirname(__file__), "web", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Mount uploads directory for serving uploaded images
uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(os.path.join(uploads_dir, "hardware"), exist_ok=True)
if os.path.exists(uploads_dir):
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(assets.router, prefix="/api", tags=["assets"])
app.include_router(licenses.router, prefix="/api", tags=["licenses"])
app.include_router(documentation.router, prefix="/api", tags=["documentation"])
app.include_router(hardware_assets.router, prefix="/api", tags=["hardware"])
from app.api import admin, problems, changes, discovery, print_management
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(problems.router, prefix="/api/problems", tags=["problems"])
app.include_router(changes.router, prefix="/api/changes", tags=["changes"])
app.include_router(discovery.router, prefix="/api", tags=["discovery"])
app.include_router(print_management.router, prefix="/api", tags=["print_management"])
app.include_router(onboarding.router)
app.include_router(web_routes.router, tags=["web"])
