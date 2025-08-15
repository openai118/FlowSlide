"""
Main FastAPI application entry point
"""

import asyncio
import logging

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from .api.config_api import router as config_router
from .api.database_api import router as database_router
from .api.global_master_template_api import router as template_api_router
from .api.image_api import router as image_router
from .api.flowslide_api import router as flowslide_router
from .api.openai_compat import router as openai_router
from .auth import auth_router, create_auth_middleware
from .database.create_default_template import \
    ensure_default_templates_exist_first_time
from .database.database import init_db
from .web import router as web_router
from . import __version__ as FS_VERSION

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Disable SQLAlchemy verbose logging completely
logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)

# Create FastAPI app
app = FastAPI(
    title="FlowSlide API",
    description="AI-powered PPT generation platform with OpenAI-compatible API",
    version=FS_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    try:
        # Get database path from config
        from .core.simple_config import DATABASE_URL
        import urllib.parse
        
        # Extract database file path from URL
        parsed = urllib.parse.urlparse(DATABASE_URL)
        if parsed.scheme == "sqlite":
            # Remove leading /// and get relative path
            db_file_path = parsed.path.lstrip("/")
            # Ensure data directory exists
            os.makedirs(os.path.dirname(db_file_path), exist_ok=True)
        else:
            db_file_path = None
        
        db_exists = db_file_path and os.path.exists(db_file_path)

        logger.info(f"Initializing database... URL: {DATABASE_URL}")
        await init_db()
        logger.info("Database initialized successfully")

        # Only import templates if database file didn't exist before (first time setup)
        if not db_exists:
            logger.info(
                "First time setup detected - importing templates from examples..."
            )
            template_ids = await ensure_default_templates_exist_first_time()
            logger.info(
                f"Template initialization completed. {len(template_ids)} templates available."
            )
        else:
            logger.info("Database already exists - skipping template import")

    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up database connections on shutdown"""
    try:
        logger.info("Shutting down application...")
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add authentication middleware
auth_middleware = create_auth_middleware()
app.middleware("http")(auth_middleware)

# Include routers
app.include_router(auth_router, prefix="", tags=["Authentication"])
app.include_router(config_router, prefix="", tags=["Configuration Management"])
app.include_router(image_router, prefix="", tags=["Image Service"])

app.include_router(openai_router, prefix="/v1", tags=["OpenAI Compatible"])
app.include_router(flowslide_router, prefix="/api", tags=["FlowSlide API"])
app.include_router(template_api_router, tags=["Global Master Templates"])
app.include_router(database_router, tags=["Database Management"])
app.include_router(web_router, prefix="", tags=["Web Interface"])

# Mount static files
import os

static_dir = os.path.join(os.path.dirname(__file__), "web", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Mount temp directory for image cache
temp_dir = os.path.join(os.getcwd(), "temp")
if os.path.exists(temp_dir):
    app.mount("/temp", StaticFiles(directory=temp_dir), name="temp")
    logger.info(f"Mounted temp directory: {temp_dir}")
else:
    logger.warning(f"Temp directory not found: {temp_dir}")


@app.get("/")
async def root_redirect():
    """Root endpoint - redirect to /home to avoid duplicate landing page"""
    return RedirectResponse(url="/home", status_code=302)


@app.get("/api/version")
async def api_version():
    """Return current server version for UI to consume"""
    return {"version": FS_VERSION}


@app.get("/version.txt", response_class=PlainTextResponse)
async def version_txt():
    """Plain text version (useful for CDN/clients)"""
    return FS_VERSION


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "FlowSlide API"}


if __name__ == "__main__":
    uvicorn.run(
    "src.flowslide.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
